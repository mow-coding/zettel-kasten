import json
import sys
import tempfile
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services


class V0419RuntimeTruthTests(unittest.TestCase):
    def test_integrity_evidence_keeps_later_checks_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            missing_mirror = project_root / ".zettel-kasten" / "source"
            result = archive_services._wom_kit_runtime_mirror_integrity_with_runner(
                project_root,
                missing_mirror,
                None,
                missing_mirror / "wom-kit" / "cli" / "archive.py",
                source_version="0.4.19",
                runner=object(),
            )

        self.assertFalse(result["verified"])
        self.assertEqual(
            result["checks"]["mirror_real_directory_inside_project"]["state"],
            "failed",
        )
        self.assertFalse(result["origin_configured"])
        self.assertEqual(
            result["checks"]["origin_configured"]["state"],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["source_tag_at_head"]["state"],
            "not_reached",
        )

    def test_runtime_preparation_revalidation_reports_dimensions_not_values(self) -> None:
        observations = {
            name: ("passed", f"runtime_preparation_{name}_verified")
            for name in (
                archive_services
                .WOM_KIT_PROJECT_UPDATE_RUNTIME_PREPARATION_CHECKS
            )
        }
        observations["target_refs"] = (
            "failed",
            "runtime_preparation_target_refs_changed",
        )
        observations["prepared_runtime_payload"] = (
            "unavailable",
            "runtime_preparation_prepared_runtime_payload_unavailable",
        )

        result = (
            archive_services
            .wom_kit_project_update_runtime_preparation_revalidation(
                observations
            )
        )

        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["changed_dimensions"], ["target_refs"])
        self.assertEqual(
            result["unavailable_dimensions"],
            ["prepared_runtime_payload"],
        )
        self.assertIn(
            "version_update_lock",
            result["expected_transaction_changes_excluded"],
        )
        self.assertFalse(result["compared_values_echoed"])
        self.assertFalse(result["private_values_echoed"])
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("refs/tags/", serialized)
        self.assertNotIn("installed-version.txt", serialized)


if __name__ == "__main__":
    unittest.main()
