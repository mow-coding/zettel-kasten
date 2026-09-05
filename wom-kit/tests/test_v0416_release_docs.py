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
RELEASE = KIT / "docs" / "releases" / "v0.4.16.md"
CURRENT_RELEASE = KIT / "docs" / "releases" / "v0.4.19.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.19.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.16.json"
LOCK_SHA256 = "f924a3f714d5913dd2afe870d07e5619172b0e1fcb92f25b18f70a9cd4ad04d8"
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
    CURRENT_RELEASE,
    PACKAGED_RELEASE,
)
PUBLIC_CURRENT_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    ROOT / "CHANGELOG.md",
    KIT / "README.md",
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "operation-control.md",
    KIT / "docs" / "project-version-update.md",
    KIT / "docs" / "public-documentation-map.md",
    KIT / "docs" / "public-documentation-map.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    CURRENT_RELEASE,
)
TERMINAL_TRUTH_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    ROOT / "CHANGELOG.md",
    KIT / "README.md",
    KIT / "docs" / "agent-operator-capabilities.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "operation-control.md",
    KIT / "docs" / "project-version-update.md",
    KIT / "docs" / "public-documentation-map.md",
    KIT / "docs" / "public-documentation-map.ko.md",
    KIT / "docs" / "python-tool-install.md",
    KIT / "docs" / "python-tool-install.ko.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "version-truth-source.md",
    RELEASE,
    CURRENT_RELEASE,
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
    ROOT / "meeting-minutes" / "2026-08-31-v0416-runtime-result-recovery.md",
    ROOT / "archive-infra-decision-log-2026-08-31-v0416-terminal-result-truth.md",
)


class V0416ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.19")
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.19"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'version = "0.4.19"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.19"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.19"', citation)
        self.assertIn('date-released: "2026-09-05"', citation)
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.19", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.18", versioning)

    def test_supply_lock_and_policy_are_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.15.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.15"',
            b'"target_tag": "v0.4.16"',
        )
        self.assertEqual(current, expected)
        self.assertEqual(len(current), 1178)
        self.assertNotIn(b"\r", current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), LOCK_SHA256)

    def test_current_release_is_the_only_packaged_note(self) -> None:
        self.assertEqual(CURRENT_RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        release_names = sorted(
            path.name for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.19.md"])
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.19")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.19.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.17.md", packaged_paths)

    def test_current_install_guides_use_new_exact_pip_bootstrap(self) -> None:
        for path in BOOTSTRAP_DOCUMENTS:
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    '$womBootstrapNonce = [guid]::NewGuid().ToString("N")',
                    document,
                )
                self.assertIn(
                    '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA '
                    '"WOM\\bootstrap-v0419-$womBootstrapNonce"',
                    document,
                )
                self.assertIn("py -3.12 -m venv $womBootstrapRoot", document)
                self.assertRegex(
                    document,
                    re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b",
                )
                self.assertIn("wom_kit-0.4.19-py3-none-any.whl", document)
                self.assertIn(
                    r'& "$womBootstrapRoot\Scripts\archive.exe" --version',
                    document,
                )

    def test_release_describes_all_v0416_contracts(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for required in (
            "authenticated terminal result handoff",
            "durable_result_delivery_acknowledged",
            "immutable terminal journal record",
            "`active` -> `display-pending` -> hash-named `consumed`",
            "at-least-once display",
            "consumed capsule is durable history, not a replay candidate",
            "does not prove that a person or model",
            "complete cleanup tombstone is recoverable only after",
            "no_resumable_project_update",
            "past_update_success_attributed: false",
            "current_project_state_independently_verified: false",
            "terminal_cleanup_outcome_unknown",
            "domain_writer_reentry_allowed",
            "python -m wom_kit.archive_cli",
            "core_module_bindings",
            "absolute paths and no hashes",
            "Same-version project runtime repair",
            "runtime_repair_required: true",
            "project-version-update --resume",
            "transaction cleanup removes the exact private recovery preimage",
            "A healthy same-version runtime still returns",
            "`no_change`",
            "Create-only feedback during runtime mismatch",
            "project_runtime_alignment_required",
            "Product language and strict secret shapes",
            "credential_secret_present",
            "input_privacy_check.scope: pre_write_caller_input_safety",
            "caller_supplied_input_read_for_safety: true",
            "body_read_for_safety: true",
            "first_read_check.body_read_for_check",
            "Approved project-update mutation, same-version repair, and mutation-bearing resume remain Windows-only",
            "POSIX supports preview and read-only inspection",
            "those mutation paths fail closed without writing",
            "Publishing or installing v0.4.16 does not inspect or modify a client archive",
            "The client chooses whether and when to run a separately reviewed project update",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

    def test_terminal_truth_is_consistent_and_rejects_superseded_design(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in TERMINAL_TRUTH_DOCUMENTS
        )
        for required in (
            "immutable terminal journal",
            "display-pending",
            "consumed",
            "at-least-once",
            "no_resumable_project_update",
            "terminal_cleanup_outcome_unknown",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), combined.casefold())
        for superseded in (
            "delivery_committed",
            "display_committed",
            "final delivery-journal append",
            "final delivery journal append",
            "resume with a fresh output",
            "fresh project-scoped output",
            "exact tombstone/proof state",
        ):
            with self.subTest(superseded=superseded):
                self.assertNotIn(superseded.casefold(), combined.casefold())

    def test_runtime_guidance_source_and_package_copies_match(self) -> None:
        for source, packaged in MIRRORED_RUNTIME_DOCUMENTS:
            with self.subTest(source=source, packaged=packaged):
                self.assertEqual(source.read_bytes(), packaged.read_bytes())

    def test_required_project_records_capture_final_terminal_truth(self) -> None:
        for path in PROJECT_RECORDS:
            document = path.read_text(encoding="utf-8")
            flat = " ".join(document.split())
            with self.subTest(path=path):
                self.assertIn("active", flat)
                self.assertIn("display-pending", flat)
                self.assertIn("consumed", flat)
                self.assertIn("immutable terminal journal", flat)
                self.assertIn("no_resumable_project_update", flat)
                self.assertIn("terminal_cleanup_outcome_unknown", flat)

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in PUBLIC_CURRENT_DOCUMENTS
        )
        self.assertNotRegex(combined, r"(?i)letter\s*151")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")


if __name__ == "__main__":
    unittest.main()
