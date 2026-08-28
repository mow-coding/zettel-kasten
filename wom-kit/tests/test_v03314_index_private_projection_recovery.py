from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
from unittest import mock

from wom_kit import archive_services
from wom_kit import private_objet_metadata_index_health as private_health
from wom_kit import private_objet_metadata_index_session as private_session


KIT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CURRENT_ACTION = (
    "Generated index matches the live zettel path/id/status/kind snapshot "
    "checked here."
)


def _copy_archive(tmp_path: Path) -> Path:
    root = tmp_path / "archive"
    shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
    return root


def _archive_file_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _public_current_health() -> dict[str, object]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "index_health",
        "archive_id": "archive:test:v03314",
        "index_path": "db/archive-index.sqlite",
        "index_state": "current",
        "summary": {},
        "samples": {},
        "stale_reasons": [],
        "privacy_guards": {"writes": False},
        "would_change": [],
        "next_safe_actions": [PUBLIC_CURRENT_ACTION],
        "blockers": [],
        "warnings": [],
    }


def _decision(case_id: str) -> private_session.PrivateObjetMetadataHealthDecision:
    envelope = private_session.build_private_objet_metadata_health_envelope(
        case_id
    )
    return private_health._decision(case_id, envelope)


def test_ordinary_index_then_health_is_current_mode_ro_and_sidecar_free(
    tmp_path: Path,
) -> None:
    root = _copy_archive(tmp_path)
    rebuilt = archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")
    journal_path = Path(str(db_path) + "-journal")

    assert rebuilt["ok"] is True
    assert rebuilt["index_rebuilt"] is True
    assert rebuilt["index_complete"] is True
    assert rebuilt["index_state"] == "current"
    assert db_path.read_bytes()[18:20] == b"\x01\x01"
    assert not wal_path.exists()
    assert not shm_path.exists()
    assert not journal_path.exists()

    before = _archive_file_snapshot(root)
    real_connect = sqlite3.connect
    with mock.patch.object(
        archive_services.sqlite3,
        "connect",
        wraps=real_connect,
    ) as opened:
        health = archive_services.index_health(root, dry_run=True)
    after = _archive_file_snapshot(root)

    assert health["ok"] is True
    assert health["index_state"] == "current"
    assert health["summary"]["live_zettel_enumeration_performed"] is True
    assert health["summary"]["index_comparison_performed"] is True
    assert health["blockers"] == []
    assert health["stale_reasons"] == []
    assert health["privacy_guards"]["writes"] is False
    assert health["private_objet_metadata"]["authority_validity"] == "valid"
    assert health["private_objet_metadata"]["projection_validity"] == "valid"
    assert health["private_objet_metadata"]["freshness"] == "current"
    assert health["private_objet_metadata"]["index_state"] == "current"
    assert before == after
    assert not wal_path.exists()
    assert not shm_path.exists()
    assert not journal_path.exists()

    read_uris = [
        call.args[0]
        for call in opened.call_args_list
        if call.kwargs.get("uri") is True
    ]
    assert len(read_uris) >= 2
    assert all(
        isinstance(uri, str)
        and uri.endswith("?mode=ro")
        and "immutable=" not in uri
        for uri in read_uris
    )


def test_ordinary_rebuild_converts_legacy_clean_wal_to_delete(
    tmp_path: Path,
) -> None:
    root = _copy_archive(tmp_path)
    archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH

    legacy = sqlite3.connect(db_path)
    try:
        assert legacy.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        legacy.execute("BEGIN IMMEDIATE")
        legacy.execute(
            "UPDATE index_metadata SET value = value WHERE key = 'state'"
        )
        legacy.commit()
    finally:
        legacy.close()
    assert db_path.read_bytes()[18:20] == b"\x02\x02"
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()

    before_health = _archive_file_snapshot(root)
    with mock.patch.object(
        archive_services,
        "live_zettel_index_entries",
        wraps=archive_services.live_zettel_index_entries,
    ) as enumerated:
        legacy_health = archive_services.index_health(root, dry_run=True)
    after_health = _archive_file_snapshot(root)

    assert legacy_health["ok"] is False
    assert legacy_health["index_state"] == "blocked"
    enumerated.assert_not_called()
    assert (
        legacy_health["summary"]["live_zettel_enumeration_performed"]
        is False
    )
    assert legacy_health["summary"]["live_zettel_count"] == 0
    assert legacy_health["summary"]["index_comparison_performed"] is False
    assert legacy_health["summary"]["missing_from_index_count"] == 0
    assert legacy_health["summary"]["extra_in_index_count"] == 0
    assert legacy_health["summary"]["changed_metadata_count"] == 0
    assert legacy_health["stale_reasons"] == ["index_health_blocked"]
    assert "archive_index_rebuild_required" in legacy_health["blockers"]
    assert (
        "private_objet_metadata_projection_unavailable"
        in legacy_health["blockers"]
    )
    assert (
        legacy_health["private_objet_metadata"]["index_state"] == "blocked"
    )
    assert len(legacy_health["next_safe_actions"]) == 2
    assert (
        "archive index <archive-root> --progress --format json"
        in legacy_health["next_safe_actions"][0]
    )
    assert (
        "archive index-health <archive-root> --dry-run --progress --format json"
        in legacy_health["next_safe_actions"][1]
    )
    assert before_health == after_health
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()

    rebuilt = archive_services.index_archive(root)
    health = archive_services.index_health(root, dry_run=True)

    assert rebuilt["ok"] is True
    assert db_path.read_bytes()[18:20] == b"\x01\x01"
    assert health["ok"] is True
    assert health["private_objet_metadata"]["index_state"] == "current"
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()
    assert not Path(str(db_path) + "-journal").exists()


def test_rebuild_preflight_closes_authority_fence_before_non_rebuild_error(
    tmp_path: Path,
) -> None:
    root = _copy_archive(tmp_path)
    assert archive_services.index_archive(root)["ok"] is True
    real_fence_factory = archive_services._ArchiveIndexAuthorityFence
    created_fences: list[object] = []

    class TrackingFence:
        def __init__(self, archive_root: Path) -> None:
            self.inner = real_fence_factory(archive_root)
            self.closed = False
            created_fences.append(self)

        def close(self) -> None:
            self.inner.close()
            self.closed = True

        def __getattr__(self, name: str) -> object:
            return getattr(self.inner, name)

    injected = archive_services.ArchiveIndexReadBoundaryError(
        "archive_index_read_preflight_failed"
    )
    with mock.patch.object(
        archive_services,
        "_ArchiveIndexAuthorityFence",
        side_effect=TrackingFence,
    ), mock.patch.object(
        archive_services,
        "connect_archive_index",
        side_effect=injected,
    ):
        try:
            archive_services.index_archive(root)
        except archive_services.ArchiveIndexReadBoundaryError as exc:
            assert exc is injected
        else:
            raise AssertionError("non-rebuild boundary error was swallowed")

    assert len(created_fences) == 1
    assert created_fences[0].closed is True
    shutil.rmtree(root)
    assert not root.exists()


def test_rebuild_preflight_closes_fence_and_preserves_base_exceptions(
    tmp_path: Path,
) -> None:
    real_fence_factory = archive_services._ArchiveIndexAuthorityFence

    for case_name, injected in (
        ("keyboard-interrupt", KeyboardInterrupt("stop")),
        ("system-exit", SystemExit(7)),
    ):
        root = tmp_path / case_name / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        assert archive_services.index_archive(root)["ok"] is True
        created_fences: list[object] = []

        class TrackingFence:
            def __init__(self, archive_root: Path) -> None:
                self.inner = real_fence_factory(archive_root)
                self.closed = False
                created_fences.append(self)

            def close(self) -> None:
                self.inner.close()
                self.closed = True

            def __getattr__(self, name: str) -> object:
                return getattr(self.inner, name)

        with mock.patch.object(
            archive_services,
            "_ArchiveIndexAuthorityFence",
            side_effect=TrackingFence,
        ), mock.patch.object(
            archive_services,
            "connect_archive_index",
            side_effect=injected,
        ):
            try:
                archive_services.index_archive(root)
            except BaseException as exc:
                assert exc is injected
            else:
                raise AssertionError("base exception was swallowed")

        assert len(created_fences) == 1
        assert created_fences[0].closed is True
        shutil.rmtree(root)
        assert not root.exists()


def test_blocked_private_cases_project_top_level_blockers_and_commands() -> None:
    for case_id, expected_blocker in (
        ("C1", "private_objet_metadata_snapshot_changed"),
        ("C2", "private_objet_metadata_projection_unavailable"),
        ("C6", "private_objet_metadata_projection_unavailable"),
    ):
        result = private_health.compose_private_objet_metadata_index_health(
            _public_current_health(),
            _decision(case_id),
        )

        assert result["ok"] is False
        assert result["index_state"] == "blocked"
        assert result["blockers"] == [expected_blocker]
        assert result["stale_reasons"] == []
        assert PUBLIC_CURRENT_ACTION not in result["next_safe_actions"]
        if case_id == "C1":
            assert len(result["next_safe_actions"]) == 1
            assert (
                "archive index-health <archive-root> --dry-run --progress "
                "--format json"
            ) in result["next_safe_actions"][0]
        else:
            assert len(result["next_safe_actions"]) == 2
            assert (
                "archive index <archive-root> --progress --format json"
            ) in result["next_safe_actions"][0]
            assert (
                "archive index-health <archive-root> --dry-run --progress "
                "--format json"
            ) in result["next_safe_actions"][1]


def test_incremental_index_writer_verifies_delete_mode(tmp_path: Path) -> None:
    root = _copy_archive(tmp_path)
    archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH

    connection = archive_services.connect_archive_index(
        db_path,
        write=True,
    )
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert (
            connection.execute("PRAGMA busy_timeout").fetchone()[0]
            == archive_services.ARCHIVE_INDEX_BUSY_TIMEOUT_MS
        )
    finally:
        connection.close()

    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()
    assert not Path(str(db_path) + "-journal").exists()


def test_health_rejects_rollback_journal_before_sqlite_open(tmp_path: Path) -> None:
    root = _copy_archive(tmp_path)
    archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    journal_path = Path(str(db_path) + "-journal")
    journal_path.write_bytes(b"")
    before = _archive_file_snapshot(root)

    with mock.patch.object(
        archive_services.sqlite3,
        "connect",
        wraps=sqlite3.connect,
    ) as opened:
        health = archive_services.index_health(root, dry_run=True)

    assert health["ok"] is False
    assert health["index_state"] == "blocked"
    assert health["summary"]["live_zettel_enumeration_performed"] is False
    assert "archive_index_rebuild_required" in health["blockers"]
    assert (
        "private_objet_metadata_projection_unavailable"
        in health["blockers"]
    )
    assert opened.call_count == 0
    assert before == _archive_file_snapshot(root)
    assert journal_path.exists()
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()


def test_incremental_writer_rejects_legacy_wal_without_migrating_it(
    tmp_path: Path,
) -> None:
    root = _copy_archive(tmp_path)
    archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    legacy = sqlite3.connect(db_path)
    try:
        assert legacy.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        legacy.execute("BEGIN IMMEDIATE")
        legacy.execute(
            "UPDATE index_metadata SET value = value WHERE key = 'state'"
        )
        legacy.commit()
    finally:
        legacy.close()
    assert db_path.read_bytes()[18:20] == b"\x02\x02"
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()

    immutable_uri = db_path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
    before_reader = sqlite3.connect(immutable_uri, uri=True)
    try:
        before_rows = before_reader.execute(
            "SELECT COUNT(*) FROM zettels"
        ).fetchone()[0]
    finally:
        before_reader.close()
    before_bytes = db_path.read_bytes()

    try:
        archive_services.connect_archive_index(db_path, write=True)
    except archive_services.ArchiveIndexReadBoundaryError as exc:
        assert str(exc) == "archive_index_rebuild_required"
    else:
        raise AssertionError("legacy WAL writer unexpectedly opened")

    after_reader = sqlite3.connect(immutable_uri, uri=True)
    try:
        after_rows = after_reader.execute(
            "SELECT COUNT(*) FROM zettels"
        ).fetchone()[0]
    finally:
        after_reader.close()
    assert after_rows == before_rows
    assert db_path.read_bytes() == before_bytes
    assert db_path.read_bytes()[18:20] == b"\x02\x02"
    assert not Path(str(db_path) + "-wal").exists()
    assert not Path(str(db_path) + "-shm").exists()
    assert not Path(str(db_path) + "-journal").exists()


def test_health_fails_closed_while_internal_delete_writer_is_active(
    tmp_path: Path,
) -> None:
    root = _copy_archive(tmp_path)
    archive_services.index_archive(root)
    db_path = root / archive_services.INDEX_RELATIVE_PATH
    journal_path = Path(str(db_path) + "-journal")
    writer = archive_services.connect_archive_index(db_path, write=True)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute(
        "UPDATE index_metadata SET value = value || '-probe' "
        "WHERE key = 'state'"
    )
    assert journal_path.exists()

    def storage_tokens() -> dict[str, tuple[int, int, int, int]]:
        return {
            path.name: (
                path.stat().st_size,
                path.stat().st_mtime_ns,
                path.stat().st_ctime_ns,
                path.stat().st_ino,
            )
            for path in (db_path, journal_path)
        }

    before = storage_tokens()
    real_connect = sqlite3.connect
    try:
        with mock.patch.object(
            archive_services.sqlite3,
            "connect",
            wraps=real_connect,
        ) as opened:
            health = archive_services.index_health(root, dry_run=True)
        assert opened.call_count == 0
        assert storage_tokens() == before
        assert health["ok"] is False
        assert health["index_state"] == "blocked"
        assert (
            health["summary"]["live_zettel_enumeration_performed"]
            is False
        )
        assert "archive_index_rebuild_required" in health["blockers"]
        assert (
            "private_objet_metadata_projection_unavailable"
            in health["blockers"]
        )
        assert health["summary"]["index_comparison_performed"] is False
    finally:
        writer.rollback()
        writer.close()

    assert not journal_path.exists()
    recovered = archive_services.index_health(root, dry_run=True)
    assert recovered["ok"] is True
    assert recovered["index_state"] == "current"
