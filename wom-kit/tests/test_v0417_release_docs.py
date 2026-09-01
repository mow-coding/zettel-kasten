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
RELEASE = KIT / "docs" / "releases" / "v0.4.17.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.17.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.17.json"
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
    ROOT / "meeting-minutes" / "2026-09-01-v0417-terminal-cleanup-recovery.md",
    ROOT / "archive-infra-decision-log-2026-09-01-v0417-terminal-cleanup-recovery.md",
)


class V0417ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.17")
        self.assertIn(
            'version = "0.4.17"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.17"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.17"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.17"', citation)
        self.assertIn('date-released: "2026-09-01"', citation)
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.17", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.16", versioning)
        self.assertIn(
            "v0.4.17 (현재 checkpoint)",
            (ROOT / "README.ko.md").read_text(encoding="utf-8"),
        )

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.16.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.16"',
            b'"target_tag": "v0.4.17"',
        )
        self.assertEqual(current, expected)
        self.assertNotIn(b"\r", current)
        lock_sha256 = hashlib.sha256(current).hexdigest()
        policy = json.loads(
            (KIT / "project-runtime-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.17.json",
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
            ["v0.4.17.md"],
        )
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.17")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.17.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.16.md", packaged_paths)

    def test_current_install_guides_use_exact_v0417_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    '$womBootstrapNonce = [guid]::NewGuid().ToString("N")',
                    document,
                )
                self.assertIn(
                    '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA '
                    '"WOM\\bootstrap-v0417-$womBootstrapNonce"',
                    document,
                )
                self.assertRegex(
                    document,
                    re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b",
                )
                self.assertIn("wom_kit-0.4.17-py3-none-any.whl", document)
                self.assertIn(
                    r'& "$womBootstrapRoot\Scripts\archive.exe" --version',
                    document,
                )
        for path in (
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
        ):
            with self.subTest(path=path, surface="dedicated-tool-root"):
                self.assertIn(
                    '$womToolRoot = Join-Path $env:LOCALAPPDATA "WOM\\tool-v0417"',
                    path.read_text(encoding="utf-8"),
                )

    def test_release_describes_v0417_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for required in (
            "same bounded, read-only classification",
            "project_version_update_terminal_cleanup_required",
            "project_version_update_terminal_cleanup_outcome_unknown",
            "before opening native approval or entering the domain writer",
            "identifier-free `project-version-update --resume`",
            "Exact preapproval-abort history compaction",
            "identity-bound",
            "no-replace tombstone",
            "retains one canonical proof",
            "does not run the project-domain writer",
            "attribute a past update success",
            "grants no fresh approval authority",
            "terminal_abort_histories_compacted",
            "cleanup_proofs_written_or_verified",
            "terminal_abort_history_compaction_state",
            "terminal_abort_history_compaction_incomplete",
            "files_written_scope: project_domain_only",
            "private_control_mutation_performed_or_verified",
            "private_control_mutation_may_be_incomplete",
            "An empty list is not a claim that no private control evidence changed",
            "Partial, malformed, mixed, changing, ambiguous, or unsafe residue",
            "strict allowlist",
            "Arbitrary exception messages",
            "held parent chain",
            "regular single-link file",
            "alternate data stream",
            "cannot fall back to a generic command error",
            "Only the fixed internal",
            "other internal exceptions remain private",
            "exact active transaction is not permission to ignore its siblings",
            "before recovery, native approval, or domain-writer entry",
            "One held terminal authority boundary",
            "keep the same guard held through the native decision",
            "different transaction state cannot borrow it",
            "recoverable cleanup tombstone",
            "strict active-handoff snapshots before and after",
            "state or digest change",
            "unrelated operation-control error is still not relabelled",
            "person is not asked to count files",
            "Publishing or installing v0.4.17 does not inspect or modify a client archive",
            "client chooses whether and when",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

    def test_runtime_guidance_source_and_package_copies_match(self) -> None:
        for source, packaged in MIRRORED_RUNTIME_DOCUMENTS:
            with self.subTest(source=source, packaged=packaged):
                self.assertEqual(source.read_bytes(), packaged.read_bytes())

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

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in PUBLIC_CURRENT_DOCUMENTS
        )
        self.assertNotRegex(combined, r"(?i)letter\s*152")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")


if __name__ == "__main__":
    unittest.main()
