from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unittest

from wom_kit import __version__, archive_cli


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.15.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.15.json"
LOCK_SHA256 = "8cc4597742bab8bb4f7c1f4e4c28d90d0b8cddd1293247e680c615531d31953d"
POLICY_SHA256 = "41594f9f21438383be0beb0d4e4aee5f7364d61690edfc920d3faf610d6c94fd"
BOOTSTRAP_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    KIT / "README.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "python-tool-install.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    RELEASE,
    RESOURCE_ROOT / "release-notes" / "v0.4.15.md",
)
ZERO_CLAIM_SUMMARIES = (
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "project-version-update.md",
    KIT / "docs" / "public-documentation-map.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    RELEASE,
)
RECOVERY_SCOPE_ENGLISH_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "UPGRADE.md",
    ROOT / "CHANGELOG.md",
    KIT / "README.md",
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "philosophy-implementation-evidence.md",
    KIT / "docs" / "project-version-update.md",
    KIT / "docs" / "public-documentation-map.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    RELEASE,
    RESOURCE_ROOT / "release-notes" / "v0.4.15.md",
)
RECOVERY_SCOPE_KOREAN_DOCUMENTS = (
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.ko.md",
    KIT / "docs" / "philosophy-implementation-evidence.ko.md",
    KIT / "docs" / "public-documentation-map.ko.md",
    KIT / "docs" / "python-tool-install.ko.md",
)


class V0415ReleaseDocsTests(unittest.TestCase):
    def test_current_version_and_release_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.15")
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.15"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'version = "0.4.15"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.15"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'version: "0.4.15"',
            (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        )
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.15", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.14", versioning)

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.14.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.14"',
            b'"target_tag": "v0.4.15"',
        )
        self.assertEqual(current, expected)
        self.assertEqual(len(current), 1178)
        self.assertNotIn(b"\r", current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), LOCK_SHA256)

        policy_path = KIT / "project-runtime-policy.json"
        policy_raw = policy_path.read_bytes()
        self.assertEqual(hashlib.sha256(policy_raw).hexdigest(), POLICY_SHA256)
        policy = json.loads(policy_raw)
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.15.json",
        )
        self.assertEqual(policy["supply_lock_sha256"], f"sha256:{LOCK_SHA256}")

    def test_current_release_is_the_only_packaged_note(self) -> None:
        packaged = RESOURCE_ROOT / "release-notes" / "v0.4.15.md"
        self.assertEqual(RELEASE.read_bytes(), packaged.read_bytes())
        release_names = sorted(
            path.name for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.15.md"])

        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.15")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.15.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.14.md", packaged_paths)

    def test_current_install_guides_require_new_real_pip_venv_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    '$womBootstrapNonce = [guid]::NewGuid().ToString("N")',
                    document,
                )
                self.assertIn(
                    '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA '
                    '"WOM\\bootstrap-v0415-$womBootstrapNonce"',
                    document,
                )
                self.assertIn(
                    "if (Test-Path -LiteralPath $womBootstrapRoot)",
                    document,
                )
                self.assertIn('throw "WOM bootstrap path must be new."', document)
                self.assertIn("py -3.12 -m venv $womBootstrapRoot", document)
                self.assertRegex(
                    document,
                    re.escape("& $womBootstrapPython")
                    + r"\s+-m\s+pip\s+install\b",
                )
                self.assertIn("wom_kit-0.4.15-py3-none-any.whl", document)
                self.assertIn(r'& "$womBootstrapRoot\Scripts\archive.exe" --version', document)
                self.assertLess(
                    document.index("if (Test-Path -LiteralPath $womBootstrapRoot)"),
                    document.index("py -3.12 -m venv $womBootstrapRoot"),
                )
                self.assertLess(
                    document.index("py -3.12 -m venv $womBootstrapRoot"),
                    document.index("& $womBootstrapPython -m pip install"),
                )
                self.assertNotIn(
                    '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA '
                    '"WOM\\bootstrap-v0415"',
                    document,
                )

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(install.split())
        self.assertIn("uv tool", normalized)
        self.assertIn("not updater evidence", normalized.casefold())
        self.assertIn("project updater", normalized.casefold())

    def test_docs_require_id_free_authenticated_update_resume(self) -> None:
        project_update = (KIT / "docs" / "project-version-update.md").read_text(
            encoding="utf-8"
        )
        approval_contract = (
            KIT / "docs" / "exact-human-approval-contract.md"
        ).read_text(encoding="utf-8")
        release = RELEASE.read_text(encoding="utf-8")
        normalized = " ".join(
            (project_update + "\n" + approval_contract + "\n" + release).split()
        )
        for required in (
            "--resume",
            "--target",
            "--transaction-ref",
            "--approval-id",
            "--reviewed-by",
            "authenticated",
            "exactly one",
            "zero",
            "multiple",
            "tamper",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), normalized.casefold())
        self.assertIn(
            "requires no caller-supplied `--target`, `--transaction-ref`, "
            "`--approval-id`, or `--reviewed-by`",
            normalized,
        )
        self.assertRegex(
            normalized.casefold(),
            r"(?:no|without a) second native (?:approval|decision)",
        )
        self.assertNotIn("advanced exact assertions", normalized.casefold())
        self.assertNotIn("controlled diagnostics", normalized.casefold())
        ordinary_examples = [
            line
            for line in project_update.splitlines()
            if "project-version-update" in line and "--resume" in line
        ]
        self.assertTrue(
            any(
                "--affirm-external-writers-quiescent" in line
                and not any(
                    forbidden in line
                    for forbidden in (
                        "--target",
                        "--transaction-ref",
                        "--approval-id",
                        "--reviewed-by",
                    )
                )
                for line in ordinary_examples
            ),
            ordinary_examples,
        )

    def test_zero_claim_docs_distinguish_preapproval_cancel_from_fail_closed(self) -> None:
        for path in ZERO_CLAIM_SUMMARIES:
            normalized = " ".join(
                path.read_text(encoding="utf-8").split()
            ).casefold()
            with self.subTest(path=path):
                self.assertIn("zero-claim", normalized)
                self.assertIn("untouched preapproval", normalized)
                self.assertIn("fresh approval", normalized)
                self.assertIn("approved or indeterminate transaction", normalized)
                self.assertRegex(normalized, r"fail(?:s)? (?:closed|before)")

        korean = " ".join(
            (KIT / "docs" / "public-documentation-map.ko.md")
            .read_text(encoding="utf-8")
            .split()
        ).casefold()
        self.assertIn("untouched preapproval", korean)
        self.assertIn("새 승인을 요구", korean)
        self.assertIn("이미 승인됐거나 판정할 수 없는 transaction", korean)
        self.assertIn("zero claim", korean)
        self.assertIn("안전하게 중단", korean)

    def test_docs_bound_update_resume_before_terminal_cleanup_rename(self) -> None:
        required = (
            "`version-update.lock`",
            "exact lockless unlock tail",
            "original transaction directory",
            "after `completed`",
            "terminal cleanup tombstone",
            "cleanup proof",
            "not authenticated outcome or cleanup authority",
            "`terminal_cleanup_outcome_unknown`",
            "nonzero",
            "infer success, failure, or cancellation",
            "automatically retry",
            "delete that evidence",
            "authenticated terminal handoff",
            "v0.4.16",
        )
        for path in RECOVERY_SCOPE_ENGLISH_DOCUMENTS:
            normalized = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                for phrase in required:
                    self.assertIn(phrase, normalized)

    def test_korean_docs_match_terminal_cleanup_scope(self) -> None:
        required = (
            "`version-update.lock`",
            "exact lockless unlock tail",
            "원본 transaction directory",
            "`completed` 뒤",
            "terminal cleanup tombstone rename",
            "cleanup proof",
            "인증된 outcome 또는 cleanup authority가 아닙니다",
            "`terminal_cleanup_outcome_unknown`",
            "nonzero",
            "success·failure·cancellation",
            "자동 retry·삭제",
            "authenticated terminal handoff",
            "v0.4.16",
        )
        for path in RECOVERY_SCOPE_KOREAN_DOCUMENTS:
            normalized = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                for phrase in required:
                    self.assertIn(phrase, normalized)

    def test_docs_do_not_claim_unbounded_update_interruption_recovery(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                *RECOVERY_SCOPE_ENGLISH_DOCUMENTS,
                *RECOVERY_SCOPE_KOREAN_DOCUMENTS,
            )
        )
        for forbidden in (
            "v0.4.15 makes an interrupted project update recoverable",
            "v0.4.15 makes a hard-interrupted project update resumable",
            "v0.4.15 closes a recovery trap after an interrupted project runtime update",
            "v0.4.15는 사람이 target·transaction·reviewer·approval·파일 identifier를 찾지 않아도 중단된 project update를 복구하게 합니다",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)
        self.assertNotRegex(
            combined.casefold(),
            r"v0\.4\.15[^\n]{0,120}(?:all|any|every) (?:hard[- ]?)?interruptions?[^\n]{0,80}(?:resumable|recoverable)",
        )

    def test_resume_parser_needs_only_root_resume_and_quiescence(self) -> None:
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "project-version-update",
                r"C:\synthetic-project",
                "--resume",
                "--affirm-external-writers-quiescent",
            ]
        )
        self.assertIsNone(args.target)
        self.assertIsNone(args.transaction_ref)
        self.assertIsNone(args.approval_id)
        self.assertIsNone(args.reviewed_by)

        asserted = parser.parse_args(
            [
                "project-version-update",
                r"C:\synthetic-project",
                "--resume",
                "--transaction-ref",
                "update_" + "a" * 32,
                "--approval-id",
                "approval_" + "b" * 32,
                "--affirm-external-writers-quiescent",
            ]
        )
        self.assertEqual(asserted.transaction_ref, "update_" + "a" * 32)
        self.assertEqual(asserted.approval_id, "approval_" + "b" * 32)

        command_action = next(
            action
            for action in parser._actions
            if getattr(action, "choices", None) is not None
            and "project-version-update" in action.choices
        )
        command_parser = command_action.choices["project-version-update"]
        option_help = {
            option: action.help or ""
            for action in command_parser._actions
            for option in action.option_strings
        }
        self.assertIn("discovered", option_help["--target"])
        self.assertEqual(
            option_help["--transaction-ref"],
            argparse.SUPPRESS,
        )
        self.assertEqual(option_help["--approval-id"], argparse.SUPPRESS)
        self.assertIn("required with --approve", option_help["--reviewed-by"])
        self.assertNotIn("resume", option_help["--reviewed-by"].casefold())
        rendered_help = command_parser.format_help()
        self.assertNotIn("--transaction-ref", rendered_help)
        self.assertNotIn("--approval-id", rendered_help)

    def test_docs_limit_update_lock_feedback_to_create_only_body(self) -> None:
        documents = (
            RELEASE,
            KIT / "docs" / "capability-matrix.md",
            KIT / "docs" / "project-version-update.md",
        )
        normalized = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in documents
        )
        for required in (
            "version-update.lock",
            "operator-feedback-compose",
            "--intent create",
            "append-only",
            "body",
            "receipt",
            "metadata",
            "revise",
            "supersede",
            "delivered",
            "resolved",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), normalized.casefold())

    def test_public_v0415_surfaces_do_not_publish_client_evidence(self) -> None:
        documents = (
            RELEASE,
            ROOT / "CHANGELOG.md",
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        self.assertNotRegex(combined, r"(?i)letter\s*150")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")


if __name__ == "__main__":
    unittest.main()
