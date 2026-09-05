"""Private per-app/task routing, never app attestation or write authority.

The registry's random client_app_ref already is the installation selector.
Callers must supply it and their task_route_ref explicitly. A task route is
only a harness routing selector, not a second app identity or authority.
There is no global/current/latest app or task route fallback.
Only registered apps are supported. Nonhuman register/claim bootstrap pending
intents are a separate, not-yet-connected orchestration concern.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat
import uuid

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import project_update_transaction as durable
from . import work_session_bundle as bundle
from . import work_session_registry as registry
from .work_session_binding import WorkSessionBinding


ACTOR_SCHEMA = "wom-kit/work-session-private-actor/v1"
PRIVATE_ROOT = ("profiles", "local", "work-sessions", "actors")
MAX_ACTOR_BYTES = 16 * 1024
MAX_ACTOR_GENERATIONS = 100_000
_NAME = re.compile(r"[0-9]{12}\.json\Z")
_PENDING = re.compile(r"\.pending_[0-9a-f]{32}\Z")
_KEYS = frozenset({
    "schema", "archive_identity_sha256", "client_app_ref", "task_route_ref", "revision",
    "previous_sha256", "work_session_ref", "observed_binding", "claim_ref",
    "pending_manifest_sha256", "pending_context_sha256", "actor_sha256",
})
_ERRORS = frozenset({
    "work_session_actor_invalid", "work_session_actor_changed",
    "work_session_actor_path_unsafe", "work_session_actor_lock_required",
    "work_session_actor_durability_unknown", "work_session_actor_app_unregistered",
})


class WorkSessionActorError(ValueError):
    def __init__(self, code="work_session_actor_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_actor_invalid"
        super().__init__(self.code)


def _fail(code="work_session_actor_invalid"):
    return WorkSessionActorError(code)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def new_task_route_ref():
    """Create an opaque route for an explicitly started harness task only.

    The caller retains this selector across processes. It grants no authority
    and must not be regenerated or inferred while resuming an existing task.
    """
    return registry._new_ref("task_route")


def _decode(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_ACTOR_BYTES:
        raise _fail()
    document = bundle._strict_document(raw)
    if set(document) != _KEYS or document["schema"] != ACTOR_SCHEMA:
        raise _fail()
    if (not registry._ref(document["client_app_ref"], "client_app")
            or not registry._ref(document["task_route_ref"], "task_route")
            or not registry._is_digest(document["archive_identity_sha256"])
            or type(document["revision"]) is not int
            or not 1 <= document["revision"] <= MAX_ACTOR_GENERATIONS
            or (document["revision"] == 1 and document["previous_sha256"] is not None)
            or (document["revision"] > 1 and not registry._is_digest(document["previous_sha256"]))):
        raise _fail()
    session, observed, claim = (document[name] for name in
                                ("work_session_ref", "observed_binding", "claim_ref"))
    if session is None:
        if observed is not None or claim is not None:
            raise _fail()
    else:
        if not registry._ref(session, "work_session") or type(observed) is not dict:
            raise _fail()
        binding = WorkSessionBinding.from_document(observed)
        if (binding.work_session_ref != session
                or binding.client_app_ref != document["client_app_ref"]
                or binding.archive_identity_sha256 != document["archive_identity_sha256"]
                or (claim is not None and not registry._ref(claim, "claim"))):
            raise _fail()
    pending = [document[name] for name in ("pending_manifest_sha256", "pending_context_sha256")]
    if (pending[0] is None) != (pending[1] is None) or any(
        item is not None and not registry._is_digest(item) for item in pending
    ):
        raise _fail()
    expected = _sha(registry._canonical({key: value for key, value in document.items()
                                       if key != "actor_sha256"}))
    if not registry._is_digest(document["actor_sha256"]) or not hmac.compare_digest(
        document["actor_sha256"], expected
    ):
        raise _fail()
    return document


@dataclass(frozen=True, repr=False)
class ActorContext:
    """Frozen private bytes; document() returns a detached private view."""

    _raw: bytes

    def __post_init__(self):
        code = "work_session_actor_invalid"
        try:
            _decode(self._raw)
            return
        except WorkSessionActorError as error:
            code = error.code
        except Exception:
            pass
        raise _fail(code)

    def __repr__(self):
        return "ActorContext(<private routing assertions>)"

    def document(self):
        return _decode(self._raw)

    @property
    def sha256(self):
        return self.document()["actor_sha256"]

    def public_summary(self):
        value = self.document()
        return {
            "schema": ACTOR_SCHEMA, "revision": value["revision"],
            "scope": "private_actor_routing",
            "routing_identity_level": "self_declared", "identity_is_app_attestation": False,
            "session_selected": value["work_session_ref"] is not None,
            "claim_assertion_present": value["claim_ref"] is not None,
            "pending_original_operation_selected": value["pending_manifest_sha256"] is not None,
            "routing_is_write_authority": False, "claim_tokens_echoed": False,
            "private_labels_echoed": False,
        }


class WorkSessionActorStore:
    """Small immutable CAS images under explicit registered app/task selectors.

    A matching digest is not a MAC. Fresh domain writes must independently call
    registry.require_claimed_binding under the writer lock. Pending operation
    resume must load its frozen bundle/context and authenticate the original
    approval/checkpoint, not replace it with these routing assertions.
    """

    def __init__(self, registry_store, *, client_app_ref, task_route_ref=None):
        code = "work_session_actor_invalid"
        try:
            if type(registry_store) is not registry.WorkSessionRegistryStore or not registry._ref(
                client_app_ref, "client_app"
            ) or not registry._ref(task_route_ref, "task_route"):
                raise _fail()
            self._store = registry_store
            self._root = registry_store.root
            self._archive_sha = registry_store.archive_identity_sha256
            self._app = client_app_ref
            self._route = task_route_ref
            self._root_identity = registry_store._root_identity
            self._parts = (*PRIVATE_ROOT, client_app_ref, task_route_ref)
            self._check_store()
            return
        except WorkSessionActorError as error:
            code = error.code
        except Exception:
            pass
        raise _fail(code)

    def __repr__(self):
        return "WorkSessionActorStore(<private explicit app/task route>)"

    def _check_store(self):
        if (self._store.root != self._root
                or self._store.path != self._root.joinpath(*registry.PRIVATE_ROOT)
                or self._store.archive_identity_sha256 != self._archive_sha
                or self._parts != (*PRIVATE_ROOT, self._app, self._route)):
            raise _fail("work_session_actor_path_unsafe")
        root, archive_id = approval._archive_identity(self._root)
        if (not os.path.samefile(root, self._root)
                or approval.exact_human_approval_archive_identity_sha256(archive_id) != self._archive_sha):
            raise _fail("work_session_actor_changed")
        snapshot = self._store.read()
        if self._app not in snapshot._document["apps"]:
            raise _fail("work_session_actor_app_unregistered")
        return snapshot

    def _lock(self, held_lock):
        try:
            self._store._require_held_lock(held_lock)
        except Exception:
            raise _fail("work_session_actor_lock_required") from None

    @contextmanager
    def _boundary(self):
        with ExitStack() as stack:
            parent = stack.enter_context(durable._bound_directory_for_move(self._root))
            if parent.identity != self._root_identity:
                raise _fail("work_session_actor_path_unsafe")
            retained, missing = [parent], None
            for part in self._parts:
                try:
                    info = registry._relative_stat(parent, part)
                except FileNotFoundError:
                    missing = part
                    break
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
                    raise _fail("work_session_actor_path_unsafe")
                child = stack.enter_context(durable._bound_directory_for_move(parent.path / part))
                if child.identity != (info.st_dev, info.st_ino):
                    raise _fail("work_session_actor_changed")
                retained.append(child)
                parent = child
            yield None if missing is not None else parent
            if missing is not None:
                try:
                    registry._relative_stat(parent, missing)
                except FileNotFoundError:
                    pass
                else:
                    raise _fail("work_session_actor_changed")
            for item in retained:
                durable._assert_named_reservation_directory_identity(item.path, item.identity)

    def _names(self, parent):
        names = []
        with os.scandir(parent.path if os.name == "nt" else parent.descriptor) as entries:
            for count, entry in enumerate(entries, 1):
                if count > MAX_ACTOR_GENERATIONS:
                    raise _fail()
                if not (_NAME.fullmatch(entry.name) or _PENDING.fullmatch(entry.name)):
                    raise _fail("work_session_actor_path_unsafe")
                if not exact._safe_regular_stat(registry._relative_stat(parent, entry.name), max_bytes=MAX_ACTOR_BYTES):
                    raise _fail("work_session_actor_path_unsafe")
                if _NAME.fullmatch(entry.name):
                    names.append(entry.name)
        return tuple(sorted(names))

    def _routes(self, context, snapshot, *, current):
        document = context.document()
        if (document["client_app_ref"] != self._app
                or document["task_route_ref"] != self._route
                or document["archive_identity_sha256"] != self._archive_sha):
            raise _fail("work_session_actor_changed")
        session_ref = document["work_session_ref"]
        if session_ref is None:
            return
        session = snapshot._document["sessions"].get(session_ref)
        if session is None or session["client_app_ref"] != self._app:
            raise _fail("work_session_actor_changed")
        # A pending original operation can have changed the registry already.
        # Do not block its real MAC/checkpoint verification on an old assertion.
        if current and document["pending_manifest_sha256"] is None:
            if (document["observed_binding"] != snapshot.binding(session_ref).document()
                    or (document["claim_ref"] is not None
                        and document["claim_ref"] != session["claim_ref"])):
                raise _fail("work_session_actor_changed")

    def _read(self, *, current):
        snapshot = self._check_store()
        with self._boundary() as parent:
            names = () if parent is None else self._names(parent)
            if any(name != f"{number:012d}.json" for number, name in enumerate(names, 1)):
                raise _fail()
            contexts = []
            for name in names[-2:]:
                context = ActorContext(bundle._read_control(parent.path / name, maximum=MAX_ACTOR_BYTES))
                if context.document()["revision"] != int(name[:12]):
                    raise _fail()
                self._routes(context, snapshot, current=False)
                contexts.append(context)
            if contexts:
                previous = contexts[-2].sha256 if len(contexts) == 2 else None
                if contexts[-1].document()["previous_sha256"] != previous:
                    raise _fail("work_session_actor_changed")
            if parent is not None and names != self._names(parent):
                raise _fail("work_session_actor_changed")
        final_snapshot = self._check_store()
        result = contexts[-1] if contexts else None
        if result is not None:
            self._routes(result, final_snapshot, current=current)
        return result

    def read(self):
        """Read only. Missing context never falls back to another app/task."""
        code = "work_session_actor_invalid"
        try:
            return self._read(current=True)
        except WorkSessionActorError as error:
            code = error.code
        except Exception:
            pass
        raise _fail(code)

    def save(self, *, expected_sha256, work_session_ref=None, claim_ref=None,
             observed_binding=None, pending_manifest_sha256=None,
             pending_context_sha256=None, held_lock):
        """Replace routing selections by appending one full CAS image.

        All selection fields are explicit full-image values; None clears them.
        Unpublished .pending files are retained and never selected as context.
        """
        code = "work_session_actor_invalid"
        try:
            return self._save(expected_sha256, work_session_ref, claim_ref,
                              observed_binding, pending_manifest_sha256,
                              pending_context_sha256, held_lock)
        except WorkSessionActorError as error:
            code = error.code
        except Exception:
            pass
        raise _fail(code)

    def _save(self, expected, session, claim, binding, manifest, context_sha, held):
        self._lock(held)
        if expected is not None and not registry._is_digest(expected):
            raise _fail()
        if binding is not None and type(binding) is not WorkSessionBinding:
            raise _fail()
        if (session is not None and not registry._ref(session, "work_session")) or (
            claim is not None and not registry._ref(claim, "claim")
        ) or (manifest is None) != (context_sha is None) or any(
            value is not None and not registry._is_digest(value)
            for value in (manifest, context_sha)
        ):
            raise _fail()
        previous = self._read(current=False)
        if expected != (previous.sha256 if previous is not None else None):
            raise _fail("work_session_actor_changed")
        basis = {
            "schema": ACTOR_SCHEMA, "archive_identity_sha256": self._archive_sha,
            "client_app_ref": self._app, "task_route_ref": self._route,
            "revision": previous.document()["revision"] + 1 if previous else 1,
            "previous_sha256": expected, "work_session_ref": session,
            "observed_binding": binding.document() if binding is not None else None,
            "claim_ref": claim, "pending_manifest_sha256": manifest,
            "pending_context_sha256": context_sha,
        }
        raw = registry._canonical({**basis, "actor_sha256": _sha(registry._canonical(basis))})
        frozen = ActorContext(raw)
        self._routes(frozen, self._check_store(), current=True)
        if previous is not None and all(
            value == previous.document()[key] for key, value in basis.items()
            if key not in {"revision", "previous_sha256"}
        ):
            self._lock(held)
            return previous
        directory = exact._ensure_private_directory(self._root, self._parts)
        durable._require_directory_durable(directory)
        with self._boundary() as parent:
            if parent is None:
                raise _fail("work_session_actor_changed")
            destination = parent.path / f"{basis['revision']:012d}.json"
            pending = parent.path / (".pending_" + uuid.uuid4().hex)
            try:
                registry._write_private_pending(pending, raw, root=self._root)
                self._lock(held)
                current = self._read(current=False)
                if expected != (current.sha256 if current is not None else None):
                    raise _fail("work_session_actor_changed")
                self._routes(frozen, self._check_store(), current=True)
                if bundle._read_control(pending, maximum=MAX_ACTOR_BYTES) != raw:
                    raise _fail("work_session_actor_changed")
                durable._assert_named_reservation_directory_identity(parent.path, parent.identity)
                durable._atomic_move_file_no_replace(
                    pending, destination, expected_parent_identity=parent.identity,
                )
                durable._require_directory_durable(directory)
            except WorkSessionActorError:
                raise
            except Exception:
                raise _fail("work_session_actor_durability_unknown") from None
        restored = self._read(current=True)
        self._lock(held)
        if restored is None or restored._raw != raw:
            raise _fail("work_session_actor_changed")
        return restored
