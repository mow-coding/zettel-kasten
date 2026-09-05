"""Complete-inventory twin observations remain generation-bound at completion."""

from pathlib import Path
import sys
import unittest


TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import archive_cli, archive_services
import test_v0419_doctor_twin_projection as twin_fixtures


class DoctorTwinBarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Compose only the existing small synthetic fixture. Inheriting its
        # TestCase would accidentally collect and rerun every unrelated test.
        twin_fixtures.DoctorTwinProjectionTests.setUpClass()

    def setUp(self) -> None:
        self.fixture = twin_fixtures.DoctorTwinProjectionTests(methodName="runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def inventoried_doctor(self) -> archive_cli.Doctor:
        doctor = archive_cli.Doctor(self.fixture.root)
        doctor._run_stage("symlink-boundaries", doctor._check_symlink_boundaries)
        self.assertTrue(doctor._archive_tree_inventory_complete)
        self.assertTrue(doctor._run_cache_snapshot_active)
        # Use the production draft-check path, including its remembered draft
        # generation, rather than invoking the small classifier in isolation.
        doctor._run_stage(
            "zettels", lambda: doctor._check_zettel_file(self.fixture.source, "draft")
        )
        return doctor

    def assert_final_snapshot_stale(self, doctor: archive_cli.Doctor) -> None:
        doctor._finalize_run_file_generation_snapshots()
        self.assertTrue(any(
            item.severity == "ERROR" and item.code == "doctor_cache_snapshot_stale"
            for item in doctor.diagnostics
        ))
        self.assertFalse(any(
            item.code == "doctor_cache_snapshot_current"
            for item in doctor.diagnostics
        ))

    def test_source_change_invalidates_completed_inventory_twin_observation(self) -> None:
        doctor = self.inventoried_doctor()
        self.assertTrue(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        self.fixture.source.write_bytes(self.fixture.source.read_bytes() + b"changed\n")
        # A cached observation may still describe the frozen generation until
        # completion. It must never survive as a current, successful result.
        doctor._observed_minted_draft_twin(self.fixture.source, self.fixture.data)
        self.assert_final_snapshot_stale(doctor)

    def test_missing_retired_directory_does_not_hide_genuine_minted_twin(self) -> None:
        retired_directory = (
            self.fixture.root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR
        )
        retired_directory.rmdir()
        doctor = self.inventoried_doctor()
        self.assertTrue(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        self.assertFalse(retired_directory.exists())
        doctor._finalize_run_file_generation_snapshots()
        self.assertFalse(any(
            item.severity == "ERROR" and item.code == "doctor_cache_snapshot_stale"
            for item in doctor.diagnostics
        ))

    def test_new_retired_receipt_invalidates_completed_inventory(self) -> None:
        doctor = self.inventoried_doctor()
        self.assertTrue(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        retired = (
            self.fixture.root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR
            / f"{self.fixture.zettel_id}.retire-draft.json"
        )
        retired.write_bytes(b"{}\n")
        self.assertFalse(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        self.assert_final_snapshot_stale(doctor)

    def test_new_mint_receipt_is_not_adopted_into_completed_inventory(self) -> None:
        receipt_bytes = self.fixture.receipt_path.read_bytes()
        self.fixture.receipt_path.unlink()
        doctor = self.inventoried_doctor()
        self.assertFalse(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        self.fixture.receipt_path.write_bytes(receipt_bytes)
        self.assertFalse(doctor._observed_minted_draft_twin(
            self.fixture.source, self.fixture.data
        ))
        self.assert_final_snapshot_stale(doctor)


if __name__ == "__main__":
    unittest.main()
