from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from wom_kit import archive_services


KIT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REFERENCES = (
    KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "references"
)
PACKAGED_REFERENCES = (
    KIT_ROOT
    / "src"
    / "wom_kit"
    / "_resources"
    / "templates"
    / "ai-runtime"
    / "wom-archive"
    / "references"
)


class V0410RuntimeDocsRoutingTests(unittest.TestCase):
    def test_runtime_references_publish_the_two_decision_batch_contract(self) -> None:
        source_resume = (
            "archive source-intake-batch <archive-root> --manifest <same-json> "
            "--resume --reviewed-by <same-actor> --format json"
        )
        capture_preview = (
            "archive objet-capture-batch <archive-root> "
            "--source-intake-execution-sha256 <intake-execution-sha256> "
            "--dry-run --format json"
        )
        for name in (
            "capture-draft-and-publication.md",
            "operator-contract.md",
        ):
            source = (RUNTIME_REFERENCES / name).read_text(encoding="utf-8")
            packaged = (PACKAGED_REFERENCES / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertEqual(packaged, source)
                self.assertIn(source_resume, source)
                self.assertIn(capture_preview, source)
                self.assertIn("capture dry-run", source)
                self.assertRegex(source, r"new(?: native)? approval")
                self.assertNotIn(
                    "archive objet-capture-batch <archive-root> --manifest",
                    source,
                )
                self.assertNotIn("batch approval is fixed fail-closed", source)

    def test_public_command_guides_use_manifest_and_automatic_resume(self) -> None:
        readme = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        routing_doc = (KIT_ROOT / "docs" / "ai-command-path-routing.md").read_text(
            encoding="utf-8"
        )
        for name, text in (("README", readme), ("routing", routing_doc)):
            with self.subTest(name=name):
                self.assertIn(
                    "source-intake-batch <archive-root> --manifest",
                    text,
                )
                self.assertIn("--source-intake-execution-sha256", text)
                self.assertIn("--resume --reviewed-by", text)
                self.assertNotIn(
                    "source-intake-batch <archive-root> --request",
                    text,
                )

    def test_machine_route_exposes_exact_two_decision_recovery_boundary(self) -> None:
        routing = archive_services.runtime_context_action_routing()
        route = next(
            row
            for row in routing["write_action_routes"]
            if row["action"] == "capture_reviewed_objet_batch"
        )
        self.assertIn("source-intake-batch", route["preview_command"])
        self.assertIn("--manifest", route["approved_command"])
        self.assertIn("--resume", route["intake_resume_command"])
        self.assertNotIn("--resume-approval-id", route["intake_resume_command"])
        self.assertNotIn("--execution-sha256", route["intake_resume_command"])
        self.assertIn(
            "--source-intake-execution-sha256",
            route["capture_preview_command"],
        )
        self.assertIn(
            "--source-intake-execution-sha256",
            route["capture_approved_command"],
        )
        self.assertEqual(route["separate_human_decision_count"], 2)
        self.assertEqual(
            route["convergence_model"],
            "two_decision_authenticated_intake_and_fresh_capture_approval",
        )
        self.assertFalse(route["intake_resume_manual_ids_required"])
        self.assertFalse(route["intake_resume_requires_new_human_decision"])
        self.assertFalse(route["capture_same_claim_resume_allowed"])
        self.assertFalse(route["capture_per_item_replay_allowed"])

    def test_staged_cleanup_never_routes_to_legacy_manifest_only_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            shutil.copytree(
                KIT_ROOT / "examples" / "fake-life-archive",
                archive_root,
            )
            (archive_root / "staging" / "incoming").mkdir(parents=True)
            result = archive_services.staged_cleanup_check(
                archive_root,
                "staging/incoming",
            )

        actions = "\n".join(result["next_safe_actions"])
        self.assertNotIn(
            "objet-capture-batch <archive-root> --manifest",
            actions,
        )
        self.assertIn("--source-intake-execution-sha256", actions)
        self.assertIn("fresh plan digest", actions)
        self.assertIn("never reuse the prior approval", actions)
        self.assertIn("never", actions)
        self.assertIn("replay individual items", actions)


if __name__ == "__main__":
    unittest.main()
