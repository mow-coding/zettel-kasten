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
RELEASE = KIT / "docs" / "releases" / "v0.4.27.md"
CURRENT_RELEASE = KIT / "docs" / "releases" / "v0.4.28.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.28.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.28.json"
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
)
CURRENT_PUBLIC_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    ROOT / "CHANGELOG.md",
    KIT / "README.md",
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "python-tool-install.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    KIT / "docs" / "recovery-operations-acceptance.md",
    KIT / "docs" / "source-fidelity-and-private-verbatim.md",
    KIT / "docs" / "writer-session-coverage.json",
    RELEASE,
)


class V0427ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.28")
        self.assertIn('version = "0.4.28"', (KIT / "pyproject.toml").read_text(encoding="utf-8"))
        for shim in (KIT / "src" / "wom_kit" / "__init__.py", ROOT / "wom_kit" / "__init__.py"):
            self.assertIn('__version__ = "0.4.28"', shim.read_text(encoding="utf-8"))
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.28"', citation)
        self.assertRegex(citation, r'date-released: "2026-09-1[89]"')
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.28", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.27", versioning)
        self.assertIn("Previous public baseline: v0.4.27.", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("v0.4.28 (현재 checkpoint)", (ROOT / "README.ko.md").read_text(encoding="utf-8"))

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.27.json").read_bytes()
        self.assertEqual(previous.replace(b'"target_tag": "v0.4.27"', b'"target_tag": "v0.4.28"'), current)
        policy = json.loads((KIT / "project-runtime-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["supply_lock"], "wom-kit/project-runtime-supply-lock-v0.4.28.json")
        self.assertEqual(policy["supply_lock_sha256"], "sha256:" + hashlib.sha256(current).hexdigest())

    def test_current_release_is_the_only_packaged_note(self) -> None:
        self.assertEqual(CURRENT_RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertEqual(sorted(path.name for path in PACKAGED_RELEASE.parent.iterdir()), ["v0.4.28.md"])
        manifest = json.loads((RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.28")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.28.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.27.md", packaged_paths)
        self.assertTrue((KIT / "docs" / "releases" / "v0.4.27.md").is_file())

    def test_current_install_guides_use_exact_v0428_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn('$womBootstrapNonce = [guid]::NewGuid().ToString("N")', document)
                self.assertIn('$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\\bootstrap-v0428-$womBootstrapNonce"', document)
                self.assertRegex(document, re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b")
                self.assertIn("wom_kit-0.4.28-py3-none-any.whl", document)
                if path.name.startswith("UPGRADE"):
                    continue  # upgrade guides keep every historical section
                self.assertNotIn("bootstrap-v0427-", document)

    def test_release_describes_v0427_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split()).casefold()
        for required in (
            "v0.4.25 success report",
            "cause_stage: starting",
            "project_runtime_exact_public_wheel_required",
            "reason_detail",
            "rejected_operation_index",
            "byte-order mark",
            "source_intake_record_plan_encoding_invalid",
            "plan_sha256",
            "publishing or installing this release does not read or modify a client archive",
            "client-run result and a new-process verification",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat)

    def test_current_docs_use_v0428_status_without_erasing_v0427_history(self) -> None:
        expected = {
            KIT / "docs" / "agent-operator-capabilities.md":
                "Status: v0.4.28 object-storage restore, client follow-ups, and writer-session coverage gate",
            KIT / "docs" / "capability-matrix.md":
                "Version: v0.4.28 implementation and release scope",
            KIT / "docs" / "runtime-canonical-entrypoints.md":
                "Status: v0.4.28 object-storage restore, client follow-ups, and session-owned writes truth",
            KIT / "docs" / "version-truth-source.md":
                "Status: v0.4.28 object-storage restore, client follow-ups, and session-owned writes",
            KIT / "docs" / "python-tool-install.md":
                "Status: v0.4.28 conditional GitHub wheel contract; object-storage restore and client follow-ups",
        }
        for path, phrase in expected.items():
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(phrase, document)
                self.assertIn("v0.4.27", document)

    def test_release_surfaces_are_documented(self) -> None:
        contract = (KIT / "docs" / "exact-human-approval-contract.md").read_text(encoding="utf-8")
        self.assertIn("since v0.4.27 a refused kind is reported by", contract)
        update_doc = (KIT / "docs" / "project-version-update.md").read_text(encoding="utf-8")
        self.assertIn("since v0.4.27", update_doc)
        register = (KIT / "docs" / "recovery-operations-acceptance.md").read_text(encoding="utf-8")
        self.assertIn("| CF-01 | v0.4.27 |", register)
        for guide in (ROOT / "UPGRADE.md", ROOT / "UPGRADE.ko.md"):
            document = guide.read_text(encoding="utf-8")
            with self.subTest(guide=guide):
                self.assertIn("reason_detail", document)
                self.assertIn("project_runtime_exact_public_wheel_required", document)

    def test_coverage_manifest_matches_release_claim(self) -> None:
        manifest = json.loads((KIT / "docs" / "writer-session-coverage.json").read_text(encoding="utf-8"))
        statuses = [row["status"] for row in manifest["paths"].values()]
        routed = sum(1 for row in manifest["paths"].values() if row.get("route"))
        # v0.4.23 integrated create-draft (LR-06a); v0.4.24 through v0.4.27 change no writer.
        self.assertEqual(len(statuses), 58)
        self.assertEqual(statuses.count("session_integrated") - routed, 6)
        self.assertEqual(routed, 1)
        self.assertEqual(statuses.count("pending"), 31)
        self.assertEqual(statuses.count("legacy_exception"), 20)
        self.assertEqual(manifest["paths"]["create-draft"]["status"], "session_integrated")

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_PUBLIC_DOCUMENTS)
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")


if __name__ == "__main__":
    unittest.main()
