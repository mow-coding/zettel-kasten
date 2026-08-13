from __future__ import annotations

import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.318.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.318.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.317.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.317.md")
GUIDE = KIT / "docs" / "letter131-credential-console-paste-and-failure-stages.md"
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-13-v03318-letter131-credential-input.md"
)
HOST_ACCEPTANCE_TOOL = KIT / "tools" / "check_windows_credential_console_host.py"
SKILL_ROOT = KIT / "templates" / "ai-runtime" / "wom-archive"
PACKAGED_SKILL_ROOT = (
    KIT
    / "src"
    / "wom_kit"
    / "_resources"
    / "templates"
    / "ai-runtime"
    / "wom-archive"
)


class V03318ReleaseDocsTests(unittest.TestCase):
    def test_version_and_current_packaged_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.3.318")
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
        self.assertEqual(manifest["version"], "0.3.318")
        self.assertEqual(manifest["file_count"], 145)
        packaged = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.3.318.md", packaged)
        self.assertNotIn("release-notes/v0.3.317.md", packaged)

    def test_release_and_guide_define_paste_and_failure_stage_contract(self) -> None:
        release = RELEASE.read_text(encoding="utf-8")
        guide = GUIDE.read_text(encoding="utf-8")
        combined = " ".join((" ".join(release.split()), " ".join(guide.split())))
        for token in (
            "Ctrl+V",
            "Shift+Insert",
            "Ctrl+Shift+V",
            "right-click",
            "입력값을 받았습니다. 검증 중입니다.",
            "credential_input_cancelled_or_empty",
            "credential_input_not_received",
            "provider_auth_rejected",
            "provider_identity_endpoint_unavailable",
            "reviewed_anchor_inaccessible",
            "wom-credential-secure-intake-result/v0.2",
            "wom-credential-workflow-result/v0.2",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

        for token in (
            "Ctrl+C",
            "empty Enter",
            "actual physical paste gesture",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, release)

        for forbidden in (
            "C:\\Users\\",
            "wom-feedback-",
            "protected archive",
        ):
            for document_name, text in (("release", release), ("guide", guide)):
                with self.subTest(forbidden=forbidden, document=document_name):
                    self.assertNotIn(forbidden, text)

    def test_decision_records_fixed_security_and_failure_stage_boundaries(self) -> None:
        text = DECISION.read_text(encoding="utf-8")
        for token in (
            "credential_input_cancelled_or_empty",
            "credential_input_not_received",
            "provider_auth_rejected",
            "provider_identity_endpoint_unavailable",
            "reviewed_anchor_inaccessible",
            "rollback",
            "echo",
            "clipboard",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_manual_host_acceptance_tool_is_publicly_routed_and_content_free(self) -> None:
        relative_tool = "tools/check_windows_credential_console_host.py"
        for path in (RELEASE, GUIDE):
            with self.subTest(document=path.name):
                self.assertIn(relative_tool, path.read_text(encoding="utf-8"))

        tool = HOST_ACCEPTANCE_TOOL.read_text(encoding="utf-8")
        for token in (
            'SCHEMA_VERSION = "wom-kit/windows-credential-console-host-acceptance/v0.1"',
            'SYNTHETIC_LINE = "WOM-PASTE-ACCEPTANCE-0318"',
            '"product_clipboard_read_performed": False',
            '"credential_store_write_performed": False',
            '"provider_request_performed": False',
            '"result_contains_input_value": False',
        ):
            with self.subTest(token=token):
                self.assertIn(token, tool)

    def test_current_maps_readmes_and_install_guides_point_to_v03318(self) -> None:
        paths = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            ROOT / "VERSIONING.md",
            KIT / "README.md",
            KIT / "cli" / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "ai-command-path-routing.md",
            KIT / "docs" / "capability-matrix.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        for path in paths:
            with self.subTest(document=path.name):
                self.assertIn("0.3.318", path.read_text(encoding="utf-8"))

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.3.318-py3-none-any.whl", install)

        status = "Status: v0.3.318 credential paste and failure-stage checkpoint"
        for path in (
            KIT / "docs" / "capability-matrix.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
        ):
            with self.subTest(status_document=path.name):
                self.assertIn(status, path.read_text(encoding="utf-8"))

    def test_runtime_skill_is_bounded_and_package_mirrors_match(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 200)
        self.assertLessEqual(len(skill.split()), 1400)
        for token in (
            "credential_input_cancelled_or_empty",
            "credential_input_not_received",
            "provider_auth_rejected",
            "provider_identity_endpoint_unavailable",
            "reviewed_anchor_inaccessible",
        ):
            with self.subTest(token=token):
                self.assertIn(token, skill)

        for relative in (
            Path("SKILL.md"),
            Path("references/startup-and-update.md"),
            Path("references/operator-contract.md"),
        ):
            with self.subTest(resource=relative.as_posix()):
                self.assertEqual(
                    (SKILL_ROOT / relative).read_bytes(),
                    (PACKAGED_SKILL_ROOT / relative).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
