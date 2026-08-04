from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import archive_cli, archive_services
from wom_kit import source_reference_coverage_audit as audit


KIT_ROOT = Path(__file__).resolve().parents[1]
FAKE_ARCHIVE = KIT_ROOT / "examples" / "fake-life-archive"
RESULT_SCHEMA_PATH = (
    KIT_ROOT
    / "schemas"
    / "source-reference-coverage-audit-result-v0.1.schema.json"
)
ARCHIVE_ID = "archive:personal:fake-life"
KNOWN_DIGEST = (
    "acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
)
PRIVATE_SOURCE_CANARY = "https://private.example/source/DO-NOT-ECHO"
PRIVATE_PATH_CANARY = "C:\\private\\archive\\DO-NOT-ECHO"


class SourceReferenceCoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result_schema = json.loads(
            RESULT_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(cls.result_schema)
        cls.validator = Draft202012Validator(cls.result_schema)

    def copy_archive(self, parent: Path) -> Path:
        archive_root = parent / "archive"
        shutil.copytree(FAKE_ARCHIVE, archive_root)
        return archive_root

    @staticmethod
    def tree_digest(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def write_canonical(
        self,
        archive_root: Path,
        *,
        zettel_id: str,
        filename: str | None = None,
        source_refs: list[object] | None = None,
        notion_omitted_count: int | None = None,
        body_marker_count: int = 0,
        private_body: str = "PRIVATE BODY MUST NOT ECHO",
    ) -> Path:
        facets: dict[str, object] = {"domain": "test"}
        provenance_source = "test"
        if notion_omitted_count is not None:
            facets.update(
                {
                    "source_system": "notion_db3",
                    "source_locator_omitted_count": notion_omitted_count,
                }
            )
            provenance_source = "notion_db3"
        frontmatter: dict[str, object] = {
            "id": zettel_id,
            "title": f"PRIVATE TITLE {zettel_id}",
            "created_at": "2026-08-04T00:00:00+09:00",
            "updated_at": "2026-08-04T00:00:00+09:00",
            "archive_id": ARCHIVE_ID,
            "status": "canonical",
            "kind": "record_note",
            "facets": facets,
            "assets": [],
            "edges": [],
            "provenance": {
                "created_by": "ai_runtime:test",
                "created_in": ARCHIVE_ID,
                "source": provenance_source,
                "creation_mode": "imported",
                "derived_from": [],
            },
            "visibility": {
                "scope": "private",
                "allowed_archives": [],
                "source_visibility": "private",
            },
        }
        if source_refs is not None:
            frontmatter["source_refs"] = source_refs
        body = private_body
        if body_marker_count:
            body += "\n" + "\n".join(
                archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
                for _ in range(body_marker_count)
            )
        text = (
            "---\n"
            + archive_cli.dump_yaml(frontmatter)
            + "---\n\n"
            + body
            + "\n"
        )
        path = archive_root / "zettels" / (filename or f"{zettel_id}.md")
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def run_cli(
        self,
        archive_root: Path,
        *extra: str,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [
            "source-reference-coverage-audit",
            str(archive_root),
            "--dry-run",
            "--format",
            "json",
            *extra,
        ]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_schema_valid(self, value: dict[str, object]) -> None:
        errors = sorted(
            self.validator.iter_errors(value),
            key=lambda item: list(item.absolute_path),
        )
        self.assertEqual(
            errors,
            [],
            "\n".join(
                f"{list(error.absolute_path)!r}: {error.message}"
                for error in errors
            ),
        )

    def test_help_and_invalid_request_are_content_free(self) -> None:
        help_stdout = io.StringIO()
        with redirect_stdout(help_stdout):
            help_code = archive_cli.main(
                ["source-reference-coverage-audit", "--help"]
            )
        self.assertEqual(help_code, 0)
        self.assertIn("python -B -m wom_kit.archive_cli", help_stdout.getvalue())

        stdout = io.StringIO()
        with mock.patch.object(audit, "_execute") as execute:
            with redirect_stdout(stdout):
                code = audit.command_source_reference_coverage_audit_argv(
                    [PRIVATE_PATH_CANARY, "--format", "json"]
                )
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["code"], "request_invalid")
        self.assertNotIn(PRIVATE_PATH_CANARY, stdout.getvalue())
        execute.assert_not_called()
        self.assert_schema_valid(result)

    def test_missing_explicit_B_blocks_before_archive_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pycache_prefix = Path(tmp) / "external-pycache"
            environment = dict(os.environ)
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment["PYTHONPYCACHEPREFIX"] = str(pycache_prefix)
            environment["PYTHONPATH"] = str(KIT_ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wom_kit.archive_cli",
                    "source-reference-coverage-audit",
                    PRIVATE_PATH_CANARY,
                    "--dry-run",
                    "--format",
                    "json",
                ],
                cwd=KIT_ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(
            result["issues"][0]["code"],
            "interpreter_no_bytecode_mode_required",
        )
        self.assertFalse(
            result["execution_guard"]["interpreter_no_bytecode_mode"]
        )
        self.assertNotIn(PRIVATE_PATH_CANARY, completed.stdout)
        self.assert_schema_valid(result)

    def test_empty_observed_population_is_complete_but_not_archive_wide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            before = self.tree_digest(archive_root)
            code, output, error = self.run_cli(archive_root)
            after = self.tree_digest(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        self.assertEqual(before, after)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "audit_complete")
        self.assertEqual(
            result["source_reference_coverage"]["state"],
            "not_applicable",
        )
        self.assertEqual(
            result["recorded_storage_evidence"]["state"],
            "not_applicable",
        )
        self.assertFalse(
            result["source_reference_coverage"][
                "archive_wide_coverage_claim_supported"
            ]
        )
        self.assertEqual(
            result["index_observation"],
            {"state": "not_used", "index_rows_consumed": 0},
        )
        self.assertFalse(result["privacy_guards"]["files_written"])
        self.assert_schema_valid(result)

    def test_population_is_limited_to_canonical_files_under_zettels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            path = self.write_canonical(
                archive_root,
                zettel_id="zet_test_canonical_but_in_inbox",
                source_refs=[
                    {"type": "url", "value": PRIVATE_SOURCE_CANARY}
                ],
            )
            inbox_path = archive_root / "inbox" / path.name
            path.replace(inbox_path)
            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        self.assertEqual(
            result["source_reference_coverage"]["population_count"],
            0,
        )
        self.assertEqual(
            result["source_reference_coverage"]["state"],
            "not_applicable",
        )
        self.assertNotIn(PRIVATE_SOURCE_CANARY, output)
        self.assert_schema_valid(result)

    def test_population_file_change_during_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            target = self.write_canonical(
                archive_root,
                zettel_id="zet_test_snapshot_change",
                source_refs=[
                    {"type": "url", "value": PRIVATE_SOURCE_CANARY}
                ],
            )
            real_snapshot = (
                archive_services.validated_approval_zettel_snapshot
            )
            changed = False

            def mutate_after_snapshot(path: Path, **kwargs: object):
                nonlocal changed
                result = real_snapshot(path, **kwargs)
                if path.resolve() == target.resolve() and not changed:
                    changed = True
                    with path.open("a", encoding="utf-8", newline="\n") as handle:
                        handle.write("changed after stable read\n")
                return result

            with mock.patch.object(
                archive_services,
                "validated_approval_zettel_snapshot",
                side_effect=mutate_after_snapshot,
            ):
                code, output, _error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "audit_incomplete")
        self.assertIn(
            "population_authority_changed",
            {issue["code"] for issue in result["issues"]},
        )
        self.assertFalse(
            result["authority_summary"]["before_after_identity_equal"]
        )
        self.assertNotIn(PRIVATE_SOURCE_CANARY, output)
        self.assert_schema_valid(result)

    def test_recovered_reference_and_storage_absence_are_separate(self) -> None:
        missing_digest = "c" * 64
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_recovered_no_storage",
                source_refs=[
                    {
                        "type": "object_id",
                        "value": f"sha256:{missing_digest}",
                    }
                ],
            )
            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        self.assertEqual(
            result["source_reference_coverage"]["state"],
            "complete",
        )
        self.assertEqual(
            result["recorded_storage_evidence"]["state"],
            "no_evidence",
        )
        self.assertEqual(result["details_returned"], 1)
        self.assertTrue(result["details"][0]["durable_reference_present"])
        self.assertTrue(result["details"][0]["exact_object_binding_present"])
        self.assertNotIn(missing_digest, output)
        self.assert_schema_valid(result)

    def test_manifest_identity_is_not_promoted_to_recorded_time_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_manifest_identity",
                source_refs=[
                    {
                        "type": "object_id",
                        "value": f"sha256:{KNOWN_DIGEST}",
                    }
                ],
            )
            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        storage = result["recorded_storage_evidence"]
        self.assertEqual(storage["state"], "manifest_identity_only")
        self.assertEqual(storage["manifest_identity_only_count"], 1)
        self.assertEqual(storage["recorded_time_evidence_count"], 0)
        self.assertFalse(storage["current_bytes_checked"])
        self.assertNotIn(KNOWN_DIGEST, output)
        self.assert_schema_valid(result)

    def test_linked_provider_receipt_is_recorded_time_evidence_only(
        self,
    ) -> None:
        object_id = f"sha256:{KNOWN_DIGEST}"
        uploaded_at = "2026-08-04T00:01:02Z"
        provider_kind = "cloudflare-r2"
        store_ref = "test-r2-store"
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_recorded_receipt",
                source_refs=[{"type": "object_id", "value": object_id}],
            )
            case_id = archive_services.object_storage_execution_case_id(
                ARCHIVE_ID,
                KNOWN_DIGEST,
                uploaded_at,
            )
            receipt = (
                archive_services._object_storage_build_execution_receipt(
                    archive_id=ARCHIVE_ID,
                    object_id=object_id,
                    provider_kind=provider_kind,
                    store_ref=store_ref,
                    key_hint=(
                        archive_services
                        .object_storage_content_addressed_key_hint(
                            KNOWN_DIGEST
                        )
                    ),
                    result={
                        "result_status": "uploaded",
                        "bytes": 151,
                        "part_count": 1,
                        "attempts": 1,
                        "backoff_ms_total": 0,
                    },
                    reviewed_by="person:test",
                    uploaded_at=uploaded_at,
                )
            )
            receipt_ref = (
                archive_services.object_storage_write_execution_receipt(
                    archive_root,
                    case_id,
                    receipt,
                )
            )
            location = archive_services.object_storage_wom_uploaded_location(
                digest=KNOWN_DIGEST,
                provider_kind=provider_kind,
                store_ref=store_ref,
                execution_receipt_ref=receipt_ref,
                uploaded_at=uploaded_at,
                remote_size=151,
            )
            manifest_path = (
                archive_root / "objects" / "manifests" / "files.jsonl"
            )
            records = [
                json.loads(line)
                for line in manifest_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            record = next(
                item for item in records if item["object_id"] == object_id
            )
            record["locations"].append(location)
            manifest_path.write_text(
                "".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                    for item in records
                ),
                encoding="utf-8",
                newline="\n",
            )

            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        storage = result["recorded_storage_evidence"]
        self.assertEqual(storage["state"], "recorded_time_full")
        self.assertEqual(storage["recorded_time_evidence_count"], 1)
        self.assertFalse(storage["live_remote_availability_claim_supported"])
        self.assertFalse(storage["live_storage_integrity_claim_supported"])
        self.assertNotIn(receipt_ref, output)
        self.assertNotIn(KNOWN_DIGEST, output)
        self.assert_schema_valid(result)

    def test_notion_omission_marker_is_an_explicit_unrecovered_occurrence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_notion_test_omission",
                notion_omitted_count=1,
                body_marker_count=1,
            )
            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        coverage = result["source_reference_coverage"]
        self.assertEqual(coverage["state"], "none")
        self.assertEqual(coverage["unrecovered_count"], 1)
        self.assertEqual(
            result["details"][0]["authority_family"],
            "canonical_notion_omission_markers",
        )
        self.assertFalse(result["details"][0]["durable_reference_present"])
        self.assertNotIn("PRIVATE BODY", output)
        self.assert_schema_valid(result)

    def test_duplicate_identity_is_detected_even_without_occurrences(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_duplicate_zero",
                filename="duplicate-a.md",
            )
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_duplicate_zero",
                filename="duplicate-b.md",
            )
            code, output, _error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "audit_incomplete")
        self.assertFalse(
            result["authority_summary"]["population_traversal_complete"]
        )
        self.assertIn(
            "population_identity_conflict",
            {issue["code"] for issue in result["issues"]},
        )
        self.assertEqual(result["details"], [])
        self.assert_schema_valid(result)

    def test_invalid_source_ref_and_marker_count_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_empty_source_ref",
                source_refs=[{"type": "", "value": ""}],
            )
            self.write_canonical(
                archive_root,
                zettel_id="zet_notion_test_count_mismatch",
                notion_omitted_count=2,
                body_marker_count=1,
            )
            code, output, _error = self.run_cli(archive_root)
        result = json.loads(output)
        coverage = result["source_reference_coverage"]
        self.assertEqual(code, 1)
        self.assertEqual(coverage["state"], "indeterminate")
        self.assertEqual(coverage["blocked_or_unknown_count"], 2)
        self.assertIn(
            "population_authority_invalid",
            {issue["code"] for issue in result["issues"]},
        )
        self.assert_schema_valid(result)

    def test_manifest_duplicate_is_contradictory_not_live_integrity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_duplicate_manifest",
                source_refs=[
                    {
                        "type": "object_id",
                        "value": f"sha256:{KNOWN_DIGEST}",
                    }
                ],
            )
            manifest_path = (
                archive_root / "objects" / "manifests" / "files.jsonl"
            )
            lines = manifest_path.read_text(encoding="utf-8").splitlines()
            manifest_path.write_text(
                "\n".join([lines[0], lines[0], *lines[1:]]) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            code, output, error = self.run_cli(archive_root)
        result = json.loads(output)
        storage = result["recorded_storage_evidence"]
        self.assertEqual(code, 0, error)
        self.assertEqual(storage["state"], "contradictory")
        self.assertEqual(storage["contradictory_count"], 1)
        self.assertFalse(storage["live_storage_integrity_claim_supported"])
        self.assertIn(
            "storage_evidence_contradictory",
            {issue["code"] for issue in result["issues"]},
        )
        self.assert_schema_valid(result)

    def test_unreadable_manifest_makes_storage_indeterminate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_invalid_manifest",
                source_refs=[
                    {
                        "type": "object_id",
                        "value": f"sha256:{KNOWN_DIGEST}",
                    }
                ],
            )
            manifest_path = (
                archive_root / "objects" / "manifests" / "files.jsonl"
            )
            manifest_path.write_bytes(b'{"object_id":"unterminated"\n')
            code, output, _error = self.run_cli(archive_root)
        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(
            result["recorded_storage_evidence"]["state"],
            "indeterminate",
        )
        self.assertFalse(
            result["authority_summary"]["storage_traversal_complete"]
        )
        self.assert_schema_valid(result)

    def test_unsafe_zettels_directory_boundary_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            archive_root = self.copy_archive(temp_root)
            outside = temp_root / "outside-zettels"
            (archive_root / "zettels").replace(outside)
            link = archive_root / "zettels"
            if os.name == "nt":
                completed = subprocess.run(
                    [
                        "cmd.exe",
                        "/d",
                        "/c",
                        "mklink",
                        "/J",
                        str(link),
                        str(outside),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    completed.stderr,
                )
            else:
                link.symlink_to(outside, target_is_directory=True)
            try:
                code, output, _error = self.run_cli(archive_root)
            finally:
                if os.name == "nt":
                    os.rmdir(link)
                else:
                    link.unlink()
        result = json.loads(output)
        self.assertEqual(code, 1)
        self.assertIn(
            "population_authority_unreadable",
            {issue["code"] for issue in result["issues"]},
        )
        self.assertFalse(
            result["authority_summary"]["before_after_identity_equal"]
        )
        self.assertNotIn(str(outside), output)
        self.assert_schema_valid(result)

    def test_detail_truncation_preserves_exact_aggregates(self) -> None:
        refs = [
            {
                "type": "url",
                "value": f"https://private.example/source/{ordinal}",
            }
            for ordinal in range(3)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_truncation",
                source_refs=refs,
            )
            code, output, error = self.run_cli(
                archive_root,
                "--max-items",
                "1",
            )
        result = json.loads(output)
        self.assertEqual(code, 0, error)
        self.assertEqual(
            result["source_reference_coverage"]["population_count"],
            3,
        )
        self.assertEqual(
            result["recorded_storage_evidence"]["assessment_count"],
            3,
        )
        self.assertEqual(result["details_returned"], 1)
        self.assertTrue(result["details_truncated"])
        self.assertEqual(result["details"][0]["reference_ordinal"], 1)
        self.assert_schema_valid(result)

    def test_axis_aggregates_are_independent_and_semantics_reject_mutation(
        self,
    ) -> None:
        occurrences = [
            audit.Occurrence(
                private_sort_key=("a", 0, 1),
                zettel_identity="zet_a",
                authority_family="canonical_zettel_source_refs",
                coverage_state="recovered_durable_reference",
                reason_codes=["exact_durable_reference"],
                evidence_kind_codes=["population_authority"],
                storage_state="recorded_time_evidence",
            ),
            audit.Occurrence(
                private_sort_key=("b", 0, 1),
                zettel_identity="zet_b",
                authority_family="canonical_zettel_source_refs",
                coverage_state="recovered_durable_reference",
                reason_codes=["exact_durable_reference"],
                evidence_kind_codes=["population_authority"],
                storage_state="no_evidence",
            ),
            audit.Occurrence(
                private_sort_key=("c", 0, 1),
                zettel_identity="zet_c",
                authority_family="canonical_notion_omission_markers",
                coverage_state="unrecovered_reference",
                reason_codes=["explicit_unrecovered_marker"],
                evidence_kind_codes=["population_authority"],
                storage_state="recorded_time_evidence",
            ),
            audit.Occurrence(
                private_sort_key=("d", 0, 1),
                zettel_identity="zet_d",
                authority_family="canonical_notion_omission_markers",
                coverage_state="unrecovered_reference",
                reason_codes=["explicit_unrecovered_marker"],
                evidence_kind_codes=["population_authority"],
                storage_state="no_evidence",
            ),
        ]
        coverage = audit._coverage_aggregate(
            occurrences,
            population_complete=True,
        )
        storage = audit._storage_aggregate(
            occurrences,
            assessment_complete=True,
        )
        self.assertEqual(coverage["recovered_count"], 2)
        self.assertEqual(coverage["unrecovered_count"], 2)
        self.assertEqual(storage["recorded_time_evidence_count"], 2)
        self.assertEqual(storage["no_evidence_count"], 2)

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            code, output, error = self.run_cli(archive_root)
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        broken = deepcopy(result)
        broken["source_reference_coverage"]["population_count"] = 1
        with self.assertRaisesRegex(ValueError, "coverage count invariant"):
            audit.validate_result_semantics(broken)
        broken = deepcopy(result)
        broken["claim_separation"][
            "source_coverage_implies_storage_integrity"
        ] = True
        with self.assertRaisesRegex(ValueError, "axis independence"):
            audit.validate_result_semantics(broken)

    def test_progress_and_result_do_not_expose_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_privacy",
                source_refs=[
                    {"type": "url", "value": PRIVATE_SOURCE_CANARY}
                ],
                private_body="PRIVATE BODY CANARY MUST NOT ECHO",
            )
            before = self.tree_digest(archive_root)
            real_path_open = Path.open

            def reject_object_byte_open(
                path: Path,
                *args: object,
                **kwargs: object,
            ):
                try:
                    relative = path.resolve().relative_to(
                        archive_root.resolve()
                    ).as_posix()
                except ValueError:
                    return real_path_open(path, *args, **kwargs)
                if (
                    relative.startswith("objects/")
                    and relative
                    != "objects/manifests/files.jsonl"
                ):
                    raise AssertionError("object bytes must not be opened")
                return real_path_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", reject_object_byte_open):
                code, output, error = self.run_cli(
                    archive_root,
                    "--progress",
                )
            after = self.tree_digest(archive_root)
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertEqual(
            error.splitlines(),
            [
                "SOURCE_REFERENCE_COVERAGE_AUDIT_PHASE=archive_boundary",
                "SOURCE_REFERENCE_COVERAGE_AUDIT_PHASE=canonical_population",
                (
                    "SOURCE_REFERENCE_COVERAGE_AUDIT_PHASE="
                    "recorded_storage_evidence"
                ),
                "SOURCE_REFERENCE_COVERAGE_AUDIT_PHASE=result",
            ],
        )
        combined = output + error
        for forbidden in (
            PRIVATE_SOURCE_CANARY,
            "PRIVATE BODY CANARY",
            str(archive_root),
            KNOWN_DIGEST,
        ):
            self.assertNotIn(forbidden, combined)
        result = json.loads(output)
        self.assertTrue(
            all(value is False for value in result["privacy_guards"].values())
        )
        self.assert_schema_valid(result)

    def test_text_and_json_render_the_same_closed_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_archive(Path(tmp))
            self.write_canonical(
                archive_root,
                zettel_id="zet_test_text_parity",
                source_refs=[
                    {"type": "url", "value": PRIVATE_SOURCE_CANARY}
                ],
            )
            json_code, json_output, _json_error = self.run_cli(
                archive_root
            )
            text_stdout = io.StringIO()
            text_stderr = io.StringIO()
            with redirect_stdout(text_stdout), redirect_stderr(text_stderr):
                text_code = archive_cli.main(
                    [
                        "source-reference-coverage-audit",
                        str(archive_root),
                        "--dry-run",
                        "--format",
                        "text",
                    ]
                )
        result = json.loads(json_output)
        text_output = text_stdout.getvalue()
        self.assertEqual(json_code, text_code)
        self.assertEqual(text_stderr.getvalue(), "")
        self.assertIn(
            (
                "SOURCE REFERENCE COVERAGE: "
                f"{result['source_reference_coverage']['state'].upper()}"
            ),
            text_output,
        )
        self.assertIn(
            (
                "RECORDED STORAGE EVIDENCE: "
                + result["recorded_storage_evidence"]["state"]
                .replace("_", " ")
                .upper()
            ),
            text_output,
        )
        self.assertIn("ARCHIVE-WIDE COVERAGE CLAIM SUPPORTED: NO", text_output)
        self.assertIn("CURRENT BYTES CHECKED: NO", text_output)
        self.assertNotIn(PRIVATE_SOURCE_CANARY, text_output)

    def test_machine_routing_preserves_the_same_claim_boundary(self) -> None:
        routing = archive_services.runtime_context_action_routing()
        self.assertEqual(
            routing["schema"],
            "wom-kit/ai-command-path-routing/v0.10",
        )
        route = next(
            item
            for item in routing["read_action_routes"]
            if item["action"]
            == (
                "inspect_observed_source_coverage_and_"
                "recorded_storage_evidence"
            )
        )
        self.assertEqual(
            route["command"],
            (
                "python -B -m wom_kit.archive_cli "
                "source-reference-coverage-audit <archive-root> "
                "--dry-run --format json"
            ),
        )
        self.assertFalse(
            route["archive_wide_population_authority_available"]
        )
        self.assertFalse(route["live_storage_checked"])
        self.assertFalse(route["generated_index_used"])
        self.assertFalse(route["writes"])


if __name__ == "__main__":
    unittest.main()
