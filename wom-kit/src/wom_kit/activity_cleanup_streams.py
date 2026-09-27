"""Native Windows ADS preservation. Stream names stay in private evidence.

The base file and every named data stream remain held while observed or copied.
The bundle contains ADS bytes plus an exact body digest, not a claim that the
body itself was backed up. Callers must preserve both objects before deletion.
"""
from contextlib import contextmanager, ExitStack
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
import zipfile

from . import legacy_cleanup_bound_delete as bound

SCHEMA = "wom-kit/windows-stream-bundle/v1"
SHA = re.compile(r"[a-f0-9]{64}\Z")


def _fail(code="activity_cleanup_streams_changed"):
    from .activity_cleanup import ActivityCleanupError
    return ActivityCleanupError(code)


def _name(value):
    if (type(value) is not str or not value.startswith(":") or not value.endswith(":$DATA")
            or not value[1:-6] or any(c in value[1:-6] for c in ":/\\\0")
            or len(value.encode("utf-16-le")) > 65534):
        raise _fail("activity_cleanup_stream_name_unsupported")
    return value


def validate(rows):
    if type(rows) is not list or len(rows) > 4096:
        raise _fail("activity_cleanup_stream_inventory_invalid")
    names = []
    for row in rows:
        if (type(row) is not dict or set(row) != {"name", "size", "sha256"}
                or type(row["size"]) is not int or not 0 <= row["size"] <= 8 * 1024**3
                or type(row["sha256"]) is not str or not SHA.fullmatch(row["sha256"])):
            raise _fail("activity_cleanup_stream_inventory_invalid")
        names.append(_name(row["name"]))
    if names != sorted(set(names)) or len({v.casefold() for v in names}) != len(names):
        raise _fail("activity_cleanup_stream_inventory_invalid")
    return rows


def _open(path, name):
    api = bound._windows_api()
    handle = api.create_file(bound._windows_extended_path(path) + _name(name),
        api.GENERIC_READ | api.FILE_READ_ATTRIBUTES, api.FILE_SHARE_READ | 4,
        None, api.OPEN_EXISTING, api.FILE_FLAG_OPEN_REPARSE_POINT, None)
    value = handle if isinstance(handle, int) else getattr(handle, "value", None)
    if value in {None, api.invalid_handle}:
        raise _fail("activity_cleanup_stream_open_uncertain")
    return int(value)


def _chunks(handle):
    api = bound._windows_api()
    position = ctypes.c_longlong()
    if not api.set_pointer(handle, 0, ctypes.byref(position), 0):
        raise _fail("activity_cleanup_stream_read_uncertain")
    while True:
        buffer = ctypes.create_string_buffer(1024 * 1024)
        count = api.DWORD()
        if not api.read_file(handle, buffer, len(buffer), ctypes.byref(count), None):
            raise _fail("activity_cleanup_stream_read_uncertain")
        if not count.value:
            return
        yield buffer.raw[:count.value]


def _state(name, handle):
    api = bound._windows_api()
    before = api.query(handle)
    digest, size = hashlib.sha256(), 0
    for chunk in _chunks(handle):
        digest.update(chunk)
        size += len(chunk)
        if size > 8 * 1024**3:
            raise _fail("activity_cleanup_stream_too_large")
    if api.query(handle) != before or size != before.size:
        raise _fail()
    return {"name": name, "size": size, "sha256": digest.hexdigest()}


@contextmanager
def hold(path, body_state, *, base_handle=None, expected=None):
    """Hold and verify every stream; an existing deletion handle may own body."""
    if os.name != "nt":
        raise _fail("activity_cleanup_streams_native_required")
    path = Path(path)
    approved = bound._approved_file(body_state)
    own_base = base_handle is None
    handles = {}
    parents = ExitStack()
    try:
        parents.enter_context(bound._activity_group_bound_directory_chain(Path(path.anchor), path.parent))
        if own_base:
            base_handle = bound._windows_open(path, directory=False)
        bound._validate_windows_named_file(path, approved)
        bound._windows_digest_handle(base_handle, approved, expected_link_count=1)
        names = sorted(bound._windows_stream_names(base_handle, directory=False))
        if "::$DATA" not in names or len(set(names)) != len(names):
            raise _fail("activity_cleanup_stream_inventory_invalid")
        names.remove("::$DATA")
        for name in names:
            handles[_name(name)] = _open(path, name)
            info = bound._windows_api().query(handles[name])
            if (info.volume_serial, info.file_index) != (bound._windows_volume_serial_from_stat_device(approved.device), approved.inode):
                raise _fail()
        rows = [_state(name, handle) for name, handle in handles.items()]
        validate(rows)
        if expected is not None and rows != validate(expected):
            raise _fail()

        def verify(*, after_delete=False):
            if sorted(bound._windows_stream_names(base_handle, directory=False)) != sorted(["::$DATA", *handles]):
                raise _fail()
            if [_state(name, handle) for name, handle in handles.items()] != rows:
                raise _fail()
            bound._windows_digest_handle(base_handle, approved, expected_link_count=0 if after_delete else 1)

        verify()
        yield rows, handles, verify
    finally:
        try:
            if own_base and base_handle is not None:
                parents.callback(bound._windows_close, base_handle)
            for handle in handles.values():
                parents.callback(bound._windows_close, handle)
        finally:
            parents.close()


def inventory(path, body_state):
    if os.name != "nt":
        return []
    with hold(path, body_state) as (rows, _handles, verify):
        verify()
        return rows


def build_bundle(path, body_state, streams, destination):
    """Create an exact new bundle. Existing destinations are never replaced."""
    validate(streams)
    destination = Path(destination)
    if destination.exists():
        verify_bundle(destination, body_state, streams)
        return destination
    from .object_storage_restore import _atomic_move_file_no_replace
    partial = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".partial")
    with hold(path, body_state, expected=streams) as (_rows, handles, verify):
        with partial.open("xb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                manifest = {"schema": SCHEMA, "body_sha256": body_state["sha256"],
                            "body_size": body_state["size"], "streams": streams}
                archive.writestr(zipfile.ZipInfo("manifest.json"), json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode())
                for ordinal, row in enumerate(streams):
                    with archive.open(zipfile.ZipInfo(f"streams/{ordinal:04d}"), "w", force_zip64=True) as sink:
                        for chunk in _chunks(handles[row["name"]]):
                            sink.write(chunk)
                verify()
            output.flush()
            os.fsync(output.fileno())
    verify_bundle(partial, body_state, streams)
    _atomic_move_file_no_replace(partial, destination)
    return destination


def verify_bundle(path, body_state, streams):
    validate(streams)
    from .activity_cleanup import _safe_path
    _safe_path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            expected_names = ["manifest.json", *(f"streams/{i:04d}" for i in range(len(streams)))]
            if archive.namelist() != expected_names or archive.getinfo("manifest.json").file_size > 4 * 1024**2:
                raise _fail("activity_cleanup_stream_bundle_invalid")
            if json.loads(archive.read("manifest.json")) != {"schema": SCHEMA, "body_sha256": body_state["sha256"],
                    "body_size": body_state["size"], "streams": streams}:
                raise _fail("activity_cleanup_stream_bundle_invalid")
            for ordinal, row in enumerate(streams):
                name = f"streams/{ordinal:04d}"
                if archive.getinfo(name).file_size != row["size"]:
                    raise _fail("activity_cleanup_stream_bundle_invalid")
                digest, size = hashlib.sha256(), 0
                with archive.open(name) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(chunk)
                        if size > row["size"]:
                            raise _fail("activity_cleanup_stream_bundle_invalid")
                        digest.update(chunk)
                if digest.hexdigest() != row["sha256"] or size != row["size"]:
                    raise _fail("activity_cleanup_stream_bundle_invalid")
    except (zipfile.BadZipFile, ValueError, KeyError):
        raise _fail("activity_cleanup_stream_bundle_invalid") from None


def restore_new(body, bundle, destination, body_state, streams, *, before_publish=None):
    """Restore both into a new file; publish only after native stream readback."""
    from . import archive_services as services
    body, bundle, destination = Path(body), Path(bundle), Path(destination)
    if os.name != "nt":
        raise _fail("activity_cleanup_streams_native_required")
    with ExitStack() as held:
        held.enter_context(services._activity_group_bound_directory_chain(Path(destination.anchor), destination.parent))
        for source in (body, bundle):
            parent = held.enter_context(services._bound_directory_chain(Path(source.anchor), source.parent))
            held.enter_context(services._hold_bound_regular_file(parent, source, os.lstat(source)))
        return _restore_new_held(body, bundle, destination, body_state, streams, before_publish=before_publish)


def _restore_new_held(body, bundle, destination, body_state, streams, *, before_publish=None):
    from .activity_cleanup import _safe_path, file_state
    from .object_storage_restore import _atomic_move_file_no_replace
    if os.name != "nt":
        raise _fail("activity_cleanup_streams_native_required")
    body, destination = _safe_path(body), Path(destination)
    _safe_path(destination.parent)
    if os.path.lexists(destination):
        raise _fail("activity_cleanup_restore_destination_exists")
    actual = file_state(body)
    if any(actual[key] != body_state[key] for key in ("sha256", "size")):
        raise _fail("activity_cleanup_restore_body_changed")
    verify_bundle(bundle, body_state, streams)
    temporary = destination.parent / (".wom-restore-" + uuid.uuid4().hex + ".partial")
    # On failure keep the owned partial as evidence; never substitute a partial
    # for the requested final file or overwrite a pre-existing file.
    with temporary.open("xb") as output, body.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    with zipfile.ZipFile(bundle) as archive:
        for ordinal, row in enumerate(streams):
            with open(str(temporary) + _name(row["name"]), "xb") as output, archive.open(f"streams/{ordinal:04d}") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
    restored = file_state(temporary)
    if any(restored[key] != body_state[key] for key in ("sha256", "size")) or inventory(temporary, restored) != streams:
        raise _fail("activity_cleanup_restore_verification_failed")
    if before_publish is not None:
        before_publish(temporary, restored)
    _atomic_move_file_no_replace(temporary, destination)
    final = file_state(destination)
    if any(final[key] != body_state[key] for key in ("sha256", "size")) or inventory(destination, final) != streams:
        raise _fail("activity_cleanup_restore_verification_failed")
    return {"ok": True, "body_verified": True, "alternate_streams_verified": len(streams), "new_file_created": True}
