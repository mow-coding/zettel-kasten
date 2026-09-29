"""Cooperative cancellation bound to the existing execution journal.

Cancellation never kills a process or removes a lock. The owning operation
checks a signed request only between effects, then records acknowledgement.
"""
from contextvars import ContextVar
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import stat
import signal
import threading

ACTIVE = ContextVar("wom_active_operation", default=None)
ACTIVE_CLAIM = ContextVar("wom_cancellation_claim", default=None)
SUPPORTED = frozenset({"objet_capture_batch", "object_storage_cleanup", "object_storage_restore", "object_storage_upload", "object_storage_bytes_preservation", "object_storage_offload", "activity_cleanup"})
_DOMAIN = b"wom-kit/operation-cancellation/v1\0"


class OperationCancelled(RuntimeError):
    code = "operation_cancelled_at_checkpoint"
    def __init__(self):
        super().__init__(self.code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _mac(root, value, provider=None):
    from .exact_human_approval_workflow import _production_key_provider
    active = ACTIVE_CLAIM.get()
    if active is not None:
        return active.operation_cancel_mac(root, _canonical(value))
    return (provider or _production_key_provider()).use_key(root,
        lambda key: hmac.new(bytes(key), _DOMAIN + _canonical(value), hashlib.sha256).hexdigest(),
        create_if_missing=False)


@contextmanager
def claim_scope(claim):
    from .exact_human_approval import _ClaimedExactHumanApproval
    if type(claim) is not _ClaimedExactHumanApproval:
        raise ValueError("operation_cancel_claim_invalid")
    token = ACTIVE_CLAIM.set(claim)
    try:
        yield
    finally:
        ACTIVE_CLAIM.reset(token)


def _load(root, path, provider=None):
    from .operation_control import _validate_existing_chain
    _validate_existing_chain(root, path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536 or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("operation_cancel_request_invalid")
    value = json.loads(path.read_bytes())
    if not hmac.compare_digest(value["mac"], _mac(root, value["document"], provider)):
        raise ValueError("operation_cancel_request_invalid")
    return value["document"]


def _save(root, path, value, provider=None):
    from .operation_control import _validate_existing_chain
    from .project_update_transaction import _require_directory_durable
    _validate_existing_chain(root, path.parent)
    payload = _canonical({"document": value, "mac": _mac(root, value, provider)})
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:
        if _load(root, path, provider) != value:
            raise ValueError("operation_cancel_request_changed") from None
        return
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    _require_directory_durable(path.parent)


def _binding(first):
    return {"schema": "wom-kit/operation-cancel-request/v1", "operation_ref": first["operation_ref"],
            "control_digest": first["control_digest"], "run_id": first["run_id"], "root_ref": first["root_ref"]}


def state(root, journal_path, first, provider=None):
    request_path = journal_path.with_suffix(".cancel.json")
    ack_path = journal_path.with_suffix(".cancel-ack.json")
    value = _binding(first)
    requested = request_path.exists()
    if requested and _load(root, request_path, provider) != value:
        raise ValueError("operation_cancel_request_changed")
    acknowledged = ack_path.exists()
    if acknowledged and (not requested or _load(root, ack_path, provider) != value):
        raise ValueError("operation_cancel_ack_invalid")
    return {"cancel_supported": first["operation_kind"] in SUPPORTED,
            "cancel_requested": requested, "cancel_acknowledged": acknowledged,
            "cancellation_state": "acknowledged_at_checkpoint" if acknowledged else "requested" if requested else "not_requested"}


@contextmanager
def observing(journal, *, provider=None):
    interrupted = threading.Event()
    token = ACTIVE.set((journal, provider, interrupted)) if journal is not None else None
    previous_handler = None
    if journal is not None and threading.current_thread() is threading.main_thread():
        previous_handler = signal.getsignal(signal.SIGINT)
        # The current effect must return and record its outcome before stopping.
        # A signal handler never writes a journal or performs remote I/O itself.
        signal.signal(signal.SIGINT, lambda _signum, _frame: interrupted.set())
    try:
        yield
    finally:
        if token is not None:
            ACTIVE.reset(token)
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)


def checkpoint():
    selected = ACTIVE.get()
    if selected is None:
        return
    journal, provider, interrupted = selected
    if journal.operation_kind not in SUPPORTED:
        return
    first = vars(journal)
    request = journal.journal_path.with_suffix(".cancel.json")
    if interrupted.is_set():
        _save(journal.control_root, request, _binding(first), provider)
    if not request.exists():
        return
    value = _binding(first)
    if _load(journal.control_root, request, provider) != value:
        raise ValueError("operation_cancel_request_changed")
    _save(journal.control_root, journal.journal_path.with_suffix(".cancel-ack.json"), value, provider)
    raise OperationCancelled()


def request_cancel(root, operation_ref, *, expected_control_digest, reviewed_by, provider=None):
    from . import operation_control as control, archive_services as services
    from .exact_human_approval import exact_human_approval_archive_identity_sha256
    from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
    from .exact_human_approval_workflow import _execute_exact_human_approved_write
    root = control.require_control_root(root)
    candidates = control._journal_candidates(root, control._operation_hex(operation_ref))
    if len(candidates) != 1:
        raise ValueError("operation_cancel_journal_unavailable")
    path = candidates[0]
    records = control._read_journal(path, root)
    first = records[0]
    if first["operation_kind"] not in SUPPORTED or expected_control_digest != first["control_digest"]:
        raise ValueError("operation_cancel_target_invalid")
    if records[-1]["terminal"]:
        return {"ok": True, "operation_ref": operation_ref, "cancel_requested": False, "state": "already_terminal"}
    value = _binding(first)
    digest = "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()
    context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.operation_control_cancel,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(services.read_archive_id(root)),
        plan_sha256=digest, target_binding_sha256=digest, reviewer_claim=reviewed_by,
        review_binding_codes=("operation_identity", "cooperative_stop_only"))
    def write(claim):
        claim.assert_ready_for_context(context)
        current = control._read_journal(path, root)
        if current[0] != first:
            raise ValueError("operation_cancel_target_changed")
        if current[-1]["terminal"]:
            return {"ok": True, "operation_ref": operation_ref, "cancel_requested": False, "state": "already_terminal"}
        _save(root, path.with_suffix(".cancel.json"), value, provider)
        return {"ok": True, "operation_ref": operation_ref, "cancel_requested": True,
                "control": {"cancel_supported": True, "cancel_requested": True, "cancel_acknowledged": False},
                "cancel_acknowledged": False, "state": "cancel_requested", "process_killed": False,
                "next_safe_actions": ["Use operation-control status or wait with this operation_ref; a request is not a completed stop."]}
    return _execute_exact_human_approved_write(root, context, write)
