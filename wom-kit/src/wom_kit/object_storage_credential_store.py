"""Store object-storage keys in the Windows Credential Manager (v0.4.53, beta letter 177).

The desktop apps keep credentials in the OS keychain: a restart or an update
never loses them and no key passes through the chat. Object-storage writers
already read ``credential-manager:<target>`` refs (exact target only); this
module lets the human enter the access key id and the secret access key in
WOM's native masked popup (the one ``credential-adopt`` uses for Notion) in an
isolated spawned child, writes each to a generic credential with a fixed,
slash-free target name, and returns only the two refs. No key reaches the
parent process, argv, the environment, stdin, a file, stdout or a receipt.

A content-free record under ``profiles/local/credential-intake/object-storage``
says which refs exist; it is a convenience listing, never authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA = "wom-kit/object-storage-credential-store/v1"
RECORD_SCHEMA = "wom-kit/object-storage-credential-record/v1"
RECORD_RELATIVE_DIR = Path("profiles") / "local" / "credential-intake" / "object-storage"
SLUG_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?\Z")
TARGET_RE = re.compile(r"wom-object-storage\.[a-z0-9-]{1,48}\.(?:access-key-id|secret-access-key)\Z")
KEY_KINDS = (
    ("access_key_id", "access-key-id", "Access Key ID"),
    ("secret_access_key", "secret-access-key", "Secret Access Key"),
)
MIN_KEY_BYTES, MAX_KEY_BYTES = 16, 256
CHILD_TIMEOUT_SECONDS = 30 * 60
_CODES = frozenset({
    "object_storage_credential_slug_invalid",
    "object_storage_credential_request_changed",
    "object_storage_credential_windows_required",
    "object_storage_credential_exists",
    "object_storage_credential_cancelled",
    "object_storage_credential_input_invalid",
    "object_storage_credential_write_failed",
    "object_storage_credential_popup_failed",
    "object_storage_credential_worker_failed",
    # v0.4.56 (letter 179): import from the operator's existing key file.
    "object_storage_credential_source_invalid",
    "object_storage_credential_source_field_invalid",
    "object_storage_credential_source_field_missing",
    "object_storage_credential_source_field_ambiguous",
})
SOURCE_MAX_BYTES = 256 * 1024
SOURCE_FIELD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")
_REPARSE_FLAG = 0x400


class ObjectStorageCredentialStoreError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code if code in _CODES else "object_storage_credential_worker_failed"
        super().__init__(self.code)


def _fail(code: str) -> ObjectStorageCredentialStoreError:
    return ObjectStorageCredentialStoreError(code)


def targets(slug: str) -> dict[str, str]:
    if type(slug) is not str or SLUG_RE.fullmatch(slug) is None:
        raise _fail("object_storage_credential_slug_invalid")
    names = {kind: f"wom-object-storage.{slug}.{suffix}" for kind, suffix, _label in KEY_KINDS}
    if any(TARGET_RE.fullmatch(name) is None for name in names.values()):
        raise _fail("object_storage_credential_slug_invalid")
    return names


def refs(slug: str) -> dict[str, str]:
    names = targets(slug)
    return {f"{kind}_ref": "credential-manager:" + names[kind] for kind, _suffix, _label in KEY_KINDS}


def request_sha256(*, archive_id: str, slug: str, replace_existing: bool) -> str:
    document = {"schema": SCHEMA, "archive_id": str(archive_id), "store_slug": slug,
                "replace_existing": bool(replace_existing), "targets": targets(slug)}
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def plan(*, archive_id: str, slug: str, replace_existing: bool) -> dict[str, Any]:
    names = targets(slug)
    return {
        "schema": SCHEMA, "ok": True, "dry_run": True, "store_slug": slug,
        "credential_manager_targets": names, "credential_refs": refs(slug),
        "replace_existing": bool(replace_existing),
        "request_sha256": request_sha256(archive_id=archive_id, slug=slug, replace_existing=replace_existing),
        "popup_count": len(KEY_KINDS), "key_values_echoed": False,
        "next_safe_actions": [
            "Re-run with --approve --expected-request-sha256 <request_sha256>; two masked WOM windows ask "
            "the human for the access key id and the secret access key. Never paste a key into the chat.",
            "Then use credential_refs as --access-key-id-ref / --secret-access-key-ref (or the "
            "activity-cleanup --reconcile --rebind-... flags).",
        ],
    }


def source_binding(path: Path | str) -> dict[str, Any]:
    """Bind the operator-named key file by a digest of its absolute path, size and change time; never its bytes."""

    import stat as _stat

    source = Path(str(path)).expanduser()
    if not source.is_absolute():
        raise _fail("object_storage_credential_source_invalid")
    try:
        info = os.lstat(source)
    except OSError:
        raise _fail("object_storage_credential_source_invalid") from None
    if (_stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_FLAG
            or not _stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= SOURCE_MAX_BYTES):
        raise _fail("object_storage_credential_source_invalid")
    identity = f"{os.path.normcase(str(source.resolve()))}\0{info.st_size}\0{info.st_mtime_ns}"
    return {"source_sha256": "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "source_bytes": int(info.st_size)}


def _validated_fields(access_field: str, secret_field: str) -> tuple[str, str]:
    for value in (access_field, secret_field):
        if type(value) is not str or SOURCE_FIELD_RE.fullmatch(value) is None:
            raise _fail("object_storage_credential_source_field_invalid")
    if access_field == secret_field:
        raise _fail("object_storage_credential_source_field_invalid")
    return access_field, secret_field


def import_request_sha256(*, archive_id: str, slug: str, replace_existing: bool, source: dict[str, Any],
                          access_field: str, secret_field: str) -> str:
    document = {"schema": SCHEMA, "mode": "file_import", "archive_id": str(archive_id), "store_slug": slug,
                "replace_existing": bool(replace_existing), "targets": targets(slug),
                "source_sha256": source["source_sha256"], "fields": [access_field, secret_field]}
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def import_plan(*, archive_id: str, slug: str, replace_existing: bool, source_path: Path | str,
                access_field: str, secret_field: str) -> dict[str, Any]:
    names = targets(slug)
    access_field, secret_field = _validated_fields(access_field, secret_field)
    source = source_binding(source_path)
    return {
        "schema": SCHEMA, "ok": True, "dry_run": True, "mode": "file_import", "store_slug": slug,
        "credential_manager_targets": names, "credential_refs": refs(slug),
        "replace_existing": bool(replace_existing),
        "source": {"kind": "operator_named_file", "path_echoed": False, "bytes": source["source_bytes"],
                   "fields": {"access_key_id": access_field, "secret_access_key": secret_field}},
        "request_sha256": import_request_sha256(archive_id=archive_id, slug=slug, replace_existing=replace_existing,
                                                source=source, access_field=access_field, secret_field=secret_field),
        "popup_count": 0, "key_values_echoed": False, "key_values_read_by_parent": False,
        "next_safe_actions": [
            "Re-run with --approve --expected-request-sha256 <request_sha256> and the same --from-file / field "
            "options; one WOM approval (or this conversation's session grant) lets an isolated process read the two "
            "fields and store them in the Windows Credential Manager. No key reaches the chat, the screen or argv.",
            "Then use credential_refs as --access-key-id-ref / --secret-access-key-ref (or the "
            "activity-cleanup --reconcile --rebind-... flags).",
        ],
    }


def _unquote(value: bytes) -> bytes:
    value = value.strip()
    if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in (b'"', b"'"):
        value = value[1:-1]
    return value


def _extract_fields(raw: bytes, fields: tuple[str, str]) -> list[bytearray]:
    """Two values from a dotenv, INI (``section.key``; rclone.conf) or JSON (dotted path) key file."""

    text = raw.lstrip()
    found: dict[str, list[bytes]] = {field: [] for field in fields}
    if text[:1] == b"{":
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise _fail("object_storage_credential_source_invalid") from None
        for field in fields:
            node: Any = document
            for part in field.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if isinstance(node, str):
                found[field].append(node.encode("utf-8"))
        del document
    else:
        section = ""
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped[:1] in (b"#", b";"):
                continue
            if stripped[:1] == b"[" and stripped[-1:] == b"]":
                section = stripped[1:-1].strip().decode("utf-8", "replace")
                continue
            if stripped.startswith(b"export "):
                stripped = stripped[7:].lstrip()
            separator = min((index for index in (stripped.find(b"="), stripped.find(b":")) if index > 0),
                            default=-1)
            if separator <= 0:
                continue
            key = stripped[:separator].strip().decode("utf-8", "replace")
            value = _unquote(stripped[separator + 1:])
            for field in fields:
                if field == key or (section and field == f"{section}.{key}"):
                    found[field].append(value)
    values: list[bytearray] = []
    for field in fields:
        if not found[field]:
            raise _fail("object_storage_credential_source_field_missing")
        if len({bytes(item) for item in found[field]}) != 1:
            raise _fail("object_storage_credential_source_field_ambiguous")
        values.append(bytearray(found[field][0]))
    return values


def import_from_file(facade: Any, *, slug: str, source_path: str, fields: tuple[str, str],
                     replace_existing: bool) -> dict[str, Any]:
    """Worker core (isolated child): read the operator-named file, check, write exact targets, wipe."""

    names = targets(slug)
    existing = [kind for kind in names if facade.generic_exists(names[kind])]
    if existing and not replace_existing:
        return {"ok": False, "code": "object_storage_credential_exists", "writes_performed": False}
    raw = bytearray()
    buffers: list[bytearray] = []
    written: list[str] = []
    try:
        source_binding(source_path)
        with open(source_path, "rb") as handle:
            raw = bytearray(handle.read(SOURCE_MAX_BYTES + 1))
        if len(raw) > SOURCE_MAX_BYTES:
            return {"ok": False, "code": "object_storage_credential_source_invalid", "writes_performed": False}
        try:
            buffers = _extract_fields(bytes(raw), fields)
        except ObjectStorageCredentialStoreError as exc:
            return {"ok": False, "code": exc.code, "writes_performed": False}
        if not all(_valid_key(buffer) for buffer in buffers):
            return {"ok": False, "code": "object_storage_credential_input_invalid", "writes_performed": False}
        for (kind, _suffix, _label), buffer in zip(KEY_KINDS, buffers):
            facade.write_generic(names[kind], memoryview(buffer))
            written.append(kind)
        if not all(facade.generic_exists(names[kind]) for kind in names):
            raise _fail("object_storage_credential_write_failed")
        return {"ok": True, "code": None, "writes_performed": True, "replaced_existing": bool(existing),
                "stored_kinds": [kind for kind, _s, _l in KEY_KINDS]}
    except Exception:
        for kind in written:
            try:
                facade.delete_generic(names[kind])
            except Exception:
                pass
        return {"ok": False, "code": "object_storage_credential_write_failed",
                "writes_performed": False, "partial_writes_rolled_back": bool(written)}
    finally:
        _wipe(raw)
        for buffer in buffers:
            _wipe(buffer)


def _import_child_entry(connection: Any, slug: str, source_path: str, fields: tuple[str, str],
                        replace_existing: bool) -> None:
    """Spawned child: the only process that ever holds a key value."""
    try:
        status = import_from_file(_ObjectStorageFacade(), slug=slug, source_path=source_path, fields=fields,
                                  replace_existing=replace_existing)
    except Exception:
        status = {"ok": False, "code": "object_storage_credential_worker_failed", "writes_performed": False}
    try:
        connection.send({key: status.get(key) for key in
                         ("ok", "code", "writes_performed", "replaced_existing", "partial_writes_rolled_back")})
    finally:
        connection.close()


def run_isolated_import(*, slug: str, source_path: str, fields: tuple[str, str],
                        replace_existing: bool) -> dict[str, Any]:
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_import_child_entry,
                             args=(sender, slug, str(source_path), tuple(fields), replace_existing), daemon=True)
    worker.start()
    sender.close()
    try:
        if not receiver.poll(300):
            raise _fail("object_storage_credential_worker_failed")
        status = receiver.recv()
    except ObjectStorageCredentialStoreError:
        raise
    except Exception:
        raise _fail("object_storage_credential_worker_failed") from None
    finally:
        receiver.close()
        worker.join(timeout=30)
        if worker.is_alive():
            worker.terminate()
    return status if type(status) is dict else {"ok": False, "code": "object_storage_credential_worker_failed"}


def windows_available() -> bool:
    """The masked window and the Credential Manager exist on Windows only."""
    return os.name == "nt"


def _wipe(buffer: Any) -> None:
    if isinstance(buffer, bytearray):
        for index in range(len(buffer)):
            buffer[index] = 0


def _valid_key(buffer: bytearray) -> bool:
    return (MIN_KEY_BYTES <= len(buffer) <= MAX_KEY_BYTES
            and all(0x21 <= byte <= 0x7E for byte in buffer))


def enroll(facade: Any, *, slug: str, store_label: str, replace_existing: bool,
           request_id_factory: Callable[[], str] | None = None) -> dict[str, Any]:
    """Worker core (runs in the isolated child): popups, checks, exact writes.

    ``facade`` provides ``prompt_masked_secret``, ``generic_exists``,
    ``write_generic`` and ``delete_generic`` (the native Credential Manager
    facade, or a test double). Returns a content-free status mapping.
    """
    from .credential_popup_windows import CredentialPopupContext

    names = targets(slug)
    make_request_id = request_id_factory or (lambda: "intake_" + secrets.token_urlsafe(24))
    existing = [kind for kind in names if facade.generic_exists(names[kind])]
    if existing and not replace_existing:
        return {"ok": False, "code": "object_storage_credential_exists", "writes_performed": False}
    buffers: dict[str, bytearray] = {}
    written: list[str] = []
    try:
        for kind, _suffix, label in KEY_KINDS:
            context = CredentialPopupContext(
                provider="object_storage", purpose="object_storage_" + kind,
                account_label=store_label, workspace_label=label,
                task_summary="원격 저장소(오브젝트 스토리지) 키를 Windows 자격 증명 관리자에 저장",
                connection_reason="업로드·보존 확인·원격 임시물 정리에 쓰는 키를 재시작 뒤에도 쓰도록 보관",
            )
            result = facade.prompt_masked_secret(request_id=make_request_id(), context=context)
            if result.cancelled or not result.complete_line_received or result.secret is None:
                return {"ok": False, "code": "object_storage_credential_cancelled", "writes_performed": False}
            buffers[kind] = result.secret
            if not _valid_key(result.secret):
                return {"ok": False, "code": "object_storage_credential_input_invalid", "writes_performed": False}
        for kind, _suffix, _label in KEY_KINDS:
            facade.write_generic(names[kind], memoryview(buffers[kind]))
            written.append(kind)
        if not all(facade.generic_exists(names[kind]) for kind in names):
            raise _fail("object_storage_credential_write_failed")
        return {"ok": True, "code": None, "writes_performed": True,
                "replaced_existing": bool(existing), "stored_kinds": [kind for kind, _s, _l in KEY_KINDS]}
    except Exception:
        # Never leave a half pair behind: remove what this run wrote.
        for kind in written:
            try:
                facade.delete_generic(names[kind])
            except Exception:
                pass
        return {"ok": False, "code": "object_storage_credential_write_failed",
                "writes_performed": False, "partial_writes_rolled_back": bool(written)}
    finally:
        for buffer in buffers.values():
            _wipe(buffer)


class _ObjectStorageFacade:
    """The native Credential Manager facade, restricted to object-storage targets."""

    def __new__(cls):
        from .credential_secure_intake_windows import _CtypesWindowsNativeFacade

        class Facade(_CtypesWindowsNativeFacade):
            @staticmethod
            def _validated_target(target_name: str) -> str:
                target = str(target_name or "")
                if TARGET_RE.fullmatch(target) is None:
                    raise _fail("object_storage_credential_slug_invalid")
                return target

        return Facade(cli_live_approved=True)


def _child_entry(connection: Any, slug: str, store_label: str, replace_existing: bool) -> None:
    """Spawned child: the only process that ever holds a key value."""
    try:
        status = enroll(_ObjectStorageFacade(), slug=slug, store_label=store_label,
                        replace_existing=replace_existing)
    except Exception:
        status = {"ok": False, "code": "object_storage_credential_popup_failed", "writes_performed": False}
    try:
        connection.send({key: status.get(key) for key in
                         ("ok", "code", "writes_performed", "replaced_existing", "partial_writes_rolled_back")})
    finally:
        connection.close()


def run_isolated(*, slug: str, store_label: str, replace_existing: bool) -> dict[str, Any]:
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_child_entry, args=(sender, slug, store_label, replace_existing), daemon=True)
    worker.start()
    sender.close()
    try:
        if not receiver.poll(CHILD_TIMEOUT_SECONDS):
            raise _fail("object_storage_credential_worker_failed")
        status = receiver.recv()
    except ObjectStorageCredentialStoreError:
        raise
    except Exception:
        raise _fail("object_storage_credential_worker_failed") from None
    finally:
        receiver.close()
        worker.join(timeout=30)
        if worker.is_alive():
            worker.terminate()
    return status if type(status) is dict else {"ok": False, "code": "object_storage_credential_worker_failed"}


def write_record(root: Path, *, slug: str, replaced_existing: bool) -> str:
    directory = Path(root) / RECORD_RELATIVE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    record = {"schema": RECORD_SCHEMA, "store_slug": slug, "credential_manager_targets": targets(slug),
              "credential_refs": refs(slug), "replaced_existing": bool(replaced_existing),
              "stored_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "key_values_recorded": False, "authority": False}
    path = directory / (slug + ".json")
    temporary = directory / (slug + ".json.tmp")
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return (RECORD_RELATIVE_DIR / (slug + ".json")).as_posix()


def list_records(root: Path) -> list[dict[str, Any]]:
    directory = Path(root) / RECORD_RELATIVE_DIR
    rows = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                slug = record.get("store_slug")
                if record.get("schema") == RECORD_SCHEMA and SLUG_RE.fullmatch(str(slug)):
                    rows.append({"store_slug": slug, "credential_refs": refs(slug),
                                 "stored_at": record.get("stored_at")})
            except Exception:
                continue
    return rows
