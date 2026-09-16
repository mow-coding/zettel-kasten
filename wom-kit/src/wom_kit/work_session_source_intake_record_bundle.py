"""Retained single-record inputs and context, never approval or ownership.

The original bounded redacted JSON is retained verbatim. All receipt, source
basis and manifest values are reconstructed by the existing pure factory;
loading does not reopen the caller input or any source/target. No batch or
capture-request artifact is manufactured. Held execution remains separate.
"""

from __future__ import annotations

import base64
from contextlib import ExitStack
from dataclasses import dataclass, replace
import os
from pathlib import Path
import stat
import uuid

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import source_intake_record_exact as intake
from . import work_session_bundle as controls
from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
from .work_session_binding import WorkSessionBinding
from .work_session_establishment import EstablishmentSelector


SCOPE_SCHEMA = "wom-kit/source-intake-record-session-scope/v1"
EVIDENCE_SCHEMA = "wom-kit/source-intake-record-session-evidence/v1"
PREPARED_SCHEMA = "wom-kit/source-intake-record-retained-prepared/v1"
CONTEXT_SCHEMA = "wom-kit/source-intake-record-original-context/v1"
PRIVATE_ROOT = ("profiles", "local", "exact-operations", "source-intake-record-contexts")
MAX_BUNDLE_BYTES = controls.MAX_BUNDLE_BYTES
_ERRORS = frozenset({
    "work_session_intake_record_bundle_invalid", "work_session_intake_record_bundle_missing",
    "work_session_intake_record_bundle_changed", "work_session_intake_record_bundle_context_invalid",
    "work_session_intake_record_bundle_lock_required", "work_session_intake_record_bundle_path_unsafe",
    "work_session_intake_record_bundle_durability_unknown",
})
_SCOPE_KEYS = frozenset({
    "schema", "task_route_ref", "actor_sha256", "registry_preimage_sha256", "claim_ref",
    "work_session_binding", "original_establishment", "establishment_execution_sha256",
    "establishment_receipt_sha256", "unbound_manifest_sha256", "retained_input_sha256", "scope_sha256",
})
_INPUT_KEYS = frozenset({"archive_id", "input_plan_path", "input_plan_bytes", "unbound_manifest"})


class WorkSessionIntakeRecordBundleError(RuntimeError):
    def __init__(self, code="work_session_intake_record_bundle_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_record_bundle_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_intake_record_bundle_invalid"
    try:
        return call()
    except WorkSessionIntakeRecordBundleError as error:
        code = error.code
    except Exception:
        pass
    # Raise outside handlers: private paths/parser values must not survive.
    raise WorkSessionIntakeRecordBundleError(code)


def _canonical(value):
    raw = controls._canonical(value)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise WorkSessionIntakeRecordBundleError()
    return raw


def _sha(value):
    return controls._sha(_canonical(value))


def _absolute_path(value):
    if type(value) is not str or not 1 <= len(value) <= 32768 or "\0" in value or not Path(value).is_absolute():
        raise WorkSessionIntakeRecordBundleError()
    return Path(value)


def _encoded(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= intake._MAX_PLAN_BYTES:
        raise WorkSessionIntakeRecordBundleError()
    if 4 * ((len(raw) + 2) // 3) > MAX_BUNDLE_BYTES:
        raise WorkSessionIntakeRecordBundleError()
    return base64.b64encode(raw).decode("ascii")


def _bytes(value):
    if (type(value) is not str or not value
            or len(value) > 4 * ((intake._MAX_PLAN_BYTES + 2) // 3)):
        raise WorkSessionIntakeRecordBundleError()
    raw = base64.b64decode(value, validate=True)
    if not raw or len(raw) > intake._MAX_PLAN_BYTES or _encoded(raw) != value:
        raise WorkSessionIntakeRecordBundleError()
    return raw


def _decode_input(root, document):
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(document) is not dict or set(document) != _INPUT_KEYS
            or type(document["archive_id"]) is not str):
        raise WorkSessionIntakeRecordBundleError()
    raw = _bytes(document["input_plan_bytes"])
    plan = intake._source_intake_record_plan_from_bytes(root, archive_id=document["archive_id"],
        input_plan_path=_absolute_path(document["input_plan_path"]), input_plan_bytes=raw)
    # Reconstruct all original fields/evidence; rehashed supplied manifests
    # cannot hide altered counts, source bindings or receipt bytes.
    if _canonical(plan.manifest.document()) != _canonical(document["unbound_manifest"]):
        raise WorkSessionIntakeRecordBundleError()
    return plan, raw


def _input_document(plan, input_plan_bytes):
    if (type(plan) is not intake.SourceIntakeRecordExactPlan or not plan.approveable
            or plan.state != "ready" or plan.blockers != ()
            or type(plan.manifest) is not exact.ExactOperationManifest
            or plan.manifest.work_session_binding is not None):
        raise WorkSessionIntakeRecordBundleError()
    document = {"archive_id": plan.archive_id, "input_plan_path": str(plan.input_plan_path),
        "input_plan_bytes": _encoded(input_plan_bytes), "unbound_manifest": plan.manifest.document()}
    reconstructed, _raw = _decode_input(plan.archive_root, document)
    if reconstructed != plan:
        raise WorkSessionIntakeRecordBundleError()
    return document


def _scope_document(raw):
    value = controls._strict_document(raw)
    if set(value) != _SCOPE_KEYS or value["schema"] != SCOPE_SCHEMA:
        raise WorkSessionIntakeRecordBundleError()
    for name in _SCOPE_KEYS:
        if name.endswith("_sha256") and not registry._is_digest(value[name]):
            raise WorkSessionIntakeRecordBundleError()
    if not registry._ref(value["task_route_ref"], "task_route") or not registry._ref(value["claim_ref"], "claim"):
        raise WorkSessionIntakeRecordBundleError()
    WorkSessionBinding.from_document(value["work_session_binding"])
    EstablishmentSelector.from_document(value["original_establishment"])
    if value["scope_sha256"] != _sha({key: field for key, field in value.items() if key != "scope_sha256"}):
        raise WorkSessionIntakeRecordBundleError()
    return value


@dataclass(frozen=True, slots=True, repr=False)
class _SourceIntakeRecordSessionScope:
    _raw: bytes

    def __post_init__(self):
        _safe_call(lambda: _scope_document(self._raw))

    def __repr__(self):
        return "<private single-intake scope; no approval or ownership authority>"

    def document(self):
        return _safe_call(lambda: _scope_document(self._raw))

    @classmethod
    def build(cls, *, plan, input_plan_bytes, work_session_binding, task_route_ref, actor_sha256,
              registry_preimage_sha256, claim_ref, original_establishment,
              establishment_execution_sha256, establishment_receipt_sha256):
        def build():
            if type(work_session_binding) is not WorkSessionBinding or type(original_establishment) is not EstablishmentSelector:
                raise WorkSessionIntakeRecordBundleError()
            data = _input_document(plan, input_plan_bytes)
            if work_session_binding.archive_identity_sha256 != plan.manifest.archive_identity_sha256:
                raise WorkSessionIntakeRecordBundleError()
            basis = {"schema": SCOPE_SCHEMA, "work_session_binding": work_session_binding.document(),
                "task_route_ref": task_route_ref, "actor_sha256": actor_sha256,
                "registry_preimage_sha256": registry_preimage_sha256, "claim_ref": claim_ref,
                "original_establishment": original_establishment.document(),
                "establishment_execution_sha256": establishment_execution_sha256,
                "establishment_receipt_sha256": establishment_receipt_sha256,
                "unbound_manifest_sha256": plan.manifest.manifest_sha256, "retained_input_sha256": _sha(data)}
            return cls(_canonical({**basis, "scope_sha256": _sha(basis)}))
        return _safe_call(build)


def _scoped_manifest(plan, scope):
    value = scope.document()
    binding = WorkSessionBinding.from_document(value["work_session_binding"])
    if (value["unbound_manifest_sha256"] != plan.manifest.manifest_sha256
            or binding.archive_identity_sha256 != plan.manifest.archive_identity_sha256):
        raise WorkSessionIntakeRecordBundleError()
    evidence = plan.manifest.operation_evidence.document()
    evidence["schema"] = EVIDENCE_SCHEMA
    evidence["digests"]["session_scope_sha256"] = value["scope_sha256"]
    return exact.ExactOperationManifest.build(operation=plan.manifest.operation,
        archive_identity_sha256=plan.manifest.archive_identity_sha256, items=plan.manifest.items,
        operation_evidence=evidence, work_session_binding=binding)


def _decode_prepared(root, raw):
    def decode():
        document = controls._strict_document(raw)
        if set(document) != {"schema", "input", "scope", "manifest"} or document["schema"] != PREPARED_SCHEMA:
            raise WorkSessionIntakeRecordBundleError()
        plan, original = _decode_input(root, document["input"])
        scope = _SourceIntakeRecordSessionScope(_canonical(document["scope"]))
        if scope.document()["retained_input_sha256"] != _sha(document["input"]):
            raise WorkSessionIntakeRecordBundleError()
        manifest = _scoped_manifest(plan, scope)
        if _canonical(manifest.document()) != _canonical(document["manifest"]):
            raise WorkSessionIntakeRecordBundleError()
        return replace(plan, manifest=manifest), scope, original
    return _safe_call(decode)


@dataclass(frozen=True, slots=True, repr=False)
class PreparedSessionSourceIntakeRecord:
    _root: Path
    _raw: bytes

    def __post_init__(self):
        _decode_prepared(self._root, self._raw)

    def __repr__(self):
        return "<private retained single-intake preparation; not approval or current source verification>"

    @property
    def plan(self):
        return _decode_prepared(self._root, self._raw)[0]

    @property
    def scope(self):
        return _decode_prepared(self._root, self._raw)[1]


def _prepare_session_source_intake_record(plan, *, input_plan_bytes, scope):
    def prepare():
        if type(scope) is not _SourceIntakeRecordSessionScope:
            raise WorkSessionIntakeRecordBundleError()
        data = _input_document(plan, input_plan_bytes)
        return PreparedSessionSourceIntakeRecord(plan.archive_root, _canonical({"schema": PREPARED_SCHEMA,
            "input": data, "scope": scope.document(), "manifest": _scoped_manifest(plan, scope).document()}))
    return _safe_call(prepare)


def _factory_context(prepared, context):
    if type(context) is not ExactHumanApprovalContext:
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_context_invalid")
    expected = intake.approval_context(prepared.plan, reviewer_claim=context.reviewer_claim)
    if approval.exact_human_approval_context_sha256(expected) != approval.exact_human_approval_context_sha256(context):
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_context_invalid")
    return expected


def _decode_context(root, raw, manifest_sha256):
    document = controls._strict_document(raw)
    if (set(document) != {"schema", "prepared", "context", "context_sha256", "bundle_sha256"}
            or document["schema"] != CONTEXT_SCHEMA or not registry._is_digest(manifest_sha256)
            or document["bundle_sha256"] != _sha({key: value for key, value in document.items() if key != "bundle_sha256"})):
        raise WorkSessionIntakeRecordBundleError()
    prepared = PreparedSessionSourceIntakeRecord(root, _canonical(document["prepared"]))
    value = document["context"]
    if (type(value) is not dict or set(value) != controls._CONTEXT_KEYS
            or type(value["review_binding_codes"]) is not list or type(value["warning_codes"]) is not list):
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_context_invalid")
    context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation(value["operation"]),
        archive_identity_sha256=value["archive_identity_sha256"], plan_sha256=value["plan_sha256"],
        target_binding_sha256=value["target_binding_sha256"], reviewer_claim=value["reviewer_claim"],
        review_binding_codes=tuple(value["review_binding_codes"]), warning_codes=tuple(value["warning_codes"]))
    context = _factory_context(prepared, context)
    if (prepared.plan.manifest.manifest_sha256 != manifest_sha256
            or approval.exact_human_approval_context_sha256(context) != document["context_sha256"]):
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_context_invalid")
    return prepared, context


@dataclass(frozen=True, slots=True, repr=False)
class ContextBoundSourceIntakeRecord:
    _root: Path
    _raw: bytes
    _manifest_sha256: str

    def __post_init__(self):
        _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256))

    def __repr__(self):
        return "<private original single-intake context; no approval, ownership or completion authority>"

    @property
    def prepared(self):
        return _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256)[0])

    @property
    def context(self):
        return _safe_call(lambda: _decode_context(self._root, self._raw, self._manifest_sha256)[1])


def _held_root(root, held):
    if type(held) is not exact.ExactOperationWriterLock:
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_lock_required")
    try:
        actual, archive_id = approval._archive_identity(root)
        held.verify_held()
        if os.path.samefile(actual, held.archive_root):
            return actual, archive_id
    except Exception:
        pass
    raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_lock_required")


def _directory(root):
    current = root
    for part in PRIVATE_ROOT:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_path_unsafe")
    return current


def _read_raw(root, manifest_sha256):
    def read():
        if not registry._is_digest(manifest_sha256):
            raise WorkSessionIntakeRecordBundleError()
        directory = _directory(root)
        if directory is None:
            raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_missing")
        try:
            return controls._read_control(directory / (manifest_sha256[7:] + ".json"), maximum=MAX_BUNDLE_BYTES)
        except FileNotFoundError:
            pass
        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_missing")
    return _safe_call(read)


def _flush_chain(root):
    paths = [root]
    for part in PRIVATE_ROOT:
        paths.append(paths[-1] / part)
    with ExitStack() as stack:
        bindings = [stack.enter_context(durable._bound_directory_for_move(path)) for path in paths]
        for path, binding in reversed(list(zip(paths, bindings))):
            durable._assert_named_reservation_directory_identity(path, binding.identity)
            durable._require_directory_durable(path)
            durable._assert_named_reservation_directory_identity(path, binding.identity)
        for path, binding in zip(paths, bindings):
            durable._assert_named_reservation_directory_identity(path, binding.identity)


def _load_original_source_intake_record_context_held(root, *, manifest_sha256, held):
    def load():
        actual, archive_id = _held_root(root, held)
        raw = _read_raw(actual, manifest_sha256)
        bound = ContextBoundSourceIntakeRecord(actual, raw, manifest_sha256)
        if bound.prepared.plan.archive_id != archive_id:
            raise WorkSessionIntakeRecordBundleError()
        if _read_raw(actual, manifest_sha256) != raw:
            raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_changed")
        _held_root(actual, held)
        return bound
    return _safe_call(load)


def _save_original_source_intake_record_context_held(prepared, *, context, held):
    def save():
        if type(prepared) is not PreparedSessionSourceIntakeRecord:
            raise WorkSessionIntakeRecordBundleError()
        # Detach caller-owned objects before filesystem callbacks.
        frozen = PreparedSessionSourceIntakeRecord(prepared._root, prepared._raw)
        original_context = _factory_context(frozen, context)
        actual, archive_id = _held_root(frozen._root, held)
        if frozen.plan.archive_id != archive_id:
            raise WorkSessionIntakeRecordBundleError()
        manifest_sha = frozen.plan.manifest.manifest_sha256
        basis = {"schema": CONTEXT_SCHEMA, "prepared": controls._strict_document(frozen._raw),
            "context": controls._context_document(original_context),
            "context_sha256": approval.exact_human_approval_context_sha256(original_context)}
        raw = _canonical({**basis, "bundle_sha256": _sha(basis)})
        ContextBoundSourceIntakeRecord(actual, raw, manifest_sha)
        directory = _directory(actual)
        if directory is not None and os.path.lexists(directory / (manifest_sha[7:] + ".json")):
            if _read_raw(actual, manifest_sha) != raw:
                raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_changed")
            _decode_context(actual, raw, manifest_sha)
            try:
                _flush_chain(actual)
            except Exception:
                raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_durability_unknown")
        else:
            try:
                directory = exact._ensure_private_directory(actual, PRIVATE_ROOT)
                with durable._bound_directory_for_move(directory) as parent:
                    _flush_chain(actual)
                    pending = directory / (".pending_" + uuid.uuid4().hex)
                    destination = directory / (manifest_sha[7:] + ".json")
                    registry._write_private_pending(pending, raw, root=actual)
                    durable._require_directory_durable(directory)
                    if controls._read_control(pending, maximum=MAX_BUNDLE_BYTES) != raw:
                        raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_changed")
                    _held_root(actual, held)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
                    durable._atomic_move_file_no_replace(pending, destination, expected_parent_identity=parent.identity)
                    durable._require_directory_durable(directory)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
            except WorkSessionIntakeRecordBundleError:
                raise
            except Exception:
                raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_durability_unknown")
        confirmed = _load_original_source_intake_record_context_held(actual, manifest_sha256=manifest_sha, held=held)
        if confirmed._raw != raw:
            raise WorkSessionIntakeRecordBundleError("work_session_intake_record_bundle_changed")
        return confirmed
    return _safe_call(save)
