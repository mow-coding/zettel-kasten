from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services
from wom_kit import private_objet_metadata_index as generated_index
from wom_kit import private_objet_metadata_index_authority as authority
from wom_kit import private_objet_metadata_index_rebuild as rebuild


_PUBLIC_HEALTH_KEYS = (
    "ok",
    "dry_run",
    "lifecycle_action",
    "archive_id",
    "index_path",
    "index_state",
    "summary",
    "samples",
    "stale_reasons",
    "privacy_guards",
    "would_change",
    "next_safe_actions",
    "blockers",
    "warnings",
)

_PRIVATE_HEALTH_KEYS = (
    "schema",
    "authority_validity",
    "projection_validity",
    "freshness",
    "index_state",
    "empty_authority",
    "private_layer_complete",
    "fingerprint_matches",
    "schema_matches",
    "observation_rows_digest_matches",
    "alias_rows_digest_matches",
    "projection_rows_digest_matches",
    "observation_count",
    "alias_count",
    "distinct_object_count",
    "projection_count",
    "blocked_alias_derivation_count",
    "blocked_label_projection_count",
    "diagnostic_codes",
)

_PRIVATE_TABLES = (
    "objet_source_metadata",
    "objet_name_aliases",
    "private_objet_label_projections",
    "private_objet_index_metadata",
)

_PUBLIC_TABLES = (
    "zettels",
    "objects",
    "derived_texts",
    "views",
    "source_map_entries",
    "edges",
    "zettel_facets",
    "index_metadata",
)


def _event_index(events: list[tuple[object, ...]], target: tuple[object, ...]) -> int:
    return next(index for index, event in enumerate(events) if event == target)


def _sql_mutation(statement: str) -> str | None:
    normalized = " ".join(statement.split()).upper()
    for operation in ("CREATE TABLE", "DELETE FROM", "INSERT INTO", "UPDATE"):
        if normalized.startswith(operation):
            return operation
    return None


def _instrumented_rebuild_factory(
    events: list[tuple[object, ...]],
):
    capture_number = 0

    def capture(root: Path, archive_id: str):
        nonlocal capture_number
        capture_number += 1
        events.append(("call", f"snapshot_{capture_number}"))
        return authority.capture_private_objet_index_authority(root, archive_id)

    def compile_projection(compiler_input):
        events.append(("call", "compile"))
        return generated_index.compile_private_objet_index_projection(
            compiler_input
        )

    def replace_rows(connection, projection) -> None:
        events.append(
            ("call", "private_replace_enter", connection.in_transaction)
        )
        generated_index.replace_private_objet_index_rows(
            connection,
            projection,
        )
        events.append(
            ("call", "private_replace_exit", connection.in_transaction)
        )

    def insert_metadata(connection, projection):
        events.append(
            ("call", "singleton_enter", connection.in_transaction)
        )
        inspection = generated_index.insert_private_objet_index_metadata(
            connection,
            projection,
        )
        events.append(
            ("call", "singleton_exit", connection.in_transaction)
        )
        return inspection

    class TrackingConnection(sqlite3.Connection):
        def executescript(self, sql_script: str):
            foreign_keys = int(
                sqlite3.Connection.execute(
                    self,
                    "PRAGMA foreign_keys",
                ).fetchone()[0]
            )
            events.append(
                (
                    "call",
                    "public_executescript_enter",
                    self.in_transaction,
                    foreign_keys,
                )
            )
            return super().executescript(sql_script)

        def commit(self) -> None:
            events.append(("call", "commit", self.in_transaction))
            return super().commit()

        def rollback(self) -> None:
            events.append(("call", "rollback", self.in_transaction))
            return super().rollback()

        def close(self) -> None:
            events.append(("call", "close", self.in_transaction))
            return super().close()

    def connect(db_path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
        connection = sqlite3.connect(
            db_path,
            timeout=busy_timeout_ms / 1000,
            factory=TrackingConnection,
        )

        def trace(statement: str) -> None:
            normalized = " ".join(statement.split())
            upper = normalized.upper().rstrip(";")
            if upper == "BEGIN IMMEDIATE":
                events.append(("sql", "begin_immediate"))
                return
            if upper == "COMMIT":
                events.append(("sql", "commit"))
                return
            if upper == "ROLLBACK":
                events.append(("sql", "rollback"))
                return
            if upper == "PRAGMA FOREIGN_KEYS=ON":
                events.append(("sql", "foreign_keys_on"))
                return
            if upper == "PRAGMA FOREIGN_KEYS":
                events.append(("sql", "foreign_keys_read"))
                return
            operation = _sql_mutation(normalized)
            if operation is None:
                return
            for table_name in _PRIVATE_TABLES:
                if re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(table_name)}"
                    rf"(?![A-Za-z0-9_])",
                    normalized,
                    flags=re.IGNORECASE,
                ):
                    events.append(
                        (
                            "private_sql",
                            operation,
                            table_name,
                            connection.in_transaction,
                        )
                    )
                    return
            for table_name in _PUBLIC_TABLES:
                if re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(table_name)}"
                    rf"(?![A-Za-z0-9_])",
                    normalized,
                    flags=re.IGNORECASE,
                ):
                    events.append(
                        (
                            "public_sql",
                            operation,
                            table_name,
                            connection.in_transaction,
                        )
                    )
                    return

        connection.set_trace_callback(trace)
        events.append(("call", "connect"))
        return connection

    dependencies = rebuild._RebuildDependencies(
        capture=capture,
        compile=compile_projection,
        replace_rows=replace_rows,
        insert_metadata=insert_metadata,
        connect=connect,
    )

    def factory(
        archive_root: Path | str,
        archive_id: str,
        db_path: Path | str,
        *,
        busy_timeout_ms: int,
    ):
        return rebuild.private_objet_index_rebuild_session(
            archive_root,
            archive_id,
            db_path,
            busy_timeout_ms=busy_timeout_ms,
            _dependencies=dependencies,
        )

    return factory


class V03297ArchiveIndexIntegrationTests(unittest.TestCase):
    def _copy_archive(self, parent: Path) -> Path:
        archive_root = parent / "archive"
        shutil.copytree(
            KIT_ROOT / "examples" / "fake-life-archive",
            archive_root,
        )
        return archive_root

    def _assert_c10_current(self, archive_root: Path) -> None:
        health = archive_services.index_health(
            archive_root,
            dry_run=True,
        )
        self.assertTrue(
            health["ok"],
            "fresh rebuild health did not remain current",
        )
        self.assertEqual(
            tuple(health),
            (*_PUBLIC_HEALTH_KEYS, "private_objet_metadata"),
        )
        private = health["private_objet_metadata"]
        self.assertEqual(tuple(private), _PRIVATE_HEALTH_KEYS)
        self.assertEqual(
            (
                private["schema"],
                private["authority_validity"],
                private["projection_validity"],
                private["freshness"],
                private["index_state"],
            ),
            (
                "wom-kit/private-objet-index-health/v0.1",
                "valid",
                "valid",
                "current",
                "current",
            ),
        )
        for key in (
            "empty_authority",
            "private_layer_complete",
            "fingerprint_matches",
            "schema_matches",
            "observation_rows_digest_matches",
            "alias_rows_digest_matches",
            "projection_rows_digest_matches",
        ):
            self.assertIs(
                private[key],
                True,
                f"C10 boolean was not authoritatively true: {key}",
            )
        self.assertEqual(
            (
                private["observation_count"],
                private["alias_count"],
                private["distinct_object_count"],
                private["projection_count"],
                private["blocked_alias_derivation_count"],
                private["blocked_label_projection_count"],
            ),
            (0, 0, 0, 0, 0, 0),
        )
        self.assertEqual(private["diagnostic_codes"], [])
    def _assert_clean_wal_c6_without_sidecars(
        self,
        archive_root: Path,
    ) -> None:
        db_path = archive_root / archive_services.INDEX_RELATIVE_PATH
        wal_path = Path(str(db_path) + "-wal")
        shm_path = Path(str(db_path) + "-shm")
        self.assertFalse(wal_path.exists())
        self.assertFalse(shm_path.exists())
        health = archive_services.index_health(
            archive_root,
            dry_run=True,
        )
        private = health["private_objet_metadata"]
        self.assertFalse(health["ok"])
        self.assertEqual(health["index_state"], "stale_or_incomplete")
        self.assertEqual(
            (
                private["authority_validity"],
                private["projection_validity"],
                private["freshness"],
                private["index_state"],
                private["diagnostic_codes"],
            ),
            (
                "valid",
                "unverifiable",
                "unverifiable",
                "blocked",
                ["private_objet_metadata_projection_unavailable"],
            ),
        )
        self.assertFalse(wal_path.exists())
        self.assertFalse(shm_path.exists())

    def _open_coherent_wal_anchor(
        self,
        archive_root: Path,
    ) -> sqlite3.Connection:
        db_path = archive_root / archive_services.INDEX_RELATIVE_PATH
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA journal_mode=WAL")
        self.assertTrue(Path(str(db_path) + "-wal").exists())
        self.assertTrue(Path(str(db_path) + "-shm").exists())
        return connection

    def _logical_snapshot_tokens(
        self,
        archive_root: Path,
    ) -> tuple[str, str]:
        db_path = archive_root / archive_services.INDEX_RELATIVE_PATH
        connection = sqlite3.connect(
            db_path.resolve().as_uri() + "?mode=ro",
            uri=True,
        )
        try:
            dump_lines = list(connection.iterdump())
        finally:
            connection.close()
        private_lines: list[str] = []
        public_lines: list[str] = []
        for line in dump_lines:
            is_private = any(
                table_name in line for table_name in _PRIVATE_TABLES
            ) or "objet_name_aliases_lookup" in line
            if is_private:
                private_lines.append(line)
            elif line not in {"BEGIN TRANSACTION;", "COMMIT;"}:
                public_lines.append(line)
        return (
            hashlib.sha256(
                "\n".join(public_lines).encode("utf-8")
            ).hexdigest(),
            hashlib.sha256(
                "\n".join(private_lines).encode("utf-8")
            ).hexdigest(),
        )

    def test_index_archive_source_freezes_transaction_owner_contract(
        self,
    ) -> None:
        source = textwrap.dedent(
            inspect.getsource(archive_services.index_archive)
        )
        module = ast.parse(source)
        function = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "index_archive"
        )
        calls = [
            node for node in ast.walk(function) if isinstance(node, ast.Call)
        ]
        executescript_calls = [
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "conn"
            and call.func.attr == "executescript"
        ]
        self.assertEqual(len(executescript_calls), 1)
        sql_script = ast.literal_eval(executescript_calls[0].args[0])
        first_statement = " ".join(
            sql_script.strip().split(";", 1)[0].split()
        ).upper()
        self.assertEqual(first_statement, "BEGIN IMMEDIATE")
        self.assertIsNone(
            re.search(r"(?im)^\s*COMMIT(?:\s|;|$)", sql_script),
            "index_archive executescript must not own COMMIT",
        )
        validate_calls = [
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "validate_and_commit"
        ]
        self.assertEqual(len(validate_calls), 1)
        direct_commit_calls = [
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "conn"
            and call.func.attr == "commit"
        ]
        self.assertEqual(direct_commit_calls, [])

    def test_actual_index_uses_one_public_private_transaction_and_final_commit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))
            events: list[tuple[object, ...]] = []
            factory = _instrumented_rebuild_factory(events)
            with patch.object(
                archive_services,
                "private_objet_index_rebuild_session",
                factory,
            ):
                result = archive_services.index_archive(archive_root)
            self.assertTrue(
                result["index_rebuilt"],
                "actual archive index did not complete",
            )

        executescript_entry = _event_index(
            events,
            ("call", "public_executescript_enter", False, 1),
        )
        foreign_keys_on = _event_index(
            events,
            ("sql", "foreign_keys_on"),
        )
        begin = _event_index(events, ("sql", "begin_immediate"))
        replace_enter = _event_index(
            events,
            ("call", "private_replace_enter", True),
        )
        replace_exit = _event_index(
            events,
            ("call", "private_replace_exit", True),
        )
        snapshot_b = _event_index(events, ("call", "snapshot_2"))
        singleton_enter = _event_index(
            events,
            ("call", "singleton_enter", True),
        )
        singleton_insert = _event_index(
            events,
            (
                "private_sql",
                "INSERT INTO",
                "private_objet_index_metadata",
                True,
            ),
        )
        commit_call = _event_index(events, ("call", "commit", True))
        commit_sql = _event_index(events, ("sql", "commit"))

        self.assertLess(foreign_keys_on, executescript_entry)
        self.assertLess(executescript_entry, begin)
        self.assertEqual(events.count(("sql", "begin_immediate")), 1)
        self.assertEqual(events.count(("call", "commit", True)), 1)
        self.assertEqual(events.count(("sql", "commit")), 1)
        self.assertLess(begin, replace_enter)
        self.assertLess(replace_enter, replace_exit)
        self.assertLess(replace_exit, snapshot_b)
        self.assertLess(snapshot_b, singleton_enter)
        self.assertLess(singleton_enter, singleton_insert)
        self.assertLess(singleton_insert, commit_call)
        self.assertLess(commit_call, commit_sql)

        public_mutations = [
            index
            for index, event in enumerate(events)
            if event[0] == "public_sql"
        ]
        self.assertTrue(
            public_mutations,
            "actual public index emitted no observed mutation",
        )
        self.assertTrue(
            all(
                begin < index < commit_sql and events[index][-1] is True
                for index in public_mutations
            ),
            "a public mutation escaped the one transaction",
        )
        self.assertLess(max(public_mutations), replace_enter)

        for table_name in _PRIVATE_TABLES:
            private_mutations = [
                index
                for index, event in enumerate(events)
                if event[0] == "private_sql"
                and event[2] == table_name
            ]
            self.assertTrue(
                private_mutations,
                f"private layer was not exercised: {table_name}",
            )
            self.assertTrue(
                all(
                    begin < index < commit_sql
                    and events[index][-1] is True
                    for index in private_mutations
                ),
                f"private layer escaped the one transaction: {table_name}",
            )

    def test_clean_wal_health_is_c6_before_query_and_creates_no_sidecars(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))
            archive_services.index_archive(archive_root)
            self._assert_clean_wal_c6_without_sidecars(archive_root)

    def test_coherent_existing_wal_health_is_exact_c10(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))
            archive_services.index_archive(archive_root)
            anchor = self._open_coherent_wal_anchor(archive_root)
            try:
                self._assert_c10_current(archive_root)
            finally:
                anchor.close()

    def test_precommit_public_failure_preserves_old_public_and_private_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))
            archive_services.index_archive(archive_root)
            public_before, private_before = self._logical_snapshot_tokens(
                archive_root
            )
            new_zettel = (
                archive_root
                / "zettels"
                / "zet_v03297_integration_rollback_probe.md"
            )
            new_zettel.write_text(
                "---\n"
                "id: zet_v03297_integration_rollback_probe\n"
                "title: Integration rollback probe\n"
                "status: canonical\n"
                "kind: note\n"
                "---\n\n"
                "Rollback integration body.\n",
                encoding="utf-8",
            )

            def fail_during_public_rows(
                stage: str,
                message: str,
                current: int | None,
                _total: int | None,
            ) -> None:
                if (
                    stage == "index-zettels"
                    and message == "scanned"
                    and current == 1
                ):
                    raise RuntimeError("simulated_public_callback_failure")

            with self.assertRaises(
                archive_services.ArchiveServiceError
            ) as caught:
                archive_services.index_archive(
                    archive_root,
                    progress_callback=fail_during_public_rows,
                )
            self.assertEqual(
                str(caught.exception),
                "private_objet_metadata_rebuild_failed",
            )
            public_after, private_after = self._logical_snapshot_tokens(
                archive_root
            )
            self.assertTrue(
                public_after == public_before,
                "pre-commit failure changed the old public snapshot",
            )
            self.assertTrue(
                private_after == private_before,
                "pre-commit failure changed the old private snapshot",
            )

    def test_postcommit_progress_failure_keeps_committed_c10_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))

            def fail_after_commit(
                stage: str,
                message: str,
                _current: int | None,
                _total: int | None,
            ) -> None:
                if stage == "index-commit" and message == "done":
                    raise BrokenPipeError(
                        "simulated_post_commit_transport_failure"
                    )

            with self.assertRaises(
                archive_services.ArchiveServiceError
            ) as caught:
                archive_services.index_archive(
                    archive_root,
                    progress_callback=fail_after_commit,
                )
            self.assertEqual(
                str(caught.exception),
                "archive_index_post_commit_progress_failed",
            )
            anchor = self._open_coherent_wal_anchor(archive_root)
            try:
                self._assert_c10_current(archive_root)
            finally:
                anchor.close()

    def test_private_trigger_bridge_blocks_and_rolls_back_public_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = self._copy_archive(Path(temporary))
            archive_services.index_archive(archive_root)
            db_path = archive_root / archive_services.INDEX_RELATIVE_PATH
            anchor = self._open_coherent_wal_anchor(archive_root)
            try:
                private_fingerprint = anchor.execute(
                    "SELECT private_authority_fingerprint_sha256 "
                    "FROM private_objet_index_metadata"
                ).fetchone()[0]
                anchor.execute(
                    "CREATE TRIGGER public_private_bridge "
                    "AFTER DELETE ON index_metadata BEGIN "
                    "INSERT OR REPLACE INTO source_map_entries"
                    "(item_id, source_id, item_kind, relative_path, "
                    "external_url, scan_status, source_json) "
                    "SELECT 'synthetic-trigger-row', NULL, 'source_map', "
                    "NULL, NULL, 'indexed', "
                    "private_authority_fingerprint_sha256 "
                    "FROM private_objet_index_metadata LIMIT 1; "
                    "END"
                )
                anchor.commit()
                health = archive_services.index_health(
                    archive_root,
                    dry_run=True,
                )
                self.assertEqual(
                    health["private_objet_metadata"]["diagnostic_codes"],
                    ["private_objet_metadata_projection_invalid"],
                )
                before = self._logical_snapshot_tokens(archive_root)
                with self.assertRaises(
                    archive_services.ArchiveServiceError
                ) as caught:
                    archive_services.index_archive(archive_root)
                self.assertEqual(
                    str(caught.exception),
                    "private_objet_metadata_projection_invalid",
                )
                after = self._logical_snapshot_tokens(archive_root)
                self.assertEqual(before, after)
                copied = anchor.execute(
                    "SELECT COUNT(*) FROM source_map_entries "
                    "WHERE item_id='synthetic-trigger-row'"
                ).fetchone()[0]
                self.assertEqual(copied, 0)
                generic = archive_services.search_archive(
                    archive_root,
                    private_fingerprint,
                )
                escaped = private_fingerprint in json.dumps(
                    generic["results"],
                    ensure_ascii=True,
                    sort_keys=True,
                )
                self.assertFalse(
                    escaped,
                    "private fingerprint escaped through a generic result",
                )
            finally:
                anchor.close()


if __name__ == "__main__":
    unittest.main()
