from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__
from wom_kit import project_runtime


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.12.md"
EVIDENCE = KIT / "docs" / "evidence" / "v0.4.12-link-index-windows-reference.json"
LOCK = KIT / "project-runtime-supply-lock-v0.4.12.json"
LOCK_SHA256 = "3bdad30b08eb6ba3152946ead94f1cf55a1130fadcfb1a1b6c9ef7dddd969e2a"


class V0412ReleaseDocsTests(unittest.TestCase):
    def test_v0412_release_is_preserved_as_source_history(self) -> None:
        self.assertEqual(__version__, "0.4.16")
        self.assertTrue(RELEASE.is_file())
        packaged = RESOURCE_ROOT / "release-notes" / "v0.4.12.md"
        self.assertFalse(packaged.exists())
        self.assertTrue((KIT / "docs" / "releases" / "v0.4.11.md").is_file())
        self.assertFalse((packaged.parent / "v0.4.11.md").exists())

    def test_release_states_current_authority_evidence_and_human_boundary(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for required in (
            "generation-bound authority projection",
            "already_present",
            "same-generation delta-or-dirty",
            "stops before native approval",
            "47` approval-available",
            "67` approval-fixed-closed",
            "v0.4.12-link-index-windows-reference.json",
            "8,616` Zets",
            "22,441` Objets",
            "actual serialized stderr progress stream",
            "first non-empty stream `write`",
            "first `flush`",
            "benchmark script",
            "exact wheel bytes",
            "superseded v0.1 callback-timing result",
            "does not open, index, recover, or otherwise modify a client archive",
            r".\.zettel-kasten\bin\archive.cmd index <archive-root>",
            r".\.zettel-kasten\bin\archive.cmd index-health <archive-root>",
            "The person does not count Zets or Objets",
            "zet-revision-restore-proposal-from-snapshot --approve",
            "derive-text capture --approve",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())
        self.assertNotRegex(text, r"(?i)letter\s*\d+")
        self.assertNotRegex(text, r"(?i)[A-Z]:\\Users\\")
        self.assertNotRegex(text, r"(?i)feedback[/\\]letters")

    def test_windows_reference_receipt_matches_published_numbers_and_is_public_safe(self) -> None:
        receipt = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertTrue(receipt["ok"])
        self.assertEqual(
            receipt["schema"],
            "wom-kit/v0412-link-index-benchmark/v0.2",
        )
        self.assertEqual(receipt["profile"], "full")
        self.assertEqual(receipt["environment"]["os_family"], "windows")
        self.assertEqual(receipt["environment"]["pointer_bits"], 64)
        self.assertEqual(receipt["counts"]["zettels"], 8616)
        self.assertEqual(receipt["counts"]["objets"], 22441)
        self.assertEqual(receipt["counts"]["manifest_size_bytes"], 38_797_312)
        status = receipt["status_delivery"]
        thresholds = receipt["thresholds_seconds"]
        self.assertLessEqual(
            status["first_serialized_write_seconds_max"],
            thresholds["first_serialized_write"],
        )
        self.assertLessEqual(
            status["first_serialized_flush_seconds_max"],
            thresholds["first_serialized_flush"],
        )
        self.assertLessEqual(
            status["max_serialized_flush_gap_seconds"],
            thresholds["max_serialized_flush_gap"],
        )
        self.assertGreater(status["serialized_utf8_bytes"], 0)
        self.assertRegex(
            status["serialized_streams_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(receipt["instrumentation"]["legacy_full_zettel_resolver_calls"], 0)
        self.assertEqual(receipt["instrumentation"]["full_manifest_json_parser_calls"], 0)
        provenance = receipt["provenance"]
        for key in (
            "source_tree_sha256",
            "git_commit_sha256",
            "benchmark_script_sha256",
            "wheel_sha256",
            "wheel_package_tree_sha256",
        ):
            self.assertRegex(provenance[key], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(provenance["wheel_matches_source_tree"])
        self.assertTrue(provenance["source_tree_matches_git_commit"])
        self.assertTrue(provenance["benchmark_script_matches_git_commit"])
        self.assertTrue(provenance["release_evidence_eligible"])
        self.assertEqual(provenance["scoped_uncommitted_entry_count"], 0)
        self.assertEqual(provenance["source_inventory_delta_count"], 0)
        self.assertTrue(all(receipt["checks"].values()), receipt["checks"])
        self.assertTrue(
            all(
                value == 0
                for value in receipt["serialized_progress_safety"].values()
            )
        )
        self.assertTrue(
            all(value == 0 for value in receipt["output_safety"].values())
        )
        for key in (
            "absolute_paths_echoed",
            "object_ids_echoed",
            "private_values_echoed",
            "zettel_ids_echoed",
        ):
            self.assertFalse(receipt[key])

        release_text = RELEASE.read_text(encoding="utf-8")
        self.assertNotIn("Publication remains blocked", release_text)
        for section, state in (
            ("cold_ready", "ready"),
            ("cold_already_present", "already_present"),
            ("warm_ready", "ready"),
            ("warm_already_present", "already_present"),
        ):
            self.assertEqual(
                receipt["plan_durations_seconds"][section]["state"],
                state,
            )

    def test_v0412_supply_lock_is_historical_and_current_policy_is_v0416(self) -> None:
        current = LOCK.read_bytes()
        historical = (KIT / "project-runtime-supply-lock-v0.4.11.json").read_bytes()
        historical_lf = historical.replace(b"\r\n", b"\n")
        expected = historical_lf.replace(
            b'"target_tag": "v0.4.11"',
            b'"target_tag": "v0.4.12"',
        )
        self.assertEqual(current, expected)
        self.assertNotIn(b"\r", current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), LOCK_SHA256)
        policy_raw = (KIT / "project-runtime-policy.json").read_bytes()
        policy = project_runtime.project_runtime_policy_document(policy_raw)
        self.assertIsNotNone(policy)
        assert policy is not None
        self.assertEqual(policy["supply_lock"], "wom-kit/project-runtime-supply-lock-v0.4.16.json")
        self.assertEqual(
            policy["supply_lock_sha256"],
            "sha256:f924a3f714d5913dd2afe870d07e5619172b0e1fcb92f25b18f70a9cd4ad04d8",
        )


if __name__ == "__main__":
    unittest.main()
