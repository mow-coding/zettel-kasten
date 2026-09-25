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
RELEASE = KIT / "docs" / "releases" / "v0.4.22.md"
CURRENT_RELEASE = KIT / "docs" / "releases" / "v0.4.43.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.43.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.43.json"
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
    KIT / "docs" / "operation-control.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "writer-session-coverage.json",
    RELEASE,
    CURRENT_RELEASE,
)


class V0422ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.43")
        self.assertIn('version = "0.4.43"', (KIT / "pyproject.toml").read_text(encoding="utf-8"))
        for shim in (KIT / "src" / "wom_kit" / "__init__.py", ROOT / "wom_kit" / "__init__.py"):
            self.assertIn('__version__ = "0.4.43"', shim.read_text(encoding="utf-8"))
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.43"', citation)
        self.assertIn('date-released: "2026-09-25"', citation)
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.43", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.42", versioning)
        self.assertIn("Previous public baseline: v0.4.42.", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("v0.4.43", (ROOT / "README.ko.md").read_text(encoding="utf-8"))

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.22.json").read_bytes()
        self.assertEqual(previous.replace(b'"target_tag": "v0.4.22"', b'"target_tag": "v0.4.43"'), current)
        policy = json.loads((KIT / "project-runtime-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["supply_lock"], "wom-kit/project-runtime-supply-lock-v0.4.43.json")
        self.assertEqual(policy["supply_lock_sha256"], "sha256:" + hashlib.sha256(current).hexdigest())

    def test_current_release_is_the_only_packaged_note(self) -> None:
        self.assertEqual(CURRENT_RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertEqual(sorted(path.name for path in PACKAGED_RELEASE.parent.iterdir()), ["v0.4.43.md"])
        manifest = json.loads((RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.43")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.43.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.22.md", packaged_paths)
        self.assertTrue((KIT / "docs" / "releases" / "v0.4.22.md").is_file())

    def test_current_install_guides_use_exact_v0437_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn('$womBootstrapNonce = [guid]::NewGuid().ToString("N")', document)
                self.assertIn('$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\\bootstrap-v0443-$womBootstrapNonce"', document)
                self.assertRegex(document, re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b")
                self.assertIn("wom_kit-0.4.43-py3-none-any.whl", document)
                if path.name.startswith("UPGRADE"):
                    continue  # upgrade guides keep every historical section
                self.assertNotIn("bootstrap-v0422-", document)

    def test_release_describes_v0422_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split()).casefold()
        for required in (
            "letters 161 and 162",
            "cause_code",
            "cause_stage",
            "fixed_literal_allowlist",
            "materialize-runtime-candidate",
            "post-claim-revalidate",
            "--abandon-started-approval",
            "operator_abandoned_before_domain_write",
            "project_version_update_abandon_unavailable",
            "preapproval_scaffold_cancelled",
            "must never be read as absence",
            "project_git_probe_budget_exhausted",
            "inspection_root_resolved_to_parent_project",
            "full deep doctor scan",
            "not known from the v0.4.21 diagnostics",
            "publishing or installing this release does not read or modify a client archive",
            "client-run result and a new-process verification",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat)

    def test_current_docs_use_v0423_status_without_erasing_v0422_history(self) -> None:
        expected = {
            KIT / "docs" / "agent-operator-capabilities.md":
                "Status: v0.4.36 no-dialog grants, letter-168, and writer-session coverage gate",
            KIT / "docs" / "capability-matrix.md":
                "Version: v0.4.36 implementation and release scope",
            KIT / "docs" / "runtime-canonical-entrypoints.md":
                "Status: v0.4.36 no-dialog grants, letter-168, and session-owned writes truth",
            KIT / "docs" / "version-truth-source.md":
                "Status: v0.4.36 no-dialog grants, letter-168, and session-owned writes",
            KIT / "docs" / "python-tool-install.md":
                "Status: v0.4.36 conditional GitHub wheel contract; no-dialog grants; letter-168",
        }
        for path, phrase in expected.items():
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(phrase, document)
                self.assertIn("v0.4.35", document)

    def test_hotfix_surfaces_are_documented(self) -> None:
        contract = (KIT / "docs" / "exact-human-approval-contract.md").read_text(encoding="utf-8")
        self.assertIn("operator_abandoned_before_domain_write", contract)
        control = (KIT / "docs" / "operation-control.md").read_text(encoding="utf-8")
        self.assertIn("inspection_root_resolved_to_parent_project", control)
        truth = (KIT / "docs" / "version-truth-source.md").read_text(encoding="utf-8")
        self.assertIn("project_git_probe_budget_exhausted", truth)
        self.assertIn("45-second", truth)
        for guide in (ROOT / "UPGRADE.md", ROOT / "UPGRADE.ko.md"):
            document = guide.read_text(encoding="utf-8")
            with self.subTest(guide=guide):
                self.assertIn("--abandon-started-approval", document)
                self.assertIn("preapproval_scaffold_cancelled", document)

    def test_coverage_manifest_is_unchanged_by_the_hotfix(self) -> None:
        manifest = json.loads((KIT / "docs" / "writer-session-coverage.json").read_text(encoding="utf-8"))
        statuses = [row["status"] for row in manifest["paths"].values()]
        routed = sum(1 for row in manifest["paths"].values() if row.get("route"))
        # v0.4.22 changes no writer: the v0.4.21 inventory and gate stand.
        self.assertEqual(len(statuses), 107)  # v0.4.42 imap-mailbox-message-fetch
        self.assertEqual(statuses.count("session_integrated") - routed, 6)
        self.assertEqual(routed, 51)  # v0.4.42 imap-mailbox-message-fetch
        self.assertEqual(statuses.count("pending"), 29)  # v0.4.36: five rows integrated through the environment route
        self.assertEqual(statuses.count("legacy_exception"), 21)  # v0.4.41: onboard and init bootstrap exceptions

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_PUBLIC_DOCUMENTS)
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")


if __name__ == "__main__":
    unittest.main()
