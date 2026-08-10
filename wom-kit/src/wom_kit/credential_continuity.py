"""Content-free credential rediscovery, adoption, and broker primitives.

This module deliberately has no CLI registration and performs no real password
manager, operating-system credential, or provider call.  Store access is
available only through injected exact-match adapters.  The split is important:

* AI-visible discovery and receipts contain safe labels, counts, and reason
  codes only.
* exact refs, vault paths, and entry locators live only in the ignored local
  binding file.
* secret values exist only for the duration of an injected trusted-consumer
  callback and are rejected if that callback tries to return them.

All raised errors contain a stable reason code and no underlying exception
text, path, locator, stderr, or secret value.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:  # Keep normalization aligned with the project-pinned Unicode database.
    import unicodedata2 as unicodedata
except ImportError:  # pragma: no cover - packaging declares unicodedata2.
    import unicodedata


LOCAL_CATALOG_RELATIVE = "profiles/local/credential-refs.local.yml"
LOCAL_BINDINGS_RELATIVE = "profiles/local/credential-bindings.local.json"
LOCAL_LOCK_RELATIVE = "profiles/local/.credential-continuity.lock"
ADOPTION_RECEIPTS_RELATIVE = "receipts/credentials/adoptions"
USE_RECEIPTS_RELATIVE = "receipts/credentials/uses"

CATALOG_VERSION = "wom-local-credential-ref-inventory/v0.1"
BINDINGS_SCHEMA_VERSION = "wom-local-credential-bindings/v0.2"
ADOPTION_RECEIPT_SCHEMA_VERSION = "wom-credential-adoption/v0.2"
USE_RECEIPT_SCHEMA_VERSION = "wom-credential-use/v0.1"

MAX_LOCAL_DOCUMENT_BYTES = 4 * 1024 * 1024
SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SAFE_METADATA_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PUBLIC_FINGERPRINT_RE = re.compile(r"^fingerprint:[A-Za-z0-9][A-Za-z0-9_.:-]{7,118}$")
SUPPORTED_ADAPTERS = {"keepassxc_cli", "windows_credential_manager"}
STORE_VERIFICATION_MODES = {"exact_probe", "stored"}
ROTATION_STATUSES = {"unknown", "current", "rotation_due", "rotated", "revoked"}
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


class CredentialContinuityError(RuntimeError):
    """A content-free credential-continuity failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> CredentialContinuityError:
    return CredentialContinuityError(code)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise _fail("credential_public_result_invalid") from None


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
    )


def _validated_archive_root(archive_root: Path | str) -> Path:
    supplied = Path(archive_root)
    if not supplied.is_absolute():
        supplied = Path(os.path.abspath(str(supplied)))
    try:
        information = os.lstat(supplied)
        if _is_reparse(information) or not stat.S_ISDIR(information.st_mode):
            raise _fail("credential_archive_root_unsafe")
        return supplied.resolve(strict=True)
    except CredentialContinuityError:
        raise
    except OSError:
        raise _fail("credential_archive_root_unavailable") from None


def _archive_path(root: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _fail("credential_internal_path_invalid")
    candidate = root.joinpath(*parts)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise _fail("credential_internal_path_invalid") from None
    return candidate


def _ensure_safe_existing_path(path: Path, *, expected_file: bool = True) -> None:
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        raise _fail("credential_local_document_missing") from None
    except OSError:
        raise _fail("credential_local_document_unavailable") from None
    if _is_reparse(information):
        raise _fail("credential_local_document_unsafe")
    if expected_file and not stat.S_ISREG(information.st_mode):
        raise _fail("credential_local_document_unsafe")


def _ensure_safe_parent_chain(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail("credential_internal_path_invalid") from None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if not current.exists():
            continue
        try:
            information = os.lstat(current)
        except OSError:
            raise _fail("credential_local_parent_unavailable") from None
        if _is_reparse(information) or not stat.S_ISDIR(information.st_mode):
            raise _fail("credential_local_parent_unsafe")
    if path.exists() or path.is_symlink():
        _ensure_safe_existing_path(path)


def _read_small_bytes(path: Path) -> bytes:
    _ensure_safe_existing_path(path)
    try:
        size = path.stat().st_size
        if size < 0 or size > MAX_LOCAL_DOCUMENT_BYTES:
            raise _fail("credential_local_document_too_large")
        return path.read_bytes()
    except CredentialContinuityError:
        raise
    except OSError:
        raise _fail("credential_local_document_unavailable") from None


def _read_archive_id(root: Path) -> str:
    path = _archive_path(root, "archive.yml")
    if not path.is_file():
        return "archive:local"
    try:
        document = yaml.safe_load(_read_small_bytes(path).decode("utf-8"))
    except CredentialContinuityError:
        raise
    except (UnicodeError, yaml.YAMLError):
        raise _fail("credential_archive_identity_invalid") from None
    if not isinstance(document, Mapping):
        raise _fail("credential_archive_identity_invalid")
    archive_id = str(document.get("archive_id") or "archive:local").strip()
    if SAFE_LABEL_RE.fullmatch(archive_id) is None:
        raise _fail("credential_archive_identity_invalid")
    return archive_id


def _safe_label(value: Any, code: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip()
    if not text and optional:
        return None
    if SAFE_LABEL_RE.fullmatch(text) is None or "@" in text:
        raise _fail(code)
    return text


def _safe_metadata(value: Any, code: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if SAFE_METADATA_RE.fullmatch(text) is None:
        raise _fail(code)
    return text


def _safe_private_text(value: Any, code: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip()
    if not text and optional:
        return None
    if not text or len(text) > 1024 or any(unicodedata.category(char).startswith("C") for char in text):
        raise _fail(code)
    return unicodedata.normalize("NFC", text)


def _parse_legacy_secret_ref(value: Any) -> tuple[str, str]:
    text = _safe_private_text(value, "credential_catalog_row_invalid")
    assert text is not None
    prefix, separator, locator = text.partition(":")
    if not separator or prefix.lower() != "secret":
        raise _fail("credential_catalog_row_invalid")
    normalized_locator = _safe_private_text(locator, "credential_catalog_row_invalid")
    assert normalized_locator is not None
    if len(normalized_locator) > 512:
        raise _fail("credential_catalog_row_invalid")
    return f"secret:{normalized_locator}", normalized_locator


def _optional_row_label(item: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in item and item.get(key) is not None:
            return _safe_label(item.get(key), "credential_catalog_row_invalid", optional=True)
    return None


@dataclass(frozen=True)
class CredentialCandidate:
    """One exact catalog row with private locator fields hidden from repr."""

    candidate_id: str
    credential_id: str
    credential_kind: str
    provider: str
    purpose: str
    account_label: str | None
    workspace_label: str | None
    suggested_adapter_kind: str
    presence: str = "not_checked"
    _archive_root: Path = field(repr=False, compare=False, default=Path("."))
    _catalog_path: Path = field(repr=False, compare=False, default=Path("."))
    _catalog_sha256: str = field(repr=False, compare=False, default="")
    _exact_ref: str = field(repr=False, compare=False, default="")
    _entry_locator: str = field(repr=False, compare=False, default="")

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "credential_id": self.credential_id,
            "credential_kind": self.credential_kind,
            "provider": self.provider,
            "purpose": self.purpose,
            "account_label": self.account_label,
            "workspace_label": self.workspace_label,
            "suggested_adapter_kind": self.suggested_adapter_kind,
            "presence": "not_checked",
            "exact_ref_echoed": False,
            "entry_locator_echoed": False,
        }


@dataclass(frozen=True)
class CredentialDiscoveryReport:
    archive_id: str
    status: str
    candidates: tuple[CredentialCandidate, ...]
    ignored_row_count: int
    catalog_present: bool
    reason_code: str

    def to_public_dict(self) -> dict[str, Any]:
        ok = self.status not in {"blocked"}
        return {
            "ok": ok,
            "dry_run": True,
            "lifecycle_action": "credential_continuity_discovery",
            "reason_code": self.reason_code,
            "archive_id": self.archive_id,
            "status": self.status,
            "catalog_path": LOCAL_CATALOG_RELATIVE,
            "catalog_present": self.catalog_present,
            "candidate_count": len(self.candidates),
            "ignored_row_count": self.ignored_row_count,
            "candidates": [candidate.to_public_dict() for candidate in self.candidates],
            "presence": "not_checked",
            "closed_actions": {
                "credential_store_opened": False,
                "secret_value_read": False,
                "provider_api_called": False,
                "files_written": False,
            },
            "privacy_guards": {
                "exact_refs_echoed": False,
                "entry_locators_echoed": False,
                "vault_paths_echoed": False,
                "secret_values_echoed": False,
            },
            "would_change": [],
        }

    def require_candidate(self, candidate_id: str) -> CredentialCandidate:
        if SAFE_LABEL_RE.fullmatch(str(candidate_id or "")) is None:
            raise _fail("credential_candidate_not_found")
        matches = [candidate for candidate in self.candidates if candidate.candidate_id == candidate_id]
        if len(matches) != 1:
            raise _fail("credential_candidate_not_found")
        return matches[0]


def discover_local_credential_candidates(
    archive_root: Path | str,
) -> CredentialDiscoveryReport:
    """Read legacy ``secret:`` rows without opening a credential store.

    Invalid rows are counted and skipped.  They never make another exact row
    unusable and no row value is returned in an error or public result.
    """

    root = _validated_archive_root(archive_root)
    archive_id = _read_archive_id(root)
    catalog_path = _archive_path(root, LOCAL_CATALOG_RELATIVE)
    if not catalog_path.exists() and not catalog_path.is_symlink():
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="catalog_absent",
            candidates=(),
            ignored_row_count=0,
            catalog_present=False,
            reason_code="credential_catalog_absent",
        )

    try:
        raw = _read_small_bytes(catalog_path)
        document = yaml.safe_load(raw.decode("utf-8"))
    except CredentialContinuityError:
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="blocked",
            candidates=(),
            ignored_row_count=0,
            catalog_present=True,
            reason_code="credential_catalog_unsafe",
        )
    except (UnicodeError, yaml.YAMLError):
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="blocked",
            candidates=(),
            ignored_row_count=0,
            catalog_present=True,
            reason_code="credential_catalog_invalid",
        )

    if not isinstance(document, Mapping):
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="blocked",
            candidates=(),
            ignored_row_count=0,
            catalog_present=True,
            reason_code="credential_catalog_invalid",
        )
    version = document.get("version")
    if version not in {None, CATALOG_VERSION}:
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="blocked",
            candidates=(),
            ignored_row_count=0,
            catalog_present=True,
            reason_code="credential_catalog_version_unsupported",
        )
    rows = document.get("credentials")
    if not isinstance(rows, list):
        return CredentialDiscoveryReport(
            archive_id=archive_id,
            status="blocked",
            candidates=(),
            ignored_row_count=0,
            catalog_present=True,
            reason_code="credential_catalog_invalid",
        )

    catalog_sha256 = _sha256_bytes(raw)
    candidates: list[CredentialCandidate] = []
    ignored = 0
    issued_ids: set[str] = set()
    for row in rows:
        try:
            if not isinstance(row, Mapping):
                raise _fail("credential_catalog_row_invalid")
            exact_ref, locator = _parse_legacy_secret_ref(row.get("credential_ref", row.get("ref")))
            credential_id = _safe_label(
                row.get("credential_id", row.get("id")),
                "credential_catalog_row_invalid",
            )
            assert credential_id is not None
            credential_kind = _safe_metadata(
                row.get("credential_kind", row.get("kind")),
                "credential_catalog_row_invalid",
            )
            provider = _safe_metadata(row.get("provider"), "credential_catalog_row_invalid")
            purpose = _safe_metadata(row.get("purpose"), "credential_catalog_row_invalid")
            account_label = _optional_row_label(row, "account_label", "account_ref")
            workspace_label = _optional_row_label(row, "workspace_label", "workspace_ref")
            adapter_kind = str(row.get("adapter_kind") or "keepassxc_cli").strip().lower().replace("-", "_")
            if adapter_kind not in SUPPORTED_ADAPTERS:
                raise _fail("credential_catalog_row_invalid")
            candidate_id = "candidate:" + secrets.token_hex(12)
            while candidate_id in issued_ids:  # pragma: no cover - cryptographic collision guard.
                candidate_id = "candidate:" + secrets.token_hex(12)
            issued_ids.add(candidate_id)
            candidates.append(
                CredentialCandidate(
                    candidate_id=candidate_id,
                    credential_id=credential_id,
                    credential_kind=credential_kind,
                    provider=provider,
                    purpose=purpose,
                    account_label=account_label,
                    workspace_label=workspace_label,
                    suggested_adapter_kind=adapter_kind,
                    _archive_root=root,
                    _catalog_path=catalog_path,
                    _catalog_sha256=catalog_sha256,
                    _exact_ref=exact_ref,
                    _entry_locator=locator,
                )
            )
        except CredentialContinuityError:
            ignored += 1

    status = "ready_with_ignored_rows" if ignored else "ready"
    reason = "credential_candidates_ready_with_ignored_rows" if ignored else "credential_candidates_ready"
    return CredentialDiscoveryReport(
        archive_id=archive_id,
        status=status,
        candidates=tuple(candidates),
        ignored_row_count=ignored,
        catalog_present=True,
        reason_code=reason,
    )


@dataclass(frozen=True)
class CredentialAdoptionPlan:
    archive_id: str
    binding_id: str
    binding_revision: int
    credential_id: str
    credential_kind: str
    provider: str
    purpose: str
    account_label: str | None
    workspace_label: str | None
    adapter_kind: str
    candidate_id: str
    presence: str
    created_at: str
    _archive_root: Path = field(repr=False, compare=False)
    _catalog_path: Path = field(repr=False, compare=False)
    _catalog_sha256: str = field(repr=False, compare=False)
    _exact_ref: str = field(repr=False, compare=False)
    _entry_locator: str = field(repr=False, compare=False)
    _vault_path: str | None = field(repr=False, compare=False)
    _plan_nonce: bytes = field(repr=False, compare=False)

    @property
    def plan_digest(self) -> str:
        return _credential_adoption_plan_digest(self)

    @property
    def receipt_path(self) -> str:
        identity = _sha256_bytes(f"{self.binding_id}:{self.binding_revision}".encode("utf-8"))[:24]
        return f"{ADOPTION_RECEIPTS_RELATIVE}/credential-adoption-{identity}.json"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "dry_run": True,
            "persisted": False,
            "lifecycle_action": "credential_continuity_adoption_plan",
            "reason_code": "credential_adoption_verification_required",
            "archive_id": self.archive_id,
            "candidate_id": self.candidate_id,
            "proposed_binding_id": self.binding_id,
            "proposed_binding_revision": self.binding_revision,
            "proposed_credential": {
                "credential_id": self.credential_id,
                "credential_kind": self.credential_kind,
                "provider": self.provider,
                "purpose": self.purpose,
                "account_label": self.account_label,
                "workspace_label": self.workspace_label,
                "adapter_kind": self.adapter_kind,
                "presence": "not_checked",
                "confirmed": False,
            },
            "plan_digest": self.plan_digest,
            "proposed_binding_path": LOCAL_BINDINGS_RELATIVE,
            "proposed_receipt_path": self.receipt_path,
            "approval_requirements": {
                "exact_store_verification": True,
                "provider_account_workspace_verification": True,
                "both_digest_bound_to_plan": True,
            },
            "privacy_guards": {
                "exact_ref_echoed": False,
                "entry_locator_echoed": False,
                "vault_path_echoed": False,
                "secret_value_read": False,
            },
            "would_change_if_verified": [LOCAL_BINDINGS_RELATIVE, self.receipt_path],
            "would_change": [],
        }


def _credential_adoption_plan_digest(plan: CredentialAdoptionPlan) -> str:
    private_bound_payload = {
        "schema": ADOPTION_RECEIPT_SCHEMA_VERSION,
        "archive_id": plan.archive_id,
        "binding_id": plan.binding_id,
        "binding_revision": plan.binding_revision,
        "credential_id": plan.credential_id,
        "credential_kind": plan.credential_kind,
        "provider": plan.provider,
        "purpose": plan.purpose,
        "account_label": plan.account_label,
        "workspace_label": plan.workspace_label,
        "adapter_kind": plan.adapter_kind,
        "candidate_id": plan.candidate_id,
        "presence": plan.presence,
        "catalog_sha256": plan._catalog_sha256,
        "exact_ref": plan._exact_ref,
        "entry_locator": plan._entry_locator,
        "vault_path": plan._vault_path,
        "nonce": plan._plan_nonce.hex(),
    }
    return _sha256_bytes(_canonical_json(private_bound_payload).encode("utf-8"))


def plan_credential_adoption(
    archive_root: Path | str,
    candidate: CredentialCandidate,
    *,
    adapter_kind: str | None = None,
    account_label: str | None = None,
    workspace_label: str | None = None,
    vault_path: str | Path | None = None,
    binding_id_factory: Callable[[], str] | None = None,
) -> CredentialAdoptionPlan:
    """Bind one in-memory exact candidate into a drift-detecting dry-run plan."""

    root = _validated_archive_root(archive_root)
    if root != candidate._archive_root:
        raise _fail("credential_candidate_archive_mismatch")
    resolved_adapter = str(adapter_kind or candidate.suggested_adapter_kind).strip().lower().replace("-", "_")
    if resolved_adapter not in SUPPORTED_ADAPTERS:
        raise _fail("credential_adapter_kind_unsupported")
    resolved_account = _safe_label(
        account_label if account_label is not None else candidate.account_label,
        "credential_account_label_invalid",
        optional=True,
    )
    resolved_workspace = _safe_label(
        workspace_label if workspace_label is not None else candidate.workspace_label,
        "credential_workspace_label_invalid",
        optional=True,
    )
    resolved_vault = _safe_private_text(vault_path, "credential_vault_path_invalid", optional=True)
    if resolved_adapter == "keepassxc_cli" and not resolved_vault:
        raise _fail("credential_vault_path_required")
    factory = binding_id_factory or (lambda: "binding:" + secrets.token_hex(16))
    try:
        binding_id = str(factory() or "").strip()
    except Exception:
        raise _fail("credential_binding_id_invalid") from None
    if SAFE_LABEL_RE.fullmatch(binding_id) is None:
        raise _fail("credential_binding_id_invalid")
    return CredentialAdoptionPlan(
        archive_id=_read_archive_id(root),
        binding_id=binding_id,
        binding_revision=1,
        credential_id=candidate.credential_id,
        credential_kind=candidate.credential_kind,
        provider=candidate.provider,
        purpose=candidate.purpose,
        account_label=resolved_account,
        workspace_label=resolved_workspace,
        adapter_kind=resolved_adapter,
        candidate_id=candidate.candidate_id,
        presence="not_checked",
        created_at=_utc_now(),
        _archive_root=root,
        _catalog_path=candidate._catalog_path,
        _catalog_sha256=candidate._catalog_sha256,
        _exact_ref=candidate._exact_ref,
        _entry_locator=candidate._entry_locator,
        _vault_path=resolved_vault,
        _plan_nonce=secrets.token_bytes(32),
    )


@dataclass(frozen=True)
class CredentialStoreVerificationEvidence:
    """Non-secret proof that the plan's exact store locator was found."""

    evidence_id: str
    plan_digest: str
    binding_id: str
    binding_revision: int
    candidate_id: str
    adapter_kind: str
    verification_mode: str
    presence: str
    verified_at: str
    _evidence_digest: str = field(repr=False, compare=False)

    @property
    def evidence_digest(self) -> str:
        return self._evidence_digest

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "reason_code": "credential_store_presence_verified",
            "evidence_id": self.evidence_id,
            "evidence_digest": self.evidence_digest,
            "plan_digest": self.plan_digest,
            "adapter_kind": self.adapter_kind,
            "verification_mode": self.verification_mode,
            "presence": "exact_match",
            "verified_at": self.verified_at,
            "privacy_guards": {
                "exact_ref_echoed": False,
                "entry_locator_echoed": False,
                "vault_path_echoed": False,
                "secret_value_read": False,
            },
        }


@dataclass(frozen=True)
class CredentialProviderVerificationEvidence:
    """Non-secret proof of the provider/account/workspace identity tuple."""

    evidence_id: str
    plan_digest: str
    binding_id: str
    binding_revision: int
    candidate_id: str
    verifier_id: str
    provider: str
    account_label: str | None
    workspace_label: str | None
    credential_fingerprint: str | None
    rotation_status: str
    default_selection: bool | None
    verified_at: str
    _evidence_digest: str = field(repr=False, compare=False)

    @property
    def evidence_digest(self) -> str:
        return self._evidence_digest

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "reason_code": "credential_provider_identity_verified",
            "evidence_id": self.evidence_id,
            "evidence_digest": self.evidence_digest,
            "plan_digest": self.plan_digest,
            "verifier_id": self.verifier_id,
            "provider": self.provider,
            "account_label": self.account_label,
            "workspace_label": self.workspace_label,
            "credential_fingerprint": self.credential_fingerprint,
            "rotation_status": self.rotation_status,
            "default_selection": self.default_selection,
            "verified_at": self.verified_at,
            "secret_value_read": False,
        }


def _adoption_evidence_digest(
    plan: CredentialAdoptionPlan,
    evidence_kind: str,
    public_payload: Mapping[str, Any],
) -> str:
    bound_payload = {
        "evidence_kind": evidence_kind,
        "plan_digest": plan.plan_digest,
        "private_reference": {
            "adapter_kind": plan.adapter_kind,
            "exact_ref": plan._exact_ref,
            "entry_locator": plan._entry_locator,
            "vault_path": plan._vault_path,
        },
        "evidence": dict(public_payload),
    }
    return hmac.new(
        plan._plan_nonce,
        _canonical_json(bound_payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _store_evidence_payload(evidence: CredentialStoreVerificationEvidence) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "plan_digest": evidence.plan_digest,
        "binding_id": evidence.binding_id,
        "binding_revision": evidence.binding_revision,
        "candidate_id": evidence.candidate_id,
        "adapter_kind": evidence.adapter_kind,
        "verification_mode": evidence.verification_mode,
        "presence": evidence.presence,
        "verified_at": evidence.verified_at,
    }


def _provider_evidence_payload(evidence: CredentialProviderVerificationEvidence) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "plan_digest": evidence.plan_digest,
        "binding_id": evidence.binding_id,
        "binding_revision": evidence.binding_revision,
        "candidate_id": evidence.candidate_id,
        "verifier_id": evidence.verifier_id,
        "provider": evidence.provider,
        "account_label": evidence.account_label,
        "workspace_label": evidence.workspace_label,
        "credential_fingerprint": evidence.credential_fingerprint,
        "rotation_status": evidence.rotation_status,
        "default_selection": evidence.default_selection,
        "verified_at": evidence.verified_at,
    }


def verify_credential_store_for_adoption(
    plan: CredentialAdoptionPlan,
    *,
    adapter: Any,
    verification_mode: str = "exact_probe",
) -> CredentialStoreVerificationEvidence:
    """Issue plan-bound evidence from one injected exact-only store probe.

    The adapter receives the private locator in memory.  Its returned payload is
    treated as untrusted: only an exact-match boolean is consumed, and all
    other values (including accidental stdout or secret material) are ignored.
    """

    mode = _safe_metadata(verification_mode, "credential_store_verification_mode_invalid")
    if mode not in STORE_VERIFICATION_MODES:
        raise _fail("credential_store_verification_mode_invalid")
    probe = getattr(adapter, "probe_exact", None)
    if not callable(probe):
        raise _fail("credential_store_verifier_invalid")
    private_binding = {
        "adapter_kind": plan.adapter_kind,
        "exact_ref": plan._exact_ref,
        "entry_locator": plan._entry_locator,
        "vault_path": plan._vault_path,
    }
    try:
        raw_result = probe(private_binding)
    except Exception:
        raise _fail("credential_store_verification_failed") from None
    if not isinstance(raw_result, Mapping):
        raise _fail("credential_store_verification_failed")
    if raw_result.get("ok") is not True or raw_result.get("presence") != "exact_match":
        raise _fail("credential_store_presence_not_verified")
    if raw_result.get("adapter_kind") != plan.adapter_kind:
        raise _fail("credential_store_verification_evidence_invalid")

    issued_at = _utc_now()
    provisional = CredentialStoreVerificationEvidence(
        evidence_id="store-evidence:" + secrets.token_hex(16),
        plan_digest=plan.plan_digest,
        binding_id=plan.binding_id,
        binding_revision=plan.binding_revision,
        candidate_id=plan.candidate_id,
        adapter_kind=plan.adapter_kind,
        verification_mode=mode,
        presence="exact_match",
        verified_at=issued_at,
        _evidence_digest="",
    )
    return CredentialStoreVerificationEvidence(
        **{
            **provisional.__dict__,
            "_evidence_digest": _adoption_evidence_digest(
                plan,
                "credential_store",
                _store_evidence_payload(provisional),
            ),
        }
    )


def verify_credential_provider_for_adoption(
    plan: CredentialAdoptionPlan,
    *,
    verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    verifier_id: str,
) -> CredentialProviderVerificationEvidence:
    """Issue plan-bound evidence from an injected provider identity verifier."""

    resolved_verifier = _safe_label(verifier_id, "credential_provider_verifier_invalid")
    assert resolved_verifier is not None
    context = {
        "plan_digest": plan.plan_digest,
        "candidate_id": plan.candidate_id,
        "provider": plan.provider,
        "account_label": plan.account_label,
        "workspace_label": plan.workspace_label,
        "secret_value_included": False,
    }
    try:
        raw_result = verifier(context)
    except Exception:
        raise _fail("credential_provider_verification_failed") from None
    if not isinstance(raw_result, Mapping) or raw_result.get("verified") is not True:
        raise _fail("credential_provider_identity_not_verified")
    for key, expected in (
        ("provider", plan.provider),
        ("account_label", plan.account_label),
        ("workspace_label", plan.workspace_label),
    ):
        if key not in raw_result or raw_result.get(key) != expected:
            raise _fail("credential_provider_identity_not_verified")

    fingerprint_value = raw_result.get("credential_fingerprint")
    if fingerprint_value is None:
        fingerprint = None
    else:
        fingerprint = str(fingerprint_value).strip()
        if PUBLIC_FINGERPRINT_RE.fullmatch(fingerprint) is None:
            raise _fail("credential_provider_fingerprint_invalid")
    rotation_status = _safe_metadata(
        raw_result.get("rotation_status", "unknown"),
        "credential_rotation_status_invalid",
    )
    if rotation_status not in ROTATION_STATUSES:
        raise _fail("credential_rotation_status_invalid")
    default_selection = raw_result.get("default_selection")
    if default_selection is not None and not isinstance(default_selection, bool):
        raise _fail("credential_default_selection_invalid")

    issued_at = _utc_now()
    provisional = CredentialProviderVerificationEvidence(
        evidence_id="provider-evidence:" + secrets.token_hex(16),
        plan_digest=plan.plan_digest,
        binding_id=plan.binding_id,
        binding_revision=plan.binding_revision,
        candidate_id=plan.candidate_id,
        verifier_id=resolved_verifier,
        provider=plan.provider,
        account_label=plan.account_label,
        workspace_label=plan.workspace_label,
        credential_fingerprint=fingerprint,
        rotation_status=rotation_status,
        default_selection=default_selection,
        verified_at=issued_at,
        _evidence_digest="",
    )
    return CredentialProviderVerificationEvidence(
        **{
            **provisional.__dict__,
            "_evidence_digest": _adoption_evidence_digest(
                plan,
                "credential_provider",
                _provider_evidence_payload(provisional),
            ),
        }
    )


def _validate_store_evidence(
    plan: CredentialAdoptionPlan,
    evidence: CredentialStoreVerificationEvidence,
) -> None:
    if not isinstance(evidence, CredentialStoreVerificationEvidence):
        raise _fail("credential_store_verification_evidence_invalid")
    expected = _adoption_evidence_digest(plan, "credential_store", _store_evidence_payload(evidence))
    if not hmac.compare_digest(evidence.evidence_digest, expected):
        raise _fail("credential_store_verification_evidence_invalid")
    if (
        evidence.plan_digest != plan.plan_digest
        or evidence.binding_id != plan.binding_id
        or evidence.binding_revision != plan.binding_revision
        or evidence.candidate_id != plan.candidate_id
        or evidence.adapter_kind != plan.adapter_kind
        or evidence.verification_mode not in STORE_VERIFICATION_MODES
        or evidence.presence != "exact_match"
    ):
        raise _fail("credential_store_verification_evidence_invalid")


def _validate_provider_evidence(
    plan: CredentialAdoptionPlan,
    evidence: CredentialProviderVerificationEvidence,
) -> None:
    if not isinstance(evidence, CredentialProviderVerificationEvidence):
        raise _fail("credential_provider_verification_evidence_invalid")
    expected = _adoption_evidence_digest(plan, "credential_provider", _provider_evidence_payload(evidence))
    if not hmac.compare_digest(evidence.evidence_digest, expected):
        raise _fail("credential_provider_verification_evidence_invalid")
    if (
        evidence.plan_digest != plan.plan_digest
        or evidence.binding_id != plan.binding_id
        or evidence.binding_revision != plan.binding_revision
        or evidence.candidate_id != plan.candidate_id
        or evidence.provider != plan.provider
        or evidence.account_label != plan.account_label
        or evidence.workspace_label != plan.workspace_label
    ):
        raise _fail("credential_provider_verification_evidence_invalid")


class _InterprocessLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None

    def __enter__(self) -> "_InterprocessLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._handle = self.path.open("a+b")
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                self._handle.write(b"\0")
                self._handle.flush()
                os.fsync(self._handle.fileno())
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
            else:  # pragma: no cover - Windows is the primary supported host.
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
            return self
        except Exception:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            raise _fail("credential_local_lock_failed") from None

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - Windows is the primary supported host.
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        finally:
            self._handle.close()
            self._handle = None


_ADOPTION_THREAD_LOCKS: dict[str, threading.RLock] = {}
_ADOPTION_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(root: Path) -> threading.RLock:
    key = os.path.normcase(str(root))
    with _ADOPTION_THREAD_LOCKS_GUARD:
        return _ADOPTION_THREAD_LOCKS.setdefault(key, threading.RLock())


def _ensure_local_profile_ignored(root: Path) -> None:
    path = _archive_path(root, ".gitignore")
    if not path.is_file():
        raise _fail("credential_local_profile_not_ignored")
    try:
        lines = _read_small_bytes(path).decode("utf-8").splitlines()
    except UnicodeError:
        raise _fail("credential_local_profile_not_ignored") from None
    normalized = {line.strip().replace("\\", "/") for line in lines if line.strip() and not line.lstrip().startswith("#")}
    if "profiles/local/" not in normalized and "/profiles/local/" not in normalized:
        raise _fail("credential_local_profile_not_ignored")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except (OSError, ValueError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / (path.name + ".part-" + secrets.token_hex(8))
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except CredentialContinuityError:
        raise
    except Exception:
        raise _fail("credential_atomic_write_failed") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _write_json_exclusive(path: Path, payload: Mapping[str, Any], *, exists_code: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError:
        raise _fail(exists_code) from None
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise _fail("credential_exclusive_write_failed") from None


def _empty_bindings_document(archive_id: str) -> dict[str, Any]:
    return {
        "schema_version": BINDINGS_SCHEMA_VERSION,
        "archive_id": archive_id,
        "bindings": [],
    }


def _load_bindings_document(root: Path, archive_id: str) -> dict[str, Any]:
    path = _archive_path(root, LOCAL_BINDINGS_RELATIVE)
    if not path.exists() and not path.is_symlink():
        return _empty_bindings_document(archive_id)
    try:
        document = json.loads(_read_small_bytes(path).decode("utf-8"))
    except CredentialContinuityError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("credential_bindings_invalid") from None
    if not isinstance(document, dict):
        raise _fail("credential_bindings_invalid")
    if document.get("schema_version") != BINDINGS_SCHEMA_VERSION:
        raise _fail("credential_bindings_version_unsupported")
    if document.get("archive_id") != archive_id or not isinstance(document.get("bindings"), list):
        raise _fail("credential_bindings_invalid")
    if not all(isinstance(item, dict) for item in document["bindings"]):
        raise _fail("credential_bindings_invalid")
    return document


def _binding_private_identity(binding: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        binding.get("adapter_kind"),
        binding.get("exact_ref"),
        binding.get("entry_locator"),
        binding.get("vault_path"),
    )


def _binding_exact_candidate_identity(binding: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        binding.get("adapter_kind"),
        binding.get("exact_ref"),
        binding.get("entry_locator"),
    )


def _binding_logical_identity(binding: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        binding.get("credential_id"),
        binding.get("credential_kind"),
        binding.get("provider"),
        binding.get("purpose"),
        binding.get("account_label"),
        binding.get("workspace_label"),
    )


def _safe_binding_projection(binding: Mapping[str, Any]) -> dict[str, Any]:
    store_verification = binding.get("store_verification")
    provider_verification = binding.get("provider_verification")
    return {
        "binding_id": binding.get("binding_id"),
        "binding_revision": binding.get("binding_revision"),
        "credential_id": binding.get("credential_id"),
        "credential_kind": binding.get("credential_kind"),
        "provider": binding.get("provider"),
        "purpose": binding.get("purpose"),
        "account_label": binding.get("account_label"),
        "workspace_label": binding.get("workspace_label"),
        "adapter_kind": binding.get("adapter_kind"),
        "status": binding.get("status"),
        "presence": binding.get("presence"),
        "persisted": binding.get("persisted") is True,
        "credential_fingerprint": binding.get("credential_fingerprint"),
        "rotation_status": binding.get("rotation_status"),
        "default_selection": binding.get("default_selection"),
        "store_verification_status": (
            store_verification.get("status") if isinstance(store_verification, Mapping) else None
        ),
        "provider_verification_status": (
            provider_verification.get("status") if isinstance(provider_verification, Mapping) else None
        ),
        "exact_ref_echoed": False,
        "entry_locator_echoed": False,
        "vault_path_echoed": False,
    }


def _unpersisted_adoption_result(
    plan: CredentialAdoptionPlan,
    *,
    reason_code: str,
) -> dict[str, Any]:
    result = {
        "ok": False,
        "dry_run": False,
        "approved": False,
        "persisted": False,
        "lifecycle_action": "credential_continuity_adoption",
        "reason_code": reason_code,
        "archive_id": plan.archive_id,
        "candidate_id": plan.candidate_id,
        "plan_digest": plan.plan_digest,
        "files_written": [],
        "privacy_guards": {
            "exact_ref_echoed": False,
            "entry_locator_echoed": False,
            "vault_path_echoed": False,
            "secret_value_read": False,
        },
    }
    _assert_no_private_payload(
        result,
        tuple(
            value
            for value in (plan._exact_ref, plan._entry_locator, plan._vault_path)
            if isinstance(value, str) and len(value) >= 3
        ),
    )
    return result


def approve_credential_adoption(
    archive_root: Path | str,
    plan: CredentialAdoptionPlan,
    *,
    expected_plan_digest: str,
    reviewed_by: str,
    store_evidence: CredentialStoreVerificationEvidence | None = None,
    provider_evidence: CredentialProviderVerificationEvidence | None = None,
) -> dict[str, Any]:
    """Persist only a plan with exact-store and provider identity evidence."""

    root = _validated_archive_root(archive_root)
    if root != plan._archive_root:
        raise _fail("credential_adoption_archive_mismatch")
    expected = str(expected_plan_digest or "").strip().lower()
    if SHA256_RE.fullmatch(expected) is None or not hmac.compare_digest(expected, plan.plan_digest):
        raise _fail("credential_adoption_plan_drift")
    try:
        current_catalog_hash = _sha256_bytes(_read_small_bytes(plan._catalog_path))
    except CredentialContinuityError:
        raise _fail("credential_adoption_source_drift") from None
    if not hmac.compare_digest(current_catalog_hash, plan._catalog_sha256):
        raise _fail("credential_adoption_source_drift")
    reviewer = _safe_label(reviewed_by, "credential_reviewer_invalid")
    assert reviewer is not None
    if store_evidence is None:
        return _unpersisted_adoption_result(
            plan,
            reason_code="credential_store_presence_not_verified",
        )
    _validate_store_evidence(plan, store_evidence)
    if provider_evidence is None:
        return _unpersisted_adoption_result(
            plan,
            reason_code="credential_provider_identity_not_verified",
        )
    _validate_provider_evidence(plan, provider_evidence)
    _ensure_local_profile_ignored(root)

    binding_path = _archive_path(root, LOCAL_BINDINGS_RELATIVE)
    receipt_path = _archive_path(root, plan.receipt_path)
    lock_path = _archive_path(root, LOCAL_LOCK_RELATIVE)
    _ensure_safe_parent_chain(root, binding_path)
    _ensure_safe_parent_chain(root, receipt_path)
    _ensure_safe_parent_chain(root, lock_path)

    adopted_at = _utc_now()
    new_binding = {
        "binding_id": plan.binding_id,
        "binding_revision": plan.binding_revision,
        "credential_id": plan.credential_id,
        "credential_kind": plan.credential_kind,
        "provider": plan.provider,
        "purpose": plan.purpose,
        "account_label": plan.account_label,
        "workspace_label": plan.workspace_label,
        "adapter_kind": plan.adapter_kind,
        "status": "active",
        "presence": "exact_match",
        "persisted": True,
        "credential_fingerprint": provider_evidence.credential_fingerprint,
        "rotation_status": provider_evidence.rotation_status,
        "default_selection": provider_evidence.default_selection,
        "store_verification": {
            "status": "verified",
            "evidence_id": store_evidence.evidence_id,
            "evidence_digest": store_evidence.evidence_digest,
            "verification_mode": store_evidence.verification_mode,
            "verified_at": store_evidence.verified_at,
        },
        "provider_verification": {
            "status": "verified",
            "evidence_id": provider_evidence.evidence_id,
            "evidence_digest": provider_evidence.evidence_digest,
            "verifier_id": provider_evidence.verifier_id,
            "verified_at": provider_evidence.verified_at,
        },
        "exact_ref": plan._exact_ref,
        "entry_locator": plan._entry_locator,
        "vault_path": plan._vault_path,
        "adopted_at": adopted_at,
        "adoption_receipt_path": plan.receipt_path,
    }
    receipt = {
        "schema_version": ADOPTION_RECEIPT_SCHEMA_VERSION,
        "receipt_kind": "credential_adoption",
        "receipt_id": "credential-adoption:" + plan.plan_digest[:24],
        "receipt_path": plan.receipt_path,
        "archive_id": plan.archive_id,
        "binding": _safe_binding_projection(new_binding),
        "candidate_id": plan.candidate_id,
        "plan_digest": plan.plan_digest,
        "reviewed_by": reviewer,
        "reviewed_at": adopted_at,
        "decision": "approve_once",
        "result": "adopted_verified",
        "persisted": True,
        "store_verification": store_evidence.to_public_dict(),
        "provider_verification": provider_evidence.to_public_dict(),
        "privacy_contract": {
            "exact_ref_included": False,
            "entry_locator_included": False,
            "vault_path_included": False,
            "secret_value_read": False,
            "secret_value_included": False,
        },
    }

    with _thread_lock_for(root):
        with _InterprocessLock(lock_path):
            document = _load_bindings_document(root, plan.archive_id)
            bindings = list(document["bindings"])
            for existing in bindings:
                same_binding_id = existing.get("binding_id") == plan.binding_id
                if same_binding_id:
                    if _binding_private_identity(existing) != _binding_private_identity(new_binding):
                        raise _fail("credential_binding_rebind_blocked")
                    raise _fail("credential_binding_duplicate")
                if _binding_exact_candidate_identity(existing) == _binding_exact_candidate_identity(new_binding):
                    raise _fail("credential_binding_duplicate")
                if _binding_logical_identity(existing) == _binding_logical_identity(new_binding):
                    raise _fail("credential_binding_rebind_blocked")
            if receipt_path.exists() or receipt_path.is_symlink():
                raise _fail("credential_binding_duplicate")
            updated = dict(document)
            updated["bindings"] = [*bindings, new_binding]
            _write_json_exclusive(receipt_path, receipt, exists_code="credential_binding_duplicate")
            try:
                _atomic_write_json(binding_path, updated)
            except CredentialContinuityError:
                try:
                    receipt_path.unlink(missing_ok=True)
                except OSError:
                    raise _fail("credential_adoption_rollback_failed") from None
                raise

    result = {
        "ok": True,
        "dry_run": False,
        "approved": True,
        "persisted": True,
        "lifecycle_action": "credential_continuity_adoption",
        "reason_code": "credential_binding_adopted_verified",
        "archive_id": plan.archive_id,
        "binding_id": plan.binding_id,
        "binding_revision": plan.binding_revision,
        "binding": _safe_binding_projection(new_binding),
        "binding_path": LOCAL_BINDINGS_RELATIVE,
        "receipt_path": plan.receipt_path,
        "files_written": [LOCAL_BINDINGS_RELATIVE, plan.receipt_path],
        "privacy_guards": {
            "exact_ref_echoed": False,
            "entry_locator_echoed": False,
            "vault_path_echoed": False,
            "secret_value_read": False,
        },
    }
    _assert_no_private_payload(result, _private_fragments(new_binding))
    _assert_no_private_payload(receipt, _private_fragments(new_binding))
    return result


def _load_binding_private(
    root: Path,
    binding_id: str,
    binding_revision: int | None,
) -> dict[str, Any]:
    archive_id = _read_archive_id(root)
    document = _load_bindings_document(root, archive_id)
    matches = [item for item in document["bindings"] if item.get("binding_id") == binding_id]
    if len(matches) != 1:
        raise _fail("credential_binding_not_found")
    binding = dict(matches[0])
    revision = binding.get("binding_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise _fail("credential_bindings_invalid")
    if binding_revision is not None and revision != binding_revision:
        raise _fail("credential_use_binding_mismatch")
    required_safe = {
        "binding_id": SAFE_LABEL_RE,
        "credential_id": SAFE_LABEL_RE,
        "credential_kind": SAFE_METADATA_RE,
        "provider": SAFE_METADATA_RE,
        "purpose": SAFE_METADATA_RE,
        "adapter_kind": SAFE_METADATA_RE,
        "status": SAFE_METADATA_RE,
        "presence": SAFE_METADATA_RE,
    }
    for key, pattern in required_safe.items():
        if not isinstance(binding.get(key), str) or pattern.fullmatch(binding[key]) is None:
            raise _fail("credential_bindings_invalid")
    for key in ("exact_ref", "entry_locator"):
        if not isinstance(binding.get(key), str) or not binding[key]:
            raise _fail("credential_bindings_invalid")
    if binding.get("vault_path") is not None and not isinstance(binding.get("vault_path"), str):
        raise _fail("credential_bindings_invalid")
    if binding.get("adapter_kind") not in SUPPORTED_ADAPTERS:
        raise _fail("credential_adapter_kind_unsupported")
    if binding.get("status") != "active":
        raise _fail("credential_binding_not_active")
    if binding.get("persisted") is not True or binding.get("presence") != "exact_match":
        raise _fail("credential_binding_store_not_verified")
    store_verification = binding.get("store_verification")
    if not isinstance(store_verification, Mapping) or store_verification.get("status") != "verified":
        raise _fail("credential_binding_store_not_verified")
    provider_verification = binding.get("provider_verification")
    if not isinstance(provider_verification, Mapping) or provider_verification.get("status") != "verified":
        raise _fail("credential_binding_provider_not_verified")
    return binding


def lookup_credential_binding(
    archive_root: Path | str,
    *,
    binding_id: str,
    binding_revision: int | None = None,
) -> dict[str, Any]:
    """Return only the non-secret projection of one local binding."""

    root = _validated_archive_root(archive_root)
    resolved_id = _safe_label(binding_id, "credential_binding_id_invalid")
    assert resolved_id is not None
    if binding_revision is not None and (
        isinstance(binding_revision, bool) or not isinstance(binding_revision, int) or binding_revision < 1
    ):
        raise _fail("credential_binding_revision_invalid")
    binding = _load_binding_private(root, resolved_id, binding_revision)
    result = {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "credential_continuity_binding_lookup",
        "reason_code": "credential_binding_ready",
        "archive_id": _read_archive_id(root),
        "binding": _safe_binding_projection(binding),
        "privacy_guards": {
            "exact_ref_echoed": False,
            "entry_locator_echoed": False,
            "vault_path_echoed": False,
            "secret_value_read": False,
        },
    }
    _assert_no_private_payload(result, _private_fragments(binding))
    return result


def _private_fragments(binding: Mapping[str, Any], *additional: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("exact_ref", "entry_locator", "vault_path"):
        value = binding.get(key)
        if isinstance(value, str) and len(value) >= 3:
            values.append(value)
    for value in additional:
        if isinstance(value, str) and len(value) >= 3:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _assert_no_private_payload(payload: Any, fragments: Sequence[str]) -> None:
    rendered = _canonical_json(payload)
    for fragment in fragments:
        if fragment and fragment in rendered:
            raise _fail("credential_private_material_leak_blocked")


@dataclass(frozen=True)
class AdapterProcessResult:
    """Injected subprocess result whose raw channels never appear in repr."""

    returncode: int
    stdout: str = field(repr=False)
    stderr: str = field(repr=False)
    outcome: str | None = field(default=None, repr=False)


class WindowsCredentialManagerExactAdapter:
    """Exact-target Windows credential abstraction with no enumeration seam."""

    adapter_kind = "windows_credential_manager"

    def __init__(
        self,
        *,
        metadata_reader: Callable[[str], bool | int | str],
        secret_reader: Callable[[str], str],
    ) -> None:
        self._metadata_reader = metadata_reader
        self._secret_reader = secret_reader

    def probe_exact(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        locator = _binding_locator(binding)
        try:
            raw = self._metadata_reader(locator)
        except Exception:
            raise _fail("credential_exact_probe_failed") from None
        if raw is True or raw == 1 or raw == "exact_match":
            presence = "exact_match"
            reason = "credential_exact_entry_found"
        elif raw is False or raw == 0 or raw == "not_found":
            presence = "not_found"
            reason = "credential_exact_entry_not_found"
        elif (isinstance(raw, int) and raw > 1) or raw == "ambiguous":
            presence = "ambiguous"
            reason = "credential_exact_entry_ambiguous"
        else:
            raise _fail("credential_exact_probe_invalid")
        result = {
            "ok": presence == "exact_match",
            "adapter_kind": self.adapter_kind,
            "match_mode": "exact_only",
            "presence": presence,
            "reason_code": reason,
            "enumeration_used": False,
            "substring_match_used": False,
            "secret_value_read": False,
            "entry_locator_echoed": False,
        }
        _assert_no_private_payload(result, _private_fragments(binding))
        return result

    def with_secret(
        self,
        binding: Mapping[str, Any],
        callback: Callable[[str], Any],
    ) -> dict[str, Any]:
        probe = self.probe_exact(binding)
        if probe["presence"] == "not_found":
            raise _fail("credential_exact_entry_not_found")
        if probe["presence"] != "exact_match":
            raise _fail("credential_exact_entry_ambiguous")
        locator = _binding_locator(binding)
        secret_value = ""
        try:
            try:
                secret_value = self._secret_reader(locator)
            except Exception:
                raise _fail("credential_adapter_failed") from None
            if not isinstance(secret_value, str) or not secret_value:
                raise _fail("credential_secret_unavailable")
            try:
                consumer_result = callback(secret_value)
            except Exception:
                raise _fail("credential_consumer_failed") from None
            result = {
                "ok": True,
                "adapter_kind": self.adapter_kind,
                "reason_code": "credential_secret_used_by_callback",
                "presence": "exact_match",
                "consumer_result": consumer_result,
                "secret_value_returned": False,
                "secret_value_echoed": False,
                "entry_locator_echoed": False,
            }
            _assert_no_private_payload(result, _private_fragments(binding, secret_value))
            return result
        finally:
            secret_value = ""


class KeePassXCExactEntryAdapter:
    """Exact-entry KeePassXC adapter with an injected subprocess runner."""

    adapter_kind = "keepassxc_cli"

    def __init__(self, *, runner: Callable[[tuple[str, ...]], AdapterProcessResult]) -> None:
        self._runner = runner

    def probe_exact(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        vault_path, locator = _keepassxc_private_target(binding)
        argv = (
            "keepassxc-cli",
            "show",
            "--quiet",
            "--attributes",
            "Title",
            vault_path,
            locator,
        )
        completed = self._run(argv)
        if completed.returncode == 0 and completed.outcome in {None, "exact_match"}:
            presence = "exact_match"
        elif completed.outcome == "not_found":
            presence = "not_found"
        else:
            raise _fail("credential_exact_probe_failed")
        result = {
            "ok": presence == "exact_match",
            "adapter_kind": self.adapter_kind,
            "match_mode": "exact_entry_only",
            "presence": presence,
            "reason_code": "credential_exact_entry_found" if presence == "exact_match" else "credential_exact_entry_not_found",
            "enumeration_used": False,
            "substring_match_used": False,
            "secret_value_read": False,
            "raw_stdout_returned": False,
            "raw_stderr_returned": False,
        }
        _assert_no_private_payload(result, _private_fragments(binding, completed.stdout, completed.stderr))
        return result

    def with_secret(
        self,
        binding: Mapping[str, Any],
        callback: Callable[[str], Any],
    ) -> dict[str, Any]:
        vault_path, locator = _keepassxc_private_target(binding)
        argv = (
            "keepassxc-cli",
            "show",
            "--quiet",
            "--show-protected",
            "--attributes",
            "Password",
            vault_path,
            locator,
        )
        completed = self._run(argv)
        if completed.returncode != 0:
            raise _fail("credential_adapter_failed")
        secret_value = completed.stdout.rstrip("\r\n")
        if not secret_value:
            raise _fail("credential_secret_unavailable")
        try:
            try:
                consumer_result = callback(secret_value)
            except Exception:
                raise _fail("credential_consumer_failed") from None
            result = {
                "ok": True,
                "adapter_kind": self.adapter_kind,
                "reason_code": "credential_secret_used_by_callback",
                "presence": "exact_match",
                "consumer_result": consumer_result,
                "secret_value_returned": False,
                "secret_value_echoed": False,
                "raw_stdout_returned": False,
                "raw_stderr_returned": False,
                "entry_locator_echoed": False,
                "vault_path_echoed": False,
            }
            _assert_no_private_payload(
                result,
                _private_fragments(binding, secret_value, completed.stderr),
            )
            return result
        finally:
            secret_value = ""

    def _run(self, argv: tuple[str, ...]) -> AdapterProcessResult:
        try:
            completed = self._runner(argv)
        except Exception:
            raise _fail("credential_adapter_failed") from None
        if not isinstance(completed, AdapterProcessResult):
            raise _fail("credential_adapter_result_invalid")
        if isinstance(completed.returncode, bool) or not isinstance(completed.returncode, int):
            raise _fail("credential_adapter_result_invalid")
        if not isinstance(completed.stdout, str) or not isinstance(completed.stderr, str):
            raise _fail("credential_adapter_result_invalid")
        if completed.outcome not in {None, "exact_match", "not_found"}:
            raise _fail("credential_adapter_result_invalid")
        return completed


def _binding_locator(binding: Mapping[str, Any]) -> str:
    locator = binding.get("entry_locator")
    if not isinstance(locator, str) or not locator:
        raise _fail("credential_binding_locator_invalid")
    return locator


def _keepassxc_private_target(binding: Mapping[str, Any]) -> tuple[str, str]:
    locator = _binding_locator(binding)
    vault_path = binding.get("vault_path")
    if not isinstance(vault_path, str) or not vault_path:
        raise _fail("credential_vault_path_required")
    return vault_path, locator


@dataclass(frozen=True)
class _TrustedConsumer:
    handler: Callable[[str, dict[str, object]], Mapping[str, object]] = field(repr=False)
    allowed_result_fields: frozenset[str]


class TrustedConsumerRegistry:
    """An explicit registry; arbitrary commands and callbacks are not accepted."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._consumers: dict[str, _TrustedConsumer] = {}

    def register(
        self,
        consumer: str,
        handler: Callable[[str, dict[str, object]], Mapping[str, object]],
        *,
        allowed_result_fields: set[str] | frozenset[str],
    ) -> None:
        resolved = _safe_label(consumer, "credential_consumer_invalid")
        assert resolved is not None
        if not callable(handler):
            raise _fail("credential_consumer_invalid")
        allowed = frozenset(str(item) for item in allowed_result_fields)
        if not allowed or any(SAFE_METADATA_RE.fullmatch(item) is None for item in allowed):
            raise _fail("credential_consumer_result_contract_invalid")
        with self._lock:
            if resolved in self._consumers:
                raise _fail("credential_consumer_duplicate")
            self._consumers[resolved] = _TrustedConsumer(handler=handler, allowed_result_fields=allowed)

    def is_trusted(self, consumer: str) -> bool:
        with self._lock:
            return consumer in self._consumers

    def invoke(
        self,
        consumer: str,
        secret_value: str,
        context: dict[str, object],
    ) -> dict[str, object]:
        with self._lock:
            registered = self._consumers.get(consumer)
        if registered is None:
            raise _fail("credential_consumer_not_trusted")
        try:
            raw_result = registered.handler(secret_value, dict(context))
        except Exception:
            raise _fail("credential_consumer_failed") from None
        if not isinstance(raw_result, Mapping):
            raise _fail("credential_consumer_result_invalid")
        if any(str(key) not in registered.allowed_result_fields for key in raw_result):
            raise _fail("credential_consumer_result_invalid")
        result: dict[str, object] = {}
        for key, value in raw_result.items():
            safe_key = str(key)
            if not _safe_consumer_result_value(value):
                raise _fail("credential_consumer_result_invalid")
            result[safe_key] = value
        _assert_no_private_payload(result, (secret_value,))
        return result


def _safe_consumer_result_value(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return -(2**63) <= value <= 2**63 - 1
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        return SAFE_LABEL_RE.fullmatch(value) is not None and "@" not in value
    return False


class CredentialUseBroker:
    """One-time, receipt-claiming broker for registered trusted consumers."""

    REQUIRED_APPROVAL_FIELDS = {
        "receipt_id",
        "decision",
        "binding_id",
        "binding_revision",
        "action_kind",
        "operation",
        "adapter_kind",
        "consumer",
    }

    def __init__(
        self,
        archive_root: Path | str,
        *,
        registry: TrustedConsumerRegistry,
        adapters: Mapping[str, Any],
    ) -> None:
        self.root = _validated_archive_root(archive_root)
        self.registry = registry
        self.adapters = dict(adapters)

    def use_once(self, approval: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._validate_approval_shape(approval)
        binding = _load_binding_private(
            self.root,
            normalized["binding_id"],
            normalized["binding_revision"],
        )
        if binding.get("binding_id") != normalized["binding_id"] or binding.get("binding_revision") != normalized["binding_revision"]:
            raise _fail("credential_use_binding_mismatch")
        if binding.get("adapter_kind") != normalized["adapter_kind"]:
            raise _fail("credential_use_binding_mismatch")
        if not self.registry.is_trusted(normalized["consumer"]):
            raise _fail("credential_consumer_not_trusted")
        adapter = self.adapters.get(normalized["adapter_kind"])
        if adapter is None or not callable(getattr(adapter, "with_secret", None)):
            raise _fail("credential_adapter_not_registered")

        claim_digest = _sha256_bytes(
            _canonical_json(
                {
                    key: normalized[key]
                    for key in sorted(self.REQUIRED_APPROVAL_FIELDS)
                }
            ).encode("utf-8")
        )
        receipt_relative = f"{USE_RECEIPTS_RELATIVE}/credential-use-{claim_digest[:24]}.json"
        receipt_path = _archive_path(self.root, receipt_relative)
        _ensure_safe_parent_chain(self.root, receipt_path)
        started_at = _utc_now()
        base_receipt = {
            "schema_version": USE_RECEIPT_SCHEMA_VERSION,
            "receipt_kind": "credential_use",
            "receipt_id": "credential-use:" + claim_digest[:24],
            "receipt_path": receipt_relative,
            "archive_id": _read_archive_id(self.root),
            "approval_receipt_id": normalized["receipt_id"],
            "binding_id": normalized["binding_id"],
            "binding_revision": normalized["binding_revision"],
            "action_kind": normalized["action_kind"],
            "operation": normalized["operation"],
            "adapter_kind": normalized["adapter_kind"],
            "consumer": normalized["consumer"],
            "decision": "approve_once",
            "started_at": started_at,
            "finished_at": None,
            "status": "started",
            "failure_code": None,
            "consumer_result": None,
            "privacy_contract": {
                "secret_value_included": False,
                "exact_ref_included": False,
                "entry_locator_included": False,
                "vault_path_included": False,
                "raw_stdout_included": False,
                "raw_stderr_included": False,
            },
        }
        _assert_no_private_payload(base_receipt, _private_fragments(binding))
        _write_json_exclusive(
            receipt_path,
            base_receipt,
            exists_code="credential_use_replay_blocked",
        )

        context: dict[str, object] = {
            "binding_id": normalized["binding_id"],
            "binding_revision": normalized["binding_revision"],
            "credential_id": binding.get("credential_id"),
            "credential_kind": binding.get("credential_kind"),
            "provider": binding.get("provider"),
            "purpose": binding.get("purpose"),
            "account_label": binding.get("account_label"),
            "workspace_label": binding.get("workspace_label"),
            "action_kind": normalized["action_kind"],
            "operation": normalized["operation"],
            "consumer": normalized["consumer"],
        }
        callback_lock = threading.Lock()
        callback_invoked = False
        captured_consumer_result: dict[str, object] | None = None

        def invoke_registered_consumer(secret: str) -> dict[str, object]:
            nonlocal callback_invoked, captured_consumer_result
            with callback_lock:
                if callback_invoked:
                    raise _fail("credential_consumer_replay_blocked")
                callback_invoked = True
            captured_consumer_result = self.registry.invoke(
                normalized["consumer"],
                secret,
                context,
            )
            return dict(captured_consumer_result)

        try:
            adapter_result = adapter.with_secret(
                binding,
                invoke_registered_consumer,
            )
            if (
                not isinstance(adapter_result, Mapping)
                or adapter_result.get("ok") is not True
                or not callback_invoked
                or captured_consumer_result is None
            ):
                raise _fail("credential_adapter_result_invalid")
            # Never trust or serialize the adapter's own return payload.  The
            # only accepted result is the registry-sanitized callback result.
            consumer_result = dict(captured_consumer_result)
            final_receipt = dict(base_receipt)
            final_receipt.update(
                {
                    "finished_at": _utc_now(),
                    "status": "succeeded",
                    "failure_code": None,
                    "consumer_result": consumer_result,
                }
            )
            _assert_no_private_payload(final_receipt, _private_fragments(binding))
            _atomic_write_json(receipt_path, final_receipt)
            result = {
                "ok": True,
                "lifecycle_action": "credential_continuity_broker_use",
                "reason_code": "credential_use_succeeded",
                "binding_id": normalized["binding_id"],
                "binding_revision": normalized["binding_revision"],
                "consumer": normalized["consumer"],
                "action_kind": normalized["action_kind"],
                "operation": normalized["operation"],
                "consumer_result": consumer_result,
                "audit_receipt_path": receipt_relative,
                "secret_value_returned": False,
                "privacy_guards": {
                    "exact_ref_echoed": False,
                    "entry_locator_echoed": False,
                    "vault_path_echoed": False,
                    "secret_value_echoed": False,
                    "raw_adapter_output_echoed": False,
                },
            }
            _assert_no_private_payload(result, _private_fragments(binding))
            return result
        except CredentialContinuityError as exc:
            self._finalize_failed_claim(receipt_path, base_receipt, binding, exc.code)
            raise _fail(exc.code) from None
        except Exception:
            self._finalize_failed_claim(
                receipt_path,
                base_receipt,
                binding,
                "credential_broker_failed",
            )
            raise _fail("credential_broker_failed") from None

    def _validate_approval_shape(self, approval: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(approval, Mapping) or set(approval) != self.REQUIRED_APPROVAL_FIELDS:
            raise _fail("credential_use_approval_invalid")
        normalized: dict[str, Any] = {}
        for key in (
            "receipt_id",
            "binding_id",
            "action_kind",
            "operation",
            "adapter_kind",
            "consumer",
        ):
            value = _safe_label(approval.get(key), "credential_use_approval_invalid")
            assert value is not None
            normalized[key] = value
        revision = approval.get("binding_revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise _fail("credential_use_approval_invalid")
        normalized["binding_revision"] = revision
        if approval.get("decision") != "approve_once":
            raise _fail("credential_use_approval_invalid")
        normalized["decision"] = "approve_once"
        if normalized["operation"] != "resolve_for_approved_action":
            raise _fail("credential_use_approval_invalid")
        if normalized["adapter_kind"] not in SUPPORTED_ADAPTERS:
            raise _fail("credential_adapter_kind_unsupported")
        return normalized

    @staticmethod
    def _finalize_failed_claim(
        receipt_path: Path,
        base_receipt: Mapping[str, Any],
        binding: Mapping[str, Any],
        failure_code: str,
    ) -> None:
        failed = dict(base_receipt)
        failed.update(
            {
                "finished_at": _utc_now(),
                "status": "failed",
                "failure_code": failure_code,
                "consumer_result": None,
            }
        )
        _assert_no_private_payload(failed, _private_fragments(binding))
        try:
            _atomic_write_json(receipt_path, failed)
        except CredentialContinuityError:
            raise _fail("credential_use_audit_finalize_failed") from None


def execute_credential_broker_use(
    archive_root: Path | str,
    *,
    approval: Mapping[str, Any],
    registry: TrustedConsumerRegistry,
    adapters: Mapping[str, Any],
) -> dict[str, Any]:
    """Functional wrapper for integrating the one-time broker later."""

    return CredentialUseBroker(
        archive_root,
        registry=registry,
        adapters=adapters,
    ).use_once(approval)


__all__ = [
    "ADOPTION_RECEIPTS_RELATIVE",
    "AdapterProcessResult",
    "CredentialAdoptionPlan",
    "CredentialCandidate",
    "CredentialContinuityError",
    "CredentialDiscoveryReport",
    "CredentialProviderVerificationEvidence",
    "CredentialStoreVerificationEvidence",
    "CredentialUseBroker",
    "KeePassXCExactEntryAdapter",
    "LOCAL_BINDINGS_RELATIVE",
    "LOCAL_CATALOG_RELATIVE",
    "TrustedConsumerRegistry",
    "USE_RECEIPTS_RELATIVE",
    "WindowsCredentialManagerExactAdapter",
    "approve_credential_adoption",
    "discover_local_credential_candidates",
    "execute_credential_broker_use",
    "lookup_credential_binding",
    "plan_credential_adoption",
    "verify_credential_provider_for_adoption",
    "verify_credential_store_for_adoption",
]
