from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
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
            ["not_implemented"] * 4,
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

            def guard_scandir(path: str | bytes | os.PathLike[str]) -> os.ScandirIterator[str]:
                resolved = Path(path).resolve()
                if resolved == external_resolved or resolved.is_relative_to(
                    external_resolved
                ):
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
                "wom-kit/ai-command-path-routing/v0.8",
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
