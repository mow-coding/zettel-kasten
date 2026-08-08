from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from wom_kit.private_objet_metadata_index import (
    PrivateObjetIndexContractError,
    compile_private_objet_index_projection,
    empty_private_objet_authority,
    insert_private_objet_index_metadata,
    replace_private_objet_index_rows,
)
from wom_kit import private_objet_metadata_index_rebuild as rebuild


@dataclass(frozen=True)
class _Capture:
    compiler_input: dict[str, Any]
    comparison_token: tuple[str, str, str]

    def as_compiler_input(self) -> dict[str, Any]:
        return self.compiler_input

    @property
    def fingerprint_sha256(self) -> str:
        return compile_private_objet_index_projection(
            self.compiler_input
        ).authority_fingerprint_sha256


def _archive(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "archive"
    (root / "objects" / "manifests").mkdir(parents=True)
    (root / "db").mkdir()
    return root, root / "db" / "archive-index.sqlite"


def test_existing_index_requires_one_canonical_filesystem_name(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    alternate_path = tmp_path / "alternate-index.sqlite"
    alternate_path.write_bytes(b"unchanged")
    os.link(alternate_path, db_path)

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=rebuild._RebuildDependencies(
                platform_name="posix"
            ),
        )

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_PROJECTION_INVALID
    )
    assert alternate_path.read_bytes() == b"unchanged"


def _connection_factory(
    events: list[str],
    *,
    rollback_failures: int = 0,
    close_failures: int = 0,
):
    class _Connection(sqlite3.Connection):
        remaining_rollback_failures = rollback_failures
        remaining_close_failures = close_failures

        def commit(self) -> None:
            # CPython 3.10 may route SQLite's pre-transaction WAL setup
            # through the overridable commit() method.  That no-op call is
            # not the rebuild transaction commit this fixture is proving.
            # Record the two cases separately so the transaction-order
            # contract is stable across every supported interpreter.
            events.append(
                "commit_call"
                if self.in_transaction
                else "idle_commit_call"
            )
            return super().commit()

        def rollback(self) -> None:
            events.append("rollback_call")
            if self.remaining_rollback_failures:
                self.remaining_rollback_failures -= 1
                raise sqlite3.OperationalError("private rollback detail")
            return super().rollback()

        def close(self) -> None:
            events.append("connection_close")
            if self.remaining_close_failures:
                self.remaining_close_failures -= 1
                raise sqlite3.OperationalError("private close detail")
            return super().close()

    def connect(path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
        events.append("connect")
        connection = sqlite3.connect(
            path,
            timeout=busy_timeout_ms / 1000,
            factory=_Connection,
        )
        connection.set_trace_callback(
            lambda statement: events.append(
                "sql:" + " ".join(statement.split())
            )
        )
        return connection

    return connect


def _captures(
    events: list[str],
    inputs: list[dict[str, Any]],
    tokens: list[tuple[str, str, str]],
):
    calls = 0

    def capture(root: Path, archive_id: str) -> _Capture:
        nonlocal calls
        del root, archive_id
        label = "snapshot_a" if calls == 0 else "snapshot_b"
        events.append(label)
        index = min(calls, len(inputs) - 1)
        token_index = min(calls, len(tokens) - 1)
        calls += 1
        return _Capture(inputs[index], tokens[token_index])

    return capture


def _fake_win32(
    events: list[str],
    *,
    acquire_error: bool = False,
    acquire_failure_at: str | None = None,
    acquire_interrupt: bool = False,
    release_error: bool = False,
    terminal_exit: bool = False,
    release_interrupt_at: str | None = None,
    guard_release_interrupt: bool = False,
):
    class Guard:
        def __init__(self, root: Path) -> None:
            del root
            events.append("guard")

        def hold_chain(self, path: Path) -> None:
            events.append("guard_hold_" + path.name)

        def validate_all(self) -> None:
            events.append("guard_validate")

        def close(self) -> None:
            events.append("guard_release")
            if guard_release_interrupt:
                raise KeyboardInterrupt

        def terminal_release_after_failure(self) -> None:
            events.append("guard_terminal_release")

    class Locks:
        def __init__(self, guard: Guard) -> None:
            del guard
            self.object_acquired = False
            self.private_acquired = False

        def acquire(self) -> None:
            events.append("object_lock")
            object_failure = acquire_error or acquire_failure_at == "object"
            if object_failure:
                if acquire_interrupt:
                    raise KeyboardInterrupt
                raise RuntimeError("private contention detail")
            self.object_acquired = True
            events.append("private_lock")
            if acquire_failure_at == "private":
                events.append("object_lock_acquire_unwind")
                self.object_acquired = False
                if acquire_interrupt:
                    raise KeyboardInterrupt
                raise RuntimeError("private contention detail")
            self.private_acquired = True

        def validate(self) -> tuple[str, str]:
            events.append("lock_validate")
            return ("object", "private")

        def release(self) -> None:
            if self.private_acquired:
                events.append("private_lock_release")
                if release_interrupt_at == "private":
                    raise KeyboardInterrupt
                if release_error:
                    raise RuntimeError("private release detail")
                self.private_acquired = False
            if self.object_acquired:
                events.append("object_lock_release")
                if release_interrupt_at == "object":
                    raise KeyboardInterrupt
                self.object_acquired = False

        def terminal_release_after_failure(self) -> None:
            events.append("lock_terminal_release")
            if terminal_exit:
                raise SystemExit(74)
            events.append("object_lock_terminal_release")
            self.private_acquired = False
            self.object_acquired = False

    class Module:
        PrivateMetadataMutationGuard = Guard
        PrivateMetadataLockPair = Locks

    return Module


def _dependencies(
    events: list[str],
    *,
    inputs: list[dict[str, Any]] | None = None,
    tokens: list[tuple[str, str, str]] | None = None,
    win32: Any | None = None,
    rollback_failures: int = 0,
    close_failures: int = 0,
    platform_name: str | None = None,
) -> rebuild._RebuildDependencies:
    authority_inputs = inputs or [empty_private_objet_authority()]
    comparison_tokens = tokens or [
        ("comparison/v0.1", "fingerprint-a", "identity-a")
    ]

    def compile_projection(authority: dict[str, Any]):
        events.append("compile")
        return compile_private_objet_index_projection(authority)

    def replace_rows(
        connection: sqlite3.Connection,
        projection: Any,
    ) -> None:
        events.append("replace_private_rows")
        replace_private_objet_index_rows(connection, projection)

    def insert_metadata(
        connection: sqlite3.Connection,
        projection: Any,
    ):
        events.append("insert_singleton")
        return insert_private_objet_index_metadata(connection, projection)

    def load_win32() -> Any:
        events.append("load_win32")
        if win32 is None:
            raise AssertionError("unexpected Windows primitive load")
        return win32

    def fatal_exit(code: int) -> None:
        events.append(f"fatal_exit:{code}")
        raise SystemExit(code)

    return rebuild._RebuildDependencies(
        capture=_captures(
            events,
            authority_inputs,
            comparison_tokens,
        ),
        compile=compile_projection,
        replace_rows=replace_rows,
        insert_metadata=insert_metadata,
        connect=_connection_factory(
            events,
            rollback_failures=rollback_failures,
            close_failures=close_failures,
        ),
        load_win32=load_win32,
        fatal_exit=fatal_exit,
        platform_name=platform_name,
    )


def _build_public_rows(
    connection: sqlite3.Connection,
    value: str,
) -> None:
    connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS public_rows (
          value TEXT NOT NULL
        );
        DELETE FROM public_rows;
        """
    )
    connection.execute(
        "INSERT INTO public_rows(value) VALUES (?)",
        (value,),
    )


def _run_successful_rebuild(
    root: Path,
    db_path: Path,
    *,
    events: list[str],
    dependencies: rebuild._RebuildDependencies,
    public_value: str,
) -> None:
    with rebuild.private_objet_index_rebuild_session(
        root,
        "archive-test",
        db_path,
        _dependencies=dependencies,
    ) as session:
        assert session.connection.in_transaction is False
        assert session.connection.row_factory is sqlite3.Row
        events.append("caller_executescript")
        _build_public_rows(session.connection, public_value)
        session.install_private_rows_after_public()
        inspection = session.validate_and_commit()
        assert inspection.observation_count == 0
        assert session.committed is True
        with pytest.raises(rebuild.PrivateObjetIndexRebuildError):
            _ = session.connection


def _first(events: list[str], prefix: str) -> int:
    return next(
        index
        for index, event in enumerate(events)
        if event.startswith(prefix)
    )


def test_windows_exact_order_single_commit_fk_and_singleton_last(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events)
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    _run_successful_rebuild(
        root,
        db_path,
        events=events,
        dependencies=dependencies,
        public_value="new",
    )

    assert _first(events, "guard") < _first(events, "object_lock")
    assert _first(events, "guard_hold_db") < _first(
        events, "object_lock"
    )
    assert _first(events, "guard_hold_manifests") < _first(
        events, "object_lock"
    )
    assert _first(events, "object_lock") < _first(events, "private_lock")
    assert _first(events, "private_lock") < _first(events, "snapshot_a")
    assert _first(events, "snapshot_a") < _first(events, "compile")
    assert _first(events, "compile") < _first(events, "connect")
    assert _first(events, "connect") < _first(
        events, "sql:PRAGMA foreign_keys=ON"
    )
    assert _first(
        events, "sql:PRAGMA foreign_keys=ON"
    ) < _first(events, "caller_executescript")
    assert _first(events, "caller_executescript") < _first(
        events, "sql:BEGIN IMMEDIATE"
    )
    assert _first(events, "replace_private_rows") < _first(
        events, "snapshot_b"
    )
    assert _first(events, "snapshot_b") < _first(
        events, "insert_singleton"
    )
    assert _first(events, "insert_singleton") < _first(
        events, "commit_call"
    )
    assert events.count("commit_call") == 1
    assert _first(events, "commit_call") < _first(
        events, "connection_close"
    )
    assert _first(events, "connection_close") < _first(
        events, "private_lock_release"
    )
    assert _first(events, "private_lock_release") < _first(
        events, "object_lock_release"
    )
    assert _first(events, "object_lock_release") < _first(
        events, "guard_release"
    )

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 0
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
        assert connection.execute(
            "SELECT COUNT(*) FROM private_objet_index_metadata"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "new"


def test_non_windows_uses_only_a_b_and_creates_no_fake_lock(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    dependencies = _dependencies(events, platform_name="posix")

    _run_successful_rebuild(
        root,
        db_path,
        events=events,
        dependencies=dependencies,
        public_value="portable",
    )

    assert "load_win32" not in events
    assert "guard" not in events
    assert "object_lock" not in events
    assert "private_lock" not in events
    assert _first(events, "snapshot_a") < _first(events, "connect")
    assert _first(events, "snapshot_b") < _first(events, "commit_call")
    assert not list((root / "objects" / "manifests").glob("*.lock"))


def test_default_authority_compiler_and_installer_empty_end_to_end(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)

    with rebuild.private_objet_index_rebuild_session(
        root,
        "archive-test",
        db_path,
        _dependencies=rebuild._RebuildDependencies(
            platform_name="posix"
        ),
    ) as session:
        _build_public_rows(session.connection, "default-dependencies")
        session.install_private_rows_after_public()
        inspection = session.validate_and_commit()

    assert inspection.observation_count == 0
    assert inspection.alias_count == 0
    assert inspection.projection_count == 0
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "default-dependencies"
        assert connection.execute(
            "SELECT authority_state "
            "FROM private_objet_index_metadata"
        ).fetchone()[0] == "empty_valid"


@pytest.mark.skipif(os.name != "nt", reason="exact Win32 lock lifecycle")
def test_real_windows_lifecycle_keeps_zero_byte_persistent_locks(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)

    with rebuild.private_objet_index_rebuild_session(
        root,
        "archive-test",
        db_path,
    ) as session:
        _build_public_rows(session.connection, "windows")
        session.install_private_rows_after_public()
        session.validate_and_commit()

    lock_root = root / "objects" / "manifests"
    object_lock = lock_root / ".files.jsonl.lock"
    private_lock = lock_root / ".private-source-metadata.jsonl.lock"
    assert object_lock.is_file()
    assert private_lock.is_file()
    assert object_lock.stat().st_size == 0
    assert private_lock.stat().st_size == 0


def test_snapshot_b_drift_rolls_back_old_public_and_private_snapshot(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    initial_events: list[str] = []
    initial = _dependencies(initial_events, platform_name="posix")
    _run_successful_rebuild(
        root,
        db_path,
        events=initial_events,
        dependencies=initial,
        public_value="old",
    )
    with sqlite3.connect(db_path) as connection:
        old_fingerprint = connection.execute(
            "SELECT private_authority_fingerprint_sha256 "
            "FROM private_objet_index_metadata"
        ).fetchone()[0]

    events: list[str] = []
    present_empty = empty_private_objet_authority("present_empty")
    dependencies = _dependencies(
        events,
        inputs=[present_empty, present_empty],
        tokens=[
            ("comparison/v0.1", "fingerprint-b", "identity-b"),
            ("comparison/v0.1", "fingerprint-b", "identity-c"),
        ],
        platform_name="posix",
    )
    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "new")
            session.install_private_rows_after_public()
            session.validate_and_commit()

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_SNAPSHOT_CHANGED
    )
    assert caught.value.committed is False
    assert events.count("rollback_call") == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "old"
        assert connection.execute(
            "SELECT private_authority_fingerprint_sha256 "
            "FROM private_objet_index_metadata"
        ).fetchone()[0] == old_fingerprint


def test_private_installer_failure_preserves_old_public_and_private_snapshot(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    initial_events: list[str] = []
    initial = _dependencies(initial_events, platform_name="posix")
    _run_successful_rebuild(
        root,
        db_path,
        events=initial_events,
        dependencies=initial,
        public_value="old",
    )
    with sqlite3.connect(db_path) as connection:
        old_fingerprint = connection.execute(
            "SELECT private_authority_fingerprint_sha256 "
            "FROM private_objet_index_metadata"
        ).fetchone()[0]

    events: list[str] = []
    present_empty = empty_private_objet_authority("present_empty")
    base = _dependencies(
        events,
        inputs=[present_empty, present_empty],
        platform_name="posix",
    )

    def fail_after_private_rows(
        connection: sqlite3.Connection,
        projection: Any,
    ) -> None:
        replace_private_objet_index_rows(connection, projection)
        events.append("private_installer_injected_failure")
        raise PrivateObjetIndexContractError(
            rebuild.PRIVATE_OBJET_METADATA_PROJECTION_INVALID
        )

    dependencies = replace(base, replace_rows=fail_after_private_rows)
    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "new")
            session.install_private_rows_after_public()

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_PROJECTION_INVALID
    )
    assert events.count("private_installer_injected_failure") == 1
    assert events.count("rollback_call") == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "old"
        assert connection.execute(
            "SELECT private_authority_fingerprint_sha256 "
            "FROM private_objet_index_metadata"
        ).fetchone()[0] == old_fingerprint


def test_first_build_failure_leaves_no_partial_schema_or_rows(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    dependencies = _dependencies(events, platform_name="posix")

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "uncommitted")
            session.install_private_rows_after_public()
            raise RuntimeError("private path and value must be redacted")

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_REBUILD_FAILED
    )
    assert "private path" not in str(caught.value)
    assert events.count("rollback_call") == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE type IN ('table','index')"
        ).fetchall() == []


def test_bounded_rollback_retries_then_preserves_snapshot(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    dependencies = _dependencies(
        events,
        rollback_failures=2,
        platform_name="posix",
    )

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError):
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "uncommitted")
            raise RuntimeError("fail")

    assert events.count("rollback_call") == 3
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table'"
        ).fetchall() == []


def test_sqlite_busy_is_bounded_and_sanitized(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    with sqlite3.connect(db_path) as setup:
        setup.execute("CREATE TABLE public_rows(value TEXT NOT NULL)")
        setup.execute("INSERT INTO public_rows VALUES ('old')")
        setup.commit()
        setup.execute("PRAGMA journal_mode=WAL")

    blocker = sqlite3.connect(db_path)
    blocker.execute("BEGIN IMMEDIATE")
    events: list[str] = []
    dependencies = _dependencies(events, platform_name="posix")
    try:
        with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
            with rebuild.private_objet_index_rebuild_session(
                root,
                "archive-test",
                db_path,
                busy_timeout_ms=10,
                _dependencies=dependencies,
            ) as session:
                session.connection.executescript(
                    "BEGIN IMMEDIATE; DELETE FROM public_rows;"
                )
    finally:
        blocker.rollback()
        blocker.close()

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE
    )
    assert str(caught.value) == (
        rebuild.PRIVATE_OBJET_METADATA_PROJECTION_UNAVAILABLE
    )
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "old"


def test_windows_lock_contention_stops_before_snapshot_or_connection(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events, acquire_error=True)
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ):
            pytest.fail("contention must fail before yielding a session")

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_REBUILD_FAILED
    )
    assert "snapshot_a" not in events
    assert "connect" not in events
    assert events[-1] == "guard_release"


def test_private_lock_contention_stops_before_snapshot_or_connection(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events, acquire_failure_at="private")
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError):
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ):
            pytest.fail("contention must fail before yielding a session")

    assert "object_lock" in events
    assert "private_lock" in events
    assert "object_lock_acquire_unwind" in events
    assert "snapshot_a" not in events
    assert "connect" not in events
    assert events[-1] == "guard_release"


@pytest.mark.parametrize("acquire_failure_at", ["object", "private"])
def test_first_or_second_lock_interruption_unwinds_before_rethrow(
    tmp_path: Path,
    acquire_failure_at: str,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(
        events,
        acquire_failure_at=acquire_failure_at,
        acquire_interrupt=True,
    )
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(KeyboardInterrupt):
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ):
            pytest.fail("interruption must fail before yielding a session")

    if acquire_failure_at == "private":
        assert "object_lock_acquire_unwind" in events
    assert "snapshot_a" not in events
    assert "connect" not in events
    assert events[-1] == "guard_release"


def test_release_failure_terminalizes_and_reports_only_closed_code(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events, release_error=True)
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        _run_successful_rebuild(
            root,
            db_path,
            events=events,
            dependencies=dependencies,
            public_value="committed",
        )

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED
    )
    assert caught.value.committed is True
    assert str(caught.value) == (
        rebuild.PRIVATE_OBJET_METADATA_LOCK_RELEASE_FAILED
    )
    assert _first(events, "connection_close") < _first(
        events, "private_lock_release"
    )
    assert _first(events, "private_lock_release") < _first(
        events, "lock_terminal_release"
    )
    assert _first(events, "lock_terminal_release") < _first(
        events, "guard_release"
    )
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "committed"


def test_terminal_release_unproved_propagates_exit_74(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(
        events,
        release_error=True,
        terminal_exit=True,
    )
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(SystemExit) as caught:
        _run_successful_rebuild(
            root,
            db_path,
            events=events,
            dependencies=dependencies,
            public_value="committed",
        )

    assert caught.value.code == 74
    assert "guard_release" not in events


@pytest.mark.parametrize("release_interrupt_at", ["private", "object"])
def test_lock_release_interruption_terminalizes_before_rethrow(
    tmp_path: Path,
    release_interrupt_at: str,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(
        events,
        release_interrupt_at=release_interrupt_at,
    )
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(KeyboardInterrupt):
        _run_successful_rebuild(
            root,
            db_path,
            events=events,
            dependencies=dependencies,
            public_value="committed",
        )

    assert _first(events, "connection_close") < _first(
        events, "private_lock_release"
    )
    assert _first(events, "private_lock_release") < _first(
        events, "lock_terminal_release"
    )
    assert _first(events, "lock_terminal_release") < _first(
        events, "guard_release"
    )
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "committed"


def test_guard_release_interruption_terminalizes_before_rethrow(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events, guard_release_interrupt=True)
    dependencies = _dependencies(
        events,
        win32=win32,
        platform_name="nt",
    )

    with pytest.raises(KeyboardInterrupt):
        _run_successful_rebuild(
            root,
            db_path,
            events=events,
            dependencies=dependencies,
            public_value="committed",
        )

    assert _first(events, "object_lock_release") < _first(
        events, "guard_release"
    )
    assert _first(events, "guard_release") < _first(
        events, "guard_terminal_release"
    )


def test_unproved_connection_close_exits_74_before_unlocking(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    win32 = _fake_win32(events)
    dependencies = _dependencies(
        events,
        win32=win32,
        rollback_failures=3,
        close_failures=3,
        platform_name="nt",
    )

    with pytest.raises(SystemExit) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "uncommitted")
            raise RuntimeError("force rollback and close unwind")

    assert caught.value.code == 74
    assert events.count("rollback_call") == 3
    assert events.count("connection_close") == 3
    assert events.count("fatal_exit:74") == 1
    assert "private_lock_release" not in events
    assert "object_lock_release" not in events
    assert "guard_release" not in events


def test_postcommit_output_failure_never_rolls_back_committed_db(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    dependencies = _dependencies(events, platform_name="posix")

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "committed")
            session.install_private_rows_after_public()
            session.validate_and_commit()
            raise RuntimeError("private output transport detail")

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_REBUILD_FAILED
    )
    assert caught.value.committed is True
    assert events.count("commit_call") == 1
    assert events.count("rollback_call") == 0
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM public_rows"
        ).fetchone()[0] == "committed"
        assert connection.execute(
            "SELECT COUNT(*) FROM private_objet_index_metadata"
        ).fetchone()[0] == 1


def test_context_without_final_commit_rolls_back_and_fails_closed(
    tmp_path: Path,
) -> None:
    root, db_path = _archive(tmp_path)
    events: list[str] = []
    dependencies = _dependencies(events, platform_name="posix")

    with pytest.raises(rebuild.PrivateObjetIndexRebuildError) as caught:
        with rebuild.private_objet_index_rebuild_session(
            root,
            "archive-test",
            db_path,
            _dependencies=dependencies,
        ) as session:
            _build_public_rows(session.connection, "uncommitted")

    assert caught.value.code == (
        rebuild.PRIVATE_OBJET_METADATA_REBUILD_NOT_COMMITTED
    )
    assert events.count("rollback_call") == 1
