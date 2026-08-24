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
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationEvidence,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    revert_exact_operation_fields,
    verify_exact_operation,
)
from .operation_approval_binding import (
    OperationApprovalBindingError,
    exact_operation_manifest_approval_binding,
)


APPLY_OPERATION = "local_recovery"
REVERT_OPERATION = "local_recovery_revert"
CONTROL_SCHEMA = "wom-kit/local-recovery-private-control/v0.1"
RESULT_SCHEMA = "wom-kit/local-recovery-execution-result/v0.1"
RESUME_LOCATOR_SCHEMA = "wom-kit/local-recovery-resume-locator/v0.1"
CONTROL_ROOT = "profiles/local/local-recovery/controls"
RESUME_ROOT = "profiles/local/local-recovery/resume"
LEDGER_ROOT = "profiles/local/local-recovery/ledgers"
MAX_CONTROL_BYTES = 128 * 1024 * 1024
MAX_LOCAL_FIELD_BYTES = 16 * 1024 * 1024
MAX_CANONICAL_BYTES = 16 * 1024 * 1024
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


def _marker_projection(body: str) -> bytes:
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
        return _marker_projection(body)
    raise ValueError("field")


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
    if current == source:
        return destination
    source_plain = source.replace(marker, "")
    destination_plain = destination.replace(marker, "")
    if source_plain != destination_plain:
        raise ValueError("marker templates")
    source_count = source.count(marker)
    destination_count = destination.count(marker)
    if source_count == destination_count:
        raise ValueError("marker count")
    result = current
    template = destination if destination_count > source_count else source
    plain = template.replace(marker, "")
    positions: list[int] = []
    consumed = 0
    for part in template.split(marker)[:-1]:
        consumed += len(part)
        positions.append(consumed)
    if destination_count > source_count:
        inserted = 0
        for position in positions:
            left = plain[max(0, position - 64) : position]
            right = plain[position : position + 64]
            needle = left + right
            matches = [m.start() for m in re.finditer(re.escape(needle), result)]
            if len(matches) != 1:
                raise ValueError("marker anchor")
            boundary = matches[0] + len(left)
            result = result[:boundary] + marker + result[boundary:]
            inserted += 1
        if inserted != destination_count - source_count:
            raise ValueError("marker insert")
    else:
        removed = 0
        for position in reversed(positions):
            left = plain[max(0, position - 64) : position]
            right = plain[position : position + 64]
            needle = left + marker + right
            matches = [m.start() for m in re.finditer(re.escape(needle), result)]
            if len(matches) != 1:
                raise ValueError("marker anchor")
            start = matches[0] + len(left)
            result = result[:start] + result[start + len(marker) :]
            removed += 1
        if removed != source_count - destination_count:
            raise ValueError("marker remove")
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


def _run_with_store(
    plan: LocalRecoveryPlan,
    authority: ExactOperationApprovalAuthority,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    mode: str,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    manifest = _operation_manifest(plan, mode=mode)
    payloads = _Payloads(plan.specs)
    writer = _Writer(plan)
    verifier = _Verifier(plan)
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
            selected_fields=tuple(
                (item.item_id, item.fields[0].field_ref)
                for item in manifest.items
            ),
            payloads=payloads,
            writer=writer,
            verifier=verifier,
            checkpoint_store=checkpoints,
            approval_authority=authority,
            resume=resume,
            progress_hook=progress_hook,
        )
    return {
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
    }


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
        if mode == "apply":
            persist_local_recovery_control(plan)
        _persist_resume_locator(
            plan,
            manifest,
            authority,
            mode=mode,
        )
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root,
            writer_lock=writer_lock,
        )
        return _run_with_store(
            plan,
            authority,
            checkpoints,
            mode=mode,
            resume=resume,
            progress_hook=progress_hook,
        )


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
        candidates: list[dict[str, Any]] = []
        for document in _locator_documents(plan, mode=mode):
            execution = document["execution_sha256"]
            if (
                checkpoints.resume_checkpoint_present(execution)
                and checkpoints.load_final_receipt(execution) is None
            ):
                candidates.append(document)
        if len(candidates) != 1:
            raise _fail("local_recovery_resume_invalid")
        locator = candidates[0]

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
            return bool(
                hmac.compare_digest(actual, locator["execution_sha256"])
                and checkpoints.resume_checkpoint_present(actual)
            )

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            authority = _authority(plan, claim, context, mode=mode)
            return _run_with_store(
                plan,
                authority,
                checkpoints,
                mode=mode,
                resume=True,
                progress_hook=progress_hook,
            )

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
    "combine_local_recovery_plans",
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
