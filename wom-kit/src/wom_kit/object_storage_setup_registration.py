"""Exact local registration of object-storage setup evidence.

This module records only local metadata.  It never creates or verifies a
bucket, calls a provider, or reads a credential value.  The public projection
is deliberately content-free; provider resource values remain in the private
exact-operation payload and deterministic local setup receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from . import archive_services
from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_workflow import _execute_exact_human_approved_write
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationItem,
    ExactOperationProgress,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_writer_lock,
    hash_field_value,
    revert_exact_operation_fields,
)
from .operation_approval_binding import (
    ExactOperationApprovalBinding,
    exact_operation_manifest_approval_binding,
)


PLAN_SCHEMA = "wom-kit/object-storage-setup-registration-plan/v0.1"
RECEIPT_SCHEMA = "wom-kit/object-storage-setup-registration-receipt/v0.1"
EVIDENCE_SCHEMA = "wom-kit/object-storage-setup-evidence/v0.1"
RESULT_SCHEMA = "wom-kit/object-storage-setup-registration-result/v0.1"
OPERATION = "object_storage_setup_registration"
PROVIDER_TARGET_REF = "provider-bindings.yml#object-storage-binding"
RECEIPT_ROOT = "receipts/providers/object-storage-setup-registration"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_PROVIDER_BYTES = 8 * 1024 * 1024
_MAX_RECEIPT_BYTES = 128 * 1024


class ObjectStorageSetupRegistrationError(RuntimeError):
    """Fixed-code error that cannot retain resource or path values."""

    _CODES = {
        "object_storage_setup_registration_archive_invalid",
        "object_storage_setup_registration_plan_invalid",
        "object_storage_setup_registration_plan_changed",
        "object_storage_setup_registration_no_writes",
        "object_storage_setup_registration_approval_required",
        "object_storage_setup_registration_source_drifted",
        "object_storage_setup_registration_collision",
        "object_storage_setup_registration_receipt_collision",
        "object_storage_setup_evidence_missing",
        "object_storage_setup_evidence_mismatch",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "object_storage_setup_registration_plan_invalid"
        )
        super().__init__(self.code)


def _fail(code: str) -> ObjectStorageSetupRegistrationError:
    return ObjectStorageSetupRegistrationError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("object_storage_setup_registration_plan_invalid") from None


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    return _sha_bytes(_canonical(value))


def _strict_json(raw: bytes) -> dict[str, Any]:
    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate member")
            result[key] = value
        return result

    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs_hook)
    if not isinstance(parsed, dict):
        raise ValueError("not an object")
    return parsed


def _read_bounded(path: Path, *, maximum: int, missing_ok: bool) -> bytes | None:
    try:
        if not path.exists():
            if missing_ok:
                return None
            raise OSError("missing")
        info = os.lstat(path)
        if not path.is_file() or path.is_symlink() or info.st_size > maximum:
            raise OSError("unsafe")
        raw = path.read_bytes()
        after = os.lstat(path)
        if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("changed")
        return raw
    except OSError:
        raise _fail("object_storage_setup_registration_source_drifted") from None


def _provider_document(root: Path) -> tuple[dict[str, Any], bytes | None]:
    path = archive_services.archive_internal_path(root, "provider-bindings.yml")
    raw = _read_bounded(path, maximum=_MAX_PROVIDER_BYTES, missing_ok=True)
    if raw is None:
        return {
            "version": "provider-bindings/v0.1",
            "archive_id": archive_services.read_archive_id(root),
            "bindings": [],
        }, None
    try:
        document = archive_services.load_yaml(raw.decode("utf-8"))
    except Exception:
        raise _fail("object_storage_setup_registration_plan_invalid") from None
    if not isinstance(document, dict):
        raise _fail("object_storage_setup_registration_plan_invalid")
    bindings = document.get("bindings")
    if not isinstance(bindings, list) or any(not isinstance(row, dict) for row in bindings):
        raise _fail("object_storage_setup_registration_plan_invalid")
    return document, raw


def _binding_account_ref(binding: Mapping[str, Any]) -> str:
    auth = binding.get("auth")
    return str(auth.get("account_ref") or "") if isinstance(auth, Mapping) else ""


def _binding_profile_id(binding: Mapping[str, Any]) -> str:
    owner = binding.get("owner_mapping")
    return str(owner.get("profile_id") or "") if isinstance(owner, Mapping) else ""


def _strict_object_storage_binding(
    binding: Mapping[str, Any], *, archive_id: str
) -> bool:
    resource = binding.get("resource")
    auth = binding.get("auth")
    owner = binding.get("owner_mapping")
    if (
        set(binding)
        != {
            "binding_id",
            "provider",
            "provider_kind",
            "enabled",
            "purpose",
            "resource",
            "auth",
            "owner_mapping",
            "notes",
        }
        or not isinstance(resource, Mapping)
        or set(resource)
        != {"bucket", "prefix", "visibility", "region", "endpoint_ref"}
        or not isinstance(auth, Mapping)
        or set(auth) != {"method", "token_env", "account_ref"}
        or not isinstance(owner, Mapping)
        or set(owner) != {"archive_id", "profile_id", "profile_slug"}
    ):
        return False
    provider = str(binding.get("provider_kind") or "")
    bucket = str(resource.get("bucket") or "")
    account_ref = str(auth.get("account_ref") or "")
    endpoint_ref = str(resource.get("endpoint_ref") or "")
    prefix = str(resource.get("prefix") or "")
    region = str(resource.get("region") or "")
    profile_id = str(owner.get("profile_id") or "")
    profile_slug = str(owner.get("profile_slug") or "")
    return bool(
        binding.get("provider") == "object_storage"
        and provider in archive_services.OBJECT_STORAGE_ALLOWED_PROVIDERS
        and binding.get("binding_id") == f"object_storage:{provider}:{bucket}"
        and binding.get("enabled") is True
        and binding.get("purpose")
        == "objet_storage_metadata_and_manual_setup_plan"
        and binding.get("notes")
        == "Manual object storage setup plan only; WOM-kit does not create buckets, upload objets, sync, copy, or hash files."
        and archive_services.safe_object_storage_bucket_name(bucket)
        and archive_services.safe_objet_prefix(prefix)
        and resource.get("visibility") == "private"
        and archive_services.safe_object_storage_region(region)
        and archive_services.safe_object_storage_ref(endpoint_ref)
        and auth.get("method") == "token_ref_or_env"
        and auth.get("token_env")
        == archive_services.OBJECT_STORAGE_PROVIDER_TOKEN_ENVS.get(
            provider, "OBJECT_STORAGE_TOKEN"
        )
        and archive_services.safe_object_storage_account_ref(account_ref)
        and owner.get("archive_id") == archive_id
        and bool(profile_id)
        and archive_services.safe_source_intake_plan_scalar(profile_id)
        and archive_services.safe_github_profile_slug_input(profile_slug)
    )


def _matching_indices(
    bindings: list[dict[str, Any]], proposed: Mapping[str, Any]
) -> list[int]:
    provider_kind = str(proposed.get("provider_kind") or "")
    account_ref = _binding_account_ref(proposed)
    profile_id = _binding_profile_id(proposed)
    return [
        index
        for index, binding in enumerate(bindings)
        if binding.get("provider") == "object_storage"
        and binding.get("provider_kind") == provider_kind
        and (
            _binding_account_ref(binding) == account_ref
            or (
                profile_id
                and _binding_profile_id(binding) == profile_id
            )
        )
    ]


def _non_target_digest(
    bindings: list[dict[str, Any]], target_index: int | None
) -> str:
    return _sha(
        [
            binding
            for index, binding in enumerate(bindings)
            if target_index is None or index != target_index
        ]
    )


def _receipt_relative(binding_sha256: str) -> str:
    if _SHA256_RE.fullmatch(binding_sha256) is None:
        raise _fail("object_storage_setup_registration_plan_invalid")
    return (
        f"{RECEIPT_ROOT}/"
        f"{binding_sha256.removeprefix('sha256:')}.json"
    )


def _receipt_document(
    *,
    archive_id: str,
    binding: Mapping[str, Any],
    binding_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "provider_binding": dict(binding),
        "provider_binding_sha256": binding_sha256,
        "registration_state": "local_metadata_registered_provider_unverified",
        "external_actions": {
            "provider_api_called": False,
            "bucket_created": False,
            "bucket_verified": False,
            "credential_value_read": False,
            "files_uploaded": False,
        },
    }


def _receipt_bytes(document: Mapping[str, Any]) -> bytes:
    raw = _canonical(dict(document)) + b"\n"
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise _fail("object_storage_setup_registration_plan_invalid")
    return raw


@dataclass(frozen=True, repr=False)
class ObjectStorageSetupEvidence:
    mode: str
    archive_identity_sha256: str
    provider_binding_sha256: str
    receipt_sha256: str

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": EVIDENCE_SCHEMA,
            "ok": True,
            "state": "setup_evidence_valid",
            "evidence_mode": self.mode,
            "archive_identity_sha256": self.archive_identity_sha256,
            "provider_binding_sha256": self.provider_binding_sha256,
            "receipt_sha256": self.receipt_sha256,
            "provider_api_called": False,
            "bucket_created": False,
            "bucket_verified": False,
            "credential_value_read": False,
            "private_values_echoed": False,
        }


@dataclass(frozen=True, repr=False)
class ObjectStorageSetupRegistrationPlan:
    archive_root: Path
    archive_id: str
    proposed_binding: Mapping[str, Any]
    original_binding: Mapping[str, Any] | None
    target_index: int | None
    non_target_binding_set_sha256: str
    provider_original_bytes: bytes | None
    provider_post_bytes: bytes
    receipt_relative: str
    receipt_bytes: bytes
    receipt_preexisting: bool
    manifest: ExactOperationManifest | None

    @property
    def plan_sha256(self) -> str:
        if self.manifest is not None:
            return self.manifest.manifest_sha256
        return _sha(
            {
                "schema_version": PLAN_SCHEMA,
                "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
                    self.archive_id
                ),
                "provider_binding_sha256": _sha(self.proposed_binding),
                "receipt_sha256": _sha_bytes(self.receipt_bytes),
                "state": "already_registered",
            }
        )

    def public_document(self) -> dict[str, Any]:
        provider_change = self.provider_original_bytes != self.provider_post_bytes
        receipt_change = not self.receipt_preexisting
        return {
            "schema_version": PLAN_SCHEMA,
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "object_storage_setup_registration",
            "state": (
                "setup_registration_planned"
                if self.manifest is not None
                else "setup_registration_already_present"
            ),
            "plan_sha256": self.plan_sha256,
            "manifest_sha256": (
                self.manifest.manifest_sha256 if self.manifest is not None else None
            ),
            "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
                self.archive_id
            ),
            "counts": {
                "provider_binding_field_change_count": int(provider_change),
                "setup_receipt_create_count": int(receipt_change),
                "exact_manifest_item_count": (
                    len(self.manifest.items) if self.manifest is not None else 0
                ),
            },
            "closed_actions": {
                "provider_api_called": False,
                "bucket_created": False,
                "bucket_verified": False,
                "credential_value_read": False,
                "files_uploaded": False,
            },
            "privacy_guards": {
                "bucket_names_echoed": False,
                "account_refs_echoed": False,
                "endpoint_refs_echoed": False,
                "receipt_paths_echoed": False,
                "local_absolute_paths_echoed": False,
                "secret_values_echoed": False,
                "private_values_echoed": False,
            },
            "provider_setup_scope": "local_registration_only_provider_unverified",
        }


def _plan_source_basis(
    plan: ObjectStorageSetupRegistrationPlan,
) -> dict[str, Any]:
    return {
        "provider_document_pre_sha256": _sha_bytes(
            plan.provider_original_bytes or b""
        ),
        "provider_binding_pre_sha256": _sha(plan.original_binding),
        "provider_binding_post_sha256": _sha(plan.proposed_binding),
        "non_target_binding_set_sha256": plan.non_target_binding_set_sha256,
        "receipt_bytes_sha256": _sha_bytes(plan.receipt_bytes),
        "receipt_path_sha256": _sha(plan.receipt_relative),
    }


def _post_provider_document(
    document: Mapping[str, Any],
    bindings: list[dict[str, Any]],
    target_index: int | None,
    proposed: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    result = dict(document)
    updated = list(bindings)
    if target_index is None:
        updated.append(dict(proposed))
    else:
        updated[target_index] = dict(proposed)
    keys = [archive_services.object_storage_binding_compare_key(row) for row in updated]
    if len(keys) != len(set(keys)):
        raise _fail("object_storage_setup_registration_collision")
    result["bindings"] = updated
    try:
        raw = archive_services.dump_yaml(archive_services.json_safe(result)).encode(
            "utf-8"
        )
    except Exception:
        raise _fail("object_storage_setup_registration_plan_invalid") from None
    if len(raw) > _MAX_PROVIDER_BYTES:
        raise _fail("object_storage_setup_registration_plan_invalid")
    return result, raw


def _target_identity(
    *, archive_id: str, target_kind: str, source: Mapping[str, Any]
) -> str:
    return _sha(
        {
            "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
                archive_id
            ),
            "target_kind": target_kind,
            "source": dict(source),
        }
    )


def plan_object_storage_setup_registration(
    archive_root: Path | str,
    *,
    provider: str | None = None,
    profile_id: str | None = None,
    profile_slug: str | None = None,
    storage_account_ref: str | None = None,
    bucket_name: str | None = None,
    region: str | None = None,
    endpoint_ref: str | None = None,
    objet_prefix: str | None = None,
    visibility: str = archive_services.OBJECT_STORAGE_DEFAULT_VISIBILITY,
) -> ObjectStorageSetupRegistrationPlan:
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        legacy_plan = archive_services.object_storage_setup_plan(
            root,
            provider=provider,
            profile_id=profile_id,
            profile_slug=profile_slug,
            storage_account_ref=storage_account_ref,
            bucket_name=bucket_name,
            region=region,
            endpoint_ref=endpoint_ref,
            objet_prefix=objet_prefix,
            visibility=visibility,
        )
    except Exception:
        raise _fail("object_storage_setup_registration_archive_invalid") from None
    blockers = [
        str(value)
        for value in legacy_plan.get("blockers", [])
        if not str(value).startswith("Proposed provider setup receipt already exists:")
    ]
    proposed = legacy_plan.get("provider_binding_preview")
    if blockers or not isinstance(proposed, dict):
        raise _fail("object_storage_setup_registration_plan_invalid")
    document, original_raw = _provider_document(root)
    if document.get("archive_id") != archive_id:
        raise _fail("object_storage_setup_registration_plan_invalid")
    bindings = document.get("bindings")
    if not isinstance(bindings, list):
        raise _fail("object_storage_setup_registration_plan_invalid")
    matches = _matching_indices(bindings, proposed)
    if len(matches) > 1:
        raise _fail("object_storage_setup_registration_collision")
    target_index = matches[0] if matches else None
    # Registration is deliberately create-only.  A pre-existing binding may
    # be reused only when it is already byte-for-byte the proposed binding;
    # this writer must never turn a setup registration into an implicit
    # account, bucket, prefix, or owner reconfiguration.
    if target_index is not None and bindings[target_index] != proposed:
        raise _fail("object_storage_setup_registration_collision")
    proposed_key = archive_services.object_storage_binding_compare_key(proposed)
    for index, binding in enumerate(bindings):
        if index != target_index and archive_services.object_storage_binding_compare_key(binding) == proposed_key:
            raise _fail("object_storage_setup_registration_collision")
    original_binding = bindings[target_index] if target_index is not None else None
    non_target_digest = _non_target_digest(bindings, target_index)
    _post_document, post_raw = _post_provider_document(
        document, bindings, target_index, proposed
    )
    if original_raw is not None and original_binding == proposed:
        # An unchanged target binding must not cause a formatting-only rewrite.
        post_raw = original_raw
    binding_sha = _sha(proposed)
    receipt_relative = _receipt_relative(binding_sha)
    receipt = _receipt_bytes(
        _receipt_document(
            archive_id=archive_id,
            binding=proposed,
            binding_sha256=binding_sha,
        )
    )
    receipt_path = archive_services.archive_internal_path(root, receipt_relative)
    existing_receipt = _read_bounded(
        receipt_path, maximum=_MAX_RECEIPT_BYTES, missing_ok=True
    )
    if existing_receipt is not None and existing_receipt != receipt:
        raise _fail("object_storage_setup_registration_receipt_collision")

    items: list[ExactOperationItem] = []
    source_basis = {
        "provider_document_pre_sha256": _sha_bytes(original_raw or b""),
        "provider_binding_pre_sha256": _sha(original_binding),
        "provider_binding_post_sha256": binding_sha,
        "non_target_binding_set_sha256": non_target_digest,
        "receipt_bytes_sha256": _sha_bytes(receipt),
        "receipt_path_sha256": _sha(receipt_relative),
    }
    if original_raw != post_raw:
        items.append(
            ExactOperationItem(
                ordinal=len(items),
                item_id="item:" + hashlib.sha256(PROVIDER_TARGET_REF.encode("ascii")).hexdigest(),
                target_kind="object_storage_setup_provider_binding",
                target_ref=PROVIDER_TARGET_REF,
                target_identity_sha256=_target_identity(
                    archive_id=archive_id,
                    target_kind="provider_binding",
                    source=source_basis,
                ),
                fields=(
                    ExactFieldEffect(
                        field_ref="provider_binding",
                        pre_sha256=hash_field_value(
                            _canonical(original_binding)
                            if original_binding is not None
                            else None
                        ),
                        post_sha256=hash_field_value(_canonical(proposed)),
                        source_sha256=hash_field_value(_canonical(source_basis)),
                    ),
                ),
            )
        )
    if existing_receipt is None:
        items.append(
            ExactOperationItem(
                ordinal=len(items),
                item_id="item:" + hashlib.sha256(receipt_relative.encode("ascii")).hexdigest(),
                target_kind="object_storage_setup_receipt",
                target_ref="object-storage-setup-registration-receipt:" + binding_sha.removeprefix("sha256:"),
                target_identity_sha256=_target_identity(
                    archive_id=archive_id,
                    target_kind="setup_receipt",
                    source=source_basis,
                ),
                fields=(
                    ExactFieldEffect(
                        field_ref="receipt_bytes",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(receipt),
                        source_sha256=hash_field_value(_canonical(source_basis)),
                    ),
                ),
            )
        )
    manifest = (
        ExactOperationManifest.build(
            operation=OPERATION,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                archive_id
            ),
            items=items,
            operation_evidence={
                "schema": "wom-kit/object-storage-setup-registration-evidence/v1",
                "counts": {
                    "provider_binding_change_count": int(original_raw != post_raw),
                    "setup_receipt_create_count": int(existing_receipt is None),
                },
                "digests": {
                    "non_target_binding_set_sha256": non_target_digest,
                    "provider_binding_sha256": binding_sha,
                    "setup_receipt_sha256": _sha_bytes(receipt),
                },
                "private_values_echoed": False,
            },
        )
        if items
        else None
    )
    return ObjectStorageSetupRegistrationPlan(
        archive_root=root,
        archive_id=archive_id,
        proposed_binding=dict(proposed),
        original_binding=(dict(original_binding) if original_binding is not None else None),
        target_index=target_index,
        non_target_binding_set_sha256=non_target_digest,
        provider_original_bytes=original_raw,
        provider_post_bytes=post_raw,
        receipt_relative=receipt_relative,
        receipt_bytes=receipt,
        receipt_preexisting=existing_receipt is not None,
        manifest=manifest,
    )


def _current_provider_field(
    plan: ObjectStorageSetupRegistrationPlan,
) -> bytes | None:
    path = archive_services.archive_internal_path(plan.archive_root, "provider-bindings.yml")
    raw = _read_bounded(path, maximum=_MAX_PROVIDER_BYTES, missing_ok=True)
    if raw == plan.provider_original_bytes:
        return (
            _canonical(plan.original_binding)
            if plan.original_binding is not None
            else None
        )
    if raw == plan.provider_post_bytes:
        return _canonical(plan.proposed_binding)
    raise _fail("object_storage_setup_registration_source_drifted")


def _current_receipt_field(plan: ObjectStorageSetupRegistrationPlan) -> bytes | None:
    path = archive_services.archive_internal_path(plan.archive_root, plan.receipt_relative)
    raw = _read_bounded(path, maximum=_MAX_RECEIPT_BYTES, missing_ok=True)
    if raw is None or raw == plan.receipt_bytes:
        return raw
    raise _fail("object_storage_setup_registration_receipt_collision")


class _Payloads:
    def __init__(self, plan: ObjectStorageSetupRegistrationPlan) -> None:
        self.plan = plan

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        if state not in {"pre", "post", "source"}:
            raise ValueError("payload boundary")
        if field_ref == "provider_binding":
            values = {
                "pre": (
                    _canonical(self.plan.original_binding)
                    if self.plan.original_binding is not None
                    else None
                ),
                "post": _canonical(self.plan.proposed_binding),
                "source": _canonical(_plan_source_basis(self.plan)),
            }
            return values[state]
        if field_ref == "receipt_bytes":
            values = {
                "pre": None,
                "post": self.plan.receipt_bytes,
                "source": _canonical(_plan_source_basis(self.plan)),
            }
            return values[state]
        raise ValueError("payload boundary")


class _Verifier:
    def __init__(self, plan: ObjectStorageSetupRegistrationPlan) -> None:
        self.plan = plan
        if plan.manifest is None:
            self.identities: dict[str, str] = {}
        else:
            self.identities = {
                item.target_kind: item.target_identity_sha256
                for item in plan.manifest.items
            }

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        identity = self.identities.get(target_kind)
        if identity is None:
            raise ValueError("target boundary")
        return identity

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        if target_kind == "object_storage_setup_provider_binding" and field_ref == "provider_binding":
            return _current_provider_field(self.plan)
        if target_kind == "object_storage_setup_receipt" and field_ref == "receipt_bytes":
            return _current_receipt_field(self.plan)
        raise ValueError("read boundary")


class _Writer:
    def __init__(self, plan: ObjectStorageSetupRegistrationPlan) -> None:
        self.plan = plan

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
        if target_kind == "object_storage_setup_provider_binding" and field_ref == "provider_binding":
            path = archive_services.archive_internal_path(
                self.plan.archive_root, "provider-bindings.yml"
            )
            current = _read_bounded(path, maximum=_MAX_PROVIDER_BYTES, missing_ok=True)
            if value == _canonical(self.plan.proposed_binding):
                if current != self.plan.provider_original_bytes:
                    raise _fail("object_storage_setup_registration_source_drifted")
                archive_services._atomic_write_text(
                    path, self.plan.provider_post_bytes.decode("utf-8")
                )
                return
            expected_pre = (
                _canonical(self.plan.original_binding)
                if self.plan.original_binding is not None
                else None
            )
            if value == expected_pre:
                if current != self.plan.provider_post_bytes:
                    raise _fail("object_storage_setup_registration_source_drifted")
                if self.plan.provider_original_bytes is None:
                    path.unlink()
                else:
                    archive_services._atomic_write_text(
                        path, self.plan.provider_original_bytes.decode("utf-8")
                    )
                return
            raise ValueError("write boundary")
        if target_kind == "object_storage_setup_receipt" and field_ref == "receipt_bytes":
            path = archive_services.archive_internal_path(
                self.plan.archive_root, self.plan.receipt_relative
            )
            current = _read_bounded(path, maximum=_MAX_RECEIPT_BYTES, missing_ok=True)
            if value == self.plan.receipt_bytes:
                if current is not None:
                    if current == value:
                        return
                    raise _fail("object_storage_setup_registration_receipt_collision")
                try:
                    archive_services._write_bytes_create_if_absent(path, value)
                except OSError:
                    # A racing exact publication, or a failure after its atomic
                    # link became durable, is idempotent only when a fresh
                    # bounded read proves the complete expected bytes.
                    try:
                        published = _read_bounded(
                            path,
                            maximum=_MAX_RECEIPT_BYTES,
                            missing_ok=True,
                        )
                    except ObjectStorageSetupRegistrationError:
                        raise _fail(
                            "object_storage_setup_registration_receipt_collision"
                        ) from None
                    if published != value:
                        raise _fail(
                            "object_storage_setup_registration_receipt_collision"
                        ) from None
                return
            if value is None:
                if current is None:
                    return
                if current != self.plan.receipt_bytes:
                    raise _fail("object_storage_setup_registration_receipt_collision")
                path.unlink()
                return
            raise ValueError("write boundary")
        raise ValueError("write boundary")


def _approval_binding(
    plan: ObjectStorageSetupRegistrationPlan,
) -> ExactOperationApprovalBinding:
    if plan.manifest is None:
        raise _fail("object_storage_setup_registration_no_writes")
    try:
        return exact_operation_manifest_approval_binding(
            plan.manifest,
            operation=ExactHumanApprovalOperation.object_storage_setup_registration,
            archive_id=plan.archive_id,
            warnings=(
                "local_registration_does_not_create_or_verify_provider_bucket",
                "credential_values_are_not_read",
            ),
        )
    except Exception:
        raise _fail("object_storage_setup_registration_plan_invalid") from None


def object_storage_setup_registration_context(
    plan: ObjectStorageSetupRegistrationPlan, *, reviewer_claim: str
) -> ExactHumanApprovalContext:
    reviewer = str(reviewer_claim or "").strip()
    if not reviewer:
        raise _fail("object_storage_setup_registration_approval_required")
    return _approval_binding(plan).context(
        archive_id=plan.archive_id, reviewer_claim=reviewer
    )


def _authority_from_claim(
    plan: ObjectStorageSetupRegistrationPlan,
    claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> ExactOperationApprovalAuthority:
    binding = _approval_binding(plan)
    if (
        type(claim) is not _ClaimedExactHumanApproval
        or context.operation is not ExactHumanApprovalOperation.object_storage_setup_registration
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("object_storage_setup_registration_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(claim, context)
        return ExactOperationApprovalAuthority.from_reference(reference)
    except (ExactHumanApprovalError, ExactOperationManifestError):
        raise _fail("object_storage_setup_registration_approval_required") from None


def apply_object_storage_setup_registration(
    plan: ObjectStorageSetupRegistrationPlan,
    *,
    approval_authority: ExactOperationApprovalAuthority,
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_setup_registration_no_writes")
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root, writer_lock=writer_lock
        )
        core = apply_exact_operation(
            plan.manifest,
            payloads=_Payloads(plan),
            writer=_Writer(plan),
            verifier=_Verifier(plan),
            checkpoint_store=checkpoints,
            approval_authority=approval_authority,
            resume=resume,
            progress_hook=progress_hook,
        )
    return {
        "schema_version": RESULT_SCHEMA,
        "ok": core.get("status") == "completed",
        "state": "setup_registration_completed",
        "plan_sha256": plan.plan_sha256,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "execution": core,
        "counts": {
            "provider_binding_field_change_count": int(
                plan.provider_original_bytes != plan.provider_post_bytes
            ),
            "setup_receipt_create_count": int(not plan.receipt_preexisting),
            "exact_manifest_item_count": len(plan.manifest.items),
        },
        "provider_api_called": False,
        "bucket_created": False,
        "bucket_verified": False,
        "credential_value_read": False,
        "files_uploaded": False,
        "private_values_echoed": False,
        "resource_values_echoed": False,
        "paths_echoed": False,
    }


def revert_object_storage_setup_registration(
    plan: ObjectStorageSetupRegistrationPlan,
    *,
    approval_authority: ExactOperationApprovalAuthority,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    if plan.manifest is None:
        raise _fail("object_storage_setup_registration_no_writes")
    selected = [
        (item.item_id, field.field_ref)
        for item in plan.manifest.items
        for field in item.fields
    ]
    with exact_operation_writer_lock(plan.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            plan.archive_root, writer_lock=writer_lock
        )
        return revert_exact_operation_fields(
            plan.manifest,
            selected_fields=selected,
            payloads=_Payloads(plan),
            writer=_Writer(plan),
            verifier=_Verifier(plan),
            checkpoint_store=checkpoints,
            approval_authority=approval_authority,
            progress_hook=progress_hook,
        )


def execute_object_storage_setup_registration(
    plan: ObjectStorageSetupRegistrationPlan,
    *,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
) -> dict[str, Any]:
    context = object_storage_setup_registration_context(
        plan, reviewer_claim=reviewer_claim
    )

    def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
        authority = _authority_from_claim(plan, claim, context)
        # Fail closed if any input changed between dry-run and the native
        # decision.  No provider or credential boundary is crossed here.
        current = plan_object_storage_setup_registration(
            plan.archive_root,
            provider=str(plan.proposed_binding.get("provider_kind") or ""),
            profile_id=_binding_profile_id(plan.proposed_binding),
            profile_slug=str(
                (plan.proposed_binding.get("owner_mapping") or {}).get(
                    "profile_slug", ""
                )
            ),
            storage_account_ref=_binding_account_ref(plan.proposed_binding),
            bucket_name=str(
                (plan.proposed_binding.get("resource") or {}).get("bucket", "")
            ),
            region=str(
                (plan.proposed_binding.get("resource") or {}).get("region", "")
            ),
            endpoint_ref=str(
                (plan.proposed_binding.get("resource") or {}).get(
                    "endpoint_ref", ""
                )
            ),
            objet_prefix=str(
                (plan.proposed_binding.get("resource") or {}).get("prefix", "")
            ),
            visibility=str(
                (plan.proposed_binding.get("resource") or {}).get(
                    "visibility", "private"
                )
            ),
        )
        if (
            current.manifest is None
            or plan.manifest is None
            or not hmac.compare_digest(current.plan_sha256, plan.plan_sha256)
            or current.manifest.document() != plan.manifest.document()
        ):
            raise _fail("object_storage_setup_registration_plan_changed")
        return apply_object_storage_setup_registration(
            current,
            approval_authority=authority,
            progress_hook=progress_hook,
        )

    return _execute_exact_human_approved_write(
        plan.archive_root, context, writer
    )


def _strict_historical_evidence(
    *, root: Path, archive_id: str, binding: dict[str, Any]
) -> ObjectStorageSetupEvidence:
    expected_relative = archive_services.provider_setup_expected_receipt_path(binding)
    if not expected_relative:
        raise _fail("object_storage_setup_evidence_mismatch")
    path = archive_services.archive_internal_path(root, expected_relative)
    raw = _read_bounded(path, maximum=_MAX_RECEIPT_BYTES, missing_ok=True)
    if raw is None:
        raise _fail("object_storage_setup_evidence_missing")
    try:
        receipt = _strict_json(raw)
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise _fail("object_storage_setup_evidence_mismatch") from None
    resource = binding.get("resource")
    bucket = str(resource.get("bucket") or "") if isinstance(resource, Mapping) else ""
    required_keys = {
        "receipt_id",
        "receipt_path",
        "lifecycle_action",
        "provider",
        "provider_kind",
        "dry_run",
        "timestamp",
        "archive_id",
        "profile_id",
        "profile_slug",
        "resource",
        "auth",
        "reviewed_by",
        "external_actions",
        "manual_steps",
    }
    allowed_keys = required_keys | {"result"}
    external = receipt.get("external_actions")
    expected_external_keys = {
        "provider_api_called",
        "bucket_created",
        "oauth_started",
        "files_uploaded",
        "sync_started",
        "files_copied",
        "files_hashed",
        "source_content_imported",
    }
    manual_steps = receipt.get("manual_steps")
    result = receipt.get("result")
    expected_result_keys = {
        "changed_paths",
        "provider_api_called",
        "bucket_created",
        "files_uploaded",
        "sync_started",
        "files_hashed",
    }
    if (
        not required_keys.issubset(receipt)
        or not set(receipt).issubset(allowed_keys)
        or receipt.get("receipt_id")
        != f"receipt:provider-setup:object-storage:{binding.get('provider_kind')}:{bucket}"
        or receipt.get("receipt_path") != expected_relative
        or not isinstance(external, dict)
        or set(external) != expected_external_keys
        or any(value is not False for value in external.values())
        or not isinstance(manual_steps, list)
        or any(not isinstance(value, str) for value in manual_steps)
        or (
            "result" in receipt
            and (
                not isinstance(result, dict)
                or set(result) != expected_result_keys
                or result.get("changed_paths")
                != ["provider-bindings.yml", expected_relative]
                or any(
                    result.get(key) is not False
                    for key in expected_result_keys - {"changed_paths"}
                )
            )
        )
    ):
        raise _fail("object_storage_setup_evidence_mismatch")
    mismatches = archive_services.provider_setup_binding_receipt_mismatches(
        binding,
        receipt,
        receipt_path=expected_relative,
        expected_receipt_path=expected_relative,
        archive_id=archive_id,
    )
    if (
        mismatches
        or receipt.get("lifecycle_action") != "object_storage_setup_plan"
        or receipt.get("provider") != "object_storage"
        or receipt.get("provider_kind") != binding.get("provider_kind")
        or receipt.get("dry_run") is not False
        or not isinstance(receipt.get("reviewed_by"), str)
        or not receipt.get("reviewed_by", "").strip()
        or not isinstance(receipt.get("timestamp"), str)
        or not receipt.get("timestamp", "").strip()
    ):
        raise _fail("object_storage_setup_evidence_mismatch")
    return ObjectStorageSetupEvidence(
        mode="strict_historical_bridge",
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        provider_binding_sha256=_sha(binding),
        receipt_sha256=_sha_bytes(raw),
    )


def validate_object_storage_setup_evidence(
    archive_root: Path | str,
    *,
    provider_kind: str,
    store_ref: str,
) -> ObjectStorageSetupEvidence:
    """Validate setup evidence without provider or credential access."""

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = archive_services.read_archive_id(root)
        document, _raw = _provider_document(root)
    except ObjectStorageSetupRegistrationError:
        raise
    except Exception:
        raise _fail("object_storage_setup_evidence_mismatch") from None
    if document.get("archive_id") != archive_id:
        raise _fail("object_storage_setup_evidence_mismatch")
    bindings = document.get("bindings")
    if not isinstance(bindings, list):
        raise _fail("object_storage_setup_evidence_mismatch")
    provider = str(provider_kind or "").strip().lower()
    store = str(store_ref or "").strip()
    matches = [
        (index, binding)
        for index, binding in enumerate(bindings)
        if isinstance(binding, dict)
        and binding.get("provider") == "object_storage"
        and binding.get("provider_kind") == provider
        and _binding_account_ref(binding) == store
    ]
    if not matches:
        raise _fail("object_storage_setup_evidence_missing")
    if len(matches) != 1:
        raise _fail("object_storage_setup_evidence_mismatch")
    index, binding = matches[0]
    if (
        binding.get("enabled") is not True
        or binding.get("purpose")
        != "objet_storage_metadata_and_manual_setup_plan"
        or not archive_services.safe_object_storage_ref(store)
        or (binding.get("owner_mapping") or {}).get("archive_id") != archive_id
        or not _strict_object_storage_binding(binding, archive_id=archive_id)
    ):
        raise _fail("object_storage_setup_evidence_mismatch")
    binding_sha = _sha(binding)
    relative = _receipt_relative(binding_sha)
    path = archive_services.archive_internal_path(root, relative)
    raw = _read_bounded(path, maximum=_MAX_RECEIPT_BYTES, missing_ok=True)
    if raw is not None:
        expected = _receipt_bytes(
            _receipt_document(
                archive_id=archive_id,
                binding=binding,
                binding_sha256=binding_sha,
            )
        )
        if raw != expected:
            raise _fail("object_storage_setup_evidence_mismatch")
        return ObjectStorageSetupEvidence(
            mode="exact_registration_v1",
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                archive_id
            ),
            provider_binding_sha256=binding_sha,
            receipt_sha256=_sha_bytes(raw),
        )
    return _strict_historical_evidence(
        root=root,
        archive_id=archive_id,
        binding=binding,
    )


__all__ = [
    "ObjectStorageSetupEvidence",
    "ObjectStorageSetupRegistrationError",
    "ObjectStorageSetupRegistrationPlan",
    "apply_object_storage_setup_registration",
    "execute_object_storage_setup_registration",
    "plan_object_storage_setup_registration",
    "revert_object_storage_setup_registration",
    "validate_object_storage_setup_evidence",
]
