from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, mcp_server


KIT_ROOT = Path(__file__).resolve().parents[1]
FAKE_ARCHIVE = KIT_ROOT / "examples" / "fake-life-archive"
PRIVATE_QUERY = "PRIVATE_QUERY_FILENAME_CANARY.hwpx"
PRIVATE_EXCEPTION = "PRIVATE_EXCEPTION_PATH_CANARY"
EXPECTED_LAYER_IDS = [
    "indexed_zettels",
    "indexed_object_manifests",
    "indexed_derived_text",
    "indexed_views",
    "indexed_source_records",
    "zettel_objet_edges",
    "private_original_name_metadata",
    "approved_external_local_store",
    "external_store_evidence",
    "unrecovered_source_references",
]


class ObjetRediscoveryPlanTests(unittest.TestCase):
    def copy_archive(self, parent: Path, *, index: bool = True) -> Path:
        archive_root = parent / "archive"
        shutil.copytree(FAKE_ARCHIVE, archive_root)
        if index:
            result = archive_services.index_archive(archive_root)
            self.assertTrue(result["ok"], result)
        return archive_root

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def create_directory_reparse(link: Path, target: Path) -> None:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(link),
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise OSError("Windows junction creation failed")
            return
        link.symlink_to(target, target_is_directory=True)

    @staticmethod
    def remove_directory_reparse(link: Path) -> None:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()

    def tree_digest(self, root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def assert_fixed_private_boundary(
        self,
        result: dict[str, object],
        *,
        serialized: str | None = None,
    ) -> None:
        self.assertEqual(
            [layer["layer_id"] for layer in result["checked_layers"]],  # type: ignore[index]
            EXPECTED_LAYER_IDS,
        )
        self.assertFalse(result["query_echoed"])
        self.assertFalse(result["rediscovery_complete"])
        self.assertFalse(result["negative_claim_supported"])
        payload = serialized if serialized is not None else json.dumps(result)
        self.assertNotIn(PRIVATE_QUERY, payload)
        self.assertNotIn(PRIVATE_EXCEPTION, payload)
        self.assertNotIn("Traceback", payload)

    def test_zero_index_matches_remain_incomplete_and_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            before = self.tree_digest(archive_root)

            result = archive_services.objet_rediscovery_plan(
                archive_root,
                PRIVATE_QUERY,
                dry_run=True,
                limit=20,
                count_total=True,
            )

            after = self.tree_digest(archive_root)

        self.assertEqual(before, after)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "search_incomplete")
        self.assertEqual(result["schema"], "wom-kit/objet-rediscovery-plan/v0.1")
        self.assertEqual(result["checked_match_count"], 0)
        self.assertTrue(result["checked_match_count_exact"])
        self.assertEqual(result["unchecked_or_unavailable_layer_count"], 5)
        self.assertTrue(result["index_search"]["complete"])
        self.assertFalse(result["index_search"]["truncated"])
        self.assertEqual(result["index_search"]["total_matches"], 0)
        self.assertTrue(result["index_search"]["total_matches_known"])
        self.assertEqual(
            [layer["check_state"] for layer in result["checked_layers"][:5]],
            ["checked_snapshot_only"] * 5,
        )
        self.assertEqual(
            [layer["freshness_proven"] for layer in result["checked_layers"]],
            [False] * 10,
        )
        self.assertEqual(
            result["checked_layers"][0]["match_state"],
            "no_match_in_checked_scope",
        )
        self.assertEqual(
            result["checked_layers"][5]["check_state"],
            "unchecked",
        )
        self.assertEqual(
            [layer["check_state"] for layer in result["checked_layers"][6:]],
            [
                "unchecked",
                "not_implemented",
                "unchecked",
                "not_implemented",
            ],
        )
        self.assertEqual(
            result["checked_layers"][8]["reason_codes"],
            ["backup_evidence_status_not_checked"],
        )
        private_metadata_layer = result["checked_layers"][6]
        self.assertEqual(
            private_metadata_layer["layer_id"],
            "private_original_name_metadata",
        )
        self.assertEqual(
            private_metadata_layer["evidence_scope"],
            "The v0.3.296 approved private metadata writer exists, but this release "
            "implements no receipt-bound private metadata index or private "
            "rediscovery query and proves no private index freshness.",
        )
        self.assertEqual(
            private_metadata_layer["reason_codes"],
            ["private_metadata_rediscovery_not_checked"],
        )
        self.assertFalse(private_metadata_layer["freshness_proven"])
        self.assertFalse(private_metadata_layer["negative_claim_contribution"])
        self.assertIn(
            "archive backup-evidence <archive-root> --dry-run",
            result["next_safe_commands"],
        )
        self.assertTrue(
            result["index_health"]["zettel_identity_metadata_current"]
        )
        self.assertFalse(
            result["index_health"][
                "zettel_search_content_freshness_proven"
            ]
        )
        self.assertFalse(
            result["index_health"]["non_zettel_source_freshness_proven"]
        )
        self.assert_fixed_private_boundary(result)
        self.assertTrue(all(not value for value in result["closed_actions"].values()))
        self.assertTrue(all(not value for value in result["privacy"].values()))

    def test_candidates_and_count_total_do_not_upgrade_rediscovery_or_search_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))

            ordinary_capped = archive_services.search_archive(
                archive_root,
                "fake",
                limit=1,
                count_total=False,
            )
            plan_capped = archive_services.objet_rediscovery_plan(
                archive_root,
                "fake",
                dry_run=True,
                limit=1,
                count_total=False,
            )
            ordinary_counted = archive_services.search_archive(
                archive_root,
                "fake",
                limit=1,
                count_total=True,
            )
            plan_counted = archive_services.objet_rediscovery_plan(
                archive_root,
                "fake",
                dry_run=True,
                limit=1,
                count_total=True,
            )

        self.assertTrue(ordinary_capped["truncated"])
        self.assertFalse(ordinary_capped["complete"])
        self.assertFalse(ordinary_capped["total_matches_known"])
        self.assertEqual(
            plan_capped["index_search"]["complete"],
            ordinary_capped["complete"],
        )
        self.assertEqual(
            plan_capped["index_search"]["truncated"],
            ordinary_capped["truncated"],
        )
        self.assertIsNone(plan_capped["index_search"]["total_matches"])
        self.assertGreater(plan_capped["checked_match_count"], 0)
        self.assertGreater(
            plan_capped["checked_match_count"],
            plan_capped["index_search"]["returned"],
        )
        self.assertFalse(plan_capped["checked_match_count_exact"])
        capped_layer_states = [
            layer["check_state"] for layer in plan_capped["checked_layers"][:5]
        ]
        self.assertEqual(capped_layer_states[0], "checked_truncated")
        self.assertTrue(
            all(
                state in {"checked_truncated", "checked_snapshot_only"}
                for state in capped_layer_states
            )
        )
        self.assertEqual(
            plan_capped["checked_layers"][0]["match_state"],
            "matches_found",
        )
        self.assertNotIn(
            "unknown",
            [
                layer["match_state"]
                for layer in plan_capped["checked_layers"][:5]
            ],
        )

        self.assertTrue(ordinary_counted["truncated"])
        self.assertFalse(ordinary_counted["complete"])
        self.assertTrue(ordinary_counted["total_matches_known"])
        self.assertFalse(plan_counted["index_search"]["complete"])
        self.assertTrue(plan_counted["index_search"]["truncated"])
        self.assertEqual(
            plan_counted["index_search"]["total_matches"],
            ordinary_counted["total_matches"],
        )
        self.assertEqual(
            plan_counted["index_search"]["matches_by_type"],
            ordinary_counted["matches_by_type"],
        )
        for result in (plan_capped, plan_counted):
            self.assertEqual(result["status"], "search_incomplete")
            self.assertFalse(result["rediscovery_complete"])
            self.assertFalse(result["negative_claim_supported"])
            self.assert_fixed_private_boundary(result)

    def test_early_global_truncation_cannot_hide_an_unavailable_later_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            index_path = archive_root / "db" / "archive-index.sqlite"
            conn = sqlite3.connect(index_path)
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.execute("DROP TABLE objects")
                conn.commit()
            finally:
                conn.close()

            result = archive_services.objet_rediscovery_plan(
                archive_root,
                "fake",
                dry_run=True,
                limit=1,
                count_total=False,
            )

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["diagnostic_codes"],
                ["archive_index_unavailable"],
            )
            self.assertEqual(
                [layer["check_state"] for layer in result["checked_layers"]],
                ["blocked"] * 10,
            )
            self.assert_fixed_private_boundary(result)

    def test_stale_zettel_and_all_non_zettel_channels_are_snapshot_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            zettel_path = (
                archive_root
                / "zettels"
                / "zet_20260519_fake_family_memory.md"
            )
            zettel_path.write_text(
                zettel_path.read_text(encoding="utf-8")
                + "\nPRIVATE_STALE_BODY_CANARY\n",
                encoding="utf-8",
                newline="\n",
            )
            future = (archive_root / "db" / "archive-index.sqlite").stat().st_mtime + 5
            os.utime(zettel_path, (future, future))
            before = self.tree_digest(archive_root)

            result = archive_services.objet_rediscovery_plan(
                archive_root,
                PRIVATE_QUERY,
                dry_run=True,
                count_total=True,
            )

            after = self.tree_digest(archive_root)

        self.assertEqual(before, after)
        self.assertEqual(result["status"], "search_incomplete")
        self.assertEqual(
            result["index_health"]["index_state"],
            "stale_or_incomplete",
        )
        self.assertFalse(
            result["index_health"]["zettel_identity_metadata_current"]
        )
        self.assertIn(
            "live_zettel_modified_after_index",
            result["index_health"]["stale_reason_codes"],
        )
        self.assertIn(
            "index_freshness_not_current",
            result["diagnostic_codes"],
        )
        self.assertEqual(
            result["checked_layers"][0]["check_state"],
            "checked_snapshot_only",
        )
        self.assertEqual(
            result["checked_layers"][0]["reason_codes"],
            ["index_freshness_not_current"],
        )
        self.assertEqual(
            [layer["freshness_proven"] for layer in result["checked_layers"][:5]],
            [False] * 5,
        )
        self.assertNotIn("PRIVATE_STALE_BODY_CANARY", json.dumps(result))
        self.assert_fixed_private_boundary(result)

    def test_missing_malformed_and_pending_wal_indexes_block_without_writes_or_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)

            missing = self.copy_archive(parent / "missing", index=False)
            missing_before = self.tree_digest(missing)
            code, stdout, stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(missing),
                    PRIVATE_QUERY,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            missing_after = self.tree_digest(missing)
            missing_result = json.loads(stdout)
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertEqual(missing_before, missing_after)
            self.assertEqual(missing_result["status"], "blocked")
            self.assertIn(
                "archive_index_unavailable",
                missing_result["diagnostic_codes"],
            )
            self.assertNotIn(str(missing), stdout)
            self.assert_fixed_private_boundary(missing_result, serialized=stdout)

            malformed = self.copy_archive(parent / "malformed")
            index_path = malformed / "db" / "archive-index.sqlite"
            index_path.write_bytes(b"not sqlite PRIVATE_DATABASE_CANARY")
            malformed_before = self.tree_digest(malformed)
            code, stdout, stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(malformed),
                    PRIVATE_QUERY,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            malformed_after = self.tree_digest(malformed)
            malformed_result = json.loads(stdout)
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertEqual(malformed_before, malformed_after)
            self.assertEqual(malformed_result["status"], "blocked")
            self.assertNotIn("PRIVATE_DATABASE_CANARY", stdout)
            self.assertNotIn(str(malformed), stdout)
            self.assert_fixed_private_boundary(
                malformed_result,
                serialized=stdout,
            )

            for suffix, canary in (
                ("-wal", b"PRIVATE_PENDING_WAL_CANARY"),
                ("-journal", b"PRIVATE_PENDING_JOURNAL_CANARY"),
            ):
                with self.subTest(pending_sidecar=suffix):
                    pending = self.copy_archive(
                        parent / f"pending-{suffix.removeprefix('-')}"
                    )
                    sidecar_path = Path(
                        f"{pending / 'db' / 'archive-index.sqlite'}{suffix}"
                    )
                    sidecar_path.write_bytes(canary)
                    pending_before = self.tree_digest(pending)
                    pending_result = archive_services.objet_rediscovery_plan(
                        pending,
                        PRIVATE_QUERY,
                        dry_run=True,
                    )
                    pending_after = self.tree_digest(pending)
                    self.assertEqual(pending_before, pending_after)
                    self.assertEqual(pending_result["status"], "blocked")
                    self.assertEqual(
                        pending_result["diagnostic_codes"],
                        ["archive_index_snapshot_unstable"],
                    )
                    self.assertNotIn(
                        canary.decode("ascii"),
                        json.dumps(pending_result),
                    )
                    self.assert_fixed_private_boundary(pending_result)

    def test_permission_decoder_and_snapshot_change_errors_are_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))

            failures = [
                (
                    "search_archive_immutable_snapshot",
                    PermissionError(PRIVATE_EXCEPTION),
                    "archive_index_unavailable",
                ),
                (
                    "index_health_immutable_snapshot",
                    UnicodeError(PRIVATE_EXCEPTION),
                    "archive_index_unavailable",
                ),
            ]
            for target, error, expected_code in failures:
                with self.subTest(target=target), mock.patch.object(
                    archive_services,
                    target,
                    side_effect=error,
                ):
                    result = archive_services.objet_rediscovery_plan(
                        archive_root,
                        PRIVATE_QUERY,
                        dry_run=True,
                    )
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["diagnostic_codes"], [expected_code])
                self.assert_fixed_private_boundary(result)

            with mock.patch.object(
                archive_services,
                "objet_rediscovery_index_snapshot_state",
                side_effect=[
                    ((100, 100, 100), False),
                    ((100, 101, 100), False),
                ],
            ):
                changed = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                )

        self.assertEqual(changed["status"], "blocked")
        self.assertEqual(
            changed["diagnostic_codes"],
            ["archive_index_snapshot_changed"],
        )
        self.assert_fixed_private_boundary(changed)

    def test_plan_uses_one_pinned_sqlite_snapshot_for_all_three_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            real_connect = archive_services.connect_archive_index
            real_health = archive_services.index_health_immutable_snapshot
            real_search = archive_services.search_archive_immutable_snapshot
            real_channels = archive_services.objet_rediscovery_index_channel_evidence
            events: list[tuple[str, str]] = []
            connect_calls: list[dict[str, object]] = []
            helper_calls: list[tuple[str, object, bool]] = []

            class RecordingConnection:
                def __init__(self, connection: sqlite3.Connection) -> None:
                    self.connection = connection

                @property
                def row_factory(self) -> object:
                    return self.connection.row_factory

                @property
                def in_transaction(self) -> bool:
                    return self.connection.in_transaction

                def execute(
                    self,
                    sql: str,
                    parameters: object = (),
                ) -> sqlite3.Cursor:
                    normalized = " ".join(sql.split())
                    events.append(("execute", normalized))
                    return self.connection.execute(sql, parameters)  # type: ignore[arg-type]

                def rollback(self) -> None:
                    events.append(("lifecycle", "rollback"))
                    self.connection.rollback()

                def close(self) -> None:
                    events.append(("lifecycle", "close"))
                    self.connection.close()

            proxy: RecordingConnection | None = None

            def connect_once(
                db_path: Path,
                **kwargs: object,
            ) -> RecordingConnection:
                nonlocal proxy
                connect_calls.append(kwargs)
                proxy = RecordingConnection(real_connect(db_path, **kwargs))  # type: ignore[arg-type]
                return proxy

            def record_helper(
                name: str,
                function: object,
            ) -> object:
                def invoke(*args: object, **kwargs: object) -> object:
                    connection = kwargs.get("connection")
                    helper_calls.append(
                        (
                            name,
                            connection,
                            bool(getattr(connection, "in_transaction", False)),
                        )
                    )
                    return function(*args, **kwargs)  # type: ignore[operator]

                return invoke

            with (
                mock.patch.object(
                    archive_services,
                    "connect_archive_index",
                    side_effect=connect_once,
                ),
                mock.patch.object(
                    archive_services,
                    "index_health_immutable_snapshot",
                    side_effect=record_helper("health", real_health),
                ),
                mock.patch.object(
                    archive_services,
                    "search_archive_immutable_snapshot",
                    side_effect=record_helper("search", real_search),
                ),
                mock.patch.object(
                    archive_services,
                    "objet_rediscovery_index_channel_evidence",
                    side_effect=record_helper("channels", real_channels),
                ),
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                    count_total=True,
                )

        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(proxy)
        self.assertEqual(
            connect_calls,
            [{"row_factory": True, "immutable_read": True}],
        )
        self.assertEqual(
            [name for name, _connection, _active in helper_calls],
            ["health", "search", "channels"],
        )
        self.assertTrue(
            all(connection is proxy for _name, connection, _active in helper_calls)
        )
        self.assertTrue(all(active for _name, _connection, active in helper_calls))
        self.assertEqual(
            [event for event in events if event == ("execute", "BEGIN")],
            [("execute", "BEGIN")],
        )
        self.assertEqual(
            [
                event
                for event in events
                if event
                == (
                    "execute",
                    "SELECT 1 FROM sqlite_master LIMIT 1",
                )
            ],
            [
                (
                    "execute",
                    "SELECT 1 FROM sqlite_master LIMIT 1",
                )
            ],
        )
        self.assertEqual(events[-2:], [("lifecycle", "rollback"), ("lifecycle", "close")])

    def test_borrowed_sqlite_helpers_do_not_manage_connection_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            db_path = archive_root / archive_services.INDEX_RELATIVE_PATH
            connection = archive_services.connect_archive_index(
                db_path,
                row_factory=True,
                immutable_read=True,
            )
            connection.execute("BEGIN")
            connection.execute(
                "SELECT 1 FROM sqlite_master LIMIT 1"
            ).fetchone()

            class BorrowedConnection:
                @property
                def row_factory(self) -> object:
                    return connection.row_factory

                @property
                def in_transaction(self) -> bool:
                    return connection.in_transaction

                def execute(
                    self,
                    sql: str,
                    parameters: object = (),
                ) -> sqlite3.Cursor:
                    if " ".join(sql.split()).upper() == "BEGIN":
                        raise AssertionError("borrowed helper began a transaction")
                    return connection.execute(sql, parameters)  # type: ignore[arg-type]

                def rollback(self) -> None:
                    raise AssertionError("borrowed helper rolled back")

                def close(self) -> None:
                    raise AssertionError("borrowed helper closed")

            borrowed = BorrowedConnection()
            try:
                with mock.patch.object(
                    archive_services,
                    "connect_archive_index",
                    side_effect=AssertionError("borrowed helper reconnected"),
                ):
                    health = archive_services.index_health_immutable_snapshot(
                        archive_root,
                        dry_run=True,
                        max_items=1,
                        connection=borrowed,  # type: ignore[arg-type]
                    )
                    search = archive_services.search_archive_immutable_snapshot(
                        archive_root,
                        PRIVATE_QUERY,
                        count_total=True,
                        connection=borrowed,  # type: ignore[arg-type]
                    )
                    channels = archive_services.objet_rediscovery_index_channel_evidence(
                        archive_root,
                        PRIVATE_QUERY,
                        limit=20,
                        connection=borrowed,  # type: ignore[arg-type]
                    )
                self.assertTrue(connection.in_transaction)
            finally:
                connection.rollback()
                connection.close()

        self.assertIn(health["index_state"], {"current", "stale_or_incomplete"})
        self.assertTrue(search["total_matches_known"])
        self.assertEqual(set(channels), set(archive_services.SEARCH_CHANNEL_TABLES[index][0] for index in range(len(archive_services.SEARCH_CHANNEL_TABLES))))

    def test_borrowed_sqlite_helpers_reject_unpinned_or_non_row_connections(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()

            class InvalidConnection:
                def __init__(self, *, row_factory: object, in_transaction: bool) -> None:
                    self.row_factory = row_factory
                    self.in_transaction = in_transaction

                def execute(self, *_args: object, **_kwargs: object) -> object:
                    raise AssertionError("invalid borrowed connection executed SQL")

            calls = (
                lambda connection: archive_services.index_health_immutable_snapshot(
                    archive_root,
                    connection=connection,  # type: ignore[arg-type]
                ),
                lambda connection: archive_services.search_archive_immutable_snapshot(
                    archive_root,
                    PRIVATE_QUERY,
                    connection=connection,  # type: ignore[arg-type]
                ),
                lambda connection: archive_services.objet_rediscovery_index_channel_evidence(
                    archive_root,
                    PRIVATE_QUERY,
                    limit=20,
                    connection=connection,  # type: ignore[arg-type]
                ),
            )
            invalid_connections = (
                InvalidConnection(
                    row_factory=None,
                    in_transaction=True,
                ),
                InvalidConnection(
                    row_factory=sqlite3.Row,
                    in_transaction=False,
                ),
            )
            for call in calls:
                for connection in invalid_connections:
                    with self.subTest(
                        helper=call,
                        row_factory=connection.row_factory,
                        in_transaction=connection.in_transaction,
                    ):
                        with self.assertRaises(archive_services.ArchiveServiceError):
                            call(connection)

    def test_shared_sqlite_rollback_failure_still_closes_without_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            real_connect = archive_services.connect_archive_index
            connection = real_connect(
                archive_root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
                immutable_read=True,
            )
            closed = False

            class RollbackFailureConnection:
                @property
                def row_factory(self) -> object:
                    return connection.row_factory

                @property
                def in_transaction(self) -> bool:
                    return connection.in_transaction

                def execute(
                    self,
                    sql: str,
                    parameters: object = (),
                ) -> sqlite3.Cursor:
                    return connection.execute(sql, parameters)  # type: ignore[arg-type]

                def rollback(self) -> None:
                    raise sqlite3.OperationalError(PRIVATE_EXCEPTION)

                def close(self) -> None:
                    nonlocal closed
                    closed = True
                    connection.close()

            with mock.patch.object(
                archive_services,
                "connect_archive_index",
                return_value=RollbackFailureConnection(),
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                )

        serialized = json.dumps(result)
        self.assertTrue(closed)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["diagnostic_codes"],
            ["archive_index_unavailable"],
        )
        self.assertNotIn(PRIVATE_EXCEPTION, serialized)
        self.assert_fixed_private_boundary(result, serialized=serialized)

    def test_blob_typed_search_columns_fail_closed_without_private_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            index_path = archive_root / "db" / "archive-index.sqlite"
            private_blob = "PRIVATE_TYPED_BLOB_CANARY"
            conn = sqlite3.connect(index_path)
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.execute(
                    "UPDATE zettels SET body = CAST(? AS BLOB)",
                    (private_blob,),
                )
                conn.commit()
            finally:
                conn.close()

            before = self.tree_digest(archive_root)
            result = archive_services.objet_rediscovery_plan(
                archive_root,
                private_blob,
                dry_run=True,
                count_total=True,
            )
            after = self.tree_digest(archive_root)

            self.assertEqual(before, after)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["diagnostic_codes"],
                ["archive_index_unavailable"],
            )
            serialized = json.dumps(result)
            self.assertNotIn(private_blob, serialized)
            self.assert_fixed_private_boundary(result, serialized=serialized)

            code, stdout, stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    private_blob,
                    "--dry-run",
                    "--count-total",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertNotIn(private_blob, stdout)
            self.assertNotIn(str(archive_root), stdout)
            self.assert_fixed_private_boundary(
                json.loads(stdout),
                serialized=stdout,
            )

    def test_plan_never_calls_writer_provider_network_credential_or_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            with (
                mock.patch.object(
                    archive_services,
                    "index_archive",
                    side_effect=AssertionError("index rebuild called"),
                ) as index_mock,
                mock.patch.object(
                    archive_services,
                    "resolve_objet_ref",
                    side_effect=AssertionError("resolver called"),
                ) as resolver_mock,
                mock.patch.object(
                    archive_services,
                    "provider_setup_status",
                    side_effect=AssertionError("provider called"),
                ) as provider_mock,
                mock.patch.object(
                    archive_services,
                    "credential_ref_inventory",
                    side_effect=AssertionError("credential called"),
                ) as credential_mock,
                mock.patch.object(
                    archive_services.urllib.request,
                    "urlopen",
                    side_effect=AssertionError("network called"),
                ) as network_mock,
                mock.patch.object(
                    archive_services.subprocess,
                    "run",
                    side_effect=AssertionError("subprocess called"),
                ) as subprocess_mock,
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                    count_total=True,
                )

        self.assertTrue(result["ok"])
        for called in (
            index_mock,
            resolver_mock,
            provider_mock,
            credential_mock,
            network_mock,
            subprocess_mock,
        ):
            called.assert_not_called()
        self.assert_fixed_private_boundary(result)

    def test_reparse_directory_blocks_before_external_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            archive_root = self.copy_archive(parent / "local")
            external_root = parent / "external"
            external_root.mkdir()
            sentinel = external_root / "PRIVATE_EXTERNAL_SENTINEL.md"
            sentinel.write_text("PRIVATE_EXTERNAL_BODY_CANARY", encoding="utf-8")
            sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
            db_path = archive_root / "db" / "archive-index.sqlite"
            db_before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            reparse = archive_root / "zettels" / "external-junction"
            try:
                self.create_directory_reparse(reparse, external_root)
            except OSError as exc:
                self.skipTest(str(exc))

            real_scandir = os.scandir
            external_resolved = external_root.resolve()
            external_stat = os.stat(
                external_resolved,
                follow_symlinks=False,
            )

            def guard_scandir(
                path: int | str | bytes | os.PathLike[str],
            ) -> os.ScandirIterator[str]:
                if isinstance(path, int):
                    observed = os.fstat(path)
                    scans_external = (
                        observed.st_dev,
                        observed.st_ino,
                    ) == (
                        external_stat.st_dev,
                        external_stat.st_ino,
                    )
                else:
                    resolved = Path(path).resolve()
                    scans_external = (
                        resolved == external_resolved
                        or resolved.is_relative_to(external_resolved)
                    )
                if scans_external:
                    raise AssertionError("external directory enumeration attempted")
                return real_scandir(path)

            try:
                with mock.patch.object(
                    archive_services.os,
                    "scandir",
                    side_effect=guard_scandir,
                ):
                    result = archive_services.objet_rediscovery_plan(
                        archive_root,
                        PRIVATE_QUERY,
                        dry_run=True,
                    )
            finally:
                self.remove_directory_reparse(reparse)

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["diagnostic_codes"],
                ["archive_scan_boundary_unsafe"],
            )
            self.assertEqual(
                hashlib.sha256(sentinel.read_bytes()).hexdigest(),
                sentinel_before,
            )
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), db_before)
            serialized = json.dumps(result)
            self.assertNotIn("PRIVATE_EXTERNAL_SENTINEL", serialized)
            self.assertNotIn("PRIVATE_EXTERNAL_BODY_CANARY", serialized)
            self.assert_fixed_private_boundary(result, serialized=serialized)

    def test_strict_nested_snapshot_is_consumed_without_path_reopen_or_body_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            nested = archive_root / "zettels" / "nested" / "deeper"
            nested.mkdir(parents=True)
            target = nested / "strict-snapshot.md"
            target.write_text(
                "---\n"
                "id: zet_strict_snapshot\n"
                "status: canonical\n"
                "kind: test_note\n"
                "---\n\n"
                "PRIVATE_BODY_MUST_NOT_BE_READ\n",
                encoding="utf-8",
            )
            before = self.tree_digest(archive_root)
            observations = {"zettel_body_text_read": False}
            issues: list[dict[str, str]] = []

            with (
                mock.patch.object(
                    archive_services,
                    "archive_relative_path",
                    side_effect=AssertionError("strict path was recomputed"),
                ),
                mock.patch.object(
                    archive_services,
                    "inspect_zettel_frontmatter_boundary",
                    side_effect=AssertionError("strict path was reopened"),
                ),
            ):
                entries = archive_services.live_zettel_index_entries(
                    archive_root,
                    read_observations=observations,
                    inspection_issues=issues,
                    reject_reparse_directories=True,
                )

            after = self.tree_digest(archive_root)

        selected = [
            entry
            for entry in entries
            if entry["path"] == "zettels/nested/deeper/strict-snapshot.md"
        ]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["zettel_id"], "zet_strict_snapshot")
        self.assertEqual(selected[0]["status"], "canonical")
        self.assertEqual(selected[0]["kind"], "test_note")
        self.assertTrue(selected[0]["metadata_readable"])
        self.assertFalse(observations["zettel_body_text_read"])
        self.assertEqual(issues, [])
        self.assertEqual(before, after)

    def test_same_name_zettel_replacement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            target = archive_root / "zettels" / "replacement-race.md"
            target.write_text(
                "---\nid: zet_original\nstatus: canonical\nkind: test_note\n---\n",
                encoding="utf-8",
            )
            replacement = archive_root / "replacement-race-candidate.tmp"
            replacement.write_text(
                "---\nid: zet_replacement\nstatus: canonical\nkind: test_note\n---\n",
                encoding="utf-8",
            )
            displaced = archive_root / "replacement-race-displaced.tmp"
            real_inspect = archive_services._inspect_bound_zettel_file
            injected = False

            def replace_while_held(
                binding: object,
            ) -> tuple[dict[str, object], float]:
                nonlocal injected
                if getattr(binding, "path", None) == target:
                    injected = True
                    os.replace(target, displaced)
                    os.replace(replacement, target)
                return real_inspect(binding)  # type: ignore[arg-type]

            with mock.patch.object(
                archive_services,
                "_inspect_bound_zettel_file",
                side_effect=replace_while_held,
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                )

        self.assertTrue(injected)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["diagnostic_codes"],
            ["archive_scan_boundary_unsafe"],
        )
        self.assert_fixed_private_boundary(result)

    @unittest.skipUnless(
        os.name == "nt",
        "Windows file-identity availability contract",
    )
    def test_windows_zero_file_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            target = parent / "identity-canary.md"
            target.write_text(
                "---\nid: zet_identity\nstatus: canonical\nkind: test_note\n---\n",
                encoding="utf-8",
            )
            observed = os.stat(target, follow_symlinks=False)
            values = list(observed)
            values[1] = 0
            values[2] = 0
            unavailable_identity = os.stat_result(values)
            binding = archive_services._BoundDirectory(
                path=parent,
                descriptor=None,
                windows_handles=(),
            )

            with self.assertRaises(OSError):
                with archive_services._hold_bound_regular_file(
                    binding,
                    target,
                    unavailable_identity,
                ):
                    self.fail("zero file identity must fail before inspection")

    def test_strict_decoder_failure_returns_fixed_blocked_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp)).resolve()
            (archive_root / "zettels" / "invalid-utf8.md").write_bytes(
                b"\xff\xfePRIVATE_DECODER_CANARY"
            )

            result = archive_services.objet_rediscovery_plan(
                archive_root,
                PRIVATE_QUERY,
                dry_run=True,
            )

        serialized = json.dumps(result)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["diagnostic_codes"],
            ["archive_index_unavailable"],
        )
        self.assertNotIn("PRIVATE_DECODER_CANARY", serialized)
        self.assert_fixed_private_boundary(result, serialized=serialized)

    def test_nested_directory_same_name_replacement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            archive_root = self.copy_archive(parent / "local").resolve()
            nested = archive_root / "zettels" / "replace-dir"
            nested.mkdir()
            (nested / "original.md").write_text(
                "---\nid: zet_original\nstatus: canonical\nkind: test_note\n---\n",
                encoding="utf-8",
            )
            replacement = parent / "replacement-dir"
            replacement.mkdir()
            (replacement / "PRIVATE_REPLACEMENT_CANARY.md").write_text(
                "PRIVATE_REPLACEMENT_BODY",
                encoding="utf-8",
            )
            displaced = parent / "displaced-dir"
            real_scan = archive_services._scan_bound_directory
            injected = False

            @contextmanager
            def replace_while_scanning(binding: object) -> object:
                nonlocal injected
                with real_scan(binding) as scanner:  # type: ignore[arg-type]
                    if getattr(binding, "path", None) == nested:
                        injected = True
                        os.replace(nested, displaced)
                        os.replace(replacement, nested)
                    yield scanner

            with mock.patch.object(
                archive_services,
                "_scan_bound_directory",
                side_effect=replace_while_scanning,
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                )

        serialized = json.dumps(result)
        self.assertTrue(injected)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["diagnostic_codes"],
            ["archive_scan_boundary_unsafe"],
        )
        self.assertNotIn("PRIVATE_REPLACEMENT_CANARY", serialized)
        self.assertNotIn("PRIVATE_REPLACEMENT_BODY", serialized)
        self.assert_fixed_private_boundary(result, serialized=serialized)

    def test_top_level_zettel_directory_replacement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            archive_root = self.copy_archive(parent / "local").resolve()
            zettels_root = archive_root / "zettels"
            replacement = parent / "replacement-zettels"
            replacement.mkdir()
            (replacement / "PRIVATE_PARENT_REPLACEMENT_CANARY.md").write_text(
                "PRIVATE_PARENT_REPLACEMENT_BODY",
                encoding="utf-8",
            )
            displaced = parent / "displaced-zettels"
            real_scan = archive_services._scan_bound_directory
            injected = False

            @contextmanager
            def replace_while_scanning(binding: object) -> object:
                nonlocal injected
                with real_scan(binding) as scanner:  # type: ignore[arg-type]
                    if getattr(binding, "path", None) == zettels_root:
                        injected = True
                        os.replace(zettels_root, displaced)
                        os.replace(replacement, zettels_root)
                    yield scanner

            with mock.patch.object(
                archive_services,
                "_scan_bound_directory",
                side_effect=replace_while_scanning,
            ):
                result = archive_services.objet_rediscovery_plan(
                    archive_root,
                    PRIVATE_QUERY,
                    dry_run=True,
                )

        serialized = json.dumps(result)
        self.assertTrue(injected)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["diagnostic_codes"],
            ["archive_scan_boundary_unsafe"],
        )
        self.assertNotIn("PRIVATE_PARENT_REPLACEMENT_CANARY", serialized)
        self.assertNotIn("PRIVATE_PARENT_REPLACEMENT_BODY", serialized)
        self.assert_fixed_private_boundary(result, serialized=serialized)

    def test_cli_and_mcp_share_structured_result_and_private_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            service = archive_services.objet_rediscovery_plan(
                archive_root,
                PRIVATE_QUERY,
                dry_run=True,
                limit=2,
                count_total=True,
            )

            code, json_stdout, json_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    PRIVATE_QUERY,
                    "--dry-run",
                    "--limit",
                    "2",
                    "--count-total",
                    "--format",
                    "json",
                ]
            )
            cli_result = json.loads(json_stdout)
            mcp_result = mcp_server.tool_objet_rediscovery_plan(
                {
                    "archive_root": str(archive_root),
                    "query": PRIVATE_QUERY,
                    "dry_run": True,
                    "limit": 2,
                    "count_total": True,
                }
            )
            text_code, text_stdout, text_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    PRIVATE_QUERY,
                    "--dry-run",
                    "--limit",
                    "2",
                ]
            )
            exact_text_code, exact_text_stdout, exact_text_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    PRIVATE_QUERY,
                    "--dry-run",
                    "--limit",
                    "2",
                    "--count-total",
                ]
            )
            bounded_text_code, bounded_text_stdout, bounded_text_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    "fake",
                    "--dry-run",
                    "--limit",
                    "1",
                ]
            )

            blocked_service = archive_services.objet_rediscovery_plan(
                archive_root,
                PRIVATE_QUERY,
                dry_run=False,
            )
            blocked_code, blocked_stdout, blocked_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    PRIVATE_QUERY,
                    "--format",
                    "json",
                ]
            )
            blocked_mcp = mcp_server.tool_objet_rediscovery_plan(
                {
                    "archive_root": str(archive_root),
                    "query": PRIVATE_QUERY,
                    "dry_run": False,
                }
            )
            empty_service = archive_services.objet_rediscovery_plan(
                archive_root,
                "",
                dry_run=True,
            )
            empty_code, empty_stdout, empty_stderr = self.run_cli(
                [
                    "objet-rediscovery-plan",
                    str(archive_root),
                    "",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            empty_mcp = mcp_server.tool_objet_rediscovery_plan(
                {
                    "archive_root": str(archive_root),
                    "query": "",
                    "dry_run": True,
                }
            )

        self.assertEqual(code, 0)
        self.assertEqual(json_stderr, "")
        self.assertEqual(cli_result, service)
        self.assertEqual(mcp_result["structuredContent"], service)
        self.assertFalse(mcp_result["isError"])
        self.assertEqual(
            mcp_result["content"][0]["text"],
            "SEARCH INCOMPLETE. No global absence claim is supported.",
        )
        self.assertNotIn(PRIVATE_QUERY, json_stdout)
        self.assertNotIn(PRIVATE_QUERY, json.dumps(mcp_result))
        self.assertEqual(text_code, 0)
        self.assertEqual(text_stderr, "")
        self.assertTrue(text_stdout.startswith("SEARCH INCOMPLETE."))
        self.assertIn(
            "Checked generated-index matches (exact): 0",
            text_stdout,
        )
        self.assertNotIn("Checked matches:", text_stdout)
        self.assertNotIn(PRIVATE_QUERY, text_stdout)
        self.assertEqual(exact_text_code, 0)
        self.assertEqual(exact_text_stderr, "")
        self.assertIn(
            "Checked generated-index matches (exact): ",
            exact_text_stdout,
        )
        self.assertNotIn("bounded lower bound", exact_text_stdout)
        self.assertNotIn(PRIVATE_QUERY, exact_text_stdout)
        self.assertEqual(bounded_text_code, 0)
        self.assertEqual(bounded_text_stderr, "")
        self.assertIn(
            "Checked generated-index matches (bounded lower bound): at least ",
            bounded_text_stdout,
        )
        self.assertNotIn(
            "Checked generated-index matches (exact):",
            bounded_text_stdout,
        )

        self.assertEqual(blocked_code, 1)
        self.assertEqual(blocked_stderr, "")
        self.assertEqual(json.loads(blocked_stdout), blocked_service)
        self.assertEqual(blocked_mcp["structuredContent"], blocked_service)
        self.assertNotIn(PRIVATE_QUERY, blocked_stdout)
        self.assertNotIn(PRIVATE_QUERY, json.dumps(blocked_mcp))
        self.assertEqual(empty_code, 1)
        self.assertEqual(empty_stderr, "")
        self.assertEqual(json.loads(empty_stdout), empty_service)
        self.assertEqual(empty_mcp["structuredContent"], empty_service)
        self.assertEqual(
            empty_service["diagnostic_codes"],
            ["query_required"],
        )

    def test_runtime_routes_capabilities_and_feedback_readiness_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp), index=False)
            context = archive_services.runtime_context(archive_root)
            start = archive_services.ai_start_here(archive_root)
            code, output, stderr = self.run_cli(
                ["capabilities", "--machine", "--format", "json"]
            )

        self.assertEqual(code, 0, output)
        self.assertEqual(stderr, "")
        capabilities = json.loads(output)
        command = next(
            item
            for item in capabilities["data"]["commands"]
            if item["name"] == "objet-rediscovery-plan"
        )
        self.assertEqual(command["required_positionals"], ["archive_root", "query"])
        self.assertIn("--dry-run", command["options"])
        self.assertIn("--count-total", command["options"])
        self.assertIn(
            "objet_rediscovery_plan",
            [item["name"] for item in mcp_server.TOOL_DEFINITIONS],
        )

        for packet in (context, start):
            routing = packet["action_routing"]
            self.assertEqual(
                routing["schema"],
                "wom-kit/ai-command-path-routing/v0.9",
            )
            route = next(
                item
                for item in routing["read_action_routes"]
                if item["action"]
                == "plan_objet_rediscovery_before_negative_claim"
            )
            self.assertEqual(
                route["command"],
                (
                    "archive objet-rediscovery-plan <archive-root> <query> "
                    "--dry-run --count-total --format json"
                ),
            )
            self.assertTrue(
                route["global_absence_claim_requires_complete_layers"]
            )
            self.assertFalse(route["writes"])
            feedback = routing["operator_feedback_routing"]
            self.assertEqual(
                [item["action"] for item in feedback["sequence"]],
                [
                    "read_feedback_policy",
                    "inspect_feedback_ledger",
                    "human_review",
                    "preview_feedback_record",
                    "approve_feedback_record",
                ],
            )
            readiness = packet["runtime_guidance_readiness"]
            self.assertEqual(readiness["status"], "not_checked")
            self.assertEqual(
                readiness["host_guidance_consumption"],
                "not_proven",
            )


if __name__ == "__main__":
    unittest.main()
