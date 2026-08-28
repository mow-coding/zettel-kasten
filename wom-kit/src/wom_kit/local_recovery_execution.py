"""Shared exact writer for receipt-bound local recovery operations.

The domain planners keep private values in memory and publish only hashes,
counts, and fixed reason codes.  This module turns those private field specs
into one native approval, one common checkpoint stream, resumable execution,
field-scoped revert, and an independent read-back verification.

Private controls are written only after approval below ignored-local
``profiles/local``.  They are required because an interrupted run must retain
the exact pre/post payloads without re-planning against partially changed
targets.  Public results never echo those controls or their values.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping

import yaml

from . import archive_services, completion_workflows
from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import (
    _execute_exact_human_approved_write,
    _resume_exact_human_approved_write_core,
)
from .exact_operation_manifest import (
    CHECKPOINT_SCHEMA,
    EXACT_OPERATION_LOCAL_ROOT,
    EXACT_OPERATION_RECEIPTS_ROOT,
    FINAL_RECEIPT_SCHEMA,
    RESULT_SCHEMA as EXACT_OPERATION_RESULT_SCHEMA,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationEvidence,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    _validate_stable_result_document,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    inspect_exact_operation_state,
    revert_exact_operation_fields,
    verify_exact_operation,
)
from .operation_approval_binding import (
    OperationApprovalBindingError,
    exact_operation_manifest_approval_binding,
)
from .zettel_index_batch_lifecycle import ZettelIndexBatchLifecycle


APPLY_OPERATION = "local_recovery"
REVERT_OPERATION = "local_recovery_revert"
CONTROL_SCHEMA = "wom-kit/local-recovery-private-control/v0.1"
RESULT_SCHEMA = "wom-kit/local-recovery-execution-result/v0.1"
RESUME_LOCATOR_SCHEMA = "wom-kit/local-recovery-resume-locator/v0.1"
SUPERSESSION_PENDING_SCHEMA = (
    "wom-kit/local-recovery-supersession-pending/v0.1"
)
SUPERSESSION_FINAL_SCHEMA = (
    "wom-kit/local-recovery-supersession-final/v0.1"
)
CONTROL_ROOT = "profiles/local/local-recovery/controls"
RESUME_ROOT = "profiles/local/local-recovery/resume"
SUPERSESSION_ROOT = "profiles/local/local-recovery/supersessions"
LEDGER_ROOT = "profiles/local/local-recovery/ledgers"
MAX_CONTROL_BYTES = 128 * 1024 * 1024
MAX_LOCAL_FIELD_BYTES = 16 * 1024 * 1024
MAX_CANONICAL_BYTES = 16 * 1024 * 1024
MAX_CONTROL_FILES = 4096
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MARKER_FIELD = "body.source_locator_omission_markers"


class LocalRecoveryError(RuntimeError):
    _CODES = {
        "local_recovery_plan_invalid",
        "local_recovery_plan_blocked",
        "local_recovery_plan_changed",
        "local_recovery_control_invalid",
        "local_recovery_approval_required",
        "local_recovery_resume_invalid",
        "local_recovery_target_unsafe",
        "local_recovery_field_unsupported",
        "local_recovery_write_failed",
        "local_recovery_partial_revert_blocked",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "local_recovery_plan_invalid"
        super().__init__(self.code)


def _fail(code: str) -> LocalRecoveryError:
    return LocalRecoveryError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("local_recovery_plan_invalid") from None


def _canonical_line(value: Mapping[str, Any]) -> bytes:
    return _canonical_bytes(dict(value)) + b"\n"


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _b64(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def _unb64(value: Any) -> bytes | None:
    if value is None:
        return None
    if type(value) is not str or len(value) > MAX_LOCAL_FIELD_BYTES * 2:
        raise _fail("local_recovery_control_invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise _fail("local_recovery_control_invalid") from None
    if len(decoded) > MAX_LOCAL_FIELD_BYTES:
        raise _fail("local_recovery_control_invalid")
    return decoded


def _safe_relative(value: str, *, prefixes: tuple[str, ...]) -> str:
    if type(value) is not str or "\\" in value or not value:
        raise _fail("local_recovery_target_unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise _fail("local_recovery_target_unsafe")
    if not any(value.startswith(prefix) for prefix in prefixes):
        raise _fail("local_recovery_target_unsafe")
    return value


def local_recovery_zettel_identity_sha256(
    archive_id: str,
    zettel_id: str,
    relative_path: str,
) -> str:
    relative = _safe_relative(relative_path, prefixes=("zettels/",))
    if type(archive_id) is not str or not archive_id:
        raise _fail("local_recovery_plan_invalid")
    if type(zettel_id) is not str or not zettel_id:
        raise _fail("local_recovery_plan_invalid")
    return _sha(
        _canonical_bytes(
            {
                "schema": "wom-kit/local-recovery-zettel-identity/v0.1",
                "archive_id": archive_id,
                "zettel_id": zettel_id,
                "relative_path": relative,
                "status": "canonical",
            }
        )
    )


def local_recovery_ledger_identity_sha256(
    archive_id: str,
    domain: str,
    relative_path: str,
) -> str:
    if _DOMAIN_RE.fullmatch(domain) is None:
        raise _fail("local_recovery_plan_invalid")
    relative = _safe_relative(relative_path, prefixes=(LEDGER_ROOT + "/",))
    return _sha(
        _canonical_bytes(
            {
                "schema": "wom-kit/local-recovery-ledger-identity/v0.1",
                "archive_id": archive_id,
                "domain": domain,
                "relative_path": relative,
            }
        )
    )


def local_recovery_ledger_relative(domain: str, ledger_bytes: bytes) -> str:
    if _DOMAIN_RE.fullmatch(domain) is None or not ledger_bytes:
        raise _fail("local_recovery_plan_invalid")
    return f"{LEDGER_ROOT}/{domain}/{_sha(ledger_bytes).removeprefix('sha256:')}.json"


@dataclass(frozen=True)
class LocalRecoveryFieldSpec:
    item_id: str
    target_kind: str
    target_ref: str
    target_identity_sha256: str
    field_ref: str
    target_relative: str
    zettel_id: str | None
    pre_value: bytes | None
    post_value: bytes | None
    source_value: bytes
    post_file_bytes: bytes | None = None
    marker_pre_body: str | None = None
    marker_post_body: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.item_id) is not str
            or type(self.target_kind) is not str
            or type(self.target_ref) is not str
            or type(self.field_ref) is not str
            or _SHA256_RE.fullmatch(self.target_identity_sha256) is None
            or type(self.source_value) is not bytes
        ):
            raise _fail("local_recovery_plan_invalid")
        for value in (
            self.pre_value,
            self.post_value,
            self.source_value,
            self.post_file_bytes,
        ):
            if value is not None and (
                type(value) is not bytes or len(value) > MAX_LOCAL_FIELD_BYTES
            ):
                raise _fail("local_recovery_plan_invalid")
        if self.target_kind in {"zettel", "external_locator_record"}:
            _safe_relative(self.target_relative, prefixes=("zettels/",))
            if type(self.zettel_id) is not str or not self.zettel_id:
                raise _fail("local_recovery_plan_invalid")
        elif self.target_kind == "local_recovery_ledger":
            _safe_relative(
                self.target_relative,
                prefixes=(LEDGER_ROOT + "/",),
            )
            if self.zettel_id is not None:
                raise _fail("local_recovery_plan_invalid")
        else:
            raise _fail("local_recovery_field_unsupported")
        marker_values = (self.marker_pre_body, self.marker_post_body)
        if self.field_ref == _MARKER_FIELD:
            if any(type(value) is not str for value in marker_values):
                raise _fail("local_recovery_plan_invalid")
            try:
                version = _marker_projection_version(self.pre_value)
                if _marker_projection_version(self.post_value) != version:
                    raise ValueError("version")
                projection = (
                    _marker_projection_v1
                    if version == "v1"
                    else _marker_projection
                )
                if (
                    projection(self.marker_pre_body or "") != self.pre_value
                    or projection(self.marker_post_body or "")
                    != self.post_value
                ):
                    raise ValueError("projection")
            except ValueError:
                raise _fail("local_recovery_plan_invalid") from None
        elif any(value is not None for value in marker_values):
            raise _fail("local_recovery_plan_invalid")

    def control_document(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "target_kind": self.target_kind,
            "target_ref": self.target_ref,
            "target_identity_sha256": self.target_identity_sha256,
            "field_ref": self.field_ref,
            "target_relative": self.target_relative,
            "zettel_id": self.zettel_id,
            "pre_value_b64": _b64(self.pre_value),
            "post_value_b64": _b64(self.post_value),
            "source_value_b64": _b64(self.source_value),
            "post_file_bytes_b64": _b64(self.post_file_bytes),
            "marker_pre_body": self.marker_pre_body,
            "marker_post_body": self.marker_post_body,
        }

    @classmethod
    def from_control_document(cls, value: Mapping[str, Any]) -> "LocalRecoveryFieldSpec":
        expected = {
            "item_id",
            "target_kind",
            "target_ref",
            "target_identity_sha256",
            "field_ref",
            "target_relative",
            "zettel_id",
            "pre_value_b64",
            "post_value_b64",
            "source_value_b64",
            "post_file_bytes_b64",
            "marker_pre_body",
            "marker_post_body",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise _fail("local_recovery_control_invalid")
        source = _unb64(value.get("source_value_b64"))
        if source is None:
            raise _fail("local_recovery_control_invalid")
        try:
            return cls(
                item_id=value.get("item_id"),
                target_kind=value.get("target_kind"),
                target_ref=value.get("target_ref"),
                target_identity_sha256=value.get("target_identity_sha256"),
                field_ref=value.get("field_ref"),
                target_relative=value.get("target_relative"),
                zettel_id=value.get("zettel_id"),
                pre_value=_unb64(value.get("pre_value_b64")),
                post_value=_unb64(value.get("post_value_b64")),
                source_value=source,
                post_file_bytes=_unb64(value.get("post_file_bytes_b64")),
                marker_pre_body=value.get("marker_pre_body"),
                marker_post_body=value.get("marker_post_body"),
            )
        except LocalRecoveryError:
            raise
        except Exception:
            raise _fail("local_recovery_control_invalid") from None


@dataclass(frozen=True)
class LocalRecoveryPlan:
    archive_root: Path
    archive_id: str
    domain: str
    manifest: ExactOperationManifest
    specs: tuple[LocalRecoveryFieldSpec, ...]
    warning_codes: tuple[str, ...] = ()
    public_summary: Mapping[str, Any] | None = None
    loaded_from_control: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.archive_root, Path)
            or type(self.archive_id) is not str
            or not self.archive_id
            or _DOMAIN_RE.fullmatch(self.domain) is None
            or type(self.manifest) is not ExactOperationManifest
            or self.manifest.operation != APPLY_OPERATION
            or self.manifest.archive_identity_sha256
            != exact_human_approval_archive_identity_sha256(self.archive_id)
            or type(self.specs) is not tuple
            or len(self.specs) != len(self.manifest.items)
            or type(self.warning_codes) is not tuple
            or any(type(code) is not str for code in self.warning_codes)
        ):
            raise _fail("local_recovery_plan_invalid")
        for item, spec in zip(self.manifest.items, self.specs):
            if (
                item.item_id != spec.item_id
                or item.target_kind != spec.target_kind
                or item.target_ref != spec.target_ref
                or item.target_identity_sha256 != spec.target_identity_sha256
                or len(item.fields) != 1
                or item.fields[0].field_ref != spec.field_ref
                or item.fields[0].pre_sha256 != hash_field_value(spec.pre_value)
                or item.fields[0].post_sha256 != hash_field_value(spec.post_value)
                or item.fields[0].source_sha256 != hash_field_value(spec.source_value)
            ):
                raise _fail("local_recovery_plan_invalid")

    @property
    def approveable(self) -> bool:
        return bool(self.specs)

    def public_document(self) -> dict[str, Any]:
        manifest_summary = self.manifest.approval_digest_context()
        return {
            "schema_version": "wom-kit/local-recovery-executable-plan/v0.1",
            "ok": True,
            "state": "ready_for_native_approval",
            "domain": self.domain,
            # The native approval and private ignored-local control bind the full
            # manifest.  The ordinary CLI projection deliberately emits only its
            # content-free digest context: printing thousands of hashed item rows
            # does not help the operator decide and makes real-scale plans noisy.
            "manifest": manifest_summary,
            "summary": dict(self.public_summary or {}),
            "warning_codes": list(self.warning_codes),
            "native_human_decision_required": True,
            "operator_counting_required": False,
            "provider_called": False,
            "credential_values_read": False,
            "writes": False,
            "private_values_echoed": False,
            "paths_echoed": False,
        }


def build_local_recovery_plan(
    archive_root: Path | str,
    *,
    domain: str,
    manifest: ExactOperationManifest,
    specs: Iterable[LocalRecoveryFieldSpec],
    warning_codes: Iterable[str] = (),
    public_summary: Mapping[str, Any] | None = None,
) -> LocalRecoveryPlan:
    root = archive_services.require_existing_archive_root(archive_root)
    return LocalRecoveryPlan(
        archive_root=root,
        archive_id=archive_services.read_archive_id(root),
        domain=domain,
        manifest=manifest,
        specs=tuple(specs),
        warning_codes=tuple(sorted(set(warning_codes))),
        public_summary=dict(public_summary or {}),
    )


def combine_local_recovery_plans(
    plans: Iterable[LocalRecoveryPlan],
    *,
    domain: str,
    public_summary: Mapping[str, Any] | None = None,
) -> LocalRecoveryPlan:
    members = tuple(plans)
    if not members or _DOMAIN_RE.fullmatch(domain) is None:
        raise _fail("local_recovery_plan_invalid")
    root = members[0].archive_root
    archive_id = members[0].archive_id
    if any(
        plan.archive_root != root
        or plan.archive_id != archive_id
        or plan.loaded_from_control
        for plan in members
    ):
        raise _fail("local_recovery_plan_invalid")
    items: list[ExactOperationItem] = []
    specs: list[LocalRecoveryFieldSpec] = []
    counts: dict[str, int] = {}
    digests: dict[str, str] = {}
    for member_ordinal, plan in enumerate(members):
        key = f"member_{member_ordinal:02d}"
        counts[f"{key}_item_count"] = len(plan.manifest.items)
        counts[f"{key}_field_count"] = sum(
            len(item.fields) for item in plan.manifest.items
        )
        digests[f"{key}_manifest_sha256"] = plan.manifest.manifest_sha256
        if plan.manifest.operation_evidence is not None:
            digests[f"{key}_evidence_sha256"] = (
                plan.manifest.operation_evidence.evidence_sha256
            )
        for source_item, source_spec in zip(plan.manifest.items, plan.specs):
            item_id = f"item:{len(items):06d}"
            item = ExactOperationItem(
                ordinal=len(items),
                item_id=item_id,
                target_kind=source_item.target_kind,
                target_ref=source_item.target_ref,
                target_identity_sha256=source_item.target_identity_sha256,
                fields=tuple(
                    ExactFieldEffect(
                        field_ref=field.field_ref,
                        pre_sha256=field.pre_sha256,
                        post_sha256=field.post_sha256,
                        source_sha256=field.source_sha256,
                    )
                    for field in source_item.fields
                ),
            )
            items.append(item)
            specs.append(replace(source_spec, item_id=item_id))
    evidence = ExactOperationEvidence(
        schema="wom-kit/local-recovery-composite-evidence/v1",
        counts=tuple(sorted(counts.items())),
        digests=tuple(sorted(digests.items())),
    )
    manifest = ExactOperationManifest.build(
        operation=APPLY_OPERATION,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        items=items,
        operation_evidence=evidence,
    )
    return LocalRecoveryPlan(
        archive_root=root,
        archive_id=archive_id,
        domain=domain,
        manifest=manifest,
        specs=tuple(specs),
        warning_codes=tuple(
            sorted({code for plan in members for code in plan.warning_codes})
        ),
        public_summary=dict(public_summary or {}),
    )


def _operation_manifest(plan: LocalRecoveryPlan, *, mode: str) -> ExactOperationManifest:
    if mode == "apply":
        return plan.manifest
    if mode != "revert":
        raise _fail("local_recovery_plan_invalid")
    return ExactOperationManifest.build(
        operation=REVERT_OPERATION,
        archive_identity_sha256=plan.manifest.archive_identity_sha256,
        items=plan.manifest.items,
        operation_evidence=plan.manifest.operation_evidence,
    )


def _control_relative(manifest_sha256: str) -> str:
    if _SHA256_RE.fullmatch(manifest_sha256) is None:
        raise _fail("local_recovery_control_invalid")
    return f"{CONTROL_ROOT}/{manifest_sha256.removeprefix('sha256:')}.json"


def _control_document(plan: LocalRecoveryPlan) -> dict[str, Any]:
    basis = {
        "schema_version": CONTROL_SCHEMA,
        "archive_id": plan.archive_id,
        "domain": plan.domain,
        "manifest": plan.manifest.document(),
        "specs": [spec.control_document() for spec in plan.specs],
        "warning_codes": list(plan.warning_codes),
        "public_summary": dict(plan.public_summary or {}),
        "private_control_document": True,
    }
    return {**basis, "control_sha256": _sha(_canonical_bytes(basis))}


def _ensure_private_parent(root: Path, relative: str) -> Path:
    path = archive_services.archive_internal_path(root, relative)
    current = root
    for part in Path(relative).parts[:-1]:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            try:
                current.mkdir()
                info = os.lstat(current)
            except (OSError, FileExistsError):
                raise _fail("local_recovery_target_unsafe") from None
        except OSError:
            raise _fail("local_recovery_target_unsafe") from None
        if (
            not stat.S_ISDIR(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & 0x400)
        ):
            raise _fail("local_recovery_target_unsafe")
    return path


def _create_or_match(root: Path, relative: str, raw: bytes) -> None:
    path = _ensure_private_parent(root, relative)
    try:
        archive_services._write_bytes_create_if_absent(path, raw)
    except OSError:
        try:
            existing = path.read_bytes()
        except OSError:
            raise _fail("local_recovery_write_failed") from None
        if existing != raw:
            raise _fail("local_recovery_write_failed")
    try:
        info = os.lstat(path)
        if (
            not stat.S_ISREG(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & 0x400)
            or path.read_bytes() != raw
        ):
            raise OSError("readback")
    except OSError:
        raise _fail("local_recovery_write_failed") from None


def persist_local_recovery_control(plan: LocalRecoveryPlan) -> str:
    raw = _canonical_line(_control_document(plan))
    if len(raw) > MAX_CONTROL_BYTES:
        raise _fail("local_recovery_control_invalid")
    relative = _control_relative(plan.manifest.manifest_sha256)
    _create_or_match(plan.archive_root, relative, raw)
    return relative


def load_local_recovery_plan(
    archive_root: Path | str,
    *,
    manifest_sha256: str,
) -> LocalRecoveryPlan:
    root = archive_services.require_existing_archive_root(archive_root)
    relative = _control_relative(manifest_sha256)
    path = archive_services.archive_internal_path(root, relative)
    try:
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=MAX_CONTROL_BYTES,
        )
        if raw is None or reason is not None or not raw.endswith(b"\n"):
            raise ValueError("unsafe")
        document = json.loads(raw.decode("ascii"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("local_recovery_control_invalid") from None
    expected = {
        "schema_version",
        "archive_id",
        "domain",
        "manifest",
        "specs",
        "warning_codes",
        "public_summary",
        "private_control_document",
        "control_sha256",
    }
    if not isinstance(document, dict) or set(document) != expected:
        raise _fail("local_recovery_control_invalid")
    supplied = document.pop("control_sha256", None)
    if (
        document.get("schema_version") != CONTROL_SCHEMA
        or document.get("private_control_document") is not True
        or document.get("archive_id") != archive_services.read_archive_id(root)
        or type(supplied) is not str
        or not hmac.compare_digest(supplied, _sha(_canonical_bytes(document)))
        or type(document.get("specs")) is not list
        or type(document.get("warning_codes")) is not list
        or not isinstance(document.get("public_summary"), dict)
    ):
        raise _fail("local_recovery_control_invalid")
    try:
        manifest = ExactOperationManifest.from_document(document["manifest"])
        specs = tuple(
            LocalRecoveryFieldSpec.from_control_document(row)
            for row in document["specs"]
        )
        plan = LocalRecoveryPlan(
            archive_root=root,
            archive_id=document["archive_id"],
            domain=document["domain"],
            manifest=manifest,
            specs=specs,
            warning_codes=tuple(document["warning_codes"]),
            public_summary=document["public_summary"],
            loaded_from_control=True,
        )
    except (LocalRecoveryError, ExactOperationManifestError):
        raise
    except Exception:
        raise _fail("local_recovery_control_invalid") from None
    if plan.manifest.manifest_sha256 != manifest_sha256:
        raise _fail("local_recovery_control_invalid")
    return plan


def _zettel_snapshot(
    root: Path,
    spec: LocalRecoveryFieldSpec,
) -> tuple[Path, bytes, dict[str, Any], str]:
    path = archive_services.archive_internal_path(root, spec.target_relative)
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=MAX_CANONICAL_BYTES,
    )
    if raw is None or reason is not None:
        raise ValueError("target")
    try:
        text = raw.decode("utf-8")
        boundary = archive_services.parse_approval_zettel_content_boundary(text)
        frontmatter = boundary.get("frontmatter")
        body = str(boundary.get("body") or "")
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("target") from None
    if (
        boundary.get("state") == "blocked"
        or not isinstance(frontmatter, dict)
        or frontmatter.get("archive_id") != archive_services.read_archive_id(root)
        or frontmatter.get("id") != spec.zettel_id
        or frontmatter.get("status") != "canonical"
        or local_recovery_zettel_identity_sha256(
            frontmatter["archive_id"],
            spec.zettel_id or "",
            spec.target_relative,
        )
        != spec.target_identity_sha256
    ):
        raise ValueError("target")
    return path, raw, frontmatter, body


def _marker_projection_v1(body: str) -> bytes:
    marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
    rows: list[dict[str, Any]] = []
    start = 0
    ordinal = 0
    while True:
        position = body.find(marker, start)
        if position < 0:
            break
        ordinal += 1
        rows.append(
            {
                "ordinal": ordinal,
                "before_anchor_sha256": _sha(
                    body[max(0, position - 64) : position].encode("utf-8")
                ),
                "after_anchor_sha256": _sha(
                    body[position + len(marker) : position + len(marker) + 64].encode(
                        "utf-8"
                    )
                ),
            }
        )
        start = position + len(marker)
    return _canonical_bytes(rows)


def _marker_projection(body: str) -> bytes:
    marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
    legacy_rows = json.loads(_marker_projection_v1(body).decode("ascii"))
    return _canonical_bytes(
        {
            "schema": "wom-kit/source-locator-omission-marker-projection/v0.2",
            "marker_count": len(legacy_rows),
            "markers": legacy_rows,
            # Independent verification must also prove that no unrelated body
            # content was replaced while adding or removing marker tokens.
            "body_without_markers_sha256": _sha(
                body.replace(marker, "").encode("utf-8")
            ),
        }
    )


def _marker_projection_version(value: bytes | None) -> str:
    if type(value) is not bytes:
        raise ValueError("marker projection")
    try:
        document = json.loads(value.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("marker projection") from None
    if isinstance(document, list):
        return "v1"
    if (
        isinstance(document, dict)
        and document.get("schema")
        == "wom-kit/source-locator-omission-marker-projection/v0.2"
    ):
        return "v2"
    raise ValueError("marker projection")


def _marker_projection_for_spec(
    body: str,
    spec: LocalRecoveryFieldSpec,
) -> bytes:
    version = _marker_projection_version(spec.pre_value)
    if _marker_projection_version(spec.post_value) != version:
        raise ValueError("marker projection version")
    return _marker_projection_v1(body) if version == "v1" else _marker_projection(body)


def _field_value(
    root: Path,
    spec: LocalRecoveryFieldSpec,
) -> bytes | None:
    if spec.target_kind == "local_recovery_ledger":
        path = archive_services.archive_internal_path(root, spec.target_relative)
        if not path.exists() and not path.is_symlink():
            return None
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=MAX_LOCAL_FIELD_BYTES,
        )
        if raw is None or reason is not None:
            raise ValueError("ledger")
        return raw
    if spec.target_kind == "external_locator_record":
        _path, _raw, _frontmatter, _body = _zettel_snapshot(root, spec)
        record, _record_raw, error = completion_workflows._read_locator_record(
            root,
            spec.zettel_id or "",
        )
        if error is not None:
            raise ValueError("locator")
        if record is None:
            return None
        coordinates = [
            {
                "locator_type": row["locator_type"],
                "locator_ref": row["locator_ref"],
            }
            for row in record.get("locators", [])
            if isinstance(row, dict) and row.get("status") == "active"
        ]
        return _canonical_bytes(sorted(coordinates, key=lambda row: (row["locator_type"], row["locator_ref"])))
    _path, _raw, frontmatter, body = _zettel_snapshot(root, spec)
    if spec.field_ref == "frontmatter.title":
        title = frontmatter.get("title")
        if type(title) is not str:
            raise ValueError("title")
        return title.encode("utf-8")
    if spec.field_ref == "frontmatter.assets":
        assets = frontmatter.get("assets")
        if type(assets) is not list:
            raise ValueError("assets")
        return _canonical_bytes(assets)
    if spec.field_ref == _MARKER_FIELD:
        return _marker_projection_for_spec(body, spec)
    raise ValueError("field")


def build_observed_post_subset_revert_plan(
    plan: LocalRecoveryPlan,
) -> tuple[LocalRecoveryPlan | None, dict[str, Any]]:
    """Select only exact post-state fields for compensation.

    The original private control supplies pre/post values.  Current targets are
    read independently; exact post-state fields become a new native-approved
    subset manifest, exact pre-state fields are left untouched, and any other or
    unreadable state blocks the whole compensation plan.
    """

    if type(plan) is not LocalRecoveryPlan or not plan.loaded_from_control:
        raise _fail("local_recovery_partial_revert_blocked")
    selected: list[tuple[ExactOperationItem, LocalRecoveryFieldSpec]] = []
    already_pre_count = 0
    divergent_count = 0
    unreadable_count = 0
    for item, spec in zip(plan.manifest.items, plan.specs):
        try:
            observed = hash_field_value(_field_value(plan.archive_root, spec))
        except Exception:
            unreadable_count += 1
            continue
        field = item.fields[0]
        if hmac.compare_digest(observed, field.post_sha256):
            selected.append((item, spec))
        elif hmac.compare_digest(observed, field.pre_sha256):
            already_pre_count += 1
        else:
            divergent_count += 1
    report_basis = {
        "schema": "wom-kit/local-recovery-subset-revert-inspection/v1",
        "parent_manifest_sha256": plan.manifest.manifest_sha256,
        "field_count": len(plan.specs),
        "selected_post_field_count": len(selected),
        "already_pre_field_count": already_pre_count,
        "divergent_field_count": divergent_count,
        "unreadable_field_count": unreadable_count,
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    report = {
        **report_basis,
        "inspection_sha256": _sha(_canonical_bytes(report_basis)),
    }
    if divergent_count or unreadable_count:
        raise _fail("local_recovery_partial_revert_blocked")
    if not selected:
        return None, report

    items: list[ExactOperationItem] = []
    specs: list[LocalRecoveryFieldSpec] = []
    selection_refs: list[str] = []
    for ordinal, (source_item, source_spec) in enumerate(selected):
        item_id = f"item:{ordinal:06d}"
        field = source_item.fields[0]
        items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=item_id,
                target_kind=source_item.target_kind,
                target_ref=source_item.target_ref,
                target_identity_sha256=source_item.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref=field.field_ref,
                        pre_sha256=field.pre_sha256,
                        post_sha256=field.post_sha256,
                        source_sha256=field.source_sha256,
                    ),
                ),
            )
        )
        specs.append(replace(source_spec, item_id=item_id))
        selection_refs.append(
            _sha(
                _canonical_bytes(
                    {
                        "target_ref": source_item.target_ref,
                        "field_ref": field.field_ref,
                    }
                )
            )
        )
    evidence = ExactOperationEvidence(
        schema="wom-kit/local-recovery-subset-revert-evidence/v1",
        counts=tuple(
            sorted(
                {
                    "parent_field_count": len(plan.specs),
                    "selected_post_field_count": len(selected),
                    "already_pre_field_count": already_pre_count,
                }.items()
            )
        ),
        digests=tuple(
            sorted(
                {
                    "parent_manifest_sha256": plan.manifest.manifest_sha256,
                    "selected_field_set_sha256": _sha(
                        _canonical_bytes(selection_refs)
                    ),
                    "state_inspection_sha256": report["inspection_sha256"],
                }.items()
            )
        ),
    )
    manifest = ExactOperationManifest.build(
        operation=APPLY_OPERATION,
        archive_identity_sha256=plan.manifest.archive_identity_sha256,
        items=items,
        operation_evidence=evidence,
    )
    return (
        LocalRecoveryPlan(
            archive_root=plan.archive_root,
            archive_id=plan.archive_id,
            domain=plan.domain,
            manifest=manifest,
            specs=tuple(specs),
            warning_codes=tuple(
                sorted(
                    {
                        *plan.warning_codes,
                        "observed_post_subset_revert",
                    }
                )
            ),
            public_summary={
                **dict(plan.public_summary or {}),
                "parent_manifest_sha256": plan.manifest.manifest_sha256,
                "subset_revert_field_count": len(selected),
                "already_pre_field_count": already_pre_count,
            },
            loaded_from_control=True,
        ),
        report,
    )


def _subset_parent_plan(
    plan: LocalRecoveryPlan,
) -> LocalRecoveryPlan | None:
    """Return and revalidate the parent of an observed-post compensation.

    A warning string or public-summary digest alone is not enough to turn a
    normal revert into a superseding compensation.  The subset manifest also
    carries the parent digest in exact operation evidence, and every selected
    private field must be a byte-identical member of the persisted parent
    control.
    """

    if "observed_post_subset_revert" not in plan.warning_codes:
        return None
    evidence = plan.manifest.operation_evidence
    parent_sha = str(
        (plan.public_summary or {}).get("parent_manifest_sha256") or ""
    )
    evidence_digests = (
        dict(evidence.digests)
        if type(evidence) is ExactOperationEvidence
        else {}
    )
    evidence_counts = (
        dict(evidence.counts)
        if type(evidence) is ExactOperationEvidence
        else {}
    )
    if (
        not plan.loaded_from_control
        or evidence is None
        or evidence.schema
        != "wom-kit/local-recovery-subset-revert-evidence/v1"
        or _SHA256_RE.fullmatch(parent_sha) is None
        or parent_sha == plan.manifest.manifest_sha256
        or evidence_digests.get("parent_manifest_sha256") != parent_sha
        or evidence_counts.get("selected_post_field_count")
        != len(plan.specs)
    ):
        raise _fail("local_recovery_partial_revert_blocked")
    try:
        parent = load_local_recovery_plan(
            plan.archive_root,
            manifest_sha256=parent_sha,
        )
    except LocalRecoveryError:
        raise _fail("local_recovery_partial_revert_blocked") from None
    if (
        parent.archive_id != plan.archive_id
        or parent.domain != plan.domain
        or not parent.loaded_from_control
    ):
        raise _fail("local_recovery_partial_revert_blocked")

    remaining = list(zip(parent.manifest.items, parent.specs))
    for subset_item, subset_spec in zip(plan.manifest.items, plan.specs):
        matches = [
            index
            for index, (parent_item, parent_spec) in enumerate(remaining)
            if (
                parent_item.target_kind == subset_item.target_kind
                and parent_item.target_ref == subset_item.target_ref
                and parent_item.target_identity_sha256
                == subset_item.target_identity_sha256
                and parent_item.fields == subset_item.fields
                and replace(parent_spec, item_id=subset_spec.item_id)
                == subset_spec
            )
        ]
        if len(matches) != 1:
            raise _fail("local_recovery_partial_revert_blocked")
        remaining.pop(matches[0])
    return parent


def _frontmatter_value_replacement(raw: bytes, key: str, value: Any) -> bytes:
    try:
        text = raw.decode("utf-8")
        has_bom = text.startswith("\ufeff")
        payload = text[1:] if has_bom else text
        match = archive_services.FRONTMATTER_RE.match(payload)
        if match is None:
            raise ValueError("frontmatter")
        source = match.group(1)
        node = yaml.compose(source)
        matches: list[tuple[Any, Any]] = []
        if node is not None and getattr(node, "id", None) == "mapping":
            for key_node, value_node in getattr(node, "value", []):
                if (
                    getattr(key_node, "id", None) == "scalar"
                    and getattr(key_node, "value", None) == key
                ):
                    matches.append((key_node, value_node))
        if len(matches) != 1:
            raise ValueError("field")
        key_node, value_node = matches[0]
        start = int(key_node.start_mark.index)
        end = int(value_node.end_mark.index)
        rendered = yaml.safe_dump(
            {key: value},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        rendered_node = yaml.compose(rendered)
        rendered_values = list(getattr(rendered_node, "value", []))
        if len(rendered_values) != 1:
            raise ValueError("render")
        original = source[start:end]
        serialized = (
            rendered
            if original.endswith(("\n", "\r"))
            else rendered.rstrip("\r\n")
        )
        candidate_source = source[:start] + serialized + source[end:]
        candidate_payload = (
            payload[: match.start(1)]
            + candidate_source
            + payload[match.end(1) :]
        )
        candidate = (("\ufeff" if has_bom else "") + candidate_payload).encode("utf-8")
        before_frontmatter, before_body = archive_services.split_zettel_text(text)
        after_frontmatter, after_body = archive_services.split_zettel_text(
            candidate.decode("utf-8")
        )
        before_value = before_frontmatter.pop(key, None)
        after_value = after_frontmatter.pop(key, None)
        if (
            before_value == value
            or after_value != value
            or before_frontmatter != after_frontmatter
            or before_body != after_body
        ):
            raise ValueError("scope")
        return candidate
    except Exception:
        raise ValueError("frontmatter replacement") from None


def _split_raw_body(raw: bytes) -> tuple[str, str, str]:
    text = raw.decode("utf-8")
    has_bom = text.startswith("\ufeff")
    payload = text[1:] if has_bom else text
    match = archive_services.FRONTMATTER_RE.match(payload)
    if match is None:
        raise ValueError("frontmatter")
    prefix = ("\ufeff" if has_bom else "") + payload[: match.end()]
    return text, prefix, payload[match.end() :]


def _marker_transform(current: str, source: str, destination: str) -> str:
    marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER

    def split_positions(value: str) -> tuple[str, tuple[int, ...]]:
        parts = value.split(marker)
        plain = "".join(parts)
        positions: list[int] = []
        consumed = 0
        for part in parts[:-1]:
            consumed += len(part)
            positions.append(consumed)
        return plain, tuple(positions)

    source_plain, source_positions = split_positions(source)
    destination_plain, destination_positions = split_positions(destination)
    current_plain, current_positions = split_positions(current)
    if source_plain != destination_plain:
        raise ValueError("marker templates")
    if current_plain != source_plain or current_positions != source_positions:
        raise ValueError("marker current body drift")
    if source_positions == destination_positions:
        raise ValueError("marker count")
    if any(
        position < 0
        or position > len(destination_plain)
        or (
            ordinal > 0
            and position < destination_positions[ordinal - 1]
        )
        for ordinal, position in enumerate(destination_positions)
    ):
        raise ValueError("marker position")
    pieces: list[str] = []
    cursor = 0
    for position in destination_positions:
        pieces.append(destination_plain[cursor:position])
        pieces.append(marker)
        cursor = position
    pieces.append(destination_plain[cursor:])
    result = "".join(pieces)
    if result != destination or result.replace(marker, "") != current_plain:
        raise ValueError("marker non-marker body changed")
    return result


def _zettel_replacement(
    raw: bytes,
    spec: LocalRecoveryFieldSpec,
    value: bytes | None,
) -> bytes:
    if value is None:
        raise ValueError("zettel field absent")
    if spec.field_ref == "frontmatter.title":
        try:
            title = value.decode("utf-8")
        except UnicodeError:
            raise ValueError("title") from None
        return archive_services.zet_title_remap_candidate_bytes(raw, title)
    if spec.field_ref == "frontmatter.assets":
        try:
            assets = json.loads(value.decode("ascii"))
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("assets") from None
        if type(assets) is not list or _canonical_bytes(assets) != value:
            raise ValueError("assets")
        return _frontmatter_value_replacement(raw, "assets", assets)
    if spec.field_ref == _MARKER_FIELD:
        if spec.marker_pre_body is None or spec.marker_post_body is None:
            raise ValueError("marker")
        _text, prefix, current_body = _split_raw_body(raw)
        if value == spec.post_value:
            replacement_body = _marker_transform(
                current_body,
                spec.marker_pre_body,
                spec.marker_post_body,
            )
        elif value == spec.pre_value:
            legacy_whole_body_compensation = bool(
                _marker_projection_version(spec.pre_value) == "v1"
                and spec.marker_post_body.replace(
                    archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER,
                    "",
                )
                != spec.marker_pre_body.replace(
                    archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER,
                    "",
                )
            )
            if legacy_whole_body_compensation:
                # v0.4.7 accidentally bound a pre-normalization whole body as
                # the marker destination. Compensation is safe only while the
                # current body is still byte-for-byte that exact bad result.
                if current_body != spec.marker_post_body:
                    raise ValueError("legacy marker compensation drift")
                replacement_body = spec.marker_pre_body
            else:
                replacement_body = _marker_transform(
                    current_body,
                    spec.marker_post_body,
                    spec.marker_pre_body,
                )
        else:
            raise ValueError("marker payload")
        return (prefix + replacement_body).encode("utf-8")
    raise ValueError("field")


class _Payloads:
    def __init__(self, specs: tuple[LocalRecoveryFieldSpec, ...]) -> None:
        self.values: dict[tuple[str, str, str], bytes | None] = {}
        for spec in specs:
            self.values[(spec.item_id, spec.field_ref, "pre")] = spec.pre_value
            self.values[(spec.item_id, spec.field_ref, "post")] = spec.post_value
            self.values[(spec.item_id, spec.field_ref, "source")] = spec.source_value

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        return self.values[(item_id, field_ref, state)]


class _Boundary:
    def __init__(self, plan: LocalRecoveryPlan) -> None:
        self.root = plan.archive_root
        self.specs = {spec.target_ref: spec for spec in plan.specs}
        if len(self.specs) != len(plan.specs):
            raise _fail("local_recovery_plan_invalid")

    def spec(self, target_kind: str, target_ref: str, field_ref: str | None = None) -> LocalRecoveryFieldSpec:
        spec = self.specs.get(target_ref)
        if spec is None or spec.target_kind != target_kind:
            raise ValueError("target")
        if field_ref is not None and spec.field_ref != field_ref:
            raise ValueError("field")
        return spec


class _Verifier(_Boundary):
    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        spec = self.spec(target_kind, target_ref)
        if target_kind in {"zettel", "external_locator_record"}:
            _zettel_snapshot(self.root, spec)
        return spec.target_identity_sha256

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        return _field_value(self.root, self.spec(target_kind, target_ref, field_ref))


class _Writer(_Boundary):
    def __init__(
        self,
        plan: LocalRecoveryPlan,
        index_lifecycle: ZettelIndexBatchLifecycle,
    ) -> None:
        super().__init__(plan)
        self.index_lifecycle = index_lifecycle

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        heartbeat()
        spec = self.spec(target_kind, target_ref, field_ref)
        if hash_field_value(value) not in {
            hash_field_value(spec.pre_value),
            hash_field_value(spec.post_value),
        }:
            raise ValueError("payload")
        if target_kind == "zettel":
            path, raw, _frontmatter, _body = _zettel_snapshot(self.root, spec)
            replacement_bytes = _zettel_replacement(raw, spec, value)
            transaction = _sha(
                _canonical_bytes(
                    {
                        "schema": "wom-kit/local-recovery-field-cas/v0.1",
                        "target_ref": target_ref,
                        "field_ref": field_ref,
                        "before_sha256": _sha(raw),
                        "after_sha256": _sha(replacement_bytes),
                    }
                )
            )
            self.index_lifecycle.before_canonical_write()
            archive_services._replace_regular_file_bytes_compare_and_swap(
                self.root,
                path,
                expected_bytes=raw,
                replacement_bytes=replacement_bytes,
                transaction_sha256=transaction,
                swap_suffix=".local-recovery.swap",
                max_bytes=MAX_CANONICAL_BYTES,
                error_prefix="local_recovery",
            )
        elif target_kind == "external_locator_record":
            _zettel_snapshot(self.root, spec)
            relative = completion_workflows._record_relative(spec.zettel_id or "")
            path = archive_services.archive_internal_path(self.root, relative)
            if value is None:
                if spec.post_file_bytes is None:
                    raise ValueError("record")
                raw, reason = archive_services._bounded_stable_regular_file_read(
                    path,
                    max_bytes=MAX_LOCAL_FIELD_BYTES,
                )
                if raw != spec.post_file_bytes or reason is not None:
                    raise ValueError("record drift")
                path.unlink()
                archive_services.fsync_directory(path.parent)
            else:
                if value != spec.post_value or spec.post_file_bytes is None:
                    raise ValueError("record")
                _create_or_match(self.root, relative, spec.post_file_bytes)
        elif target_kind == "local_recovery_ledger":
            path = archive_services.archive_internal_path(
                self.root,
                spec.target_relative,
            )
            if value is None:
                raw, reason = archive_services._bounded_stable_regular_file_read(
                    path,
                    max_bytes=MAX_LOCAL_FIELD_BYTES,
                )
                if raw != spec.post_value or reason is not None:
                    raise ValueError("ledger drift")
                path.unlink()
                archive_services.fsync_directory(path.parent)
            else:
                if value != spec.post_value:
                    raise ValueError("ledger")
                _create_or_match(self.root, spec.target_relative, value)
        else:
            raise ValueError("target")
        heartbeat()


def _zettel_index_entries(
    plan: LocalRecoveryPlan,
) -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in plan.specs:
        if spec.target_kind != "zettel" or spec.target_relative in seen:
            continue
        seen.add(spec.target_relative)
        path, raw, frontmatter, body = _zettel_snapshot(
            plan.archive_root,
            spec,
        )
        entries.append(
            {
                "path": path,
                "frontmatter": frontmatter,
                "body": body,
                "expected_file_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return tuple(entries)


def _binding(plan: LocalRecoveryPlan, *, mode: str):
    manifest = _operation_manifest(plan, mode=mode)
    operation = (
        ExactHumanApprovalOperation.local_recovery
        if mode == "apply"
        else ExactHumanApprovalOperation.local_recovery_revert
    )
    try:
        return exact_operation_manifest_approval_binding(
            manifest,
            operation=operation,
            archive_id=plan.archive_id,
            warnings=plan.warning_codes,
        )
    except OperationApprovalBindingError:
        raise _fail("local_recovery_plan_invalid") from None


def local_recovery_context(
    plan: LocalRecoveryPlan,
    *,
    mode: str,
    reviewer_claim: str = "person:local-recovery-operator",
) -> ExactHumanApprovalContext:
    return _binding(plan, mode=mode).context(
        archive_id=plan.archive_id,
        reviewer_claim=reviewer_claim,
    )


def _authority(
    plan: LocalRecoveryPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    mode: str,
) -> ExactOperationApprovalAuthority:
    binding = _binding(plan, mode=mode)
    expected = (
        ExactHumanApprovalOperation.local_recovery
        if mode == "apply"
        else ExactHumanApprovalOperation.local_recovery_revert
    )
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not expected
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("local_recovery_approval_required")
    try:
        return ExactOperationApprovalAuthority.from_reference(
            _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        )
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("local_recovery_approval_required") from None


def _resume_relative(
    manifest_sha256: str,
    mode: str,
    approval_id: str,
) -> str:
    if (
        _SHA256_RE.fullmatch(manifest_sha256) is None
        or mode not in {"apply", "revert"}
        or _APPROVAL_ID_RE.fullmatch(approval_id) is None
    ):
        raise _fail("local_recovery_resume_invalid")
    return (
        f"{RESUME_ROOT}/{manifest_sha256.removeprefix('sha256:')}."
        f"{mode}.{approval_id}.json"
    )


def _persist_resume_locator(
    plan: LocalRecoveryPlan,
    manifest: ExactOperationManifest,
    authority: ExactOperationApprovalAuthority,
    *,
    mode: str,
) -> tuple[str, str]:
    execution = exact_operation_execution_sha256(
        manifest,
        mode=mode,
        selected_fields=(
            tuple((item.item_id, item.fields[0].field_ref) for item in manifest.items)
            if mode == "revert"
            else None
        ),
        approval_authority=authority,
    )
    relative = _resume_relative(
        plan.manifest.manifest_sha256,
        mode,
        authority.approval_id,
    )
    document = {
        "schema_version": RESUME_LOCATOR_SCHEMA,
        "domain": plan.domain,
        "mode": mode,
        "approval_id": authority.approval_id,
        "execution_sha256": execution,
        "apply_manifest_sha256": plan.manifest.manifest_sha256,
        "operation_manifest_sha256": manifest.manifest_sha256,
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    _create_or_match(plan.archive_root, relative, _canonical_line(document))
    return relative, execution


def _supersession_relative(
    parent_execution_sha256: str,
    compensation_execution_sha256: str,
    *,
    final: bool,
) -> str:
    if (
        _SHA256_RE.fullmatch(parent_execution_sha256) is None
        or _SHA256_RE.fullmatch(compensation_execution_sha256) is None
    ):
        raise _fail("local_recovery_resume_invalid")
    suffix = "final" if final else "pending"
    return (
        f"{SUPERSESSION_ROOT}/"
        f"{parent_execution_sha256.removeprefix('sha256:')}."
        f"{compensation_execution_sha256.removeprefix('sha256:')}."
        f"{suffix}.json"
    )


def _pending_supersession_document(
    *,
    parent: LocalRecoveryPlan,
    parent_locator: Mapping[str, Any],
    compensation: LocalRecoveryPlan,
    compensation_manifest: ExactOperationManifest,
    compensation_authority: ExactOperationApprovalAuthority,
    compensation_execution_sha256: str,
    compensation_locator: Mapping[str, Any],
) -> dict[str, Any]:
    parent_execution = str(parent_locator.get("execution_sha256") or "")
    if (
        parent_locator.get("mode") != "apply"
        or parent_locator.get("apply_manifest_sha256")
        != parent.manifest.manifest_sha256
        or compensation_locator.get("mode") != "revert"
        or compensation_locator.get("execution_sha256")
        != compensation_execution_sha256
        or compensation_locator.get("apply_manifest_sha256")
        != compensation.manifest.manifest_sha256
    ):
        raise _fail("local_recovery_partial_revert_blocked")
    basis = {
        "schema_version": SUPERSESSION_PENDING_SCHEMA,
        "status": "pending",
        "parent_apply_manifest_sha256": parent.manifest.manifest_sha256,
        "parent_apply_operation_manifest_sha256": parent_locator.get(
            "operation_manifest_sha256"
        ),
        "parent_apply_execution_sha256": parent_execution,
        "parent_apply_approval_id": parent_locator.get("approval_id"),
        "compensation_manifest_sha256": compensation.manifest.manifest_sha256,
        "compensation_operation_manifest_sha256": (
            compensation_manifest.manifest_sha256
        ),
        "compensation_execution_sha256": compensation_execution_sha256,
        "compensation_approval_authority": compensation_authority.document(),
        "compensation_resume_locator_sha256": _sha(
            _canonical_bytes(dict(compensation_locator))
        ),
        "compensation_field_count": len(compensation.specs),
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    return {
        **basis,
        "supersession_sha256": _sha(_canonical_bytes(basis)),
    }


def _persist_subset_supersession_pending(
    plan: LocalRecoveryPlan,
    manifest: ExactOperationManifest,
    authority: ExactOperationApprovalAuthority,
    compensation_execution_sha256: str,
) -> tuple[LocalRecoveryPlan, dict[str, Any]] | None:
    parent = _subset_parent_plan(plan)
    if parent is None:
        if not plan.loaded_from_control:
            return None
        parent = plan
    parent_locators = _locator_documents(parent, mode="apply")
    active = [
        locator
        for locator in parent_locators
        if _strict_resume_checkpoint_present(
            parent,
            locator,
            respect_supersession=False,
        )
    ]
    if not active and parent.manifest.manifest_sha256 == plan.manifest.manifest_sha256:
        return None
    if len(active) != 1:
        raise _fail("local_recovery_partial_revert_blocked")
    compensation_locators = [
        locator
        for locator in _locator_documents(plan, mode="revert")
        if locator.get("execution_sha256") == compensation_execution_sha256
        and locator.get("approval_id") == authority.approval_id
        and locator.get("operation_manifest_sha256")
        == manifest.manifest_sha256
    ]
    if len(compensation_locators) != 1:
        raise _fail("local_recovery_partial_revert_blocked")
    document = _pending_supersession_document(
        parent=parent,
        parent_locator=active[0],
        compensation=plan,
        compensation_manifest=manifest,
        compensation_authority=authority,
        compensation_execution_sha256=compensation_execution_sha256,
        compensation_locator=compensation_locators[0],
    )
    relative = _supersession_relative(
        document["parent_apply_execution_sha256"],
        document["compensation_execution_sha256"],
        final=False,
    )
    _create_or_match(plan.archive_root, relative, _canonical_line(document))
    return parent, document


def _safe_supersession_entries(
    root: Path,
    *,
    parent_execution_sha256: str,
) -> tuple[Path, ...]:
    if _SHA256_RE.fullmatch(parent_execution_sha256) is None:
        raise _fail("local_recovery_resume_invalid")
    directory = archive_services.archive_internal_path(root, SUPERSESSION_ROOT)
    try:
        info = os.lstat(directory)
    except FileNotFoundError:
        return ()
    except OSError:
        raise _fail("local_recovery_resume_invalid") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    ):
        raise _fail("local_recovery_resume_invalid")
    try:
        entries = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    except OSError:
        raise _fail("local_recovery_resume_invalid") from None
    if len(entries) > MAX_CONTROL_FILES:
        raise _fail("local_recovery_resume_invalid")
    prefix = parent_execution_sha256.removeprefix("sha256:") + "."
    return tuple(
        path
        for path in entries
        if path.name.startswith(prefix)
        and path.name.endswith((".pending.json", ".final.json"))
    )


def _validated_parent_supersession_records(
    parent: LocalRecoveryPlan,
    parent_locator: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    parent_execution = str(parent_locator.get("execution_sha256") or "")
    expected_fields = {
        "schema_version",
        "status",
        "parent_apply_manifest_sha256",
        "parent_apply_operation_manifest_sha256",
        "parent_apply_execution_sha256",
        "parent_apply_approval_id",
        "compensation_manifest_sha256",
        "compensation_operation_manifest_sha256",
        "compensation_execution_sha256",
        "compensation_approval_authority",
        "compensation_resume_locator_sha256",
        "compensation_field_count",
        "private_values_echoed",
        "paths_echoed",
        "supersession_sha256",
    }
    entries = _safe_supersession_entries(
        parent.archive_root,
        parent_execution_sha256=parent_execution,
    )
    pending_paths = tuple(
        path for path in entries if path.name.endswith(".pending.json")
    )
    final_paths = tuple(
        path for path in entries if path.name.endswith(".final.json")
    )
    validated: list[dict[str, Any]] = []
    for path in pending_paths:
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=64 * 1024,
        )
        try:
            if raw is None or reason is not None or not raw.endswith(b"\n"):
                raise ValueError("read")
            document = json.loads(raw[:-1].decode("ascii"))
            if (
                not isinstance(document, dict)
                or set(document) != expected_fields
                or _canonical_line(document) != raw
            ):
                raise ValueError("document")
            supplied = document.pop("supersession_sha256")
            if (
                document.get("schema_version")
                != SUPERSESSION_PENDING_SCHEMA
                or document.get("status") != "pending"
                or document.get("parent_apply_manifest_sha256")
                != parent.manifest.manifest_sha256
                or document.get("parent_apply_operation_manifest_sha256")
                != parent_locator.get("operation_manifest_sha256")
                or document.get("parent_apply_execution_sha256")
                != parent_execution
                or document.get("parent_apply_approval_id")
                != parent_locator.get("approval_id")
                or type(document.get("compensation_field_count")) is not int
                or document["compensation_field_count"] <= 0
                or document.get("private_values_echoed") is not False
                or document.get("paths_echoed") is not False
                or path.name
                != Path(
                    _supersession_relative(
                        parent_execution,
                        str(document.get("compensation_execution_sha256") or ""),
                        final=False,
                    )
                ).name
                or not isinstance(supplied, str)
                or not hmac.compare_digest(
                    supplied,
                    _sha(_canonical_bytes(document)),
                )
            ):
                raise ValueError("binding")
            compensation = load_local_recovery_plan(
                parent.archive_root,
                manifest_sha256=document["compensation_manifest_sha256"],
            )
            rebound_parent = _subset_parent_plan(compensation)
            if (
                rebound_parent is None
                and compensation.loaded_from_control
                and compensation.manifest.manifest_sha256
                == parent.manifest.manifest_sha256
            ):
                rebound_parent = compensation
            if (
                rebound_parent is None
                or rebound_parent.manifest.manifest_sha256
                != parent.manifest.manifest_sha256
                or len(compensation.specs)
                != document["compensation_field_count"]
            ):
                raise ValueError("parent")
            operation_manifest = _operation_manifest(
                compensation,
                mode="revert",
            )
            if (
                operation_manifest.manifest_sha256
                != document["compensation_operation_manifest_sha256"]
            ):
                raise ValueError("operation")
            raw_authority = document["compensation_approval_authority"]
            if not isinstance(raw_authority, dict) or set(raw_authority) != {
                "schema",
                "approval_id",
                "context_sha256",
                "approval_authority_sha256",
                "binding_sha256",
            }:
                raise ValueError("authority")
            authority = ExactOperationApprovalAuthority(
                approval_id=raw_authority["approval_id"],
                context_sha256=raw_authority["context_sha256"],
                approval_authority_sha256=raw_authority[
                    "approval_authority_sha256"
                ],
                binding_sha256=raw_authority["binding_sha256"],
            )
            compensation_execution = exact_operation_execution_sha256(
                operation_manifest,
                mode="revert",
                selected_fields=tuple(
                    (item.item_id, item.fields[0].field_ref)
                    for item in operation_manifest.items
                ),
                approval_authority=authority,
            )
            if (
                compensation_execution
                != document["compensation_execution_sha256"]
                or authority.approval_id
                != document["compensation_approval_authority"]["approval_id"]
            ):
                raise ValueError("execution")
            matching_locators = [
                locator
                for locator in _locator_documents(compensation, mode="revert")
                if locator.get("execution_sha256") == compensation_execution
                and locator.get("approval_id") == authority.approval_id
                and locator.get("operation_manifest_sha256")
                == operation_manifest.manifest_sha256
            ]
            if (
                len(matching_locators) != 1
                or _sha(_canonical_bytes(matching_locators[0]))
                != document["compensation_resume_locator_sha256"]
            ):
                raise ValueError("locator")
            document["supersession_sha256"] = supplied
            validated.append(document)
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
            LocalRecoveryError,
            ExactOperationManifestError,
        ):
            raise _fail("local_recovery_resume_invalid") from None

    final_expected_fields = {
        "schema_version",
        "status",
        "parent_apply_manifest_sha256",
        "parent_apply_execution_sha256",
        "compensation_manifest_sha256",
        "compensation_execution_sha256",
        "pending_supersession_sha256",
        "compensation_final_receipt_sha256",
        "parent_pre_state_verified",
        "parent_pre_verification_sha256",
        "private_values_echoed",
        "paths_echoed",
        "supersession_final_sha256",
    }
    matched_pending_hashes: set[str] = set()
    for path in final_paths:
        raw, reason = archive_services._bounded_stable_regular_file_read(
            path,
            max_bytes=64 * 1024,
        )
        try:
            if raw is None or reason is not None or not raw.endswith(b"\n"):
                raise ValueError("read")
            document = json.loads(raw[:-1].decode("ascii"))
            if (
                not isinstance(document, dict)
                or set(document) != final_expected_fields
                or _canonical_line(document) != raw
            ):
                raise ValueError("document")
            supplied_final = document.pop("supersession_final_sha256")
            pending_hash = str(
                document.get("pending_supersession_sha256") or ""
            )
            compensation_execution = str(
                document.get("compensation_execution_sha256") or ""
            )
            matching_pending = [
                pending
                for pending in validated
                if pending.get("supersession_sha256") == pending_hash
                and pending.get("parent_apply_execution_sha256")
                == parent_execution
                and pending.get("compensation_manifest_sha256")
                == document.get("compensation_manifest_sha256")
                and pending.get("compensation_execution_sha256")
                == compensation_execution
            ]
            if (
                document.get("schema_version") != SUPERSESSION_FINAL_SCHEMA
                or document.get("status") != "final"
                or document.get("parent_apply_manifest_sha256")
                != parent.manifest.manifest_sha256
                or document.get("parent_apply_execution_sha256")
                != parent_execution
                or document.get("parent_pre_state_verified") is not True
                or document.get("private_values_echoed") is not False
                or document.get("paths_echoed") is not False
                or _SHA256_RE.fullmatch(pending_hash) is None
                or _SHA256_RE.fullmatch(compensation_execution) is None
                or _SHA256_RE.fullmatch(
                    str(document.get("compensation_final_receipt_sha256") or "")
                )
                is None
                or _SHA256_RE.fullmatch(
                    str(document.get("parent_pre_verification_sha256") or "")
                )
                is None
                or len(matching_pending) != 1
                or pending_hash in matched_pending_hashes
                or path.name
                != Path(
                    _supersession_relative(
                        parent_execution,
                        compensation_execution,
                        final=True,
                    )
                ).name
                or not isinstance(supplied_final, str)
                or not hmac.compare_digest(
                    supplied_final,
                    _sha(_canonical_bytes(document)),
                )
            ):
                raise ValueError("binding")

            receipt_path = archive_services.archive_internal_path(
                parent.archive_root,
                f"{EXACT_OPERATION_RECEIPTS_ROOT}/"
                f"{compensation_execution.removeprefix('sha256:')}.json",
            )
            receipt_raw, receipt_reason = (
                archive_services._bounded_stable_regular_file_read(
                    receipt_path,
                    max_bytes=MAX_CANONICAL_BYTES,
                )
            )
            if (
                receipt_raw is None
                or receipt_reason is not None
                or not receipt_raw.endswith(b"\n")
            ):
                raise ValueError("receipt")
            receipt_document = json.loads(receipt_raw[:-1].decode("ascii"))
            if not isinstance(receipt_document, dict):
                raise ValueError("receipt")
            receipt_basis = dict(receipt_document)
            supplied_receipt_sha256 = receipt_basis.pop(
                "receipt_sha256",
                None,
            )
            if (
                _canonical_line(receipt_document) != receipt_raw
                or receipt_document.get("schema") != FINAL_RECEIPT_SCHEMA
                or not isinstance(receipt_document.get("result"), dict)
                or receipt_document["result"].get("execution_sha256")
                != compensation_execution
                or supplied_receipt_sha256
                != document["compensation_final_receipt_sha256"]
                or _sha(_canonical_bytes(receipt_basis))
                != supplied_receipt_sha256
            ):
                raise ValueError("receipt")
            verification = verify_exact_operation(
                parent.manifest,
                verifier=_Verifier(parent),
                state="pre",
            )
            if (
                verification.get("all_match") is not True
                or _sha(_canonical_bytes(verification))
                != document["parent_pre_verification_sha256"]
            ):
                raise ValueError("verification")
            matched_pending_hashes.add(pending_hash)
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
            LocalRecoveryError,
            ExactOperationManifestError,
        ):
            raise _fail("local_recovery_resume_invalid") from None
    return tuple(validated)


def _persist_subset_supersession_final(
    parent: LocalRecoveryPlan,
    pending: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    execution = result.get("execution")
    if not isinstance(execution, Mapping):
        raise _fail("local_recovery_partial_revert_blocked")
    compensation_execution = str(execution.get("execution_sha256") or "")
    final_receipt_sha256 = str(execution.get("final_receipt_sha256") or "")
    if (
        result.get("ok") is not True
        or compensation_execution
        != pending.get("compensation_execution_sha256")
        or _SHA256_RE.fullmatch(final_receipt_sha256) is None
    ):
        raise _fail("local_recovery_partial_revert_blocked")
    verification = verify_exact_operation(
        parent.manifest,
        verifier=_Verifier(parent),
        state="pre",
    )
    if verification.get("all_match") is not True:
        raise _fail("local_recovery_partial_revert_blocked")
    receipt_path = archive_services.archive_internal_path(
        parent.archive_root,
        f"{EXACT_OPERATION_RECEIPTS_ROOT}/"
        f"{compensation_execution.removeprefix('sha256:')}.json",
    )
    receipt_raw, receipt_reason = (
        archive_services._bounded_stable_regular_file_read(
            receipt_path,
            max_bytes=MAX_CANONICAL_BYTES,
        )
    )
    try:
        receipt_document = (
            json.loads(receipt_raw[:-1].decode("ascii"))
            if receipt_raw is not None
            and receipt_reason is None
            and receipt_raw.endswith(b"\n")
            else None
        )
        receipt_basis = dict(receipt_document or {})
        supplied_receipt_sha256 = receipt_basis.pop(
            "receipt_sha256",
            None,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        receipt_document = None
        receipt_basis = {}
        supplied_receipt_sha256 = None
    if (
        not isinstance(receipt_document, dict)
        or _canonical_line(receipt_document) != receipt_raw
        or receipt_document.get("schema") != FINAL_RECEIPT_SCHEMA
        or not isinstance(receipt_document.get("result"), dict)
        or receipt_document["result"].get("execution_sha256")
        != compensation_execution
        or supplied_receipt_sha256 != final_receipt_sha256
        or _sha(_canonical_bytes(receipt_basis)) != final_receipt_sha256
    ):
        raise _fail("local_recovery_partial_revert_blocked")
    basis = {
        "schema_version": SUPERSESSION_FINAL_SCHEMA,
        "status": "final",
        "parent_apply_manifest_sha256": pending[
            "parent_apply_manifest_sha256"
        ],
        "parent_apply_execution_sha256": pending[
            "parent_apply_execution_sha256"
        ],
        "compensation_manifest_sha256": pending[
            "compensation_manifest_sha256"
        ],
        "compensation_execution_sha256": compensation_execution,
        "pending_supersession_sha256": pending["supersession_sha256"],
        "compensation_final_receipt_sha256": final_receipt_sha256,
        "parent_pre_state_verified": True,
        "parent_pre_verification_sha256": _sha(
            _canonical_bytes(verification)
        ),
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    document = {
        **basis,
        "supersession_final_sha256": _sha(_canonical_bytes(basis)),
    }
    relative = _supersession_relative(
        basis["parent_apply_execution_sha256"],
        compensation_execution,
        final=True,
    )
    _create_or_match(parent.archive_root, relative, _canonical_line(document))


def _matching_subset_supersession_pending(
    plan: LocalRecoveryPlan,
    authority: ExactOperationApprovalAuthority,
    compensation_execution_sha256: str,
) -> tuple[LocalRecoveryPlan, dict[str, Any]] | None:
    parent = _subset_parent_plan(plan)
    if parent is None:
        if not plan.loaded_from_control:
            return None
        parent = plan
    matches: list[dict[str, Any]] = []
    for parent_locator in _locator_documents(parent, mode="apply"):
        for document in _validated_parent_supersession_records(
            parent,
            parent_locator,
        ):
            if (
                document.get("compensation_manifest_sha256")
                == plan.manifest.manifest_sha256
                and document.get("compensation_execution_sha256")
                == compensation_execution_sha256
                and document.get("compensation_approval_authority")
                == authority.document()
            ):
                matches.append(document)
    if len(matches) != 1:
        raise _fail("local_recovery_resume_invalid")
    return parent, matches[0]


def _completed_subset_supersession_pending(
    plan: LocalRecoveryPlan,
    compensation_execution_sha256: str,
    *,
    authority: ExactOperationApprovalAuthority | None = None,
) -> tuple[LocalRecoveryPlan, dict[str, Any], dict[str, Any]] | None:
    """Recover a compensation that finished before its final supersession.

    The common exact-operation receipt is the durable commit record.  If that
    receipt exists but the small parent-supersession finalizer was interrupted,
    the old apply must stay blocked *and* the already approved compensation
    must remain finishable without replaying any field write.
    """

    if _SHA256_RE.fullmatch(compensation_execution_sha256) is None:
        raise _fail("local_recovery_resume_invalid")
    parent = _subset_parent_plan(plan)
    if parent is None:
        if not plan.loaded_from_control:
            return None
        parent = plan
    matches: list[dict[str, Any]] = []
    for parent_locator in _locator_documents(parent, mode="apply"):
        for document in _validated_parent_supersession_records(
            parent,
            parent_locator,
        ):
            if (
                document.get("compensation_manifest_sha256")
                == plan.manifest.manifest_sha256
                and document.get("compensation_execution_sha256")
                == compensation_execution_sha256
                and (
                    authority is None
                    or document.get("compensation_approval_authority")
                    == authority.document()
                )
            ):
                matches.append(document)
    if not matches:
        return None
    if len(matches) != 1:
        raise _fail("local_recovery_resume_invalid")
    pending = matches[0]

    final_path = archive_services.archive_internal_path(
        parent.archive_root,
        _supersession_relative(
            pending["parent_apply_execution_sha256"],
            compensation_execution_sha256,
            final=True,
        ),
    )
    final_raw, final_reason = archive_services._bounded_stable_regular_file_read(
        final_path,
        max_bytes=64 * 1024,
    )
    if final_reason is None and final_raw is not None:
        return None
    if final_reason != "missing" or final_raw is not None:
        raise _fail("local_recovery_resume_invalid")

    receipt_path = archive_services.archive_internal_path(
        parent.archive_root,
        f"{EXACT_OPERATION_RECEIPTS_ROOT}/"
        f"{compensation_execution_sha256.removeprefix('sha256:')}.json",
    )
    raw, reason = archive_services._bounded_stable_regular_file_read(
        receipt_path,
        max_bytes=MAX_CANONICAL_BYTES,
    )
    if reason == "missing":
        return None
    try:
        if raw is None or reason is not None or not raw.endswith(b"\n"):
            raise ValueError("receipt")
        receipt = json.loads(raw[:-1].decode("ascii"))
        if not isinstance(receipt, dict) or _canonical_line(receipt) != raw:
            raise ValueError("receipt")
        receipt_basis = dict(receipt)
        receipt_sha256 = receipt_basis.pop("receipt_sha256", None)
        result = receipt.get("result")
        if not isinstance(result, dict):
            raise ValueError("result")
        _validate_stable_result_document(result)
        result_basis = dict(result)
        result_sha256 = result_basis.pop("result_sha256", None)
        operation_manifest = _operation_manifest(plan, mode="revert")
        raw_authority = pending.get("compensation_approval_authority")
        if (
            receipt.get("schema") != FINAL_RECEIPT_SCHEMA
            or _SHA256_RE.fullmatch(str(receipt_sha256 or "")) is None
            or _sha(_canonical_bytes(receipt_basis)) != receipt_sha256
            or result.get("schema") != EXACT_OPERATION_RESULT_SCHEMA
            or result.get("status") != "completed"
            or result.get("mode") != "revert"
            or result.get("manifest_sha256")
            != operation_manifest.manifest_sha256
            or result.get("execution_sha256")
            != compensation_execution_sha256
            or not isinstance(raw_authority, dict)
            or result.get("approval_binding_sha256")
            != raw_authority.get("binding_sha256")
            or result.get("item_count") != len(operation_manifest.items)
            or result.get("field_count")
            != sum(len(item.fields) for item in operation_manifest.items)
            or result.get("private_values_echoed") is not False
            or _SHA256_RE.fullmatch(str(result_sha256 or "")) is None
            or _sha(_canonical_bytes(result_basis)) != result_sha256
        ):
            raise ValueError("binding")
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeError,
        json.JSONDecodeError,
        LocalRecoveryError,
        ExactOperationManifestError,
    ):
        raise _fail("local_recovery_resume_invalid") from None

    execution = {
        **result,
        "final_receipt_sha256": receipt_sha256,
        "written_field_count": 0,
        "resumed_field_count": 0,
        "progress_delivery_failure_count": 0,
    }
    public = {
        "schema_version": RESULT_SCHEMA,
        "ok": True,
        "state": "reverted",
        "domain": plan.domain,
        "mode": "revert",
        "manifest_sha256": plan.manifest.manifest_sha256,
        "operation_manifest_sha256": operation_manifest.manifest_sha256,
        "execution": execution,
        "item_count": len(plan.specs),
        "field_count": sum(
            len(item.fields) for item in operation_manifest.items
        ),
        "written_field_count": 0,
        "resumed_field_count": 0,
        "field_scoped_revert_supported": True,
        "common_exact_operation_manifest_used": True,
        "independent_verification": True,
        "finalized_existing_receipt": True,
        "operator_counting_required": False,
        "provider_called": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    return parent, pending, public


def _index_precondition_blocked_result(
    plan: LocalRecoveryPlan,
    manifest: ExactOperationManifest,
    *,
    mode: str,
    lifecycle: ZettelIndexBatchLifecycle,
) -> dict[str, Any]:
    field_count = sum(len(item.fields) for item in manifest.items)
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": False,
        "state": "local_recovery_index_rebuild_required",
        "domain": plan.domain,
        "mode": mode,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "operation_manifest_sha256": manifest.manifest_sha256,
        "reason_codes": [archive_services.INDEX_REBUILD_REQUIRED],
        "blockers": [archive_services.INDEX_REBUILD_REQUIRED],
        "item_count": len(plan.specs),
        "field_count": field_count,
        "written_field_count": 0,
        "resumed_field_count": 0,
        "applied_field_count": 0,
        "reverted_field_count": 0,
        "remaining_field_count": field_count,
        "checkpointed_field_count": 0,
        "written_before_checkpoint_field_count": 0,
        "writes_performed": False,
        "resume_supported": False,
        "subset_revert_supported": False,
        "next_safe_actions": list(
            archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS
        ),
        "automatic_retry_allowed": False,
        "field_scoped_revert_supported": True,
        "common_exact_operation_manifest_used": True,
        "independent_verification": True,
        "operator_counting_required": False,
        "provider_called": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
        **lifecycle.precondition_truth(),
    }


def _run_with_store(
    plan: LocalRecoveryPlan,
    authority: ExactOperationApprovalAuthority,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    mode: str,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    index_lifecycle: ZettelIndexBatchLifecycle | None = None,
) -> dict[str, Any]:
    manifest = _operation_manifest(plan, mode=mode)
    payloads = _Payloads(plan.specs)
    index_lifecycle = index_lifecycle or ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=any(
            spec.target_kind == "zettel" for spec in plan.specs
        ),
        allow_dirty_resume=resume or mode == "revert",
        operation_owner_sha256=(
            archive_services.archive_manifest_mutation_owner_sha256(
                operation="local_recovery",
                operation_binding_sha256=plan.manifest.manifest_sha256,
            )
        ),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            manifest,
            mode=mode,
            lifecycle=index_lifecycle,
        )
    writer = _Writer(plan, index_lifecycle)
    verifier = _Verifier(plan)
    selected_fields = (
        tuple(
            (item.item_id, item.fields[0].field_ref)
            for item in manifest.items
        )
        if mode == "revert"
        else None
    )
    try:
        if mode == "apply":
            core = apply_exact_operation(
                manifest,
                payloads=payloads,
                writer=writer,
                verifier=verifier,
                checkpoint_store=checkpoints,
                approval_authority=authority,
                resume=resume,
                progress_hook=progress_hook,
            )
        else:
            core = revert_exact_operation_fields(
                manifest,
                selected_fields=selected_fields or (),
                payloads=payloads,
                writer=writer,
                verifier=verifier,
                checkpoint_store=checkpoints,
                approval_authority=authority,
                resume=resume,
                progress_hook=progress_hook,
            )
    except Exception as error:
        index_truth = index_lifecycle.interrupted()
        try:
            inspection = inspect_exact_operation_state(
                manifest,
                verifier=verifier,
                checkpoint_store=checkpoints,
                mode=mode,
                selected_fields=selected_fields,
                approval_authority=authority,
            )
        except Exception:
            raise error
        reason_code = (
            error.code
            if isinstance(error, (ExactOperationManifestError, LocalRecoveryError))
            else "local_recovery_write_interrupted"
        )
        destination_count = inspection["destination_field_count"]
        source_count = inspection["source_field_count"]
        unsafe_legacy_marker_apply = bool(
            mode == "apply"
            and any(
                spec.field_ref == _MARKER_FIELD
                and _marker_projection_version(spec.pre_value) == "v1"
                and (spec.marker_pre_body or "").replace(
                    archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER,
                    "",
                )
                != (spec.marker_post_body or "").replace(
                    archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER,
                    "",
                )
                for spec in plan.specs
            )
        )
        resume_supported = bool(
            inspection["resume_supported"]
            and not unsafe_legacy_marker_apply
        )
        local_state = {
            "partially_written": (
                "partially_reverted" if mode == "revert" else "partially_applied"
            ),
            "fully_written_receipt_pending": (
                "fully_reverted_receipt_pending"
                if mode == "revert"
                else "fully_applied_receipt_pending"
            ),
            "started_no_fields_written": "started_no_fields_changed",
            "not_started": "not_started",
            "requires_review": "requires_review",
            "completed": "reverted" if mode == "revert" else "applied",
        }[inspection["state"]]
        next_safe_actions = []
        if resume_supported:
            next_safe_actions.append("resume_same_manifest")
        if mode == "apply" and inspection["subset_compensation_supported"]:
            next_safe_actions.append("revert_observed_applied_subset")
        return {
            "schema_version": RESULT_SCHEMA,
            "ok": False,
            "state": local_state,
            "domain": plan.domain,
            "mode": mode,
            "manifest_sha256": plan.manifest.manifest_sha256,
            "operation_manifest_sha256": manifest.manifest_sha256,
            "reason_codes": [reason_code],
            "execution_state": inspection,
            "item_count": len(plan.specs),
            "field_count": sum(len(item.fields) for item in manifest.items),
            "applied_field_count": (
                destination_count if mode == "apply" else source_count
            ),
            "reverted_field_count": (
                destination_count if mode == "revert" else 0
            ),
            "remaining_field_count": source_count,
            "divergent_field_count": inspection["divergent_field_count"],
            "unreadable_field_count": inspection["unreadable_field_count"],
            "checkpointed_field_count": inspection[
                "checkpointed_field_count"
            ],
            "written_before_checkpoint_field_count": inspection[
                "written_before_checkpoint_field_count"
            ],
            "resume_supported": resume_supported,
            "subset_revert_supported": (
                mode == "apply"
                and inspection["subset_compensation_supported"]
            ),
            "next_safe_actions": next_safe_actions,
            "automatic_retry_allowed": False,
            "operator_counting_required": False,
            "provider_called": False,
            "credential_values_read": False,
            "private_values_echoed": False,
            "paths_echoed": False,
            **index_truth,
        }
    try:
        index_entries = (
            _zettel_index_entries(plan)
            if index_lifecycle.mutation_active
            else ()
        )
        index_truth = index_lifecycle.finalize(index_entries)
    except Exception:
        index_truth = index_lifecycle.delta_failed()
    result = {
        "schema_version": RESULT_SCHEMA,
        "ok": core.get("status") == "completed",
        "state": "reverted" if mode == "revert" else "applied",
        "domain": plan.domain,
        "mode": mode,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "operation_manifest_sha256": manifest.manifest_sha256,
        "execution": core,
        "item_count": len(plan.specs),
        "field_count": sum(len(item.fields) for item in manifest.items),
        "written_field_count": core.get("written_field_count", 0),
        "resumed_field_count": core.get("resumed_field_count", 0),
        "field_scoped_revert_supported": True,
        "common_exact_operation_manifest_used": True,
        "independent_verification": True,
        "operator_counting_required": False,
        "provider_called": False,
        "credential_values_read": False,
        "private_values_echoed": False,
        "paths_echoed": False,
        **index_truth,
    }
    if index_truth["index_rebuild_required"]:
        result.update(
            {
                "ok": False,
                "state": (
                    "reverted_index_update_failed"
                    if mode == "revert"
                    else "applied_index_update_failed"
                ),
                "reason_codes": [archive_services.INDEX_REBUILD_REQUIRED],
                "blockers": [archive_services.INDEX_REBUILD_REQUIRED],
            }
        )
    return result


def _execute_core(
    plan: LocalRecoveryPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    mode: str,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    authority = _authority(plan, claim, context, mode=mode)
    manifest = _operation_manifest(plan, mode=mode)
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        index_lifecycle = ZettelIndexBatchLifecycle.inspect(
            plan.archive_root,
            has_zettel_targets=any(
                spec.target_kind == "zettel" for spec in plan.specs
            ),
            allow_dirty_resume=resume or mode == "revert",
            operation_owner_sha256=(
                archive_services.archive_manifest_mutation_owner_sha256(
                    operation="local_recovery",
                    operation_binding_sha256=plan.manifest.manifest_sha256,
                )
            ),
        )
        if index_lifecycle.precondition_blocked:
            return _index_precondition_blocked_result(
                plan,
                manifest,
                mode=mode,
                lifecycle=index_lifecycle,
            )
        # Revert may use an observed-post subset manifest that did not exist
        # until after the original interruption. Persist its exact private
        # values only after native approval, just like an initial apply.
        persist_local_recovery_control(plan)
        _resume_relative_path, execution_sha256 = _persist_resume_locator(
            plan,
            manifest,
            authority,
            mode=mode,
        )
        supersession = (
            _persist_subset_supersession_pending(
                plan,
                manifest,
                authority,
                execution_sha256,
            )
            if mode == "revert"
            else None
        )
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        result = _run_with_store(
            plan,
            authority,
            checkpoints,
            mode=mode,
            resume=resume,
            progress_hook=progress_hook,
            index_lifecycle=index_lifecycle,
        )
        if supersession is not None and result.get("ok") is True:
            parent, pending = supersession
            _persist_subset_supersession_final(parent, pending, result)
            result["superseded_parent_apply_execution"] = True
        return result


def execute_local_recovery(
    plan: LocalRecoveryPlan,
    *,
    mode: str = "apply",
    reviewer_claim: str = "person:local-recovery-operator",
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not LocalRecoveryPlan or not plan.approveable:
        raise _fail("local_recovery_plan_blocked")
    if mode == "revert" and not plan.loaded_from_control:
        raise _fail("local_recovery_control_invalid")
    manifest = _operation_manifest(plan, mode=mode)
    index_lifecycle = ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=any(
            spec.target_kind == "zettel" for spec in plan.specs
        ),
        allow_dirty_resume=mode == "revert",
        operation_owner_sha256=(
            archive_services.archive_manifest_mutation_owner_sha256(
                operation="local_recovery",
                operation_binding_sha256=plan.manifest.manifest_sha256,
            )
        ),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            manifest,
            mode=mode,
            lifecycle=index_lifecycle,
        )
    context = local_recovery_context(
        plan,
        mode=mode,
        reviewer_claim=reviewer_claim,
    )
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _execute_core(
            plan,
            claim,
            context,
            mode=mode,
            resume=False,
            progress_hook=progress_hook,
        ),
    )


def verify_local_recovery_state(
    plan: LocalRecoveryPlan,
    *,
    state: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if type(plan) is not LocalRecoveryPlan or state not in {"pre", "post"}:
        raise _fail("local_recovery_plan_invalid")
    if progress_hook is not None:
        progress_hook(
            ExactOperationProgress(
                plan.manifest.manifest_sha256,
                None,
                "apply",
                "preflight",
                0,
                len(plan.manifest.items),
                0,
                len(plan.manifest.items),
            )
        )
    return verify_exact_operation(
        plan.manifest,
        verifier=_Verifier(plan),
        state=state,
    )


def _locator_documents(
    plan: LocalRecoveryPlan,
    *,
    mode: str,
) -> list[dict[str, Any]]:
    root = archive_services.archive_internal_path(plan.archive_root, RESUME_ROOT)
    if not root.exists():
        return []
    prefix = plan.manifest.manifest_sha256.removeprefix("sha256:") + f".{mode}."
    documents: list[dict[str, Any]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        raise _fail("local_recovery_resume_invalid") from None
    for path in entries:
        if not path.name.startswith(prefix) or not path.name.endswith(".json"):
            continue
        try:
            raw, reason = archive_services._bounded_stable_regular_file_read(
                path,
                max_bytes=32 * 1024,
            )
            if raw is None or reason is not None:
                raise ValueError("unsafe")
            document = json.loads(raw.decode("ascii"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            raise _fail("local_recovery_resume_invalid") from None
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != RESUME_LOCATOR_SCHEMA
            or document.get("domain") != plan.domain
            or document.get("mode") != mode
            or document.get("apply_manifest_sha256")
            != plan.manifest.manifest_sha256
            or _APPROVAL_ID_RE.fullmatch(str(document.get("approval_id") or ""))
            is None
            or _SHA256_RE.fullmatch(str(document.get("execution_sha256") or ""))
            is None
            or document.get("private_values_echoed") is not False
            or document.get("paths_echoed") is not False
        ):
            raise _fail("local_recovery_resume_invalid")
        documents.append(document)
    return documents


def _safe_control_entries(root: Path) -> tuple[Path, ...]:
    controls_root = archive_services.archive_internal_path(root, CONTROL_ROOT)
    try:
        info = os.lstat(controls_root)
    except FileNotFoundError:
        return ()
    except OSError:
        raise _fail("local_recovery_control_invalid") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    ):
        raise _fail("local_recovery_control_invalid")
    try:
        entries = tuple(sorted(controls_root.iterdir(), key=lambda path: path.name))
    except OSError:
        raise _fail("local_recovery_control_invalid") from None
    if len(entries) > MAX_CONTROL_FILES:
        raise _fail("local_recovery_control_invalid")
    return entries


def _strict_resume_checkpoint_present(
    plan: LocalRecoveryPlan,
    locator: Mapping[str, Any],
    *,
    respect_supersession: bool = True,
) -> bool:
    execution = str(locator.get("execution_sha256") or "")
    if _SHA256_RE.fullmatch(execution) is None:
        raise _fail("local_recovery_resume_invalid")
    name = execution.removeprefix("sha256:")
    checkpoint = archive_services.archive_internal_path(
        plan.archive_root,
        f"{EXACT_OPERATION_LOCAL_ROOT}/checkpoints/{name}.jsonl",
    )
    raw, reason = archive_services._bounded_stable_regular_file_read(
        checkpoint,
        max_bytes=MAX_CONTROL_BYTES,
    )
    if reason == "missing":
        return False
    if raw is None or reason is not None or not raw or not raw.endswith(b"\n"):
        raise _fail("local_recovery_resume_invalid")
    try:
        rows = raw.splitlines()
        if not rows:
            raise ValueError("empty")
        for sequence, line in enumerate(rows):
            document = json.loads(line.decode("ascii"))
            if (
                not isinstance(document, dict)
                or _canonical_bytes(document) != line
                or document.get("schema") != CHECKPOINT_SCHEMA
                or document.get("execution_sha256") != execution
                or document.get("manifest_sha256")
                != locator.get("operation_manifest_sha256")
                or document.get("mode") != locator.get("mode")
                or document.get("sequence") != sequence
            ):
                raise ValueError("checkpoint")
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("local_recovery_resume_invalid") from None

    final_receipt = archive_services.archive_internal_path(
        plan.archive_root,
        f"{EXACT_OPERATION_RECEIPTS_ROOT}/{name}.json",
    )
    receipt_raw, receipt_reason = archive_services._bounded_stable_regular_file_read(
        final_receipt,
        max_bytes=MAX_CANONICAL_BYTES,
    )
    if receipt_reason == "missing":
        if respect_supersession and _validated_parent_supersession_records(
            plan,
            locator,
        ):
            return False
        return True
    if (
        receipt_raw is None
        or receipt_reason is not None
        or not receipt_raw.endswith(b"\n")
    ):
        raise _fail("local_recovery_resume_invalid")
    try:
        receipt = json.loads(receipt_raw[:-1].decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("local_recovery_resume_invalid") from None
    if (
        not isinstance(receipt, dict)
        or _canonical_line(receipt) != receipt_raw
        or receipt.get("schema") != FINAL_RECEIPT_SCHEMA
        or not isinstance(receipt.get("result"), dict)
        or receipt["result"].get("execution_sha256") != execution
    ):
        raise _fail("local_recovery_resume_invalid")
    return False


def discover_local_recovery_plan(
    archive_root: Path | str,
    *,
    allowed_domains: Iterable[str],
    mode: str,
    resume: bool = False,
) -> tuple[LocalRecoveryPlan | None, dict[str, Any]]:
    """Find one unambiguous recovery control without asking for a digest.

    Discovery is read-only and content-free.  A revert candidate must have at
    least one field in the exact recorded post-state and no divergent or
    unreadable fields.  A resume candidate must have exactly one durable,
    unfinished execution locator.  If evidence is absent, corrupt, or
    ambiguous, WOM stops instead of guessing.
    """

    root = archive_services.require_existing_archive_root(archive_root)
    domains = frozenset(allowed_domains)
    if (
        mode not in {"apply", "revert"}
        or type(resume) is not bool
        or (not resume and mode != "revert")
        or not domains
        or any(_DOMAIN_RE.fullmatch(value) is None for value in domains)
    ):
        raise _fail("local_recovery_control_invalid")

    candidates: list[LocalRecoveryPlan] = []
    already_complete: list[LocalRecoveryPlan] = []
    blocked_control_count = 0
    matching_control_count = 0
    scanned_control_count = 0
    for path in _safe_control_entries(root):
        scanned_control_count += 1
        match = re.fullmatch(r"([0-9a-f]{64})\.json", path.name)
        if match is None:
            raise _fail("local_recovery_control_invalid")
        try:
            plan = load_local_recovery_plan(
                root,
                manifest_sha256="sha256:" + match.group(1),
            )
        except LocalRecoveryError:
            raise _fail("local_recovery_control_invalid") from None
        if plan.domain not in domains:
            continue
        matching_control_count += 1
        if not resume and mode == "revert":
            try:
                subset, _inspection = build_observed_post_subset_revert_plan(plan)
            except LocalRecoveryError:
                blocked_control_count += 1
                continue
            if subset is None:
                already_complete.append(plan)
            else:
                candidates.append(plan)
            continue

        try:
            active = 0
            for locator in _locator_documents(plan, mode=mode):
                if _strict_resume_checkpoint_present(plan, locator):
                    active += 1
                    continue
                if (
                    mode == "revert"
                    and _completed_subset_supersession_pending(
                        plan,
                        str(locator.get("execution_sha256") or ""),
                    )
                    is not None
                ):
                    active += 1
        except LocalRecoveryError:
            blocked_control_count += 1
            continue
        if active == 1:
            candidates.append(plan)
        elif active > 1:
            blocked_control_count += 1

    selected: LocalRecoveryPlan | None = None
    state = "local_recovery_control_not_found"
    if blocked_control_count:
        state = "local_recovery_control_requires_review"
    elif len(candidates) == 1:
        selected = candidates[0]
        state = "local_recovery_control_selected"
    elif len(candidates) > 1:
        state = "local_recovery_control_ambiguous"
    elif not resume and mode == "revert" and len(already_complete) == 1:
        selected = already_complete[0]
        state = "local_recovery_control_selected_already_reverted"
    elif not resume and mode == "revert" and len(already_complete) > 1:
        state = "local_recovery_control_ambiguous"

    public = {
        "schema": "wom-kit/local-recovery-control-discovery/v1",
        "ok": selected is not None,
        "state": state,
        "mode": mode,
        "action": "resume" if resume else "revert",
        "auto_discovered": selected is not None,
        "scanned_control_count": scanned_control_count,
        "matching_control_count": matching_control_count,
        "candidate_count": len(candidates),
        "already_complete_control_count": len(already_complete),
        "blocked_control_count": blocked_control_count,
        "operator_counting_required": False,
        "private_values_echoed": False,
        "paths_echoed": False,
    }
    return selected, public


def resume_local_recovery(
    plan: LocalRecoveryPlan,
    *,
    mode: str = "apply",
    reviewer_claim: str = "person:local-recovery-operator",
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    if (
        type(plan) is not LocalRecoveryPlan
        or not plan.loaded_from_control
        or mode not in {"apply", "revert"}
    ):
        raise _fail("local_recovery_resume_invalid")
    context = local_recovery_context(
        plan,
        mode=mode,
        reviewer_claim=reviewer_claim,
    )
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        candidates: list[
            tuple[
                dict[str, Any],
                tuple[
                    LocalRecoveryPlan,
                    dict[str, Any],
                    dict[str, Any],
                ]
                | None,
            ]
        ] = []
        for document in _locator_documents(plan, mode=mode):
            if _strict_resume_checkpoint_present(plan, document):
                candidates.append((document, None))
                continue
            finalized = (
                _completed_subset_supersession_pending(
                    plan,
                    str(document.get("execution_sha256") or ""),
                )
                if mode == "revert"
                else None
            )
            if finalized is not None:
                candidates.append((document, finalized))
        if len(candidates) != 1:
            raise _fail("local_recovery_resume_invalid")
        locator, finalize_only = candidates[0]

        def guard(claim: _ClaimedExactHumanApproval) -> bool:
            authority = _authority(plan, claim, context, mode=mode)
            actual = exact_operation_execution_sha256(
                _operation_manifest(plan, mode=mode),
                mode=mode,
                selected_fields=(
                    tuple(
                        (item.item_id, item.fields[0].field_ref)
                        for item in plan.manifest.items
                    )
                    if mode == "revert"
                    else None
                ),
                approval_authority=authority,
            )
            if not (
                hmac.compare_digest(actual, locator["execution_sha256"])
                and checkpoints.resume_checkpoint_present(actual)
            ):
                return False
            if finalize_only is None:
                return True
            refreshed = _completed_subset_supersession_pending(
                plan,
                actual,
                authority=authority,
            )
            if refreshed is None:
                return False
            _parent, _pending, completed = refreshed
            inspection = inspect_exact_operation_state(
                _operation_manifest(plan, mode="revert"),
                verifier=_Verifier(plan),
                checkpoint_store=checkpoints,
                mode="revert",
                selected_fields=tuple(
                    (item.item_id, item.fields[0].field_ref)
                    for item in plan.manifest.items
                ),
                approval_authority=authority,
            )
            return bool(
                inspection.get("state") == "completed"
                and inspection.get("checkpoint_valid") is True
                and inspection.get("final_receipt_valid") is True
                and inspection.get("checkpoint_count")
                == completed["execution"].get("checkpoint_count")
                and inspection.get("checkpointed_field_count")
                == completed["execution"].get("field_count")
                and completed.get("ok") is True
            )

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            authority = _authority(plan, claim, context, mode=mode)
            if finalize_only is not None:
                refreshed = _completed_subset_supersession_pending(
                    plan,
                    locator["execution_sha256"],
                    authority=authority,
                )
                if refreshed is None:
                    raise _fail("local_recovery_resume_invalid")
                parent, pending_document, completed = refreshed
                _persist_subset_supersession_final(
                    parent,
                    pending_document,
                    completed,
                )
                completed["superseded_parent_apply_execution"] = True
                return completed
            pending = (
                _matching_subset_supersession_pending(
                    plan,
                    authority,
                    locator["execution_sha256"],
                )
                if mode == "revert"
                else None
            )
            resumed = _run_with_store(
                plan,
                authority,
                checkpoints,
                mode=mode,
                resume=True,
                progress_hook=progress_hook,
            )
            if pending is not None and resumed.get("ok") is True:
                parent, pending_document = pending
                _persist_subset_supersession_final(
                    parent,
                    pending_document,
                    resumed,
                )
                resumed["superseded_parent_apply_execution"] = True
            return resumed

        result = _resume_exact_human_approved_write_core(
            plan.archive_root,
            context,
            locator["approval_id"],
            guard,
            writer,
            key_provider=key_provider,
        )
        result["native_approval_redisplayed"] = False
        return result


__all__ = [
    "APPLY_OPERATION",
    "CONTROL_ROOT",
    "LEDGER_ROOT",
    "LocalRecoveryError",
    "LocalRecoveryFieldSpec",
    "LocalRecoveryPlan",
    "REVERT_OPERATION",
    "build_local_recovery_plan",
    "build_observed_post_subset_revert_plan",
    "combine_local_recovery_plans",
    "discover_local_recovery_plan",
    "execute_local_recovery",
    "load_local_recovery_plan",
    "local_recovery_context",
    "local_recovery_ledger_identity_sha256",
    "local_recovery_ledger_relative",
    "local_recovery_zettel_identity_sha256",
    "persist_local_recovery_control",
    "resume_local_recovery",
    "verify_local_recovery_state",
]
