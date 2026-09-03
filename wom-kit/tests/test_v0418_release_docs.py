from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.18.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.18.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.18.json"
PUBLIC_CURRENT_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    ROOT / "CHANGELOG.md",
    KIT / "README.md",
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "ai-command-path-routing.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "operation-control.md",
    KIT / "docs" / "philosophy-implementation-evidence.md",
    KIT / "docs" / "philosophy-implementation-evidence.ko.md",
    KIT / "docs" / "project-version-update.md",
    KIT / "docs" / "public-documentation-map.md",
    KIT / "docs" / "public-documentation-map.ko.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "python-tool-install.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    RELEASE,
)
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
    PACKAGED_RELEASE,
)
MIRRORED_RUNTIME_DOCUMENTS = (
    (
        KIT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md",
        RESOURCE_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md",
    ),
    (
        KIT
        / "templates"
        / "ai-runtime"
        / "wom-archive"
        / "references"
        / "startup-and-update.md",
        RESOURCE_ROOT
        / "templates"
        / "ai-runtime"
        / "wom-archive"
        / "references"
        / "startup-and-update.md",
    ),
    *(
        (
            KIT / "templates" / profile / "AGENTS.md",
            RESOURCE_ROOT / "templates" / profile / "AGENTS.md",
        )
        for profile in ("company", "family", "personal")
    ),
)
PROJECT_RECORDS = (
    ROOT / "meeting-minutes" / "2026-09-03-v0418-terminal-original-cleanup.md",
    ROOT
    / "archive-infra-decision-log-2026-09-03-v0418-terminal-original-cleanup.md",
)


class V0418ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.18")
        self.assertIn(
            'version = "0.4.18"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.18"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.18"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.18"', citation)
        self.assertIn('date-released: "2026-09-03"', citation)
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.18", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.17", versioning)
        self.assertIn(
            "v0.4.18 (현재 checkpoint)",
            (ROOT / "README.ko.md").read_text(encoding="utf-8"),
        )
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## v0.4.18 - 2026-09-03", changelog)
        self.assertLess(
            changelog.index("## v0.4.18 - 2026-09-03"),
            changelog.index("## v0.4.17 - 2026-09-01"),
        )

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.17.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.17"',
            b'"target_tag": "v0.4.18"',
        )
        self.assertEqual(current, expected)
        self.assertNotIn(b"\r", current)
        lock_sha256 = hashlib.sha256(current).hexdigest()
        policy = json.loads(
            (KIT / "project-runtime-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.18.json",
        )
        self.assertEqual(
            policy["supply_lock_sha256"],
            f"sha256:{lock_sha256}",
        )
        runtime_source = (KIT / "src" / "wom_kit" / "project_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(policy["supply_lock"], runtime_source)
        self.assertIn(policy["supply_lock_sha256"], runtime_source)

    def test_current_release_is_the_only_packaged_note(self) -> None:
        self.assertEqual(RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertEqual(
            sorted(path.name for path in PACKAGED_RELEASE.parent.glob("v*.md")),
            ["v0.4.18.md"],
        )
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.18")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.18.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.17.md", packaged_paths)

    def test_current_install_guides_use_exact_v0418_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    '$womBootstrapNonce = [guid]::NewGuid().ToString("N")',
                    document,
                )
                self.assertIn(
                    '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA '
                    '"WOM\\bootstrap-v0418-$womBootstrapNonce"',
                    document,
                )
                self.assertRegex(
                    document,
                    re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b",
                )
                self.assertIn("wom_kit-0.4.18-py3-none-any.whl", document)
                self.assertIn(
                    r'& "$womBootstrapRoot\Scripts\archive.exe" --version',
                    document,
                )
                self.assertNotIn("bootstrap-v0417", document)
        for path in (
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
        ):
            with self.subTest(path=path, surface="dedicated-tool-root"):
                self.assertIn(
                    '$womToolRoot = Join-Path $env:LOCALAPPDATA "WOM\\tool-v0418"',
                    path.read_text(encoding="utf-8"),
                )

    def test_release_describes_v0418_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for required in (
            "terminal_original_exact",
            "exact, forward, and terminal",
            "names the journal approval reference as its cleanup authority",
            "plan's file list and directories equal the current tree exactly",
            "keeps its existing route",
            "exact_terminal_transaction_cleanup_requires_resume",
            "terminal_transaction_cleanup_required: true",
            "Claim-reference cleanup authority",
            "live active pin still equals the transaction's post-image",
            "exactly one MAC-verified `succeeded` claim",
            "No approval context is rebuilt",
            "The retained plan is historical evidence; the authenticated claim is the authority",
            "terminal_transaction_cleanup_completed",
            "past_update_success_attributed: false",
            "attributes nothing and grants no retry, cleanup, or fresh approval authority",
            "Re-entrant and fail-closed",
            "next resume finishes it",
            "terminal_cleanup_platform_unsupported",
            "cause_code_source: fixed_literal_allowlist",
            "project_version_update_preapproval_recovery_failed",
            "Raw exception text, paths, values, and identifiers are never copied",
            "marker.json is an identity anchor",
            "not a lifecycle record",
            "Publishing or installing v0.4.18 does not inspect or modify a client archive",
            "client chooses whether and when",
            "not asked to count files",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

    def test_runtime_guidance_source_and_package_copies_match(self) -> None:
        for source, packaged in MIRRORED_RUNTIME_DOCUMENTS:
            with self.subTest(source=source, packaged=packaged):
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
        skill = (
            KIT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("terminal_transaction_cleanup_completed", skill)

    def test_project_records_capture_decision_and_release_boundary(self) -> None:
        for path in PROJECT_RECORDS:
            document = path.read_text(encoding="utf-8")
            flat = " ".join(document.split())
            with self.subTest(path=path):
                self.assertIn("dry-run", flat)
                self.assertIn("approval", flat)
                self.assertIn("identifier-free", flat)
                self.assertIn("canonical proof", flat)
                self.assertIn("project-domain", flat)
                self.assertIn("terminal guard", flat)
                self.assertIn("transaction", flat)
                self.assertIn("client", flat)
                self.assertIn("release", flat)
                self.assertIn("post-image", flat)
                self.assertIn("claim", flat)

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in PUBLIC_CURRENT_DOCUMENTS
        )
        self.assertNotRegex(combined, r"(?i)letter\s*15[23]")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")


if __name__ == "__main__":
    unittest.main()
