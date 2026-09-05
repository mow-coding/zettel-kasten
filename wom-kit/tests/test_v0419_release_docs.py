from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest

import yaml

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.19.md"
PACKAGED_RELEASE = RESOURCE_ROOT / "release-notes" / "v0.4.19.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.19.json"
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
CURRENT_PUBLIC_DOCUMENTS = (
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
PROJECT_RECORDS = (
    ROOT / "meeting-minutes" / "2026-09-04-v0419-v0424-recovery-operations.md",
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-09-04-v0419-v0424-release-train.md",
)


class V0419ReleaseDocsTests(unittest.TestCase):
    def test_required_ci_exercises_both_scale_profiles_and_installed_wheel(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        )
        jobs = workflow["jobs"]
        doctor = jobs["doctor_scale"]
        profiles = doctor["strategy"]["matrix"]["include"]
        self.assertEqual(
            {row["profile"]: row["payload_args"] for row in profiles},
            {"count": "", "mixed-payload": "--mixed-payload"},
        )
        self.assertGreaterEqual(doctor["timeout-minutes"], 20)
        installed = jobs["installed_wheel"]
        self.assertEqual(installed["runs-on"], "windows-latest")
        self.assertTrue(any(
            "check_wheel_install.py --format json" in step.get("run", "")
            for step in installed["steps"]
        ))
        for gate in ("doctor_scale", "installed_wheel"):
            self.assertIn(gate, jobs["required"]["needs"])
        required = jobs["required"]["steps"][0]
        self.assertIn("needs.installed_wheel.result", required["env"]["INSTALLED_WHEEL_RESULT"])
        self.assertIn('test "$INSTALLED_WHEEL_RESULT" = "success"', required["run"])

    def test_current_version_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.19")
        self.assertIn(
            'version = "0.4.19"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
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
        previous = (KIT / "project-runtime-supply-lock-v0.4.18.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.18"',
            b'"target_tag": "v0.4.19"',
        )
        self.assertEqual(current, expected)
        self.assertNotIn(b"\r", current)
        lock_sha256 = hashlib.sha256(current).hexdigest()
        policy = json.loads(
            (KIT / "project-runtime-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.19.json",
        )
        self.assertEqual(policy["supply_lock_sha256"], f"sha256:{lock_sha256}")
        runtime_source = (KIT / "src" / "wom_kit" / "project_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(policy["supply_lock"], runtime_source)
        self.assertIn(policy["supply_lock_sha256"], runtime_source)

    def test_current_release_is_the_only_packaged_note(self) -> None:
        self.assertEqual(RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertEqual(
            sorted(path.name for path in PACKAGED_RELEASE.parent.glob("v*.md")),
            ["v0.4.19.md"],
        )
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.19")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.19.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.18.md", packaged_paths)

    def test_current_install_guides_use_exact_v0419_bootstrap(self) -> None:
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
                self.assertRegex(
                    document,
                    re.escape("& $womBootstrapPython") + r"\s+-m\s+pip\s+install\b",
                )
                self.assertIn("wom_kit-0.4.19-py3-none-any.whl", document)
                self.assertIn(
                    r'& "$womBootstrapRoot\Scripts\archive.exe" --version',
                    document,
                )

    def test_release_describes_v0419_contract(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split()).casefold()
        for required in (
            "passed",
            "failed",
            "not_reached",
            "unavailable",
            "field-level runtime-preparation revalidation",
            "expected transaction effects",
            "same-version target remains a no-op",
            "before downloading or building any candidate",
            "directory-size-only change",
            "damaged same-version runtime remains an atomic repair",
            "CapabilityAvailability v0.1",
            "writer_unavailable",
            "before a handler",
            "CREATE_NO_WINDOW",
            "credential-vault unlock route",
            "Native exact-human approval dialogs",
            "180-second per-run limit",
            "mixed-payload fixture",
            "not advertised as cold-cache client measurements",
            "Publishing or installing this release does not read or modify a client archive",
            "client-run result and a new-process verification",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat)

    def test_current_docs_use_v0419_status_without_erasing_v0418_history(self) -> None:
        expected = {
            KIT / "docs" / "agent-operator-capabilities.md":
                "Status: v0.4.19 shared capability availability and four-state runtime truth",
            KIT / "docs" / "capability-matrix.md":
                "Version: v0.4.19 implementation and release scope",
            KIT / "docs" / "project-version-update.md":
                "Status: v0.4.19 four-state preflight and field-level approved-runtime revalidation",
            KIT / "docs" / "runtime-canonical-entrypoints.md":
                "Status: v0.4.19 runtime, updater, capability, and Windows child-process truth",
            KIT / "docs" / "version-truth-source.md":
                "Status: v0.4.19 four-state runtime, updater revalidation, and exact-pip bootstrap",
        }
        for path, phrase in expected.items():
            document = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(phrase, document)
                self.assertIn("v0.4.18", document)

    def test_project_records_capture_scope_and_client_boundary(self) -> None:
        for path in PROJECT_RECORDS:
            flat = " ".join(path.read_text(encoding="utf-8").split()).casefold()
            with self.subTest(path=path):
                for required in (
                    "v0.4.19",
                    "capability",
                    "runtime",
                    "client",
                    "release",
                    "evidence",
                ):
                    self.assertIn(required.casefold(), flat)

    def test_current_docs_are_private_safe(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in CURRENT_PUBLIC_DOCUMENTS
        )
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        private_client_marker = "ba" + "soon"
        self.assertNotRegex(combined, rf"(?i){private_client_marker}")


if __name__ == "__main__":
    unittest.main()
