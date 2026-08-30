from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from wom_kit import __version__, archive_cli


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.8.md"
CURRENT_RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.15.md"
CURRENT_PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.15.md"
HISTORICAL_V0411_RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.11.md"
HISTORICAL_V0407_RELEASE = KIT / "docs" / "releases" / "v0.4.7.md"
DECISION_PATH = (
    KIT / "docs" / "archive-infra-decision-log-2026-08-26-v048-integrity-recovery.md"
)
WHEEL_URL = (
    "https://github.com/mow-coding/zettel-kasten/releases/download/"
    "v0.4.8/wom_kit-0.4.8-py3-none-any.whl"
)


class V0408AndCurrentReleaseDocsTests(unittest.TestCase):
    def test_current_install_bootstrap_uses_one_exact_release_version(self) -> None:
        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        install_ko = (KIT / "docs" / "python-tool-install.ko.md").read_text(
            encoding="utf-8"
        )
        combined = install + "\n" + install_ko
        for required in (
            '$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\\bootstrap-v0415"',
            "py -3.12 -m venv $womBootstrapRoot",
            r'& "$womBootstrapRoot\Scripts\python.exe"',
            r'& "$womBootstrapRoot\Scripts\archive.exe" --version',
            "wom_kit-0.4.15-py3-none-any.whl",
        ):
            with self.subTest(required=required):
                self.assertIn(required, combined)
        self.assertIn("exactly `archive 0.4.15`", install)
        self.assertIn("정확히 `archive 0.4.15`", install_ko)
        self.assertNotIn(".wom-bootstrap-v043", combined)
        self.assertNotIn("exactly `archive 0.4.3`", install)
        self.assertNotIn("정확히 `archive 0.4.3`", install_ko)
        self.assertIn(
            "outside the inspected project or archive", " ".join(install.split())
        )
        self.assertIn("프로젝트·보관함 밖", " ".join(install_ko.split()))

    def test_letter138_docs_never_delegate_machine_verification_to_the_person(self) -> None:
        recovery = (
            KIT / "docs" / "notion-source-properties-recovery.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(recovery.split())
        for required in (
            "WOM, not the person",
            "not an approval prerequisite",
            "machine gates, not a checklist delegated to the person",
            "does not count categories, compare hashes, or determine canonical completeness",
            "asks only `복구 실행` or `취소`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)
        for forbidden in (
            "Review that exact private file",
            "Do not approve unless the digest matches",
            "after a human reviews those exact unresolved digests",
            "apply the reviewed plan",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, normalized)

    def test_same_account_project_runtime_scope_is_explicit(self) -> None:
        surfaces = (
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "version-truth-source.md",
            RELEASE_PATH,
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in surfaces
        )
        for token in (
            "archive --version",
            "archive version <project-or-archive-root> --format json",
            "PATH",
            ".zettel-kasten/runtimes/vX.Y.Z/",
            ".zettel-kasten/bin/archive.cmd",
            "project_runtime_mismatch",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_version_sources_and_wheel_contract_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.4.15")
        self.assertIn(
            'version = "0.4.15"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        for version_file in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(version_file=version_file):
                self.assertIn(
                    '__version__ = "0.4.15"',
                    version_file.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.15"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "0.4.15"', citation)
        self.assertIn('date-released: "2026-08-30"', citation)
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.15", versioning)

    def test_current_release_and_resources_are_packaged_exactly(self) -> None:
        self.assertEqual(
            CURRENT_RELEASE_PATH.read_bytes(),
            CURRENT_PACKAGED_RELEASE_PATH.read_bytes(),
        )
        release_names = sorted(
            path.name
            for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.15.md"])

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.15")
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        packaged_paths = [row["packaged"] for row in manifest["files"]]
        self.assertEqual(len(packaged_paths), len(set(packaged_paths)))
        self.assertIn("release-notes/v0.4.15.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.14.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.13.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.12.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.11.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.10.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.9.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.8.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.7.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.2.md", packaged_paths)
        for row in manifest["files"]:
            with self.subTest(packaged=row["packaged"]):
                source = KIT / row["source"]
                packaged = RESOURCE_ROOT / row["packaged"]
                source_bytes = source.read_bytes()
                self.assertEqual(source_bytes, packaged.read_bytes())
                self.assertEqual(row["bytes"], len(source_bytes))
                self.assertEqual(
                    row["sha256"], hashlib.sha256(source_bytes).hexdigest()
                )

    def test_release_defines_the_outcome_and_nonclaim_boundaries(self) -> None:
        documents = (
            RELEASE_PATH,
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            KIT / "docs" / "exact-operation-manifest-v1.md",
            KIT / "docs" / "project-version-update.md",
            DECISION_PATH,
        )
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in documents
        )
        for token in (
            WHEEL_URL,
            "ExactOperationManifest v1",
            "Interrupted work explains itself",
            "source-index field",
            "marker token",
            "fixed safety bound",
            "occurrence anchors are diagnostic",
            "does not yet support a verified occurrence-recovery receipt",
            "existing canonical intake record",
            "does not create a bucket",
            "strict duplicate pairs",
            "durably closes its parent apply",
            "before or after receipt publication",
            "revalidates the original approval",
            "rerun_duplicate_revert_resume_with_same_reviewer",
            "project-scoped recovery operation",
            "independent verification",
            "versioned URL alone is not proof",
        ):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), combined.casefold())

    def test_v0411_release_preserves_historical_scope_and_privacy_boundaries(self) -> None:
        release = HISTORICAL_V0411_RELEASE_PATH.read_text(encoding="utf-8")
        normalized = " ".join(release.split())
        for required in (
            "live evidence",
            "Deep Doctor remains the safe default",
            "one descriptor-bound stable SHA-256 read",
            "exact chronology",
            "remains an explicit ERROR",
            "local-only target preview",
            "WOM-safe Markdown projection",
            "validation digests as approval authority",
            "v0.4.12 work",
            "one deep hash per unique objet",
            "wom_kit-0.4.11-py3-none-any.whl",
            "does not modify a client archive",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), normalized.casefold())
        self.assertNotRegex(normalized, r"(?i)letter\s*\d+")
        self.assertNotRegex(normalized, r"\b[0-9a-f]{64}\b")
        self.assertNotIn("C:\\Users\\", release)

    def test_current_docs_keep_interruption_and_occurrence_truth_exact(self) -> None:
        matrix = (KIT / "docs" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        normalized_matrix = " ".join(matrix.split())
        for required in (
            "interrupted_started_journal",
            "interrupted_receipt_published",
            "validates source structure, snapshot/current/lock/optional-receipt state, and plan basis",
            "before any revert write, the approved writer HMAC- and claim-revalidates",
            "tamper or mismatch fails with zero writes",
            "preserve the source journal",
            "authenticated terminal-compensation evidence that blocks forward replay",
            "--revert --resume --reviewed-by <same-reviewer>",
            "public planner uses the production terminal auditor",
            "without a second native dialog",
            "neither branch performs another manifest write",
            "duplicate_object_revert_state_unknown",
            "exact_human_approval_state_unknown",
            "next_safe_actions: [rerun_duplicate_revert_resume_with_same_reviewer]",
            "an explicit failed resume does not recurse into that advice",
            "A locator sidecar or occurrence anchor alone is not proof of resolution",
            "a successful revert durably supersedes an unfinished parent apply",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), normalized_matrix.casefold())

        approval_contract = (
            KIT / "docs" / "exact-human-approval-contract.md"
        ).read_text(encoding="utf-8")
        normalized_approval_contract = " ".join(approval_contract.split())
        for required in (
            "authenticated `finalization_pending` revert",
            "opens no second native approval dialog",
            "An already `succeeded` claim skips the writer",
            "perform no second manifest write",
            "without creating a key or claim",
            "`next_safe_actions` value `rerun_duplicate_revert_resume_with_same_reviewer`",
            "echoes no approval id, private value, or path",
            "does not recursively recommend another resume",
        ):
            with self.subTest(required=required):
                self.assertIn(
                    required.casefold(), normalized_approval_contract.casefold()
                )

    def test_duplicate_revert_resume_help_explains_the_narrow_reuse_boundary(
        self,
    ) -> None:
        parser = archive_cli.build_parser()
        command_action = next(
            action
            for action in parser._actions
            if getattr(action, "choices", None) is not None
            and "duplicate-object-reconcile" in action.choices
        )
        command_parser = command_action.choices["duplicate-object-reconcile"]
        option_help = {
            option: action.help
            for action in command_parser._actions
            for option in action.option_strings
        }
        self.assertIn("--resume", option_help["--revert"])
        self.assertIn(
            "without another native approval dialog or another manifest write",
            option_help["--resume"],
        )
        self.assertIn(
            "Requires --revert and the same --reviewed-by value",
            option_help["--resume"],
        )
        self.assertIn("approve or --resume", option_help["--reviewed-by"])

    def test_current_schemas_are_valid_and_exactly_packaged(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        for source in sorted((KIT / "schemas").glob("*.json")):
            with self.subTest(schema=source.name):
                schema = json.loads(source.read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(schema)
                packaged = RESOURCE_ROOT / "schemas" / source.name
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
                self.assertIn(f"schemas/{source.name}", packaged_paths)

    def test_release_note_links_are_github_release_safe(self) -> None:
        for release_path in (RELEASE_PATH, CURRENT_RELEASE_PATH):
            release = release_path.read_text(encoding="utf-8")
            with self.subTest(release=release_path.name):
                self.assertNotIn("](../", release)
                self.assertNotIn("](../../../", release)
                self.assertNotIn("C:\\Users\\", release)

    def test_v0407_release_history_is_byte_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(HISTORICAL_V0407_RELEASE.read_bytes()).hexdigest(),
            "825e2f9fbca20b74b6fe4094f13665eccfeb25e417438056fe4e36ab18264174",
        )

    def test_release_keeps_private_acceptance_details_out_of_public_note(self) -> None:
        release = " ".join(RELEASE_PATH.read_text(encoding="utf-8").split())
        decision = " ".join(DECISION_PATH.read_text(encoding="utf-8").split())
        self.assertNotIn("current client evidence snapshot", release.casefold())
        for public_text in (release, decision):
            self.assertNotRegex(public_text, r"(?i)letter\s*\d+")
            self.assertNotRegex(public_text, r"\b[0-9a-f]{64}\b")
            self.assertNotIn("C:\\Users\\", public_text)
        self.assertIn("public artifacts contain no private title", release.casefold())
        self.assertIn("writes no client archive", release)


if __name__ == "__main__":
    unittest.main()
