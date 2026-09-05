"""Internal authentication foundation, not Git completion or remote proof.

Ordered OIDs are signed assertions supplied by the future writer observer. This
module never observes Git objects, queries a remote, publishes a record, or
infers session ownership. Its authenticated result must not authorize actor
completion until independent Git anchors have also been verified.

Only a still-started original claim can sign, and only after an authenticated
common final receipt plus its exact checkpoints exist. Historical verification
uses the existing terminal-MAC audit inside the caller's key consumer. It never
signs replacement evidence or upgrades unsigned legacy Git receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import re

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import git_backup_writer as writer
from .exact_human_approval_windows import ExactHumanApprovalContext


RECORD_SCHEMA = "wom-kit/work-session-git-terminal-record/v1"
PAYLOAD_SCHEMA = "wom-kit/work-session-git-terminal-assertions/v1"
MAX_RECORD_BYTES = min(1024 * 1024, approval.TERMINAL_RECORD_MAC_MAX_PAYLOAD_BYTES)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAC = re.compile(r"hmac-sha256:[0-9a-f]{64}\Z")
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_ERRORS = frozenset({
    "work_session_git_terminal_invalid", "work_session_git_terminal_context_invalid",
    "work_session_git_terminal_common_evidence_invalid",
    "work_session_git_terminal_authentication_invalid",
})
_PAYLOAD_KEYS = frozenset({
    "schema", "manifest_sha256", "context_sha256", "approval_reference",
    "approval_binding_sha256", "execution_sha256", "common_final_receipt_sha256",
    "common_result_sha256", "selection_sha256", "operation_evidence_sha256",
    "work_session_binding_sha256", "initial_head_oid", "commit_oids",
    "terminal_commit_oid", "exact_remote_ref_binding_sha256",
})


class WorkSessionGitTerminalError(RuntimeError):
    def __init__(self, code="work_session_git_terminal_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_git_terminal_invalid"
        super().__init__(self.code)


def _safe_call(call):
    # Suppressing a cause alone leaves __context__ retaining private values.
    code = "work_session_git_terminal_invalid"
    try:
        return call()
    except WorkSessionGitTerminalError as error:
        code = error.code
    except Exception:
        pass
    raise WorkSessionGitTerminalError(code)


def _is_digest(value):
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _canonical(document):
    return approval._canonical_bytes(document)


def _oids(value):
    if (type(value) is not tuple or not value or len(value) > writer.GIT_BACKUP_MAX_GROUPS
            or any(type(oid) is not str or _OID.fullmatch(oid) is None
                   or oid == "0" * len(oid) for oid in value)
            or len({len(oid) for oid in value}) != 1 or len(set(value)) != len(value)):
        raise WorkSessionGitTerminalError()
    return value


def _decode(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_RECORD_BYTES:
        raise WorkSessionGitTerminalError()
    document = writer._strict_json(raw)
    if (set(document) != {"schema", "payload", "terminal_mac"}
            or document["schema"] != RECORD_SCHEMA or _canonical(document) != raw
            or type(document["terminal_mac"]) is not str
            or _MAC.fullmatch(document["terminal_mac"]) is None):
        raise WorkSessionGitTerminalError()
    payload = document["payload"]
    if type(payload) is not dict or set(payload) != _PAYLOAD_KEYS or payload["schema"] != PAYLOAD_SCHEMA:
        raise WorkSessionGitTerminalError()
    for name in _PAYLOAD_KEYS - {
        "schema", "approval_reference", "initial_head_oid", "commit_oids", "terminal_commit_oid",
    }:
        if name in {"operation_evidence_sha256", "work_session_binding_sha256"} and payload[name] is None:
            continue
        if not _is_digest(payload[name]):
            raise WorkSessionGitTerminalError()
    if type(payload["commit_oids"]) is not list:
        raise WorkSessionGitTerminalError()
    commits = _oids(tuple(payload["commit_oids"]))
    initial = _oids((payload["initial_head_oid"],))[0]
    if (initial in commits or len(initial) != len(commits[0])
            or payload["terminal_commit_oid"] != commits[-1]):
        raise WorkSessionGitTerminalError()
    authority = exact.ExactOperationApprovalAuthority.from_reference(payload["approval_reference"])
    if (authority.binding_sha256 != payload["approval_binding_sha256"]
            or authority.context_sha256 != payload["context_sha256"]):
        raise WorkSessionGitTerminalError()
    return document


@dataclass(frozen=True, slots=True, repr=False)
class _GitTerminalRecord:
    """Detached canonical data only; constructing this type grants no trust."""

    _raw: bytes

    def __post_init__(self):
        _safe_call(lambda: _decode(self._raw))

    def _document(self):
        return _safe_call(lambda: _decode(self._raw))

    def __repr__(self):
        return "<_GitTerminalRecord private assertions; authentication and Git state unchecked>"


@dataclass(frozen=True, slots=True, repr=False)
class _AuthenticatedGitTerminalRecord:
    """Historical MAC result, deliberately insufficient for actor completion."""

    _record: _GitTerminalRecord

    def authentication_summary(self):
        return {
            "authentication_verified": True,
            "common_completion_authentication_verified": True,
            "commit_anchors_verified": False,
            "remote_ref_independently_verified": False,
            "backup_completion_verified": False,
            "private_values_echoed": False,
        }

    def __repr__(self):
        return "<_AuthenticatedGitTerminalRecord historical authentication only; Git state unverified>"


def _original(prepared, context):
    frozen = writer._freeze_validated_prepared(prepared)
    if type(context) is not ExactHumanApprovalContext:
        raise WorkSessionGitTerminalError("work_session_git_terminal_context_invalid")
    expected = writer._git_backup_approval_context(frozen, reviewer_claim=context.reviewer_claim)
    if not hmac.compare_digest(approval.exact_human_approval_context_sha256(expected),
                               approval.exact_human_approval_context_sha256(context)):
        raise WorkSessionGitTerminalError("work_session_git_terminal_context_invalid")
    return frozen


def _common(prepared, context, reference):
    authority = exact.ExactOperationApprovalAuthority.from_reference(reference)
    if authority.context_sha256 != approval.exact_human_approval_context_sha256(context):
        raise WorkSessionGitTerminalError("work_session_git_terminal_context_invalid")
    execution = exact.exact_operation_execution_sha256(prepared.manifest, approval_authority=authority)
    receipt = exact.load_exact_operation_final_receipt_read_only(prepared.root, execution)
    if receipt is None:
        raise WorkSessionGitTerminalError("work_session_git_terminal_common_evidence_invalid")
    result = receipt["result"]
    authentication = result.get("completion_authentication")
    evidence = prepared.manifest.operation_evidence
    expected_evidence = None if evidence is None else evidence.document()
    if (result["mode"] != "apply" or result["manifest_sha256"] != prepared.manifest.manifest_sha256
            or result["execution_sha256"] != execution
            or result["approval_binding_sha256"] != authority.binding_sha256
            or result.get("operation_evidence") != expected_evidence
            or result["item_count"] != len(prepared.manifest.items)
            or result["field_count"] != sum(len(item.fields) for item in prepared.manifest.items)
            or type(authentication) is not dict
            or authentication["approval_reference"] != reference
            or authentication["operation"] != context.operation.value
            or authentication["target_binding_sha256"] != context.target_binding_sha256):
        raise WorkSessionGitTerminalError("work_session_git_terminal_common_evidence_invalid")
    session_fields = exact._work_session_digest_fields(prepared.manifest)
    if any(result.get(name) != session_fields.get(name) for name in (
        "work_session_binding_sha256", "extension_sha256",
    )):
        raise WorkSessionGitTerminalError("work_session_git_terminal_common_evidence_invalid")
    return authority, receipt, exact.exact_operation_completion_authentication_payload(result)


def _basis(prepared, context, reference, commits, authority, receipt):
    if len(commits) != len(prepared.groups) or prepared.initial_head_oid in commits:
        raise WorkSessionGitTerminalError()
    evidence = prepared.manifest.operation_evidence
    binding = prepared.manifest.work_session_binding
    return {
        "schema": PAYLOAD_SCHEMA,
        "manifest_sha256": prepared.manifest.manifest_sha256,
        "context_sha256": approval.exact_human_approval_context_sha256(context),
        "approval_reference": dict(reference),
        "approval_binding_sha256": authority.binding_sha256,
        "execution_sha256": receipt["result"]["execution_sha256"],
        "common_final_receipt_sha256": receipt["receipt_sha256"],
        "common_result_sha256": receipt["result"]["result_sha256"],
        "selection_sha256": prepared.selection_sha256,
        "operation_evidence_sha256": None if evidence is None else writer._sha256_json(evidence.document()),
        "work_session_binding_sha256": None if binding is None else binding.binding_sha256,
        "initial_head_oid": prepared.initial_head_oid,
        "commit_oids": list(commits),
        "terminal_commit_oid": commits[-1],
        "exact_remote_ref_binding_sha256": writer._sha256_json({
            "schema": "wom-kit/git-terminal-exact-remote-ref/v1",
            "remote_url": prepared.remote_url, "target_ref": prepared.target_ref,
        }),
    }


def _audit_with_key(prepared, context, reference, payload, mac, key):
    return approval._audit_exact_human_approval_terminal_record_core(
        prepared.root, reference, expected_operation=context.operation,
        expected_plan_sha256=context.plan_sha256,
        expected_target_binding_sha256=context.target_binding_sha256,
        allowed_statuses=frozenset({"succeeded"}), expected_succeeded_evidence_digests=None,
        payload=payload, expected_mac=mac, receipt_authentication_key=key,
    )


def _build_git_terminal_record(prepared, *, context, claim, commit_oids) -> _GitTerminalRecord:
    """Sign assertions only while the original claim is ready, never on replay.

    The caller must eventually supply a trusted writer terminal observer. OIDs
    passed here are not independently verified, even when the MAC is valid.
    """
    def build():
        frozen = _original(prepared, context)
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise WorkSessionGitTerminalError("work_session_git_terminal_authentication_invalid")
        reference = claim.assert_ready_for_context(context)
        commits = _oids(commit_oids)
        authority, receipt, common_payload = _common(frozen, context, reference)
        if not claim.exact_terminal_record_matches(
            reference, context.operation, context.plan_sha256, context.target_binding_sha256,
            frozenset({"started"}), None, common_payload,
            receipt["result"]["completion_authentication"]["terminal_mac"],
        ):
            raise WorkSessionGitTerminalError("work_session_git_terminal_authentication_invalid")
        payload = _basis(frozen, context, reference, commits, authority, receipt)
        claim.assert_ready_for_context(context)
        mac = claim.exact_terminal_record_mac(_canonical(payload))
        claim.assert_ready_for_context(context)
        if _common(frozen, context, reference)[1] != receipt:
            raise WorkSessionGitTerminalError("work_session_git_terminal_common_evidence_invalid")
        claim.assert_ready_for_context(context)
        return _GitTerminalRecord(_canonical({"schema": RECORD_SCHEMA, "payload": payload, "terminal_mac": mac}))
    return _safe_call(build)


def _authenticate_git_terminal_record(
    prepared, *, context, record, receipt_authentication_key,
) -> _AuthenticatedGitTerminalRecord:
    """Read-only historical authentication inside one existing key consumer.

    No provider is opened here, no key escapes, and no current Git state is
    consulted. A succeeded claim can verify old assertions, never create new.
    """
    def authenticate():
        if type(record) is not _GitTerminalRecord or type(receipt_authentication_key) is not memoryview:
            raise WorkSessionGitTerminalError()
        # Freeze the exact supplied bytes before nested audit callbacks. Even a
        # frozen dataclass can be changed with object.__setattr__; retaining the
        # caller's object would let a later replacement inherit our old proof.
        detached = _GitTerminalRecord(record._raw)
        frozen = _original(prepared, context)
        document = detached._document()
        payload = document["payload"]
        reference = payload["approval_reference"]
        authority, receipt, common_payload = _common(frozen, context, reference)
        expected = _basis(frozen, context, reference, tuple(payload["commit_oids"]), authority, receipt)
        if payload != expected or not _audit_with_key(
            frozen, context, reference, _canonical(payload), document["terminal_mac"], receipt_authentication_key,
        ) or not _audit_with_key(
            frozen, context, reference, common_payload,
            receipt["result"]["completion_authentication"]["terminal_mac"], receipt_authentication_key,
        ):
            raise WorkSessionGitTerminalError("work_session_git_terminal_authentication_invalid")
        if _common(frozen, context, reference)[1] != receipt:
            raise WorkSessionGitTerminalError("work_session_git_terminal_common_evidence_invalid")
        return _AuthenticatedGitTerminalRecord(detached)
    return _safe_call(authenticate)
