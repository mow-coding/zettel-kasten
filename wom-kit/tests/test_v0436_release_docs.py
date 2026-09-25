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
RELEASE = KIT / "docs" / "releases" / "v0.4.36.md"
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
    KIT / "docs" / "ai-start-here.md",
    KIT / "docs" / "backup-evidence-status.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "python-tool-install.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    KIT / "docs" / "recovery-operations-acceptance.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "writer-session-coverage.json",
    KIT / "docs" / "archive-infra-decision-log-2026-09-21-v0436-letter-168.md",
    ROOT / "meeting-minutes" / "2026-09-21-v0436-letter-168.md",
    KIT / "docs" / "ai-response-concept-guide.md",
    KIT / "docs" / "project-version-update.md",
    RELEASE,
)


class V0436ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.43")
        self.assertIn('version = "0.4.43"', (KIT / "pyproject.toml").read_text(encoding="utf-8"))
        for shim in (KIT / "src" / "wom_kit" / "__init__.py", ROOT / "wom_kit" / "__init__.py"):
            self.assertIn('__version__ = "0.4.43"', shim.read_text(encoding="utf-8"))
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.43"', citation)
        self.assertRegex(citation, r'date-released: "2026-09-(2[0-9])"')
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.43", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.42", versioning)
        self.assertIn("Previous public baseline: v0.4.42.", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("v0.4.43", (ROOT / "README.ko.md").read_text(encoding="utf-8"))

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.35.json").read_bytes()
        self.assertEqual(previous.replace(b'"target_tag": "v0.4.35"', b'"target_tag": "v0.4.43"'), current)
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
        self.assertNotIn("release-notes/v0.4.35.md", packaged_paths)
        self.assertTrue((KIT / "docs" / "releases" / "v0.4.35.md").is_file())

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
                self.assertNotIn("bootstrap-v0435-", document)

    def test_release_describes_v0436_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split()).casefold()
        for required in (
            "always_dialog_operations",
            "dialog_only_actions",
            "2026-09-17 decision restored",
            "exact_human_approval_writer_refused",
            "manifest_index_authority",
            "credential_refs_present",
            "object_storage_upload_credential_ref_unresolved",
            "--progress-log",
            "registered_store_refs",
            "operator-feedback-archive",
            "archived_stub",
            "approve_rescans_receipts",
            "required_keys",
            "--no-create-draft-record",
            "61 approval-available, 59 fixed-closed",
            "follow-up backlog (version not committed)",
            "publishing or installing this release does not read or modify a client archive",
            "client-run result and a new-process verification",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat)

    def test_current_docs_use_v0436_status_without_erasing_v0432_history(self) -> None:
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

    def test_release_surfaces_are_documented(self) -> None:
        contract = (KIT / "docs" / "exact-human-approval-contract.md").read_text(encoding="utf-8")
        self.assertIn("Since v0.4.36 (beta letter 168 ⑥; the 2026-09-17 decision restored)", contract)
        self.assertIn("107 approval-available, 8 fixed-closed", " ".join(contract.split()))
        capabilities = (KIT / "docs" / "agent-operator-capabilities.md").read_text(encoding="utf-8")
        self.assertIn("operator-feedback-archive", capabilities)
        self.assertIn("approval_available:                   107", capabilities)
        matrix = (KIT / "docs" / "capability-matrix.md").read_text(encoding="utf-8")
        self.assertIn("| Operator feedback archival (v0.4.36) |", matrix)
        self.assertIn("107 approval-available, 8 fixed-closed", " ".join(matrix.split()))
        register = (KIT / "docs" / "recovery-operations-acceptance.md").read_text(encoding="utf-8")
        for row in ("L168-01", "L168-02", "L168-03", "L168-04", "L168-05"):
            self.assertIn(f"| {row} | v0.4.36 |", register)
        self.assertIn("### 2026-09-21 v0.4.36 letter 168", register)
        decision_log = (KIT / "docs" / "archive-infra-decision-log-2026-09-21-v0436-letter-168.md").read_text(encoding="utf-8")
        self.assertIn("## Correction of a deviation from the 2026-09-17 decision", decision_log)
        self.assertIn("## Root cause of the upload failure", decision_log)
        coverage = json.loads((KIT / "docs" / "writer-session-coverage.json").read_text(encoding="utf-8"))
        for row in ("operator-feedback-compose", "object-storage-restore", "object-storage-offload",
                    "exact-approval-claim-finalize", "object-storage-upload", "operator-feedback-archive"):
            self.assertEqual(coverage["paths"][row]["status"], "session_integrated")
            self.assertEqual(coverage["paths"][row]["route"], "environment")
        for guide_path in (ROOT / "UPGRADE.md", ROOT / "UPGRADE.ko.md"):
            document = guide_path.read_text(encoding="utf-8")
            with self.subTest(guide=guide_path):
                self.assertIn("operator-feedback-archive", document)
                self.assertIn("set-permission-mode", document)

    def test_coverage_manifest_matches_release_claim(self) -> None:
        manifest = json.loads((KIT / "docs" / "writer-session-coverage.json").read_text(encoding="utf-8"))
        statuses = [row["status"] for row in manifest["paths"].values()]
        routed = sum(1 for row in manifest["paths"].values() if row.get("route"))
        # v0.4.23 integrated create-draft (LR-06a); v0.4.24 through v0.4.27, v0.4.31 and v0.4.35 change no writer;
        # v0.4.28 restore, v0.4.29 offload, v0.4.30 claim finalize, v0.4.33 upload and v0.4.35 compose are pending (target v0.4.36).
        self.assertEqual(len(statuses), 107)  # v0.4.42 imap-mailbox-message-fetch
        self.assertEqual(statuses.count("session_integrated") - routed, 6)
        self.assertEqual(routed, 51)  # v0.4.42 imap-mailbox-message-fetch
        self.assertEqual(statuses.count("pending"), 29)  # v0.4.36: five rows integrated through the environment route
        self.assertEqual(statuses.count("legacy_exception"), 21)  # v0.4.41: onboard and init bootstrap exceptions
        self.assertEqual(manifest["paths"]["create-draft"]["status"], "session_integrated")

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_PUBLIC_DOCUMENTS)
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")
        self.assertNotIn("mylife" + "isbusy", combined.casefold())


if __name__ == "__main__":
    unittest.main()
