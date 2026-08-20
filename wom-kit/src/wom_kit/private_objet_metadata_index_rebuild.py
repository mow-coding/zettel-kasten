"""Single-transaction rebuild lifecycle for the v0.3.297 private projection.

The public archive index remains owned by :mod:`wom_kit.archive_services`.
This module only owns the private authority/lock lifecycle around that existing
work.  A trusted caller receives the raw connection so its existing
``executescript`` can keep ``BEGIN IMMEDIATE`` as the first statement.  No
transaction is active when the connection is handed to that caller.

All exceptions crossing this boundary have closed, content-free messages.
Runtime archive paths and private authority values are intentionally absent
from errors and object representations.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any, Callable

from .private_objet_metadata_index import (
    PrivateObjetIndexContractError,
    PrivateObjetIndexInspection,
    _PrivateObjetIndexProjection,
    _compile_private_objet_index_projection,
    insert_private_objet_index_metadata,
    replace_private_objet_index_rows,
)
from .private_objet_metadata_index_authority import (
    PrivateObjetAuthorityError,
    _PrivateObjetIndexAuthorityCapture,
    _capture_private_objet_index_authority,
)


PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED = (
    "private_objet_metadata_lock_release_failed"
)
PRIVATE_OBJET_METADATA_REBUILD_FAILED = (
    "private_objet_metadata_rebuild_failed"
)
PRIVATE_OBJET_METADATA_REBUILD_NOT_COMMITTED = (
    "private_objet_metadata_rebuild_not_committed"
)
PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE = (
    "private_objet_metadata_projection_unavailable"
)
PRIVATE_OBJET_METADATA_PROJECTION_INVALID = (
    "private_objet_metadata_projection_invalid"
)
PRIVATE_OBJET_METADATA_SNAPSHOT_CHANGED = (
    "private_objet_metadata_snapshot_changed"
)

DEFAULT_BUSY_TIMEOUT_MS = 30_000
_ROLLBACK_ATTEMPTS = 3
_INDEX_RELATIVE_PARTS = ("db", "archive-index.sqlite")
_WINDOWS_REPARSE_ATTRIBUTE = 0x00000400

_CLOSED_CODES = frozenset(
    {
        PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED,
        PRIVATE_OBJET_METADATA_REBUILD_FAILED,
        PRIVATE_OBJET_METADATA_REBUILD_NOT_COMMITTED,
        PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE,
        PRIVATE_OBJET_METADATA_PROJECTION_INVALID,
        PRIVATE_OBJET_METADATA_SNAPSHOT_CHANGED,
        "private_objet_metadata_authority_blocked",
        "private_objet_metadata_authority_invalid",
    }
)


class PrivateObjetIndexRebuildError(RuntimeError):
    """Sanitized rebuild failure with a stable operation code and exit 1."""

    def __init__(self, code: str, *, committed: bool = False) -> None:
        if code not in _CLOSED_CODES:
            raise ValueError("private_objet_metadata_rebuild_code_invalid")
        self.code = code
        self.committed = bool(committed)
        self.exit_code = 1
        super().__init__(code)


@dataclass(frozen=True)
class _RebuildDependencies:
    capture: Callable[
        [Path, str], _PrivateObjetIndexAuthorityCapture
    ] = _capture_private_objet_index_authority
    compile: Callable[
        [dict[str, Any]], _PrivateObjetIndexProjection
    ] = _compile_private_objet_index_projection
    replace_rows: Callable[
        [sqlite3.Connection, _PrivateObjetIndexProjection], None
    ] = replace_private_objet_index_rows
    insert_metadata: Callable[
        [sqlite3.Connection, _PrivateObjetIndexProjection],
        PrivateObjetIndexInspection,
    ] = insert_private_objet_index_metadata
    connect: Callable[[Path, int], sqlite3.Connection] | None = None
    load_win32: Callable[[], Any] | None = None
    fatal_exit: Callable[[int], Any] | None = None
    platform_name: str | None = None


@dataclass(frozen=True, repr=False)
class _IndexPathIdentity:
    present: bool
    device: int | None
    inode: int | None


@dataclass(frozen=True, repr=False)
class _IndexStorageIdentity:
    parent: _IndexPathIdentity
    database: _IndexPathIdentity
    wal: _IndexPathIdentity
    shm: _IndexPathIdentity
    journal: _IndexPathIdentity


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(
        getattr(stat_result, "st_file_attributes", 0)
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _capture_index_path_identity(
    path: Path,
    *,
    expected_directory: bool,
    allow_missing: bool,
) -> _IndexPathIdentity:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return _IndexPathIdentity(False, None, None)
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        ) from None
    except OSError:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        ) from None
    if stat.S_ISLNK(observed.st_mode) or _is_reparse(observed):
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    if expected_directory:
        if not stat.S_ISDIR(observed.st_mode):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )
    elif not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    inode = int(observed.st_ino)
    if inode == 0:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    return _IndexPathIdentity(True, int(observed.st_dev), inode)


def _capture_index_storage_identity(
    root: Path,
    db_path: Path,
) -> _IndexStorageIdentity:
    parent = root / _INDEX_RELATIVE_PARTS[0]
    if db_path.parent != parent:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    parent_identity = _capture_index_path_identity(
        parent,
        expected_directory=True,
        allow_missing=False,
    )
    database = _capture_index_path_identity(
        db_path,
        expected_directory=False,
        allow_missing=True,
    )
    wal = _capture_index_path_identity(
        db_path.with_name(db_path.name + "-wal"),
        expected_directory=False,
        allow_missing=True,
    )
    shm = _capture_index_path_identity(
        db_path.with_name(db_path.name + "-shm"),
        expected_directory=False,
        allow_missing=True,
    )
    journal = _capture_index_path_identity(
        db_path.with_name(db_path.name + "-journal"),
        expected_directory=False,
        allow_missing=True,
    )
    if not database.present and (
        wal.present or shm.present or journal.present
    ):
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    return _IndexStorageIdentity(
        parent_identity,
        database,
        wal,
        shm,
        journal,
    )


def _require_storage_transition(
    before: _IndexStorageIdentity,
    after: _IndexStorageIdentity,
    *,
    allow_database_creation: bool,
    allow_new_sidecars: bool,
) -> None:
    if before.parent != after.parent:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )
    if before.database != after.database:
        database_created = (
            allow_database_creation
            and not before.database.present
            and after.database.present
        )
        if not database_created:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )
    for old_path, new_path in (
        (before.wal, after.wal),
        (before.shm, after.shm),
        (before.journal, after.journal),
    ):
        if old_path == new_path:
            continue
        sidecar_created = (
            allow_new_sidecars
            and not old_path.present
            and new_path.present
        )
        if not sidecar_created:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )


def _default_connect(
    db_path: Path,
    busy_timeout_ms: int,
) -> sqlite3.Connection:
    return sqlite3.connect(
        db_path,
        timeout=busy_timeout_ms / 1000,
    )


def _default_load_win32() -> Any:
    from . import private_metadata_win32

    return private_metadata_win32


def _sanitize_failure(
    exc: BaseException,
    *,
    committed: bool,
) -> PrivateObjetIndexRebuildError:
    if isinstance(exc, PrivateObjetIndexRebuildError):
        return PrivateObjetIndexRebuildError(
            exc.code,
            committed=committed or exc.committed,
        )
    if isinstance(exc, PrivateObjetAuthorityError):
        return PrivateObjetIndexRebuildError(
            exc.code,
            committed=committed,
        )
    if isinstance(exc, PrivateObjetIndexContractError):
        code = str(exc)
        if code not in _CLOSED_CODES:
            code = PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        return PrivateObjetIndexRebuildError(code, committed=committed)
    if isinstance(exc, sqlite3.Error):
        return PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE,
            committed=committed,
        )
    return PrivateObjetIndexRebuildError(
        PRIVATE_OBJET_METADATA_REBUILD_FAILED,
        committed=committed,
    )


def _resolved_index_paths(
    archive_root: Path | str,
    db_path: Path | str,
) -> tuple[Path, Path]:
    try:
        root = Path(archive_root).resolve(strict=True)
        candidate = Path(db_path).resolve(strict=False)
        expected = root.joinpath(*_INDEX_RELATIVE_PARTS).resolve(strict=False)
        common = Path(os.path.commonpath((str(root), str(candidate))))
    except (OSError, RuntimeError, TypeError, ValueError):
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_REBUILD_FAILED
        ) from None
    if not root.is_dir() or candidate != expected or common != root:
        raise PrivateObjetIndexRebuildError(
            PRIVATE_OBJET_METADATA_REBUILD_FAILED
        )
    _capture_index_storage_identity(root, candidate)
    return root, candidate


class _PrivateObjetIndexRebuildSession:
    """Own one rebuild's authority, connection, transaction, and lock unwind."""

    def __init__(
        self,
        archive_root: Path | str,
        archive_id: str,
        db_path: Path | str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        _dependencies: _RebuildDependencies | None = None,
    ) -> None:
        if type(archive_id) is not str or not archive_id:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED
            )
        if (
            type(busy_timeout_ms) is not int
            or not 1 <= busy_timeout_ms <= 120_000
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED
            )
        self._root, self._db_path = _resolved_index_paths(
            archive_root,
            db_path,
        )
        self._archive_id = archive_id
        self._busy_timeout_ms = busy_timeout_ms
        self._dependencies = _dependencies or _RebuildDependencies()
        self._platform_name = (
            os.name
            if self._dependencies.platform_name is None
            else self._dependencies.platform_name
        )
        if self._platform_name not in {"nt", "posix"}:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED
            )

        self._entered = False
        self._closed = False
        self._committed = False
        self._rows_installed = False
        self._connection: sqlite3.Connection | None = None
        self._authority_a: _PrivateObjetIndexAuthorityCapture | None = None
        self._projection: _PrivateObjetIndexProjection | None = None
        self._inspection: PrivateObjetIndexInspection | None = None
        self._storage_identity: _IndexStorageIdentity | None = None
        self._win32: Any | None = None
        self._guard: Any | None = None
        self._locks: Any | None = None

    def __repr__(self) -> str:
        return (
            "_PrivateObjetIndexRebuildSession("
            f"entered={self._entered!r}, "
            f"committed={self._committed!r}, "
            f"closed={self._closed!r})"
        )

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the raw connection only to the trusted public-index caller."""

        if (
            not self._entered
            or self._closed
            or self._committed
            or self._connection is None
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED,
                committed=self._committed,
            )
        return self._connection

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def inspection(self) -> PrivateObjetIndexInspection | None:
        return self._inspection

    def _enter_windows_boundary(self) -> None:
        loader = self._dependencies.load_win32 or _default_load_win32
        try:
            win32 = loader()
            guard = win32._PrivateMetadataMutationGuard(self._root)
            self._win32 = win32
            self._guard = guard
            guard.hold_chain(self._root / "db")
            guard.hold_chain(self._root / "objects" / "manifests")
            guard.validate_all()
            locks = win32._PrivateMetadataLockPair(guard)
            self._locks = locks
            locks.acquire()
            locks.validate()
            guard.validate_all()
        except BaseException:
            raise

    def _capture_a_and_compile(self) -> None:
        if self._platform_name == "nt":
            assert self._guard is not None
            assert self._locks is not None
            self._locks.validate()
            self._guard.validate_all()
        authority = self._dependencies.capture(
            self._root,
            self._archive_id,
        )
        if self._platform_name == "nt":
            self._locks.validate()
            self._guard.validate_all()
        projection = self._dependencies.compile(
            authority.as_compiler_input()
        )
        if (
            not isinstance(projection, _PrivateObjetIndexProjection)
            or projection.authority_fingerprint_sha256
            != authority.fingerprint_sha256
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )
        self._authority_a = authority
        self._projection = projection

    def _open_and_configure_connection(self) -> None:
        connector = self._dependencies.connect or _default_connect
        before = _capture_index_storage_identity(
            self._root,
            self._db_path,
        )
        connection = connector(self._db_path, self._busy_timeout_ms)
        if not isinstance(connection, sqlite3.Connection):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED
            )
        self._connection = connection
        after_open = _capture_index_storage_identity(
            self._root,
            self._db_path,
        )
        _require_storage_transition(
            before,
            after_open,
            allow_database_creation=True,
            allow_new_sidecars=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(
            f"PRAGMA busy_timeout = {self._busy_timeout_ms}"
        )
        journal_mode = connection.execute(
            "PRAGMA journal_mode=DELETE"
        ).fetchone()
        if (
            journal_mode is None
            or str(journal_mode[0]).lower() != "delete"
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE
            )
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()
        if (
            foreign_keys is None
            or foreign_keys[0] != 1
            or connection.in_transaction
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )
        after_configuration = _capture_index_storage_identity(
            self._root,
            self._db_path,
        )
        _require_storage_transition(
            after_open,
            after_configuration,
            allow_database_creation=True,
            allow_new_sidecars=True,
        )
        self._storage_identity = after_configuration

    def _require_current_storage_identity(
        self,
        *,
        allow_new_sidecars: bool,
    ) -> None:
        if self._storage_identity is None:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID
            )
        current = _capture_index_storage_identity(
            self._root,
            self._db_path,
        )
        _require_storage_transition(
            self._storage_identity,
            current,
            allow_database_creation=False,
            allow_new_sidecars=allow_new_sidecars,
        )
        self._storage_identity = current

    def __enter__(self) -> "_PrivateObjetIndexRebuildSession":
        if self._entered or self._closed:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_FAILED
            )
        try:
            if self._platform_name == "nt":
                self._enter_windows_boundary()
            self._capture_a_and_compile()
            self._open_and_configure_connection()
            self._entered = True
            return self
        except BaseException as exc:
            cleanup_code = self._cleanup()
            if cleanup_code is not None:
                raise PrivateObjetIndexRebuildError(cleanup_code) from None
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise _sanitize_failure(exc, committed=False) from None

    def install_private_rows_after_public(self) -> None:
        """Install the three row sets after the caller has built public rows."""

        connection = self.connection
        if (
            self._committed
            or self._rows_installed
            or self._projection is None
            or not connection.in_transaction
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID,
                committed=self._committed,
            )
        try:
            self._require_current_storage_identity(
                allow_new_sidecars=True
            )
            self._dependencies.replace_rows(
                connection,
                self._projection,
            )
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise _sanitize_failure(exc, committed=False) from None
        self._rows_installed = True

    def _capture_b(self) -> _PrivateObjetIndexAuthorityCapture:
        if self._platform_name == "nt":
            assert self._guard is not None
            assert self._locks is not None
            self._locks.validate()
            self._guard.validate_all()
        authority = self._dependencies.capture(
            self._root,
            self._archive_id,
        )
        if self._platform_name == "nt":
            self._locks.validate()
            self._guard.validate_all()
        return authority

    def validate_and_commit(self) -> PrivateObjetIndexInspection:
        """Capture B, insert the singleton last, verify, and commit once."""

        connection = self.connection
        if (
            self._committed
            or not self._rows_installed
            or self._authority_a is None
            or self._projection is None
            or not connection.in_transaction
        ):
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_PROJECTION_INVALID,
                committed=self._committed,
            )
        try:
            self._require_current_storage_identity(
                allow_new_sidecars=True
            )
            if connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall():
                raise PrivateObjetIndexRebuildError(
                    PRIVATE_OBJET_METADATA_PROJECTION_INVALID
                )
            authority_b = self._capture_b()
            if (
                authority_b.comparison_token
                != self._authority_a.comparison_token
                or authority_b.fingerprint_sha256
                != self._authority_a.fingerprint_sha256
                or authority_b.fingerprint_sha256
                != self._projection.authority_fingerprint_sha256
            ):
                raise PrivateObjetIndexRebuildError(
                    PRIVATE_OBJET_METADATA_SNAPSHOT_CHANGED
                )
            inspection = self._dependencies.insert_metadata(
                connection,
                self._projection,
            )
            self._require_current_storage_identity(
                allow_new_sidecars=False
            )
            if (
                not connection.in_transaction
                or connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            ):
                raise PrivateObjetIndexRebuildError(
                    PRIVATE_OBJET_METADATA_PROJECTION_INVALID
                )
            self._require_current_storage_identity(
                allow_new_sidecars=False
            )
            connection.commit()
            self._committed = True
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise _sanitize_failure(
                exc,
                committed=self._committed,
            ) from None
        self._inspection = inspection
        return inspection

    def _bounded_rollback(self) -> bool:
        connection = self._connection
        if (
            connection is None
            or self._committed
            or not connection.in_transaction
        ):
            return True
        for _attempt in range(_ROLLBACK_ATTEMPTS):
            try:
                connection.rollback()
            except Exception:
                if not connection.in_transaction:
                    return True
                continue
            return not connection.in_transaction
        return not connection.in_transaction

    def _close_connection(self) -> bool:
        connection = self._connection
        if connection is None:
            return True
        for _attempt in range(_ROLLBACK_ATTEMPTS):
            try:
                connection.close()
            except Exception:
                continue
            self._connection = None
            return True
        return False

    def _fatal_unproved_connection_release(self) -> None:
        """Do not unlock filesystem authorities around an unclosed DB handle."""

        fatal_exit = self._dependencies.fatal_exit or os._exit
        fatal_exit(74)
        # A production ``os._exit`` never returns.  Keep a fail-stop boundary
        # even if a test double or invalid dependency violates that contract.
        raise SystemExit(74)

    def _release_windows_boundary(self) -> bool:
        """Release locks in pair order, then guard, with terminal fallback."""

        if self._platform_name != "nt":
            return True
        release_ok = True
        pending_interrupt: BaseException | None = None
        locks = self._locks
        if locks is not None:
            try:
                locks.release()
            except BaseException as exc:
                release_ok = False
                # The production primitive performs three bounded raw-handle
                # release cycles and calls os._exit(74) if closure is not
                # proven.  Do not catch that BaseException boundary here.
                locks.terminal_release_after_failure()
                if not isinstance(exc, Exception):
                    pending_interrupt = exc
            self._locks = None
        guard = self._guard
        if guard is not None:
            try:
                guard.close()
            except BaseException as exc:
                release_ok = False
                guard.terminal_release_after_failure()
                if (
                    pending_interrupt is None
                    and not isinstance(exc, Exception)
                ):
                    pending_interrupt = exc
            self._guard = None
        if pending_interrupt is not None:
            raise pending_interrupt
        return release_ok

    def _cleanup(self) -> str | None:
        if self._closed:
            return None
        rollback_ok = self._bounded_rollback()
        close_ok = self._close_connection()
        if not close_ok:
            self._fatal_unproved_connection_release()
        release_ok = self._release_windows_boundary()
        self._closed = True
        self._entered = False
        if not release_ok:
            return PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED
        if not rollback_ok or not close_ok:
            return PRIVATE_OBJET_METADATA_REBUILD_FAILED
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        del exc_type, traceback
        cleanup_code = self._cleanup()
        if cleanup_code is not None:
            raise PrivateObjetIndexRebuildError(
                cleanup_code,
                committed=self._committed,
            ) from None
        if exc is not None:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                return False
            raise _sanitize_failure(
                exc,
                committed=self._committed,
            ) from None
        if not self._committed:
            raise PrivateObjetIndexRebuildError(
                PRIVATE_OBJET_METADATA_REBUILD_NOT_COMMITTED
            )
        return False


def _private_objet_index_rebuild_session(
    archive_root: Path | str,
    archive_id: str,
    db_path: Path | str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    _dependencies: _RebuildDependencies | None = None,
) -> _PrivateObjetIndexRebuildSession:
    """Construct the one lifecycle owner used by ``archive index``."""

    return _PrivateObjetIndexRebuildSession(
        archive_root,
        archive_id,
        db_path,
        busy_timeout_ms=busy_timeout_ms,
        _dependencies=_dependencies,
    )


__all__ = [
    "DEFAULT_BUSY_TIMEOUT_MS",
    "PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED",
    "PRIVATE_OBJET_METADATA_PROJECTION_INVALID",
    "PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE",
    "PRIVATE_OBJET_METADATA_REBUILD_FAILED",
    "PRIVATE_OBJET_METADATA_REBUILD_NOT_COMMITTED",
    "PRIVATE_OBJET_METADATA_SNAPSHOT_CHANGED",
    "PrivateObjetIndexRebuildError",
]
