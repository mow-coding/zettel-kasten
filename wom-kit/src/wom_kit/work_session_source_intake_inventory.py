"""Bounded original-context hints, never authenticated intake provenance.

Only the fixed private context directory is visited. Published and pending
leaves both contribute to its complete generation; pending leaves are never
returned as context hints. No JSON bodies, approvals or source files are read
semantically, and no directory, key, claim, receipt or index is created.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat

from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import work_session_bundle as controls
from . import work_session_source_intake_bundle as bundle


MAX_CONTEXT_DIRECTORY_ENTRIES = 128
MAX_CONTEXT_INVENTORY_BYTES = 32 * 1024 * 1024
_CONTEXT_NAME = re.compile(r"([0-9a-f]{64})\.json\Z")
_PENDING_NAME = re.compile(r"\.pending_[0-9a-f]{32}\Z")
_ERRORS = frozenset({
    "work_session_intake_inventory_invalid", "work_session_intake_inventory_unavailable",
    "work_session_intake_inventory_changed", "work_session_intake_inventory_limit",
    "work_session_intake_inventory_lock_required",
})


class WorkSessionIntakeInventoryError(RuntimeError):
    def __init__(self, code="work_session_intake_inventory_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_inventory_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_intake_inventory_unavailable"
    try:
        return call()
    except WorkSessionIntakeInventoryError as error:
        code = error.code
    except bundle.WorkSessionIntakeBundleError as error:
        if error.code == "work_session_intake_bundle_lock_required":
            code = "work_session_intake_inventory_lock_required"
    except Exception:
        pass
    # Never retain OS/parser/callback exception text, cause or hidden context.
    raise WorkSessionIntakeInventoryError(code)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class _SourceIntakeContextHint:
    """Opaque private bytes and a locator hint; neither has been authenticated."""
    manifest_sha256: str
    raw: bytes

    def __repr__(self):
        return "<private source-intake context hint; not authenticated>"


@dataclass(frozen=True, slots=True, repr=False)
class _SourceIntakeContextInventory:
    _root: Path
    _state: str
    _ancestor_depth: int
    _ancestor_identity: tuple[int, int]
    # Each leaf: name, exact stat identity, raw bytes. No caller JSON parsing.
    _leaves: tuple

    def __post_init__(self):
        if (not isinstance(self._root, Path) or not self._root.is_absolute()
                or type(self._state) is not str or self._state not in {"absent", "present"}
                or type(self._ancestor_depth) is not int
                or not 0 <= self._ancestor_depth <= len(bundle.PRIVATE_ROOT)
                or type(self._ancestor_identity) is not tuple or len(self._ancestor_identity) != 2
                or any(type(value) is not int for value in self._ancestor_identity)
                or type(self._leaves) is not tuple or len(self._leaves) > MAX_CONTEXT_DIRECTORY_ENTRIES
                or (self._state == "present") != (self._ancestor_depth == len(bundle.PRIVATE_ROOT))
                or self._state == "absent" and self._leaves):
            raise WorkSessionIntakeInventoryError()
        names, byte_count = [], 0
        for leaf in self._leaves:
            if (type(leaf) is not tuple or len(leaf) != 3 or type(leaf[0]) is not str
                    or (_CONTEXT_NAME.fullmatch(leaf[0]) is None and _PENDING_NAME.fullmatch(leaf[0]) is None)
                    or type(leaf[1]) is not tuple or len(leaf[1]) != 7
                    or any(type(value) is not int for value in leaf[1])
                    or type(leaf[2]) is not bytes or len(leaf[2]) != leaf[1][2]
                    or not 0 <= len(leaf[2]) <= bundle.MAX_BUNDLE_BYTES):
                raise WorkSessionIntakeInventoryError()
            names.append(leaf[0])
            byte_count += len(leaf[2])
        if names != sorted(set(names)) or byte_count > MAX_CONTEXT_INVENTORY_BYTES:
            raise WorkSessionIntakeInventoryError()

    def __repr__(self):
        return "<private source-intake context inventory; not authentication or ownership>"

    @property
    def state(self):
        return self._state

    def hints(self):
        # New detached wrappers; repeated access neither decodes nor rereads a
        # context, regardless of how many outputs the later producer examines.
        return tuple(_SourceIntakeContextHint("sha256:" + match[1], raw)
                     for name, _identity, raw in self._leaves
                     if (match := _CONTEXT_NAME.fullmatch(name)) is not None)

    def public_summary(self):
        contexts = sum(_CONTEXT_NAME.fullmatch(leaf[0]) is not None for leaf in self._leaves)
        return {"state": self._state, "entry_count": len(self._leaves), "context_hint_count": contexts,
                "pending_entry_count": len(self._leaves) - contexts,
                "raw_byte_count": sum(len(leaf[2]) for leaf in self._leaves),
                "directory_snapshot_complete": True, "context_bodies_validated": False,
                "completion_authenticated": False, "ownership_evaluated": False,
                "backup_performed": False, "private_values_echoed": False, "paths_echoed": False}

    def _generation(self):
        return (self._root, self._state, self._ancestor_depth, self._ancestor_identity,
                tuple((name, identity, _sha(raw)) for name, identity, raw in self._leaves))


def _identity(info):
    return (int(info.st_dev), int(info.st_ino), int(info.st_size), int(info.st_mtime_ns),
            int(info.st_mode), int(info.st_nlink), int(getattr(info, "st_file_attributes", 0)))


def _names(parent):
    target = parent.path if os.name == "nt" else parent.descriptor
    names = []
    with os.scandir(target) as entries:
        for count, entry in enumerate(entries, 1):
            if count > MAX_CONTEXT_DIRECTORY_ENTRIES:
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_limit")
            names.append(entry.name)
    # Count every entry first; no prefix filtering can hide an over-budget or
    # unsafe directory. A pending file is inventory, never a published hint.
    if any(type(name) is not str or (_CONTEXT_NAME.fullmatch(name) is None
           and _PENDING_NAME.fullmatch(name) is None) for name in names):
        raise WorkSessionIntakeInventoryError("work_session_intake_inventory_unavailable")
    return tuple(sorted(names))


def _metadata(parent, names):
    observations, total = [], 0
    for name in names:
        info = (os.lstat(parent.path / name) if os.name == "nt" else
                os.stat(name, dir_fd=parent.descriptor, follow_symlinks=False))
        if not exact._safe_regular_stat(info, max_bytes=bundle.MAX_BUNDLE_BYTES):
            # Size excess is an explicit budget refusal, not unsafe/absent.
            if (stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                    and not exact._path_is_reparse(info) and info.st_nlink == 1
                    and info.st_size > bundle.MAX_BUNDLE_BYTES):
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_limit")
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_unavailable")
        total += info.st_size
        if total > MAX_CONTEXT_INVENTORY_BYTES:
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_limit")
        observations.append(_identity(info))
    return tuple(observations)


def _capture(root, held):
    actual, _archive_id = bundle._held_root(root, held)
    # Reuse the existing no-reparse fixed-directory admission. Locate only its
    # deepest existing ancestor so absence can be observed without mkdir.
    directory = bundle._directory(actual)
    ancestor, depth = actual, 0
    if directory is not None:
        ancestor, depth = directory, len(bundle.PRIVATE_ROOT)
    else:
        for part in bundle.PRIVATE_ROOT:
            candidate = ancestor / part
            try:
                info = os.lstat(candidate)
            except FileNotFoundError:
                break
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_unavailable")
            ancestor, depth = candidate, depth + 1
        if depth == len(bundle.PRIVATE_ROOT):
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
    with durable._bound_directory_for_move(ancestor) as parent:
        durable._assert_named_reservation_directory_identity(ancestor, parent.identity)
        held.verify_held()
        if directory is None:
            missing = ancestor / bundle.PRIVATE_ROOT[depth]
            # lstat distinguishes true absence from a dangling link, denied
            # access, unknown topology, or a concurrently published directory.
            for _ in range(2):
                try:
                    os.lstat(missing)
                except FileNotFoundError:
                    pass
                else:
                    raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
                durable._assert_named_reservation_directory_identity(ancestor, parent.identity)
                held.verify_held()
            bundle._held_root(actual, held)
            if bundle._directory(actual) is not None:
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
            return _SourceIntakeContextInventory(actual, "absent", depth, parent.identity, ())

        names = _names(parent)
        identities = _metadata(parent, names)  # Aggregate budget before body allocation.
        bodies = []
        for name, identity in zip(names, identities):
            # Pin each read ceiling to its already budgeted size; a growing
            # leaf cannot turn many tiny preflight stats into huge allocations.
            value = controls._read_control(directory / name, maximum=identity[2])
            if len(value) != identity[2]:
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
            bodies.append(value)
        raw = tuple(bodies)
        if _names(parent) != names or _metadata(parent, names) != identities:
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
        durable._assert_named_reservation_directory_identity(directory, parent.identity)
        held.verify_held()
        # A second stable byte observation rejects same-size edits even if a
        # caller restores mtime. Bodies stay opaque; corrupt JSON is still only
        # a hint and must be rejected by the later authenticated producer.
        for name, original in zip(names, raw):
            if _sha(controls._read_control(directory / name, maximum=len(original))) != _sha(original):
                raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
        held.verify_held()
        if _names(parent) != names or _metadata(parent, names) != identities:
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
        durable._assert_named_reservation_directory_identity(directory, parent.identity)
        # Recheck every named private ancestor, not merely the deepest inode:
        # a new junction could otherwise route back to that same directory.
        bundle._held_root(actual, held)
        if bundle._directory(actual) != directory:
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
        leaves = tuple(zip(names, identities, raw))
        return _SourceIntakeContextInventory(actual, "present", depth, parent.identity, leaves)


def _capture_source_intake_context_inventory_held(root, *, held):
    return _safe_call(lambda: _capture(root, held))


def _require_source_intake_context_inventory_unchanged_held(root, *, inventory, held):
    def require():
        if type(inventory) is not _SourceIntakeContextInventory:
            raise WorkSessionIntakeInventoryError()
        # Detach all exact immutable fields before any filesystem callback.
        frozen = _SourceIntakeContextInventory(inventory._root, inventory._state, inventory._ancestor_depth,
                                              inventory._ancestor_identity, inventory._leaves)
        observed = _capture(root, held)
        if observed._generation() != frozen._generation():
            raise WorkSessionIntakeInventoryError("work_session_intake_inventory_changed")
    return _safe_call(require)
