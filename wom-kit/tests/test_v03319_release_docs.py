from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.319.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.319.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.318.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.318.md")
HISTORICAL_GUIDE = KIT / "docs" / "letter131-credential-console-paste-and-failure-stages.md"
HISTORICAL_DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-13-v03318-letter131-credential-input.md"
)
HISTORICAL_MINUTES = (
    ROOT / "meeting-minutes" / "2026-08-13-letter131-credential-paste-and-failure-stages.md"
)
HISTORICAL_RELEASE_PREPARATION_MINUTES = (
    ROOT / "meeting-minutes" / "2026-08-13-v03318-release-preparation.md"
)
HISTORICAL_PUBLIC_RELEASE_MINUTES = (
    ROOT / "meeting-minutes" / "2026-08-14-v03318-public-release-verification.md"
)
GUIDE = KIT / "docs" / "letter132-credential-console-keyboard-readiness-and-causal-evidence.md"
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-14-v03319-letter132-credential-input-evidence.md"
)
HOST_ACCEPTANCE_TOOL = KIT / "tools" / "check_windows_credential_console_host.py"
ARCHIVE_CLI = KIT / "src" / "wom_kit" / "archive_cli.py"
MEETING_MINUTES = (
    ROOT / "meeting-minutes" / "2026-08-14-letter132-credential-input-evidence.md"
)
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
CURRENT_LIVING_SURFACES = (
    ROOT / "CHANGELOG.md",
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    KIT / "README.md",
    KIT / "cli" / "README.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "references" / "operator-contract.md",
    RELEASE,
    GUIDE,
    DECISION,
)


class V03319ReleaseDocsTests(unittest.TestCase):
    def test_v03318_historical_letter131_bytes_are_immutable(self) -> None:
        expected = {
            HISTORICAL_RELEASE: (
                "649899aa8ad6150f27f8ffb551e72c90dce20eecaea8e78c098d342e6e174735"
            ),
            HISTORICAL_GUIDE: (
                "907d67acac3528dea9e5f7715c662a3a9cd7e8cad03c6b6be3c12490838cd8d6"
            ),
            HISTORICAL_DECISION: (
                "124295193b2f9d78d6c369c3cb5e4cf090711fc8e4b8f20792d696ce2fcb328b"
            ),
            HISTORICAL_MINUTES: (
                "0038a42f7bef4314243a75188853a0afc267872eb1d5208b6ecffb245fa31bff"
            ),
            HISTORICAL_RELEASE_PREPARATION_MINUTES: (
                "6a39ac90a0e13d01e60db172bb2a672126c5ef337ef22824726f4eaa273bab43"
            ),
            HISTORICAL_PUBLIC_RELEASE_MINUTES: (
                "79551b60ff1eb30d3faafb9cb74f3bbc630ca4c86398304f50034665239817b2"
            ),
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_sha256,
                )

    def test_version_and_current_packaged_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.3.319")
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
        self.assertEqual(manifest["version"], "0.3.319")
        self.assertEqual(len(manifest["files"]), 145)
        packaged = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.3.319.md", packaged)
        self.assertNotIn("release-notes/v0.3.318.md", packaged)

    def test_release_guide_and_decision_define_native_popup_contract(self) -> None:
        documents = {
            "release": RELEASE.read_text(encoding="utf-8"),
            "guide": GUIDE.read_text(encoding="utf-8"),
            "decision": DECISION.read_text(encoding="utf-8"),
        }
        combined = " ".join(" ".join(text.split()) for text in documents.values())
        for token in (
            "native Windows popup",
            "CredentialPopupInputIntent.live_registration",
            "CredentialPopupInputIntent.synthetic_acceptance",
            "실제 자격 증명 등록",
            "합성 입력 테스트 · 실제 키 입력 금지",
            "경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.",
            "WOM-INPUT-ACCEPTANCE-0319",
            "wom-kit/windows-credential-popup-acceptance/v0.1",
            "codex_desktop_native_popup",
            "popup_child_detached",
            "final mapping",
            "terminal pipe EOF",
            "per-monitor-v2",
            "system message font",
            "1155×823",
            "168 DPI",
            "credential_input_received",
            "complete_line_received",
            "temporary_store_write_attempted",
            "provider_request_attempted",
            "credential_input_invalid_for_provider",
            "credential_input_boundary_failed",
            "repair_secure_input_boundary_and_create_a_new_plan",
            "provider_request_not_attempted",
            "provider_auth_rejected",
            "post-delete absence probe",
            "not_performed",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

        for forbidden in ("C:\\Users\\", "wom-feedback-", "protected archive"):
            for document_name, text in documents.items():
                with self.subTest(forbidden=forbidden, document=document_name):
                    self.assertNotIn(forbidden, text)

    def test_current_living_surfaces_have_no_withdrawn_console_contract(self) -> None:
        forbidden = (
            "codex_desktop_attached_parent_console",
            "conpty_parent_attached_console",
            "wom-kit/windows-credential-console-host-acceptance/v0.4",
            "CONIN$",
            "CONOUT$",
            "ReadConsoleW",
            "PeekConsoleInputW",
            "same-terminal",
            "No separate window",
            "no separate window",
            "같은 현재 터미널",
            "공유 터미널",
        )
        for path in CURRENT_LIVING_SURFACES:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(document=path.name, token=token):
                    self.assertNotIn(token, text)

    def test_manual_popup_acceptance_contract_is_synthetic_only(self) -> None:
        tool = HOST_ACCEPTANCE_TOOL.read_text(encoding="utf-8")
        for token in (
            'SCHEMA_VERSION = "wom-kit/windows-credential-popup-acceptance/v0.1"',
            'SYNTHETIC_LINE = "WOM-INPUT-ACCEPTANCE-0319"',
            '"codex_desktop": "codex_desktop_native_popup"',
            '"windows_terminal": "windows_terminal_native_popup"',
            '"console_host": "console_host_native_popup"',
            '"conpty_parent": "conpty_parent_native_popup"',
            "CredentialPopupInputIntent.synthetic_acceptance",
            '"test_intent": "synthetic_popup_acceptance_only"',
            '"actual_credential_registration_performed": False',
            '"actual_pat_requested": False',
            '"credential_store_write_performed": False',
            '"provider_request_performed": False',
            '"result_contains_input_value": False',
            '"machine_input_classification": machine_input_classification',
            '"no_input"',
            '"partial_input_cancelled"',
            '"empty_confirmation"',
            '"nonempty_input_mismatch"',
            '"exact_synthetic_input_received"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, tool)

        for withdrawn in (
            "prompt_masked_secret_in_attached_console",
            "prompt_masked_secret_in_new_console",
            "codex_desktop_attached_parent_console",
            "windows-credential-console-host-acceptance/v0.4",
        ):
            with self.subTest(withdrawn=withdrawn):
                self.assertNotIn(withdrawn, tool)

        relative_tool = "tools/check_windows_credential_console_host.py"
        for path in (RELEASE, GUIDE):
            with self.subTest(document=path.name):
                self.assertIn(relative_tool, path.read_text(encoding="utf-8"))

    def test_archive_cli_copy_separates_registration_from_acceptance(self) -> None:
        source = ARCHIVE_CLI.read_text(encoding="utf-8")
        for token in (
            "separate native Windows popup",
            "actual credential registration",
            "synthetic acceptance harness",
            "native Windows registration popup",
            "Enter an actual credential only in that popup",
            "credential-adopt accepts secrets only inside its native Windows registration popup",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        for withdrawn in (
            "codex_desktop_attached_parent_console",
            "same-terminal",
            "CONIN$",
            "ReadConsoleW",
        ):
            with self.subTest(withdrawn=withdrawn):
                self.assertNotIn(withdrawn, source)

    def test_human_synthetic_row_failed_and_is_not_a_registration_gate(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (RELEASE, GUIDE, DECISION, MEETING_MINUTES)
        )
        for token in (
            "pre-intent",
            "actual secret",
            "failed evidence",
            "not a live registration",
            "no credential-store write",
            "provider request",
            "not repeated as a recovery prerequisite",
            "optional future acceptance",
            "Actual credential registration: `not_performed`",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_release_does_not_overclaim_delivery_or_physical_acceptance(self) -> None:
        text = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for token in (
            "do not prove merge, external CI, exact tag",
            "human synthetic row is failed evidence",
            "not be repeated as a prerequisite",
            "optional future acceptance",
            "Production registration remains `not_performed`",
            "wheel publication",
            "live credential registration",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_exact_synthetic_pass_is_not_a_recovery_prerequisite(self) -> None:
        paths = (RELEASE, GUIDE, DECISION, MEETING_MINUTES)
        forbidden = (
            "fresh exact synthetic popup row passes",
            "fresh post-intent synthetic human row passes",
            "Only after the synthetic row passes",
            "합성 row가 pass한 뒤에만",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(document=path.name, forbidden=token):
                    self.assertNotIn(token, text)
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split()) for path in paths
        )
        for token in (
            "failed synthetic row",
            "not repeated as a prerequisite",
            "optional future acceptance",
            "published v0.3.319 runtime",
            "실제 자격 증명 등록",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_host_matrix_and_actual_registration_homework_are_bounded(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        release = RELEASE.read_text(encoding="utf-8")

        for token in (
            "--host-family codex_desktop --launch-route codex_desktop_native_popup",
            "--host-family windows_terminal --launch-route windows_terminal_native_popup",
            "--host-family console_host --launch-route console_host_native_popup",
            "--host-family conpty_parent --launch-route conpty_parent_native_popup",
        ):
            with self.subTest(host_row=token):
                self.assertIn(token, guide)
        self.assertGreaterEqual(guide.count("--gesture direct_keyboard_typing"), 4)

        for document_name, text in (("guide", guide), ("release", release)):
            with self.subTest(document=document_name, token="homework heading"):
                self.assertIn("## Bounded post-acceptance homework", text)
            homework = text.split("## Bounded post-acceptance homework", 1)[1]
            homework_flat = " ".join(homework.split())
            for token in (
                "Step 1 — Pre-enrollment authenticated list",
                "Step 2 — New adoption dry-run and one digest-bound approval",
                "Step 3 — Post-enrollment authenticated list",
                "Step 4 — Missing-source recovery dry-run",
                "archive credential-secure-list <archive-root> --verify --format json",
                "--purpose notion-page-recovery",
                "--reviewed-anchor-page-id <reviewed-anchor-uuid>",
                "--expected-request-sha256 <fresh-request-sha256>",
                "archive notion-page-recovery-plan <archive-root>",
                "not evidence",
                "실제 자격 증명 등록",
            ):
                with self.subTest(document=document_name, token=token):
                    self.assertIn(token, homework_flat)
            with self.subTest(document=document_name, token="not run"):
                self.assertRegex(homework_flat, r"\b(?:run|ran) or succeeded\b")
            self.assertIn("not repeated as a prerequisite", homework_flat)
            self.assertIn("published v0.3.319 runtime", homework_flat)
            self.assertIn("do not retry automatically", homework_flat.casefold())
            self.assertNotIn("synthetic popup row passes", homework_flat)
            self.assertGreaterEqual(
                homework.count(
                    "archive credential-secure-list <archive-root> --verify --format json"
                ),
                2,
            )
            self.assertNotIn("archive notion-page-recovery <archive-root>", homework)
            self.assertNotIn("ntn_", homework)
            self.assertNotIn("Bearer ", homework)
            self.assertIn("`not_performed`", text)

    def test_current_maps_readmes_and_install_guides_point_to_v03319(self) -> None:
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
                self.assertIn("0.3.319", path.read_text(encoding="utf-8"))

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.3.319-py3-none-any.whl", install)

        status = "Status: v0.3.319 native credential popup and causal-evidence checkpoint"
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
            "CredentialPopupInputIntent.live_registration",
            "CredentialPopupInputIntent.synthetic_acceptance",
            "실제 자격 증명 등록",
            "합성 입력 테스트 · 실제 키 입력 금지",
            "wom-kit/windows-credential-popup-acceptance/v0.1",
            "codex_desktop_native_popup",
            "credential_input_received",
            "complete_line_received",
            "temporary_store_write_attempted",
            "provider_request_attempted",
            "credential_input_invalid_for_provider",
            "credential_input_boundary_failed",
            "provider_request_not_attempted",
            "post-delete absence probe",
            "not_performed",
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
