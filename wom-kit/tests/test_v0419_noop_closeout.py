"""Own-reservation no-op closeout against real local Git and cleanup primitives."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import archive_services, exact_human_approval_windows, project_update_transaction
import test_cli


@unittest.skipUnless(os.name == "nt", "Exact compare-and-delete is Windows-only")
class NoopCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wom-noop-closeout-")
        self.addCleanup(self.temporary.cleanup)
        self.helper = test_cli.ArchiveCliTests(methodName="runTest")
        self.addCleanup(self.helper.doCleanups)
        self.fixture = self.helper.create_project_version_update_fixture(Path(self.temporary.name))
        mirror = self.fixture["mirror"]
        self.helper.git_fixture_command(mirror, "fetch", "--quiet", "origin", "--tags")
        self.helper.git_fixture_command(
            mirror, "checkout", "--detach", "--quiet", self.fixture["target_tag"]
        )
        for pin in (
            mirror / "installed-version.txt",
            self.fixture["metadata_root"] / "installed-version.txt",
        ):
            pin.write_text(self.fixture["target_tag"] + "\n", encoding="utf-8")
        self.domain_before = self.domain_snapshot()

    def domain_snapshot(self):
        paths = [
            self.fixture["metadata_root"] / "installed-version.txt",
            self.fixture["mirror"] / "installed-version.txt",
            *self.fixture["runtime_paths"],
        ]
        return {path: path.read_bytes() for path in paths}

    def run_noop(self):
        # This is the same production core used by public approval. The absent
        # runtime-policy fixture isolates reservation closeout from venv setup;
        # no-op must finish before any approval callback or domain writer.
        def unexpected_approval(*args, **kwargs):
            self.fail("no-op must not enter approval")

        return archive_services._wom_kit_project_version_update_legacy_core(
            self.fixture["project_root"],
            target=self.fixture["target_tag"],
            approve=True,
            reviewed_by="person:synthetic-closeout",
            affirm_external_writers_quiescent=True,
            approval_executor=unexpected_approval,
            _expected_approval_root=self.fixture["archive_root"],
            _expected_archive_id="archive:personal:project-update-fixture",
        )

    def assert_domain_preserved(self, result):
        self.assertEqual(self.domain_snapshot(), self.domain_before)
        self.assertEqual(result["files_written"], [])
        self.assertNotIn(str(self.fixture["project_root"]), json.dumps(result))

    def test_noop_compacts_own_history_and_next_preview_is_ready(self):
        result = self.run_noop()
        self.assertEqual(result["status"], "no_change", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["terminal_abort_history_compaction_state"], "complete")
        self.assertEqual(result["cleanup_proofs_written_or_verified"], 1)
        self.assertEqual(
            project_update_transaction.discover_exact_reservation_abort_cleanup_read_only(
                self.fixture["project_root"]
            ), ()
        )
        preview = archive_services.wom_kit_project_version_update(
            self.fixture["project_root"], target=self.fixture["target_tag"], dry_run=True
        )
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["status"], "ready_for_approval")
        self.assert_domain_preserved(result)

    def test_partial_cleanup_plan_never_claims_no_change(self):
        with mock.patch.object(
            project_update_transaction,
            "_atomic_move_directory_no_replace",
            side_effect=OSError("synthetic stop after durable cleanup plan"),
        ):
            result = self.run_noop()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "terminal_cleanup_outcome_unknown", result)
        self.assertTrue(result["terminal_abort_history_compaction_incomplete"])
        pending = project_update_transaction.discover_exact_reservation_abort_cleanup_read_only(
            self.fixture["project_root"]
        )
        self.assertEqual(len(pending), 1)
        self.assertIsNotNone(pending[0].cleanup_authority_sha256)
        self.assert_domain_preserved(result)

        # The caller lost the previous output: neither an approval identifier,
        # transaction identifier nor a manually selected checkpoint is needed.
        # Resume the real interrupted cleanup, without opening another approval
        # or replacing the old receipt's authority.
        with mock.patch.object(
            exact_human_approval_windows._CtypesTaskDialogNative, "show",
            side_effect=AssertionError("cleanup resume must reuse exact existing evidence"),
        ) as native:
            code, stdout, stderr = self.helper.run_cli_split([
                "project-version-update", str(self.fixture["project_root"]),
                "--resume", "--affirm-external-writers-quiescent", "--format", "json",
            ])
        self.assertEqual(code, 0, stdout + stderr)
        resumed = json.loads(stdout)
        self.assertEqual(resumed["status"], "terminal_history_compacted", resumed)
        self.assertEqual(resumed["terminal_abort_histories_compacted"], 1)
        native.assert_not_called()
        self.assertEqual(
            project_update_transaction.discover_exact_reservation_abort_cleanup_read_only(
                self.fixture["project_root"]
            ), ()
        )
        preview = archive_services.wom_kit_project_version_update(
            self.fixture["project_root"], target=self.fixture["target_tag"], dry_run=True
        )
        self.assertTrue(preview["ok"], preview)
        self.assert_domain_preserved(resumed)

    def test_cleanup_interrupt_never_claims_no_change(self):
        with mock.patch.object(
            project_update_transaction.ReservedProjectUpdateTransaction,
            "exact_cleanup", side_effect=KeyboardInterrupt,
        ):
            result = self.run_noop()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "terminal_cleanup_outcome_unknown", result)
        self.assertTrue(result["effect_summary"]["private_control_mutation_may_be_incomplete"])
        self.assert_domain_preserved(result)

    def test_new_writer_lock_is_not_reported_absent_after_cleanup_refusal(self):
        native_cleanup = project_update_transaction.ReservedProjectUpdateTransaction.exact_cleanup
        competing = []

        def acquire_competing_lock(reservation, **kwargs):
            other = project_update_transaction.ProjectUpdateTransaction.reserve(
                self.fixture["project_root"],
                project_identity_sha256="sha256:" + "a" * 64,
                requested_target_tag=self.fixture["target_tag"],
                created_at="2026-09-05T00:00:00Z",
            )
            other.acquire_lock()
            competing.append(other)
            return native_cleanup(reservation, **kwargs)

        with mock.patch.object(
            project_update_transaction.ReservedProjectUpdateTransaction,
            "exact_cleanup", acquire_competing_lock,
        ):
            result = self.run_noop()
        self.assertEqual(len(competing), 1)
        lock = self.fixture["metadata_root"] / "version-update.lock"
        self.assertEqual(lock.read_bytes(), competing[0].lock_bytes())
        self.assertFalse(result["ok"])
        self.assertIsNot(result.get("observed_version_update_lock_present"), False)
        self.assert_domain_preserved(result)
