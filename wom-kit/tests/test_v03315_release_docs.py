from __future__ import annotations

from pathlib import Path
import json
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.315.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.315.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.314.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.314.md")
L127_DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-11-v03315-letter127.md"
)
L128_DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-11-v03315-letter128.md"
)
SKILL = KIT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"


class V03315ReleaseDocsTests(unittest.TestCase):
    def test_version_and_current_packaged_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.3.315")
        self.assertEqual(RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertTrue(HISTORICAL_RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())

        manifest = json.loads(
            (
                KIT
                / "src"
                / "wom_kit"
                / "_resources"
                / "resource-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.3.315")
        packaged = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.3.315.md", packaged)
        self.assertNotIn("release-notes/v0.3.314.md", packaged)

    def test_release_states_exact_collision_and_batch_boundaries(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for token in (
            "materialization_plan_sha256",
            "update-entry:0001",
            "project-version-update-collision",
            "NFKC",
            "8.3-looking",
            "empty ignored descendant directory",
            "pre-HEAD exact verifier",
            "writes: null",
            "unauthenticated_private_state_internal_consistency",
            "selection_sha256",
            "attempt_sha256",
            "exact `files_written` delta",
            "64 MiB",
            "batch_capture_outcome_unverified",
            "derive-text capture --from-manifest",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, flat)

        for forbidden in (
            "C:\\Users\\",
            "wom-feedback-",
            "protected archive",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_decisions_and_operator_guidance_match_final_contract(self) -> None:
        l127 = L127_DECISION.read_text(encoding="utf-8")
        l128 = L128_DECISION.read_text(encoding="utf-8")
        derived = (KIT / "docs" / "derived-text.md").read_text(encoding="utf-8")
        operation = (KIT / "docs" / "operation-control.md").read_text(
            encoding="utf-8"
        )
        for token in (
            "NFKC",
            "8.3-looking",
            "empty ignored descendant",
            "pre-HEAD",
            "nullable relocation",
            "unauthenticated_private_state_internal_consistency",
        ):
            with self.subTest(surface="letter127", token=token):
                self.assertIn(token, l127)
        for token in (
            "exact `files_written` delta",
            "64 MiB",
            "attempt_sha256",
            "tri-state",
            "derive-text capture --from-manifest",
        ):
            with self.subTest(surface="letter128", token=token):
                self.assertIn(token, l128)
        for token in (
            "original_requested = original_written + original_skipped + original_blocked",
            "batch_capture_outcome_unverified",
            "fresh_batch_dry_run_then_reconcile",
        ):
            with self.subTest(surface="derived", token=token):
                self.assertIn(token, derived)
        self.assertIn("Successful transport is also routed", operation)
        self.assertIn("ready_to_fetch_on_approve", operation)
        self.assertIn("updated_restart_required", operation)

    def test_current_maps_readmes_and_install_guides_point_to_v03315(self) -> None:
        paths = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            KIT / "README.md",
            KIT / "cli" / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "ai-command-path-routing.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        for path in paths:
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("0.3.315", text)

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.3.315-py3-none-any.whl", install)
        self.assertIn("installed v0.3.314 client cannot use", install)

    def test_runtime_skill_is_bounded_and_routes_both_recoveries(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 200)
        self.assertLessEqual(len(text.split()), 1400)
        for token in (
            "project-version-update-collision",
            "fresh updater preview and separate approval",
            "original and derived",
            "evidence_incomplete",
            "recovery_required",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_batch_schema_source_and_package_mirrors_match(self) -> None:
        for name in (
            "objet-capture-batch-request.schema.json",
            "objet-capture-batch-receipt.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertEqual(
                    (KIT / "schemas" / name).read_bytes(),
                    (
                        KIT
                        / "src"
                        / "wom_kit"
                        / "_resources"
                        / "schemas"
                        / name
                    ).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
