"""Strict private-objet authority capture for the generated v0.3.297 index.

This module deliberately exposes an internal, non-JSON-serializable result.
Private source records must never become part of a public service result.  The
index compiler receives defensive copies through ``compiler_input`` while the
captured fingerprint and comparison token remain immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any

from . import private_objet_metadata as private_metadata
from . import private_objet_metadata_writer as writer
from . import private_objet_metadata_writer_contract as contract


AUTHORITY_FINGERPRINT_SCHEMA = (
    "wom-kit/private-objet-authority-fingerprint/v0.1"
)
GENERATED_SCHEMA = "wom-kit/private-objet-generated-index/v0.1"
GENERATED_SCHEMA_MANIFEST_SCHEMA = (
    "wom-kit/private-objet-generated-schema-manifest/v0.1"
)

SOURCE_SCHEMA_SHA256 = (
    "sha256:c5f2aae02b068bca976ed256e45bea33c8ec44e004df89adc4e15113c09c2150"
)
NORMALIZATION_PROFILE_SHA256 = (
    "sha256:efd98c04a3adbbabb6907b94f3cb0646be635f2f317d417ce79ba9befb58514c"
)
NORMALIZATION_HELPER_SHA256 = (
    "sha256:79081fd211d06705b06fe2123271c135bc6e9c4af2de5dc3331eddd51fb592c2"
)
UNICODE_TABLE_SHA256 = (
    "sha256:62ad6ed6e49d5d4fe811907822fbff5949a0b86693c36c4196743cfcda06b036"
)
PROJECTION_SCHEMA_SHA256 = (
    "sha256:baf23a8c453ffd61d32a9d6a7b9cf2024073d91aa821e7712190c28374952d66"
)
RECEIPT_SCHEMA_SHA256 = (
    "sha256:d56f48ba45094b9bd7fecebf3739700ecd7e4e02f607d709101e02bcf6dd0149"
)
AUTHORITY_CHAIN_SCHEMA_SHA256 = (
    "sha256:b9704fabf8c718b79f21497cb4c163bb89eecc7ca7620f297a63c402e7155da9"
)
WRITER_CONTRACT_SOURCE_SHA256 = (
    "sha256:55f8b4bc23a146640669c231c9a1808de0458c420db95c4e40a9155f36403860"
)
GENERATED_SCHEMA_MANIFEST_SHA256 = (
    "sha256:a521cf945384ea8cb653fb39fdfec38821e6e0c549f4a2d57af4acb1dc89ef0a"
)
EMPTY_SHA256 = (
    "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)

_RECEIPT_RELATIVE_ROOT = "receipts/objects/private-source-metadata"
_RECEIPT_BASENAME = re.compile(r"^[0-9a-f]{64}\.json$")
_REPARSE_ATTRIBUTE = 0x400
_COMPARISON_SCHEMA = (
    "wom-kit/private-objet-index-authority-comparison/v0.1"
)

_NORMALIZATION_PROFILE = {
    "id": "wom-kit/filename-normalization/v0.1",
    "unicode_version": "17.0.0",
    "confusables_data_sha256": None,
    "confusable_status": "not_checked",
}

_PINNED_PACKAGE_FILES = (
    (
        "private_objet_metadata.py",
        NORMALIZATION_HELPER_SHA256,
    ),
    (
        "private_objet_metadata_writer_contract.py",
        WRITER_CONTRACT_SOURCE_SHA256,
    ),
    (
        "_unicode17_tables.py",
        UNICODE_TABLE_SHA256,
    ),
    (
        "_resources/schemas/private-objet-source-metadata-v0.1.schema.json",
        SOURCE_SCHEMA_SHA256,
    ),
    (
        "_resources/schemas/objet-safe-label-projection-v0.1.schema.json",
        PROJECTION_SCHEMA_SHA256,
    ),
    (
        "_resources/schemas/"
        "private-objet-source-metadata-write-receipt-v0.1.schema.json",
        RECEIPT_SCHEMA_SHA256,
    ),
    (
        "_resources/schemas/"
        "private-objet-source-metadata-authority-chain-v0.1.schema.json",
        AUTHORITY_CHAIN_SCHEMA_SHA256,
    ),
    (
        "_resources/schemas/private-objet-generated-schema-manifest-v0.1.json",
        GENERATED_SCHEMA_MANIFEST_SHA256,
    ),
)

_INVALID_REASONS = frozenset(
    {
        "authority_state_invalid",
        "duplicate_authority_identity",
        "journal_present",
        "orphan_or_missing_receipt",
        "receipt_semantic_mismatch",
        "receipt_inventory_invalid",
        "receipt_inventory_mismatch",
        "invalid_archive_id",
    }
)


class PrivateObjetAuthorityError(RuntimeError):
    """Closed private-authority failure with no path or private data."""

    def __init__(self, code: str, validity: str) -> None:
        if validity not in {"blocked", "invalid"}:
            raise ValueError("invalid closed authority validity")
        if code not in {
            "private_objet_metadata_authority_blocked",
            "private_objet_metadata_authority_invalid",
        }:
            raise ValueError("invalid closed authority error code")
        self.code = code
        self.validity = validity
        super().__init__(code)


@dataclass(frozen=True)
class _PrivateObjetIndexAuthorityCapture:
    """Immutable internal capture; private values are held as canonical bytes."""

    _compiler_input_bytes: bytes = field(repr=False)
    _fingerprint_bytes: bytes = field(repr=False)
    fingerprint_sha256: str
    comparison_token: tuple[str, str, str]

    @property
    def compiler_input(self) -> dict[str, Any]:
        """Return a fresh compiler input on every access."""

        return json.loads(self._compiler_input_bytes)

    def as_compiler_input(self) -> dict[str, Any]:
        return self.compiler_input

    @property
    def observations(self) -> list[dict[str, Any]]:
        return self.compiler_input["observations"]

    @property
    def fingerprint_bytes(self) -> bytes:
        return bytes(self._fingerprint_bytes)

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return json.loads(self._fingerprint_bytes)

    @property
    def private_manifest_state(self) -> str:
        return self.compiler_input["private_manifest_state"]

    @property
    def receipt_inventory_state(self) -> str:
        return self.compiler_input["receipt_inventory_state"]

    @property
    def object_manifest_state(self) -> str:
        return self.compiler_input["object_manifest_state"]

    @property
    def writer_journal_state(self) -> str:
        return self.compiler_input["writer_journal_state"]


@dataclass(frozen=True)
class _ReceiptInventory:
    state: str
    entries: tuple[tuple[str, str], ...]
    inventory_sha256: str
    builder_inventory: tuple[tuple[str, int], ...]
    identity_material: tuple[tuple[Any, ...], ...]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _inventory_bytes(entries: list[list[str]]) -> bytes:
    ordered = sorted(entries, key=lambda item: item[0].encode("utf-8"))
    return b"\n".join(_canonical_json_bytes(item) for item in ordered)


def _stat_identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


def _stat_token(info: os.stat_result) -> tuple[int, ...]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_mode),
        int(info.st_nlink),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
        int(getattr(info, "st_file_attributes", 0)),
    )


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        int(getattr(info, "st_file_attributes", 0))
        & _REPARSE_ATTRIBUTE
    )


def _path_token(path: Path) -> tuple[Any, ...]:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return ("absent",)
    return ("present",) + _stat_token(info)


def _closed_error(validity: str) -> PrivateObjetAuthorityError:
    return PrivateObjetAuthorityError(
        f"private_objet_metadata_authority_{validity}",
        validity,
    )


def _verify_package_pins() -> None:
    package_root = Path(private_metadata.__file__).parent
    for relative, expected in _PINNED_PACKAGE_FILES:
        path = package_root.joinpath(*PurePosixPath(relative).parts)
        try:
            raw = path.read_bytes()
        except OSError:
            raise writer._SnapshotError("package_pin_unavailable") from None
        if _sha256(raw) != expected:
            raise writer._SnapshotError("package_pin_mismatch")
    if contract.NORMALIZATION_PROFILE_VALUE != _NORMALIZATION_PROFILE:
        raise writer._SnapshotError("package_pin_mismatch")


def _validate_root_and_archive_id(
    root: Path,
    archive_id: str,
) -> tuple[Path, tuple[Any, ...]]:
    if (
        type(archive_id) is not str
        or not 1 <= len(archive_id) <= 200
        or any(0xD800 <= ord(char) <= 0xDFFF for char in archive_id)
        or "/" in archive_id
        or "\\" in archive_id
    ):
        raise writer._SnapshotError("invalid_archive_id")
    root = root.absolute()
    try:
        info = os.lstat(root)
    except OSError:
        raise writer._SnapshotError("unavailable") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        raise writer._SnapshotError("unsafe")
    try:
        canonical_root = root.resolve(strict=True)
        canonical_info = os.lstat(canonical_root)
    except OSError:
        raise writer._SnapshotError("unavailable") from None
    if (
        not stat.S_ISDIR(canonical_info.st_mode)
        or stat.S_ISLNK(canonical_info.st_mode)
        or _is_reparse(canonical_info)
        or _stat_identity(canonical_info) != _stat_identity(info)
    ):
        raise writer._SnapshotError("unsafe")
    root = canonical_root
    return root, _path_token(root)


def _strict_receipt_inventory(root: Path) -> _ReceiptInventory:
    from . import archive_services as services

    before, _ = writer._observe_receipt_directory_chain(root)
    directory_state = before["private_receipt_directory"]["state"]
    if directory_state == "absent":
        return _ReceiptInventory(
            state="absent",
            entries=(),
            inventory_sha256=EMPTY_SHA256,
            builder_inventory=(),
            identity_material=(),
        )

    directory = root.joinpath(*PurePosixPath(_RECEIPT_RELATIVE_ROOT).parts)
    entries: list[list[str]] = []
    builder_inventory: list[tuple[str, int]] = []
    identities: list[tuple[Any, ...]] = []
    total_bytes = 0
    entries_seen = 0
    try:
        with services._bound_directory_chain(root, directory) as binding:
            with services._scan_bound_directory(binding) as scanned:
                for entry in scanned:
                    entries_seen += 1
                    if entries_seen > writer.PRIVATE_RECEIPT_DIR_MAX_ENTRIES:
                        raise writer._SnapshotError(
                            "receipt_directory_entries_limit"
                        )
                    name = entry.name
                    try:
                        # ``DirEntry.stat`` obtained from a Windows directory
                        # descriptor can expose zeroed identity/link fields.
                        # The retained directory chain makes this path lstat
                        # safe while preserving the real Win32 identity.
                        info = os.lstat(directory / name)
                    except OSError:
                        raise writer._SnapshotError(
                            "directory_unavailable"
                        ) from None
                    if (
                        _RECEIPT_BASENAME.fullmatch(name) is None
                    ):
                        raise writer._SnapshotError(
                            "receipt_inventory_invalid"
                        )
                    if (
                        entry.is_symlink()
                        or not stat.S_ISREG(info.st_mode)
                        or _is_reparse(info)
                        or int(info.st_nlink) != 1
                    ):
                        raise writer._SnapshotError("unsafe")
                    size = int(info.st_size)
                    if size > writer.PRIVATE_RECEIPT_MAX_BYTES:
                        raise writer._SnapshotError("receipt_bytes_limit")
                    relative = f"{_RECEIPT_RELATIVE_ROOT}/{name}"
                    snapshot, document = writer._observe_receipt(
                        root,
                        relative,
                    )
                    if (
                        snapshot.state.get("state") != "present"
                        or snapshot.state.get("link_count") != 1
                        or snapshot.identity != _stat_identity(info)
                        or snapshot.raw is None
                        or document is None
                    ):
                        raise writer._SnapshotError(
                            "receipt_inventory_invalid"
                        )
                    try:
                        after = os.lstat(snapshot.path)
                    except OSError:
                        raise writer._SnapshotError(
                            "unstable_authority"
                        ) from None
                    if _stat_token(after) != _stat_token(info):
                        raise writer._SnapshotError("unstable_authority")
                    digest = _sha256(snapshot.raw)
                    if digest != snapshot.state.get("sha256"):
                        raise writer._SnapshotError(
                            "receipt_inventory_invalid"
                        )
                    entries.append([relative, digest])
                    builder_inventory.append((name, size))
                    identities.append(
                        (relative, digest) + _stat_token(after)
                    )
                    if len(entries) > writer.PRIVATE_RECEIPT_MAX_COUNT:
                        raise writer._SnapshotError("receipt_count_limit")
                    total_bytes += size
                    if total_bytes > writer.PRIVATE_RECEIPT_TOTAL_BYTES_MAX:
                        raise writer._SnapshotError(
                            "receipt_total_bytes_limit"
                        )
    except writer._SnapshotError:
        raise
    except (OSError, ValueError):
        raise writer._SnapshotError("directory_unavailable") from None

    entries.sort(key=lambda item: item[0].encode("utf-8"))
    builder_inventory.sort(key=lambda item: item[0].encode("utf-8"))
    identities.sort(key=lambda item: str(item[0]).encode("utf-8"))
    raw_inventory = _inventory_bytes(entries)
    state = "present_nonempty" if entries else "present_empty"
    return _ReceiptInventory(
        state=state,
        entries=tuple((item[0], item[1]) for item in entries),
        inventory_sha256=_sha256(raw_inventory),
        builder_inventory=tuple(builder_inventory),
        identity_material=tuple(identities),
    )


def _fingerprint_payload(
    *,
    private_manifest_state: str,
    private_manifest_sha256: str | None,
    private_manifest_bytes: int,
    private_manifest_rows: int,
    receipt_inventory: _ReceiptInventory,
    object_manifest_state: str,
    object_manifest_sha256: str | None,
    object_manifest_bytes: int,
    object_manifest_rows: int,
) -> dict[str, Any]:
    private_marker = {
        "absent": "wom-kit/private-manifest/absent/v0.1",
        "present_nonempty": None,
    }[private_manifest_state]
    receipt_marker = {
        "absent": "wom-kit/receipt-inventory/absent/v0.1",
        "present_empty": (
            "wom-kit/receipt-inventory/present-empty/v0.1"
        ),
        "present_nonempty": None,
    }[receipt_inventory.state]
    object_marker = {
        "not_applicable_zero_private_rows": (
            "wom-kit/object-manifest/"
            "not-applicable-zero-private-rows/v0.1"
        ),
        "present": None,
    }[object_manifest_state]
    return {
        "schema": AUTHORITY_FINGERPRINT_SCHEMA,
        "private_manifest": {
            "state": private_manifest_state,
            "state_marker": private_marker,
            "sha256": private_manifest_sha256,
            "byte_count": private_manifest_bytes,
            "row_count": private_manifest_rows,
        },
        "receipt_inventory": {
            "state": receipt_inventory.state,
            "state_marker": receipt_marker,
            "entries": [list(item) for item in receipt_inventory.entries],
            "inventory_sha256": receipt_inventory.inventory_sha256,
            "count": len(receipt_inventory.entries),
        },
        "object_manifest": {
            "state": object_manifest_state,
            "state_marker": object_marker,
            "sha256": object_manifest_sha256,
            "byte_count": object_manifest_bytes,
            "row_count": object_manifest_rows,
        },
        "source_schema": {
            "id": private_metadata.PRIVATE_METADATA_SCHEMA,
            "sha256": SOURCE_SCHEMA_SHA256,
        },
        "normalization": {
            "profile_id": _NORMALIZATION_PROFILE["id"],
            "profile": _NORMALIZATION_PROFILE,
            "profile_sha256": NORMALIZATION_PROFILE_SHA256,
            "helper_sha256": NORMALIZATION_HELPER_SHA256,
            "unicode_version": "17.0.0",
            "unicode_table_sha256": UNICODE_TABLE_SHA256,
        },
        "projection_schema": {
            "id": "wom-kit/objet-safe-label-projection/v0.1",
            "sha256": PROJECTION_SCHEMA_SHA256,
        },
        "receipt_schema": {
            "id": contract.RECEIPT_SCHEMA,
            "sha256": RECEIPT_SCHEMA_SHA256,
        },
        "authority_chain_schema": {
            "id": contract.AUTHORITY_CHAIN_SCHEMA,
            "sha256": AUTHORITY_CHAIN_SCHEMA_SHA256,
        },
        "writer_contract": {
            "source_sha256": WRITER_CONTRACT_SOURCE_SHA256,
        },
        "generated_schema": {
            "id": GENERATED_SCHEMA,
            "manifest_schema_id": GENERATED_SCHEMA_MANIFEST_SCHEMA,
            "manifest_sha256": GENERATED_SCHEMA_MANIFEST_SHA256,
        },
        "writer_journal": {
            "state": "absent",
            "state_marker": (
                "wom-kit/private-writer-journal/absent/v0.1"
            ),
        },
    }


def _authority_path_tokens(
    root: Path,
    *,
    include_object_manifest: bool,
) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    relatives = [
        "objects",
        "objects/manifests",
        contract.PRIVATE_MANIFEST_PATH,
        contract.JOURNAL_PATH,
        "receipts",
        "receipts/objects",
        _RECEIPT_RELATIVE_ROOT,
    ]
    if include_object_manifest:
        relatives.append(contract.OBJECT_MANIFEST_PATH)
    return tuple(
        (
            relative,
            _path_token(root.joinpath(*PurePosixPath(relative).parts)),
        )
        for relative in relatives
    )


def _capture(
    root: Path,
    archive_id: str,
) -> _PrivateObjetIndexAuthorityCapture:
    _verify_package_pins()
    root, root_token = _validate_root_and_archive_id(root, archive_id)

    private_snapshot, rows, stored_rows = writer._observe_private_manifest(root)
    private_state = private_snapshot.state.get("state")
    if private_state == "absent":
        if rows or stored_rows or private_snapshot.raw is not None:
            raise writer._SnapshotError("authority_state_invalid")
        private_manifest_state = "absent"
        private_sha256 = None
        private_bytes = 0
        private_rows = 0
    elif private_state == "present" and rows:
        if (
            private_snapshot.raw is None
            or len(rows) != len(stored_rows)
            or private_snapshot.state.get("row_count") != len(rows)
        ):
            raise writer._SnapshotError("authority_state_invalid")
        private_manifest_state = "present_nonempty"
        private_sha256 = private_snapshot.state["sha256"]
        private_bytes = int(private_snapshot.state["byte_count"])
        private_rows = len(rows)
    else:
        raise writer._SnapshotError("authority_state_invalid")

    include_object = private_rows > 0
    path_tokens_before = _authority_path_tokens(
        root,
        include_object_manifest=include_object,
    )

    journal_snapshot, journal_document = writer._observe_journal(root)
    if (
        journal_snapshot.state.get("state") != "absent"
        or journal_document is not None
    ):
        raise writer._SnapshotError("journal_present")

    inventory = _strict_receipt_inventory(root)

    observations: list[dict[str, Any]] = []
    object_snapshot: writer._FileSnapshot | None = None
    object_prefix: writer._ObjectManifestPrefixAuthority | None = None
    if private_rows == 0:
        if inventory.entries:
            raise writer._SnapshotError("orphan_or_missing_receipt")
        object_manifest_state = "not_applicable_zero_private_rows"
        object_sha256 = None
        object_bytes = 0
        object_rows = 0
    else:
        if (
            inventory.state != "present_nonempty"
            or len(inventory.entries) != private_rows
        ):
            raise writer._SnapshotError("orphan_or_missing_receipt")
        object_snapshot, object_prefix, _ = writer._observe_object_manifest(
            root,
            rows[0]["object_id"],
        )
        writer._build_complete_authority_chain(
            root,
            rows,
            stored_rows,
            private_manifest_state=private_snapshot.state,
            inventory=list(inventory.builder_inventory),
            archive_id=archive_id,
            object_manifest=object_snapshot,
            object_manifest_prefix_authority=object_prefix,
        )
        receipt_by_relative = dict(inventory.entries)
        for ordinal, row in enumerate(rows, start=1):
            evidence = row["source_provenance"][
                "observation_evidence_sha256"
            ]
            authority_key = contract.authority_key_sha256(evidence)
            relative = contract.receipt_relative_path(authority_key)
            observations.append(
                {
                    "manifest_row_ordinal": ordinal,
                    "authority_key_sha256": authority_key,
                    "canonical_row_sha256": contract.sha256_digest(
                        contract.canonical_json_bytes(row)
                    ),
                    "receipt_sha256": receipt_by_relative[relative],
                    "source_record": row,
                }
            )
        object_manifest_state = "present"
        object_sha256 = object_snapshot.state["sha256"]
        object_bytes = int(object_snapshot.state["byte_count"])
        object_rows = int(object_snapshot.state["row_count"])

    # A final independent observation makes a successful capture internally
    # stable even before the outer A/B lock-session comparison.
    final_private, final_rows, final_stored = writer._observe_private_manifest(
        root
    )
    if (
        final_private.raw != private_snapshot.raw
        or final_private.identity != private_snapshot.identity
        or final_private.state != private_snapshot.state
        or final_rows != rows
        or final_stored != stored_rows
    ):
        raise writer._SnapshotError("unstable_authority")
    final_inventory = _strict_receipt_inventory(root)
    if final_inventory != inventory:
        raise writer._SnapshotError("unstable_authority")
    if include_object:
        assert object_snapshot is not None
        final_object, _, _ = writer._observe_object_manifest(
            root,
            rows[0]["object_id"],
        )
        if (
            final_object.raw != object_snapshot.raw
            or final_object.identity != object_snapshot.identity
            or final_object.state != object_snapshot.state
        ):
            raise writer._SnapshotError("unstable_authority")
    final_journal, final_journal_document = writer._observe_journal(root)
    if (
        final_journal.state.get("state") != "absent"
        or final_journal_document is not None
    ):
        raise writer._SnapshotError("unstable_authority")

    path_tokens_after = _authority_path_tokens(
        root,
        include_object_manifest=include_object,
    )
    if (
        root_token != _path_token(root)
        or path_tokens_before != path_tokens_after
    ):
        raise writer._SnapshotError("unstable_authority")

    compiler_input = {
        "observations": observations,
        "private_manifest_state": private_manifest_state,
        "private_manifest_sha256": private_sha256,
        "private_manifest_bytes": private_bytes,
        "private_manifest_rows": private_rows,
        "receipt_inventory_state": inventory.state,
        "receipt_inventory_entries": [
            list(item) for item in inventory.entries
        ],
        "receipt_inventory_sha256": inventory.inventory_sha256,
        "receipt_count": len(inventory.entries),
        "object_manifest_state": object_manifest_state,
        "object_manifest_sha256": object_sha256,
        "object_manifest_bytes": object_bytes,
        "object_manifest_rows": object_rows,
        "writer_journal_state": "absent",
    }
    fingerprint_bytes = _canonical_json_bytes(
        _fingerprint_payload(
            private_manifest_state=private_manifest_state,
            private_manifest_sha256=private_sha256,
            private_manifest_bytes=private_bytes,
            private_manifest_rows=private_rows,
            receipt_inventory=inventory,
            object_manifest_state=object_manifest_state,
            object_manifest_sha256=object_sha256,
            object_manifest_bytes=object_bytes,
            object_manifest_rows=object_rows,
        )
    )
    fingerprint_sha256 = _sha256(fingerprint_bytes)
    identity_bytes = _canonical_json_bytes(
        {
            "root": root_token,
            "paths": path_tokens_after,
            "receipts": inventory.identity_material,
            "private_file": private_snapshot.identity,
            "object_file": (
                object_snapshot.identity
                if object_snapshot is not None
                else None
            ),
        }
    )
    comparison_token = (
        _COMPARISON_SCHEMA,
        fingerprint_sha256,
        _sha256(identity_bytes),
    )
    return _PrivateObjetIndexAuthorityCapture(
        _compiler_input_bytes=_canonical_json_bytes(compiler_input),
        _fingerprint_bytes=fingerprint_bytes,
        fingerprint_sha256=fingerprint_sha256,
        comparison_token=comparison_token,
    )


def _capture_private_objet_index_authority(
    root: Path,
    archive_id: str,
) -> _PrivateObjetIndexAuthorityCapture:
    """Capture one strict whole-authority snapshot or fail closed."""

    try:
        return _capture(Path(root), archive_id)
    except PrivateObjetAuthorityError:
        raise
    except writer._SnapshotError as exc:
        validity = "invalid" if exc.reason in _INVALID_REASONS else "blocked"
        raise _closed_error(validity) from None
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise _closed_error("invalid") from None
    except OSError:
        raise _closed_error("blocked") from None


__all__ = [
    "PrivateObjetAuthorityError",
]
