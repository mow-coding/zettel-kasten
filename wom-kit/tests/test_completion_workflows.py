from __future__ import annotations

import io
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, completion_workflows


class CompletionWorkflowTests(unittest.TestCase):
    COMPLETION_SCHEMA_NAMES = (
        "external-locator-record.schema.json",
        "external-locator-receipt.schema.json",
        "external-locator-revert-receipt.schema.json",
        "zettel-objet-link-receipt.schema.json",
        "zettel-objet-link-revert-receipt.schema.json",
        "draft-discard-receipt.schema.json",
        "draft-discard-restore-receipt.schema.json",
        "authoring-conventions.schema.json",
        "source-intake-batch-request.schema.json",
        "source-intake-batch-receipt.schema.json",
        "objet-capture-batch-request.schema.json",
        "objet-capture-batch-receipt.schema.json",
        "markup-reference-binding-manifest.schema.json",
        "markup-normalization-plan.schema.json",
        "markup-normalization-journal.schema.json",
        "markup-normalization-receipt.schema.json",
        "markup-normalization-revert-receipt.schema.json",
        "markup-normalization-recovery-receipt.schema.json",
        "relation-candidate-plan.schema.json",
        "relation-judgment.schema.json",
        "relation-judgment-receipt.schema.json",
        "principal-record.schema.json",
        "principal-registration-receipt.schema.json",
        "principal-unregistration-receipt.schema.json",
        "project-bytecode-repair-receipt.schema.json",
    )

    def run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    def assert_schema_instance(
        self,
        schema_name: str,
        instance: dict[str, object],
    ) -> None:
        schema = json.loads(
            (KIT_ROOT / "schemas" / schema_name).read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(instance)

    def fake_archive(self, target: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", target)
        return target

    def capture_batch_fixture(
        self,
        archive_root: Path,
        *,
        count: int,
        title_length: int = 0,
    ) -> Path:
        (archive_root / ".wom-sandbox").write_text(
            "sandbox\n",
            encoding="utf-8",
        )
        plan = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "source_intake_plan",
            "blockers": [],
            "content_access": dict(
                completion_workflows.archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
            ),
            "source_refs_for_draft": [],
        }
        source_plan_relative = "receipts/sources/batch.source-intake-plan.json"
        source_plan_path = archive_root / source_plan_relative
        source_plan_path.parent.mkdir(parents=True, exist_ok=True)
        source_plan_path.write_text(
            json.dumps(plan),
            encoding="utf-8",
        )
        items = []
        staging = archive_root / "staging" / "incoming" / "batch"
        staging.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            relative = f"staging/incoming/batch/item-{index:04d}.txt"
            (archive_root / relative).write_bytes(
                f"synthetic-{index}\n".encode("utf-8")
            )
            item = {
                "item_id": f"item-{index:04d}",
                "staged_path": relative,
                "source_intake_receipt_path": source_plan_relative,
            }
            if title_length:
                item["title"] = "T" * title_length
            items.append(item)
        request = {
            "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
            "batch_id": f"synthetic-batch-{count}",
            "items": items,
        }
        request_path = archive_root / "staging" / "batch-request.json"
        request_path.write_text(
            json.dumps(request),
            encoding="utf-8",
        )
        return request_path

    def write_markup_zettel(
        self,
        archive_root: Path,
        zettel_id: str,
        body: str,
    ) -> Path:
        path = archive_root / "zettels" / f"{zettel_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"id: {zettel_id}\n"
            f"title: Synthetic {zettel_id}\n"
            "status: canonical\n"
            "kind: note\n"
            "---\n"
            + body,
            encoding="utf-8",
        )
        return path

    def write_schema_valid_markup_zettel(
        self,
        archive_root: Path,
        zettel_id: str,
        body: str,
        *,
        status: str = "canonical",
        folder: str = "zettels",
    ) -> Path:
        path = archive_root / folder / f"{zettel_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        archive_id = completion_workflows.archive_services.read_archive_id(
            archive_root
        )
        path.write_text(
            "---\n"
            f"id: {zettel_id}\n"
            f"title: Synthetic {zettel_id}\n"
            "created_at: '2026-08-09T00:00:00Z'\n"
            "updated_at: '2026-08-09T00:00:00Z'\n"
            f"archive_id: {archive_id}\n"
            f"status: {status}\n"
            "kind: note\n"
            "facets: {}\n"
            "assets: []\n"
            "edges: []\n"
            "provenance:\n"
            "  created_by: person:test\n"
            "  created_in: synthetic-test\n"
            "  source: synthetic-test\n"
            "  derived_from: []\n"
            "visibility:\n"
            "  scope: private\n"
            "  allowed_archives: []\n"
            "  source_visibility: private\n"
            "---\n"
            + body,
            encoding="utf-8",
        )
        return path

    @staticmethod
    def locator_fixture_id(marker: str) -> str:
        return f"locator:sha256:{marker * 64}"

    def locator_fixture_row(
        self,
        marker: str,
        *,
        locator_ref: str = "message-id:synthetic-duplicate",
        locator_type: str = "export_coordinate",
        status: str = "active",
        service_ref: str | None = "mail-service",
        account_ref: str | None = None,
        occurrence_anchor: str | None = "body:paragraph-2",
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "locator_id": self.locator_fixture_id(marker),
            "locator_type": locator_type,
            "locator_ref": locator_ref,
            "status": status,
            "recorded_at": "2026-08-08T00:00:00Z",
            "reviewed_by": "person:original-reviewer",
            "provenance": {
                "source": "human_reviewed_cli",
                "automatic_recovery_claimed": False,
            },
        }
        for name, value in (
            ("service_ref", service_ref),
            ("account_ref", account_ref),
            ("occurrence_anchor", occurrence_anchor),
        ):
            if value is not None:
                row[name] = value
        return row

    def write_locator_record_fixture(
        self,
        archive_root: Path,
        zettel_id: str,
        rows: list[dict[str, object]],
        *,
        schema: str = "wom-kit/external-locator-record/v0.2",
    ) -> Path:
        record = {
            "schema": schema,
            "archive_id": completion_workflows.archive_services.read_archive_id(
                archive_root
            ),
            "zettel_id": zettel_id,
            "created_at": "2026-08-08T00:00:00Z",
            "updated_at": "2026-08-08T00:00:00Z",
            "locators": rows,
        }
        path = (
            archive_root
            / "ops"
            / "external-locators"
            / f"{zettel_id}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def write_markup_objet_binding_manifest(
        self,
        archive_root: Path,
        relative: str,
        bindings: list[tuple[str, str]],
    ) -> str:
        object_id = (
            "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
        )
        manifest = {
            "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
            "archive_id": completion_workflows.archive_services.read_archive_id(
                archive_root
            ),
            "bindings": [
                {
                    "zettel_id": zettel_id,
                    "tag_sha256": tag_sha256,
                    "binding_kind": "objet",
                    "binding_id": object_id,
                }
                for zettel_id, tag_sha256 in bindings
            ],
        }
        path = archive_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return relative

    def write_relation_zettel(
        self,
        archive_root: Path,
        zettel_id: str,
        *,
        title: str,
        recurring_series: str,
        sequence_index: int,
    ) -> Path:
        path = archive_root / "zettels" / f"{zettel_id}.md"
        path.write_text(
            "---\n"
            f"id: {zettel_id}\n"
            f"title: {title}\n"
            "status: canonical\n"
            "kind: note\n"
            "facets:\n"
            f"  recurring_series: {recurring_series}\n"
            f"  sequence_index: {sequence_index}\n"
            "---\n"
            "Private body is intentionally irrelevant to candidate discovery.\n",
            encoding="utf-8",
        )
        return path

    def project_mirror_fixture(
        self,
        project_root: Path,
        *,
        tracked_bytecode: bool = False,
    ) -> tuple[Path, Path, bytes]:
        mirror = project_root / ".zettel-kasten" / "source"
        package = mirror / "wom-kit" / "src" / "wom_kit"
        package.mkdir(parents=True)
        source = package / "archive_cli.py"
        source_bytes = b"VALUE = 'tracked source stays exact'\n"
        source.write_bytes(source_bytes)
        (package / "__init__.py").write_text(
            '__version__ = "0.3.300"\n',
            encoding="utf-8",
        )
        pycache = package / "__pycache__"
        pycache.mkdir()
        bytecode = pycache / "archive_cli.cpython-312.pyc"
        bytecode.write_bytes(b"SYNTHETIC DERIVED BYTECODE")
        (mirror / ".gitignore").write_text(
            "" if tracked_bytecode else "__pycache__/\n*.pyc\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init"],
            cwd=mirror,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=mirror,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=mirror,
            check=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=mirror,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=mirror,
            check=True,
            capture_output=True,
            text=True,
        )
        return mirror, bytecode, source_bytes

    def test_completion_workflow_schemas_are_valid_draft_2020_12(self) -> None:
        for name in self.COMPLETION_SCHEMA_NAMES:
            with self.subTest(name=name):
                schema = json.loads(
                    (KIT_ROOT / "schemas" / name).read_text(
                        encoding="utf-8"
                    )
                )
                Draft202012Validator.check_schema(schema)

    def test_runtime_routing_exposes_integrated_plan_write_and_recovery_paths(self) -> None:
        routing = (
            completion_workflows.archive_services
            .runtime_context_action_routing()
        )
        self.assertEqual(
            routing["schema"],
            "wom-kit/ai-command-path-routing/v0.13",
        )
        read_actions = {
            row["action"] for row in routing["read_action_routes"]
        }
        write_actions = {
            row["action"] for row in routing["write_action_routes"]
        }
        self.assertTrue(
            {
                "plan_external_locator_change",
                "plan_relation_candidate_review",
                "plan_markup_normalization",
                "plan_project_bytecode_repair",
            }
            <= read_actions
        )
        self.assertTrue(
            {
                "capture_reviewed_objet_batch",
                "record_or_revert_external_locator",
                "decide_relation_candidate",
                "normalize_or_recover_markup",
                "repair_project_derived_bytecode",
            }
            <= write_actions
        )

    def test_external_locator_is_digest_bound_multi_value_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            first_ref = "https://provider.example/private/page-alpha"
            plan_code, plan_output = self.run_cli(
                [
                    "external-locator-plan",
                    str(archive_root),
                    "--zettel-id",
                    zettel_id,
                    "--locator-type",
                    "source_url",
                    "--locator-ref",
                    first_ref,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(plan_code, 0, plan_output)
            self.assertNotIn(first_ref, plan_output)
            plan = json.loads(plan_output)
            self.assertFalse(plan["privacy_guards"]["locator_ref_echoed"])
            plan_sha256 = plan["summary"]["plan_sha256"]

            record_code, record_output = self.run_cli(
                [
                    "external-locator-record",
                    str(archive_root),
                    "--zettel-id",
                    zettel_id,
                    "--locator-type",
                    "source_url",
                    "--locator-ref",
                    first_ref,
                    "--expected-plan-sha256",
                    plan_sha256,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(record_code, 0, record_output)
            self.assertNotIn(first_ref, record_output)
            recorded = json.loads(record_output)
            record_path = archive_root / recorded["summary"]["record_path"]
            self.assertTrue(record_path.is_file())
            stored = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["locators"][0]["locator_ref"], first_ref)
            self.assert_schema_instance(
                "external-locator-record.schema.json",
                stored,
            )
            self.assert_schema_instance(
                "external-locator-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / recorded["summary"]["receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )

            second_ref = "workspace-page:synthetic-beta"
            second_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="provider_page_id",
                locator_ref=second_ref,
            )
            second = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="provider_page_id",
                locator_ref=second_ref,
                expected_plan_sha256=second_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(second["ok"], second)

            recovery_code, recovery_output = self.run_cli(
                [
                    "external-locator-recovery-plan",
                    str(archive_root),
                    "--zettel-id",
                    zettel_id,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(recovery_code, 0, recovery_output)
            self.assertNotIn(first_ref, recovery_output)
            self.assertNotIn(second_ref, recovery_output)
            recovery = json.loads(recovery_output)
            self.assertEqual(recovery["state"], "candidates_available")
            self.assertEqual(recovery["summary"]["locator_count"], 2)
            self.assertTrue(recovery["summary"]["multiple_locators"])
            self.assertFalse(
                recovery["truth_boundaries"]["global_recoverability_claimed"]
            )
            self.assertFalse(
                recovery["truth_boundaries"][
                    "locator_presence_proves_remote_reachability"
                ]
            )

            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=second["summary"]["receipt_path"],
            )
            self.assertTrue(revert_plan["ok"], revert_plan)
            reverted = completion_workflows.external_locator_revert(
                archive_root,
                receipt=second["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"][
                    "plan_sha256"
                ],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assert_schema_instance(
                "external-locator-revert-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / reverted["summary"]["receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            after_revert = (
                completion_workflows.external_locator_recovery_plan(
                    archive_root,
                    zettel_id=zettel_id,
                )
            )
            self.assertEqual(
                after_revert["summary"]["locator_count"],
                1,
            )
            restored = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(
                restored["locators"][0]["locator_ref"],
                first_ref,
            )

    def test_external_locator_stale_plan_and_secret_query_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20240504_fake_lunch_thought"
            stale_ref = "export-coordinate:synthetic-a"
            stale = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=stale_ref,
            )
            other_ref = "export-coordinate:synthetic-b"
            other = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=other_ref,
            )
            written = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=other_ref,
                expected_plan_sha256=other["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(written["ok"], written)
            blocked = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=stale_ref,
                expected_plan_sha256=stale["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertFalse(blocked["ok"], blocked)
            self.assertIn("external_locator_plan_changed", blocked["blockers"])

            secret_ref = "https://provider.example/page?access_token=PRIVATE_MARKER"
            secret = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="source_url",
                locator_ref=secret_ref,
            )
            self.assertFalse(secret["ok"])
            self.assertIn(
                "external_locator_ref_invalid_or_secret_like",
                secret["blockers"],
            )
            self.assertNotIn(
                secret_ref,
                json.dumps(secret, ensure_ascii=False),
            )

    def test_external_locator_distinguishes_service_account_and_repeated_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            locator_ref = "message-id:reviewed-synthetic-message"
            service_ref = "mail-service"
            account_ref = "reviewed-account@example.test"
            first_anchor = "body:paragraph-2"
            second_anchor = "body:paragraph-9"

            first_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=locator_ref,
                service_ref=service_ref,
                account_ref=account_ref,
                occurrence_anchor=first_anchor,
            )
            self.assertTrue(first_plan["ok"], first_plan)
            first = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=locator_ref,
                service_ref=service_ref,
                account_ref=account_ref,
                occurrence_anchor=first_anchor,
                expected_plan_sha256=first_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(first["ok"], first)

            exact_duplicate = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=locator_ref,
                service_ref=service_ref,
                account_ref=account_ref,
                occurrence_anchor=first_anchor,
            )
            self.assertFalse(exact_duplicate["ok"])
            self.assertIn(
                "external_locator_already_recorded",
                exact_duplicate["blockers"],
            )

            second_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=locator_ref,
                service_ref=service_ref,
                account_ref=account_ref,
                occurrence_anchor=second_anchor,
            )
            self.assertTrue(second_plan["ok"], second_plan)
            self.assertNotEqual(
                first_plan["summary"]["locator_id"],
                second_plan["summary"]["locator_id"],
            )
            second = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref=locator_ref,
                service_ref=service_ref,
                account_ref=account_ref,
                occurrence_anchor=second_anchor,
                expected_plan_sha256=second_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(second["ok"], second)

            record_path = archive_root / second["summary"]["record_path"]
            stored = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["schema"], "wom-kit/external-locator-record/v0.3")
            self.assertEqual(len(stored["locators"]), 2)
            self.assertEqual(stored["locators"][0]["account_ref"], account_ref)
            self.assertEqual(stored["locators"][1]["occurrence_anchor"], second_anchor)
            self.assert_schema_instance("external-locator-record.schema.json", stored)

            recovery = completion_workflows.external_locator_recovery_plan(
                archive_root,
                zettel_id=zettel_id,
            )
            self.assertEqual(recovery["summary"]["locator_count"], 2)
            self.assertTrue(
                recovery["locators"][0]["coordinate_presence"]["account_ref"]
            )
            public = json.dumps(recovery, ensure_ascii=False)
            self.assertNotIn(locator_ref, public)
            self.assertNotIn(service_ref, public)
            self.assertNotIn(account_ref, public)
            self.assertNotIn(first_anchor, public)
            self.assertFalse(recovery["privacy_guards"]["account_ref_echoed"])

    def test_external_locator_enriches_one_matching_row_without_active_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            locator_ref = "https://provider.example/reviewed/message"

            bare_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="source_url",
                locator_ref=locator_ref,
            )
            bare = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="source_url",
                locator_ref=locator_ref,
                expected_plan_sha256=bare_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(bare["ok"], bare)

            enrich_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="source_url",
                locator_ref=locator_ref,
                service_ref="mail-service",
                account_ref="reviewed-account@example.test",
            )
            self.assertTrue(enrich_plan["ok"], enrich_plan)
            self.assertEqual(
                enrich_plan["summary"]["planned_action"],
                "update_locator_coordinates",
            )
            self.assertEqual(
                enrich_plan["summary"]["locator_id"],
                bare["summary"]["locator_id"],
            )
            enriched = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="source_url",
                locator_ref=locator_ref,
                service_ref="mail-service",
                account_ref="reviewed-account@example.test",
                expected_plan_sha256=enrich_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(enriched["ok"], enriched)
            record = json.loads(
                (
                    archive_root / enriched["summary"]["record_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(len(record["locators"]), 1)
            self.assertEqual(
                record["locators"][0]["locator_id"],
                bare["summary"]["locator_id"],
            )
            self.assertEqual(
                record["locators"][0]["account_ref"],
                "reviewed-account@example.test",
            )
            receipt = json.loads(
                (
                    archive_root / enriched["summary"]["receipt_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["action"], "update_locator_coordinates")
            self.assert_schema_instance(
                "external-locator-receipt.schema.json",
                receipt,
            )

            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=enriched["summary"]["receipt_path"],
            )
            reverted = completion_workflows.external_locator_revert(
                archive_root,
                receipt=enriched["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            restored = json.loads(
                (
                    archive_root / enriched["summary"]["record_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(len(restored["locators"]), 1)
            self.assertNotIn("account_ref", restored["locators"][0])

    def test_external_locator_deactivate_duplicate_is_reversible_and_preserves_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            locator_ref = "message-id:synthetic-private-duplicate"
            target = self.locator_fixture_row(
                "a",
                locator_ref=locator_ref,
            )
            keeper = self.locator_fixture_row(
                "b",
                locator_ref=locator_ref,
                account_ref="reviewed-account@example.test",
            )
            record_path = self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [target, keeper],
            )
            before_bytes = record_path.read_bytes()

            plan = completion_workflows.external_locator_deactivate_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_id=str(target["locator_id"]),
                keep_locator_id=str(keeper["locator_id"]),
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "ready")
            self.assertEqual(
                plan["summary"]["planned_action"],
                "deactivate_duplicate_locator",
            )
            self.assertEqual(plan["files_written"], [])
            public_plan = json.dumps(plan, ensure_ascii=False)
            for private_value in (
                locator_ref,
                "mail-service",
                "reviewed-account@example.test",
                "body:paragraph-2",
                str(archive_root.resolve()),
            ):
                self.assertNotIn(private_value, public_plan)

            applied = completion_workflows.external_locator_deactivate(
                archive_root,
                zettel_id=zettel_id,
                locator_id=str(target["locator_id"]),
                keep_locator_id=str(keeper["locator_id"]),
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["state"], "written")
            stored = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(
                stored["schema"],
                "wom-kit/external-locator-record/v0.3",
            )
            self.assertEqual(
                stored["locators"],
                [{**target, "status": "inactive"}, keeper],
            )
            self.assert_schema_instance(
                "external-locator-record.schema.json",
                stored,
            )
            receipt_path = archive_root / applied["summary"]["receipt_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["schema"],
                "wom-kit/external-locator-receipt/v0.4",
            )
            self.assertEqual(
                receipt["action"],
                "deactivate_duplicate_locator",
            )
            self.assertEqual(receipt["locator_id"], target["locator_id"])
            self.assertEqual(receipt["kept_locator_id"], keeper["locator_id"])
            self.assertEqual(receipt["previous_status"], "active")
            self.assertEqual(receipt["new_status"], "inactive")
            self.assert_schema_instance(
                "external-locator-receipt.schema.json",
                receipt,
            )
            self.assertFalse(
                completion_workflows._verified_locator_binding(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(target["locator_id"]),
                )
            )
            self.assertTrue(
                completion_workflows._verified_locator_binding(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(keeper["locator_id"]),
                )
            )

            recovery = completion_workflows.external_locator_recovery_plan(
                archive_root,
                zettel_id=zettel_id,
            )
            self.assertEqual(recovery["summary"]["locator_count"], 2)
            self.assertEqual(recovery["summary"]["active_locator_count"], 1)
            self.assertEqual(recovery["summary"]["inactive_locator_count"], 1)
            duplicate_add = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type=str(target["locator_type"]),
                locator_ref=locator_ref,
                service_ref=str(target["service_ref"]),
                occurrence_anchor=str(target["occurrence_anchor"]),
            )
            self.assertFalse(duplicate_add["ok"], duplicate_add)
            self.assertIn(
                "external_locator_already_recorded",
                duplicate_add["blockers"],
            )

            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            self.assertTrue(revert_plan["ok"], revert_plan)
            reverted = completion_workflows.external_locator_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(record_path.read_bytes(), before_bytes)

    def test_external_locator_deactivate_duplicate_safety_matrix_fails_closed(self) -> None:
        cases = {
            "target_invalid": "external_locator_deactivate_locator_id_invalid",
            "keeper_invalid": "external_locator_deactivate_keep_locator_id_invalid",
            "same": "external_locator_deactivate_ids_must_differ",
            "target_missing": "external_locator_deactivate_target_missing",
            "keeper_missing": "external_locator_deactivate_keeper_missing",
            "target_duplicate": "external_locator_deactivate_target_ambiguous",
            "keeper_duplicate": "external_locator_deactivate_keeper_ambiguous",
            "target_duplicate_mixed": "external_locator_deactivate_target_ambiguous",
            "keeper_duplicate_mixed": "external_locator_deactivate_keeper_ambiguous",
            "target_inactive": "external_locator_deactivate_target_inactive",
            "keeper_inactive": "external_locator_deactivate_keeper_inactive",
            "ref_mismatch": "external_locator_deactivate_ref_type_mismatch",
            "type_mismatch": "external_locator_deactivate_ref_type_mismatch",
            "occurrence_mismatch": "external_locator_deactivate_occurrence_mismatch",
            "coordinate_conflict": "external_locator_deactivate_coordinate_conflict",
            "coordinate_missing": "external_locator_deactivate_coordinate_conflict",
            "record_shape_invalid": "external_locator_record_invalid",
            "body_reference": "external_locator_deactivate_target_referenced",
        }
        for case_name, expected_blocker in cases.items():
            with self.subTest(case_name=case_name), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                target = self.locator_fixture_row("a")
                keeper = self.locator_fixture_row(
                    "b",
                    account_ref="reviewed-account@example.test",
                )
                target_id = str(target["locator_id"])
                keeper_id = str(keeper["locator_id"])
                rows = [target, keeper]
                if case_name == "target_invalid":
                    target_id = "not-a-locator-id"
                elif case_name == "keeper_invalid":
                    keeper_id = "not-a-locator-id"
                elif case_name == "same":
                    keeper_id = target_id
                elif case_name == "target_missing":
                    target_id = self.locator_fixture_id("c")
                elif case_name == "keeper_missing":
                    keeper_id = self.locator_fixture_id("c")
                elif case_name == "target_duplicate":
                    rows = [target, dict(target), keeper]
                elif case_name == "keeper_duplicate":
                    rows = [target, keeper, dict(keeper)]
                elif case_name == "target_duplicate_mixed":
                    inactive_target = dict(target)
                    inactive_target["status"] = "inactive"
                    rows = [target, inactive_target, keeper]
                elif case_name == "keeper_duplicate_mixed":
                    inactive_keeper = dict(keeper)
                    inactive_keeper["status"] = "inactive"
                    rows = [target, keeper, inactive_keeper]
                elif case_name == "target_inactive":
                    target["status"] = "inactive"
                elif case_name == "keeper_inactive":
                    keeper["status"] = "inactive"
                elif case_name == "ref_mismatch":
                    keeper["locator_ref"] = "message-id:different"
                elif case_name == "type_mismatch":
                    keeper["locator_type"] = "provider_page_id"
                elif case_name == "occurrence_mismatch":
                    keeper["occurrence_anchor"] = "body:paragraph-9"
                elif case_name == "coordinate_conflict":
                    keeper["service_ref"] = "different-service"
                elif case_name == "coordinate_missing":
                    keeper.pop("service_ref")
                elif case_name == "record_shape_invalid":
                    keeper["recorded_at"] = ""

                record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    rows,
                    schema="wom-kit/external-locator-record/v0.3",
                )
                zettel_path = (
                    completion_workflows.archive_services.resolve_zettel_path(
                        archive_root,
                        zettel_id=zettel_id,
                        relative_path=None,
                    )
                )
                if case_name == "body_reference":
                    target_digest = target_id.removeprefix("locator:sha256:")
                    with zettel_path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            "\n[External](WOM-LOCATOR://SHA256/"
                            f"{target_digest.upper()})\n"
                        )
                before_record = record_path.read_bytes()
                before_zettel = zettel_path.read_bytes()
                plan = completion_workflows.external_locator_deactivate_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=target_id,
                    keep_locator_id=keeper_id,
                )
                self.assertFalse(plan["ok"], plan)
                self.assertIn(expected_blocker, plan["blockers"])
                self.assertEqual(plan["files_written"], [])
                blocked = completion_workflows.external_locator_deactivate(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=target_id,
                    keep_locator_id=keeper_id,
                    expected_plan_sha256="0" * 64,
                    reviewed_by="person:test",
                )
                self.assertFalse(blocked["ok"], blocked)
                self.assertEqual(blocked["files_written"], [])
                self.assertEqual(record_path.read_bytes(), before_record)
                self.assertEqual(zettel_path.read_bytes(), before_zettel)
                public = json.dumps(blocked, ensure_ascii=False)
                for private_value in (
                    str(target["locator_ref"]),
                    "mail-service",
                    "reviewed-account@example.test",
                    "body:paragraph-2",
                    str(archive_root.resolve()),
                    "wom-locator://sha256/",
                ):
                    self.assertNotIn(private_value, public)

    def test_external_locator_deactivate_unreadable_stale_and_bad_approval_are_byte_exact(self) -> None:
        cases = (
            "record_unreadable",
            "zettel_unreadable",
            "stale_plan",
            "bad_hash",
            "bad_reviewer",
        )
        for case_name in cases:
            with self.subTest(case_name=case_name), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                target = self.locator_fixture_row("a")
                keeper = self.locator_fixture_row(
                    "b",
                    account_ref="reviewed-account@example.test",
                )
                record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    [target, keeper],
                )
                zettel_path = (
                    completion_workflows.archive_services.resolve_zettel_path(
                        archive_root,
                        zettel_id=zettel_id,
                        relative_path=None,
                    )
                )
                initial_plan = (
                    completion_workflows.external_locator_deactivate_plan(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_id=str(target["locator_id"]),
                        keep_locator_id=str(keeper["locator_id"]),
                    )
                )
                self.assertTrue(initial_plan["ok"], initial_plan)
                expected = initial_plan["summary"]["plan_sha256"]
                reviewer = "person:test"
                if case_name == "record_unreadable":
                    record_path.write_bytes(b"\xff\xfe")
                elif case_name == "zettel_unreadable":
                    zettel_path.write_bytes(b"\xff\xfe")
                elif case_name == "stale_plan":
                    record_path.write_bytes(record_path.read_bytes() + b" \n")
                elif case_name == "bad_hash":
                    expected = "not-a-sha256"
                elif case_name == "bad_reviewer":
                    reviewer = "bad reviewer with spaces"
                before_record = record_path.read_bytes()
                before_zettel = zettel_path.read_bytes()
                blocked = completion_workflows.external_locator_deactivate(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(target["locator_id"]),
                    keep_locator_id=str(keeper["locator_id"]),
                    expected_plan_sha256=expected,
                    reviewed_by=reviewer,
                )
                self.assertFalse(blocked["ok"], blocked)
                self.assertEqual(blocked["files_written"], [])
                self.assertEqual(record_path.read_bytes(), before_record)
                self.assertEqual(zettel_path.read_bytes(), before_zettel)
                self.assertNotIn(
                    str(archive_root.resolve()),
                    json.dumps(blocked, ensure_ascii=False),
                )

    def test_external_locator_deactivate_cli_gates_and_privacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            target = self.locator_fixture_row("a")
            keeper = self.locator_fixture_row(
                "b",
                account_ref="reviewed-account@example.test",
            )
            record_path = self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [target, keeper],
            )
            before = record_path.read_bytes()
            common = [
                str(archive_root),
                "--zettel-id",
                zettel_id,
                "--locator-id",
                str(target["locator_id"]),
                "--keep-locator-id",
                str(keeper["locator_id"]),
            ]
            code, output = self.run_cli(
                ["external-locator-deactivate-plan", *common]
            )
            self.assertEqual(code, 1, output)
            self.assertEqual(record_path.read_bytes(), before)
            code, output = self.run_cli(
                [
                    "external-locator-deactivate-plan",
                    *common,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            plan = json.loads(output)
            expected = plan["summary"]["plan_sha256"]
            code, output = self.run_cli(
                [
                    "external-locator-deactivate",
                    *common,
                    "--expected-plan-sha256",
                    expected,
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1, output)
            self.assertEqual(record_path.read_bytes(), before)
            code, output = self.run_cli(
                [
                    "external-locator-deactivate",
                    *common,
                    "--expected-plan-sha256",
                    expected,
                    "--reviewed-by",
                    "person:test",
                    "--approve",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            for private_value in (
                str(target["locator_ref"]),
                "mail-service",
                "reviewed-account@example.test",
                "body:paragraph-2",
                str(archive_root.resolve()),
            ):
                self.assertNotIn(private_value, output)

    def test_external_locator_recovery_reports_all_inactive_and_legacy_receipts_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            first = self.locator_fixture_row("a", status="inactive")
            second = self.locator_fixture_row(
                "b",
                status="inactive",
                account_ref="reviewed-account@example.test",
            )
            self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [first, second],
                schema="wom-kit/external-locator-record/v0.3",
            )
            recovery = completion_workflows.external_locator_recovery_plan(
                archive_root,
                zettel_id=zettel_id,
            )
            self.assertTrue(recovery["ok"], recovery)
            self.assertEqual(recovery["state"], "all_candidates_inactive")
            self.assertEqual(recovery["summary"]["active_locator_count"], 0)
            self.assertEqual(recovery["summary"]["inactive_locator_count"], 2)
            self.assertTrue(recovery["summary"]["all_inactive"])
            self.assertTrue(recovery["warnings"])
            self.assertFalse(
                completion_workflows._verified_locator_binding(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(first["locator_id"]),
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            target = self.locator_fixture_row(
                "a",
                service_ref=None,
                occurrence_anchor=None,
            )
            keeper = self.locator_fixture_row(
                "b",
                service_ref=None,
                occurrence_anchor=None,
            )
            self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [target, keeper],
                schema="wom-kit/external-locator-record/v0.1",
            )
            legacy_record_plan = (
                completion_workflows.external_locator_deactivate_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(target["locator_id"]),
                    keep_locator_id=str(keeper["locator_id"]),
                )
            )
            self.assertTrue(legacy_record_plan["ok"], legacy_record_plan)

        for legacy_schema in (
            "wom-kit/external-locator-receipt/v0.1",
            "wom-kit/external-locator-receipt/v0.2",
            "wom-kit/external-locator-receipt/v0.3",
        ):
            with self.subTest(legacy_schema=legacy_schema), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20240504_fake_lunch_thought"
                plan = completion_workflows.external_locator_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_type="export_coordinate",
                    locator_ref="synthetic:legacy-receipt",
                )
                written = completion_workflows.external_locator_record(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_type="export_coordinate",
                    locator_ref="synthetic:legacy-receipt",
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:test",
                )
                receipt_path = archive_root / written["summary"]["receipt_path"]
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["schema"] = legacy_schema
                if legacy_schema.endswith("/v0.1"):
                    receipt.pop("coordinate_presence", None)
                legacy_path = receipt_path.with_name(
                    f"legacy-{legacy_schema.rsplit('/', 1)[-1]}.json"
                )
                legacy_path.write_text(
                    json.dumps(receipt),
                    encoding="utf-8",
                )
                revert_plan = (
                    completion_workflows.external_locator_revert_plan(
                        archive_root,
                        receipt=legacy_path,
                    )
                )
                self.assertTrue(revert_plan["ok"], revert_plan)

    def test_external_locator_revert_rejects_forged_paths_and_invalid_records(self) -> None:
        def receipt_document(
            archive_root: Path,
            zettel_id: str,
            *,
            action: str,
            record_relative: str,
            after_bytes: bytes,
            before_bytes: bytes | None,
        ) -> dict[str, object]:
            before_sha256 = (
                hashlib.sha256(before_bytes).hexdigest()
                if before_bytes is not None
                else None
            )
            return {
                "schema": completion_workflows.EXTERNAL_LOCATOR_RECEIPT_SCHEMA,
                "action": action,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "zettel_id": zettel_id,
                "locator_id": self.locator_fixture_id("a"),
                "locator_type": "export_coordinate",
                "coordinate_presence": {
                    "service_ref": True,
                    "account_ref": False,
                    "occurrence_anchor": True,
                },
                "plan_sha256": "1" * 64,
                "before_record_sha256": before_sha256,
                "after_record_sha256": hashlib.sha256(after_bytes).hexdigest(),
                "before_snapshot_path": (
                    f"{completion_workflows.EXTERNAL_LOCATOR_SNAPSHOT_DIR}/"
                    f"{before_sha256}.json"
                    if before_sha256 is not None
                    else None
                ),
                "record_path": record_relative,
                "reviewed_by": "person:test",
                "created_at": "2026-08-09T00:00:00Z",
                "privacy": {
                    "locator_ref_included": False,
                    "provider_called": False,
                    "network_checked": False,
                },
            }

        for forged_relative in (
            "zettels/zet_20110228_fake_school_record.md",
            "ops/unrelated-state.json",
        ):
            with self.subTest(forged_relative=forged_relative), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                before_record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    [self.locator_fixture_row("a")],
                )
                before_bytes = before_record_path.read_bytes()
                before_sha256 = hashlib.sha256(before_bytes).hexdigest()
                snapshot_path = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_SNAPSHOT_DIR
                    / f"{before_sha256}.json"
                )
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path.write_bytes(before_bytes)
                target_path = archive_root / forged_relative
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not target_path.exists():
                    target_path.write_bytes(b'{"private":"must-stay-exact"}\n')
                target_before = target_path.read_bytes()
                receipt = receipt_document(
                    archive_root,
                    zettel_id,
                    action="update_locator_coordinates",
                    record_relative=forged_relative,
                    after_bytes=target_before,
                    before_bytes=before_bytes,
                )
                receipt_path = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_RECEIPTS_DIR
                    / "forged-path.json"
                )
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

                plan = completion_workflows.external_locator_revert_plan(
                    archive_root,
                    receipt=receipt_path,
                )
                self.assertFalse(plan["ok"], plan)
                self.assertIn("external_locator_receipt_invalid", plan["blockers"])
                blocked = completion_workflows.external_locator_revert(
                    archive_root,
                    receipt=receipt_path,
                    expected_plan_sha256="0" * 64,
                    reviewed_by="person:test",
                )
                self.assertFalse(blocked["ok"], blocked)
                self.assertEqual(target_path.read_bytes(), target_before)

        for invalid_source in ("current_record", "snapshot_record"):
            with self.subTest(invalid_source=invalid_source), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    [self.locator_fixture_row("a")],
                )
                valid_record_bytes = record_path.read_bytes()
                invalid_record = json.loads(valid_record_bytes.decode("utf-8"))
                invalid_record["archive_id"] = "archive:forged:other"
                invalid_bytes = json.dumps(invalid_record).encode("utf-8")
                if invalid_source == "current_record":
                    record_path.write_bytes(invalid_bytes)
                    before_bytes = None
                    action = "add_locator"
                else:
                    before_bytes = invalid_bytes
                    action = "update_locator_coordinates"
                    before_sha256 = hashlib.sha256(before_bytes).hexdigest()
                    snapshot_path = (
                        archive_root
                        / completion_workflows.EXTERNAL_LOCATOR_SNAPSHOT_DIR
                        / f"{before_sha256}.json"
                    )
                    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    snapshot_path.write_bytes(before_bytes)
                record_before = record_path.read_bytes()
                receipt = receipt_document(
                    archive_root,
                    zettel_id,
                    action=action,
                    record_relative=(
                        f"{completion_workflows.EXTERNAL_LOCATOR_DIR}/{zettel_id}.json"
                    ),
                    after_bytes=record_before,
                    before_bytes=before_bytes,
                )
                receipt_path = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_RECEIPTS_DIR
                    / "invalid-record.json"
                )
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

                plan = completion_workflows.external_locator_revert_plan(
                    archive_root,
                    receipt=receipt_path,
                )
                self.assertFalse(plan["ok"], plan)
                self.assertIn(
                    (
                        "external_locator_record_invalid"
                        if invalid_source == "current_record"
                        else "external_locator_snapshot_invalid"
                    ),
                    plan["blockers"],
                )
                self.assertEqual(record_path.read_bytes(), record_before)

    def test_external_locator_revert_validates_schema_action_and_first_add_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20240504_fake_lunch_thought"
            plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:first-add-revert",
            )
            written = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:first-add-revert",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(written["ok"], written)
            record_path = archive_root / written["summary"]["record_path"]
            receipt_path = archive_root / written["summary"]["receipt_path"]
            forged = json.loads(receipt_path.read_text(encoding="utf-8"))
            forged["schema"] = "wom-kit/external-locator-receipt/v0.3"
            forged["action"] = "deactivate_duplicate_locator"
            forged_path = receipt_path.with_name("forged-schema-action.json")
            forged_path.write_text(json.dumps(forged), encoding="utf-8")
            rejected = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=forged_path,
            )
            self.assertFalse(rejected["ok"], rejected)
            self.assertIn("external_locator_receipt_invalid", rejected["blockers"])

            record_before = record_path.read_bytes()
            outside_receipt = archive_root / "ops" / "forged-add-receipt.json"
            outside_receipt.write_bytes(receipt_path.read_bytes())
            outside_rejected = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=outside_receipt,
            )
            self.assertFalse(outside_rejected["ok"], outside_rejected)
            self.assertIn(
                "external_locator_receipt_path_invalid",
                outside_rejected["blockers"],
            )
            outside_apply = completion_workflows.external_locator_revert(
                archive_root,
                receipt=outside_receipt,
                expected_plan_sha256="0" * 64,
                reviewed_by="person:test",
            )
            self.assertFalse(outside_apply["ok"], outside_apply)
            self.assertEqual(record_path.read_bytes(), record_before)

            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=receipt_path,
            )
            self.assertTrue(revert_plan["ok"], revert_plan)
            reverted = completion_workflows.external_locator_revert(
                archive_root,
                receipt=receipt_path,
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertFalse(record_path.exists())

    def test_external_locator_corrupt_content_addressed_snapshots_block_before_write(self) -> None:
        for action in ("add", "update", "deactivate"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                target = self.locator_fixture_row(
                    "a",
                    service_ref=None if action == "update" else "mail-service",
                    occurrence_anchor=None if action == "update" else "body:paragraph-2",
                )
                rows = [target]
                if action == "deactivate":
                    rows.append(
                        self.locator_fixture_row(
                            "b",
                            account_ref="reviewed-account@example.test",
                        )
                    )
                record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    rows,
                )
                record_before = record_path.read_bytes()
                before_sha256 = hashlib.sha256(record_before).hexdigest()
                snapshot_path = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_SNAPSHOT_DIR
                    / f"{before_sha256}.json"
                )
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                corrupt_bytes = b'{"corrupt":true}\n'
                snapshot_path.write_bytes(corrupt_bytes)
                receipts_root = archive_root / completion_workflows.EXTERNAL_LOCATOR_RECEIPTS_DIR
                receipts_before = {
                    path.relative_to(archive_root).as_posix()
                    for path in receipts_root.rglob("*.json")
                } if receipts_root.exists() else set()

                if action == "deactivate":
                    change_plan = completion_workflows.external_locator_deactivate_plan(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_id=str(target["locator_id"]),
                        keep_locator_id=str(rows[1]["locator_id"]),
                    )
                    blocked = completion_workflows.external_locator_deactivate(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_id=str(target["locator_id"]),
                        keep_locator_id=str(rows[1]["locator_id"]),
                        expected_plan_sha256="0" * 64,
                        reviewed_by="person:test",
                    )
                else:
                    locator_ref = (
                        "message-id:new-distinct-locator"
                        if action == "add"
                        else str(target["locator_ref"])
                    )
                    change_plan = completion_workflows.external_locator_plan(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_type="export_coordinate",
                        locator_ref=locator_ref,
                        service_ref=("mail-service" if action == "update" else None),
                    )
                    blocked = completion_workflows.external_locator_record(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_type="export_coordinate",
                        locator_ref=locator_ref,
                        service_ref=("mail-service" if action == "update" else None),
                        expected_plan_sha256="0" * 64,
                        reviewed_by="person:test",
                    )
                self.assertFalse(change_plan["ok"], change_plan)
                self.assertIn(
                    "external_locator_snapshot_mismatch",
                    change_plan["blockers"],
                )
                self.assertFalse(blocked["ok"], blocked)
                self.assertEqual(record_path.read_bytes(), record_before)
                self.assertEqual(snapshot_path.read_bytes(), corrupt_bytes)
                receipts_after = {
                    path.relative_to(archive_root).as_posix()
                    for path in receipts_root.rglob("*.json")
                } if receipts_root.exists() else set()
                self.assertEqual(receipts_after, receipts_before)

    def test_external_locator_forward_writes_roll_back_record_and_receipts(self) -> None:
        for action in ("record", "deactivate"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                zettel_id = "zet_20110228_fake_school_record"
                target = self.locator_fixture_row("a")
                rows = [target]
                if action == "deactivate":
                    rows.append(
                        self.locator_fixture_row(
                            "b",
                            account_ref="reviewed-account@example.test",
                        )
                    )
                record_path = self.write_locator_record_fixture(
                    archive_root,
                    zettel_id,
                    rows,
                )
                record_before = record_path.read_bytes()
                receipts_root = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_RECEIPTS_DIR
                )
                snapshots_root = (
                    archive_root
                    / completion_workflows.EXTERNAL_LOCATOR_SNAPSHOT_DIR
                )
                receipts_before = {
                    path.relative_to(archive_root).as_posix()
                    for path in receipts_root.rglob("*.json")
                } if receipts_root.exists() else set()
                snapshots_before = {
                    path.relative_to(archive_root).as_posix()
                    for path in snapshots_root.rglob("*.json")
                } if snapshots_root.exists() else set()

                if action == "record":
                    plan = completion_workflows.external_locator_plan(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_type="export_coordinate",
                        locator_ref="message-id:forward-rollback",
                    )
                else:
                    plan = completion_workflows.external_locator_deactivate_plan(
                        archive_root,
                        zettel_id=zettel_id,
                        locator_id=str(target["locator_id"]),
                        keep_locator_id=str(rows[1]["locator_id"]),
                    )
                self.assertTrue(plan["ok"], plan)

                original_write = (
                    completion_workflows.archive_services.write_bytes_atomic
                )
                failed_after_replace = False

                def fail_once_after_record_replace(path: Path, value: bytes) -> None:
                    nonlocal failed_after_replace
                    original_write(path, value)
                    if (
                        path.resolve() == record_path.resolve()
                        and not failed_after_replace
                    ):
                        failed_after_replace = True
                        raise OSError("synthetic post-replace fsync failure")

                with mock.patch.object(
                    completion_workflows.archive_services,
                    "write_bytes_atomic",
                    side_effect=fail_once_after_record_replace,
                ):
                    if action == "record":
                        blocked = completion_workflows.external_locator_record(
                            archive_root,
                            zettel_id=zettel_id,
                            locator_type="export_coordinate",
                            locator_ref="message-id:forward-rollback",
                            expected_plan_sha256=plan["summary"]["plan_sha256"],
                            reviewed_by="person:test",
                        )
                    else:
                        blocked = completion_workflows.external_locator_deactivate(
                            archive_root,
                            zettel_id=zettel_id,
                            locator_id=str(target["locator_id"]),
                            keep_locator_id=str(rows[1]["locator_id"]),
                            expected_plan_sha256=plan["summary"]["plan_sha256"],
                            reviewed_by="person:test",
                        )
                self.assertTrue(failed_after_replace)
                self.assertFalse(blocked["ok"], blocked)
                self.assertNotIn(
                    (
                        "external_locator_rollback_failed"
                        if action == "record"
                        else "external_locator_deactivate_rollback_failed"
                    ),
                    blocked["blockers"],
                )
                self.assertEqual(record_path.read_bytes(), record_before)
                receipts_after = {
                    path.relative_to(archive_root).as_posix()
                    for path in receipts_root.rglob("*.json")
                } if receipts_root.exists() else set()
                snapshots_after = {
                    path.relative_to(archive_root).as_posix()
                    for path in snapshots_root.rglob("*.json")
                } if snapshots_root.exists() else set()
                self.assertEqual(receipts_after, receipts_before)
                self.assertEqual(snapshots_after, snapshots_before)

    def test_external_locator_deactivate_uses_one_body_hash_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            target = self.locator_fixture_row("a")
            keeper = self.locator_fixture_row("b")
            self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [target, keeper],
            )
            with mock.patch.object(
                completion_workflows.archive_services,
                "require_readable_zettel_content",
                wraps=completion_workflows.archive_services.require_readable_zettel_content,
            ) as legacy_double_read:
                plan = completion_workflows.external_locator_deactivate_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_id=str(target["locator_id"]),
                    keep_locator_id=str(keeper["locator_id"]),
                )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(legacy_double_read.call_count, 0)

    def test_external_locator_revert_rolls_back_if_receipt_publish_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            first_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:rollback-first",
            )
            first = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:rollback-first",
                expected_plan_sha256=first_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            second_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:rollback-second",
            )
            second = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:rollback-second",
                expected_plan_sha256=second_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            record_path = archive_root / second["summary"]["record_path"]
            record_before = record_path.read_bytes()
            receipts_root = archive_root / completion_workflows.EXTERNAL_LOCATOR_RECEIPTS_DIR
            receipt_paths_before = {
                path.relative_to(archive_root).as_posix()
                for path in receipts_root.rglob("*.json")
            }
            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=second["summary"]["receipt_path"],
            )

            def fail_after_receipt_publish(path: Path, value: bytes) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
                raise OSError("synthetic receipt fsync failure")

            with mock.patch.object(
                completion_workflows.archive_services,
                "_write_bytes_create_if_absent",
                side_effect=fail_after_receipt_publish,
            ):
                blocked = completion_workflows.external_locator_revert(
                    archive_root,
                    receipt=second["summary"]["receipt_path"],
                    expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                    reviewed_by="person:test",
                )
            self.assertFalse(blocked["ok"], blocked)
            self.assertIn("external_locator_revert_write_failed", blocked["blockers"])
            self.assertEqual(record_path.read_bytes(), record_before)
            receipt_paths_after = {
                path.relative_to(archive_root).as_posix()
                for path in receipts_root.rglob("*.json")
            }
            self.assertEqual(receipt_paths_after, receipt_paths_before)

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20240504_fake_lunch_thought"
            plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:first-add-receipt-failure",
            )
            written = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=zettel_id,
                locator_type="export_coordinate",
                locator_ref="synthetic:first-add-receipt-failure",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            record_path = archive_root / written["summary"]["record_path"]
            record_before = record_path.read_bytes()
            revert_plan = completion_workflows.external_locator_revert_plan(
                archive_root,
                receipt=written["summary"]["receipt_path"],
            )

            def fail_first_add_receipt(path: Path, value: bytes) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
                raise OSError("synthetic first-add receipt fsync failure")

            with mock.patch.object(
                completion_workflows.archive_services,
                "_write_bytes_create_if_absent",
                side_effect=fail_first_add_receipt,
            ):
                blocked = completion_workflows.external_locator_revert(
                    archive_root,
                    receipt=written["summary"]["receipt_path"],
                    expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                    reviewed_by="person:test",
                )
            self.assertFalse(blocked["ok"], blocked)
            self.assertNotIn(
                "external_locator_revert_rollback_failed",
                blocked["blockers"],
            )
            self.assertEqual(record_path.read_bytes(), record_before)

    def test_external_locator_lexical_reparse_guard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20110228_fake_school_record"
            self.write_locator_record_fixture(
                archive_root,
                zettel_id,
                [self.locator_fixture_row("a")],
            )
            with mock.patch.object(
                completion_workflows.archive_services,
                "zet_revision_path_has_symlink_component",
                return_value=True,
            ):
                plan = completion_workflows.external_locator_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_type="export_coordinate",
                    locator_ref="synthetic:reparse-guard",
                )
            self.assertFalse(plan["ok"], plan)
            self.assertIn("external_locator_record_unsafe", plan["blockers"])

            def receipts_only(_root: Path, path: Path) -> bool:
                return "receipts" in {
                    part.casefold() for part in path.parts
                }

            with mock.patch.object(
                completion_workflows.archive_services,
                "zet_revision_path_has_symlink_component",
                side_effect=receipts_only,
            ):
                receipt_plan = completion_workflows.external_locator_plan(
                    archive_root,
                    zettel_id=zettel_id,
                    locator_type="export_coordinate",
                    locator_ref="synthetic:receipt-reparse-guard",
                )
            self.assertFalse(receipt_plan["ok"], receipt_plan)
            self.assertIn(
                "external_locator_receipt_path_unsafe",
                receipt_plan["blockers"],
            )

    def test_objet_capture_batch_uses_one_reviewed_plan_and_converges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            request_path = self.capture_batch_fixture(
                archive_root,
                count=3,
                title_length=241,
            )
            before = {
                path.relative_to(archive_root).as_posix()
                for path in archive_root.rglob("*")
                if path.is_file()
            }
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assert_schema_instance(
                "objet-capture-batch-request.schema.json",
                json.loads(request_path.read_text(encoding="utf-8")),
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["item_count"], 3)
            self.assertEqual(plan["summary"]["ready_item_count"], 3)
            self.assertEqual(plan["summary"]["blocked_item_count"], 0)
            self.assertEqual(plan["summary"]["convergence_model"], "bounded_per_item_with_replay")
            self.assertFalse(plan["summary"]["all_or_nothing_claimed"])
            self.assertFalse(plan["privacy_guards"]["titles_echoed"])
            after_plan = {
                path.relative_to(archive_root).as_posix()
                for path in archive_root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after_plan)

            applied = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["state"], "written")
            self.assertEqual(
                applied["summary"]["capture_summary"]["captured"],
                3,
            )
            self.assertTrue(
                (
                    archive_root
                    / applied["summary"]["batch_receipt_path"]
                ).is_file()
            )
            self.assert_schema_instance(
                "objet-capture-batch-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / applied["summary"]["batch_receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            self.assertTrue(
                (
                    archive_root
                    / applied["summary"]["capture_receipt_path"]
                ).is_file()
            )
            for index in range(3):
                data = f"synthetic-{index}\n".encode("utf-8")
                digest = hashlib.sha256(data).hexdigest()
                self.assertTrue(
                    (
                        archive_root
                        / "objects"
                        / "sha256"
                        / digest[:2]
                        / digest
                    ).is_file()
                )

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            self.assertEqual(replay_plan["summary"]["would_skip"], 3)
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(
                replay["summary"]["capture_summary"]["skipped"],
                3,
            )

    def test_zettel_objet_link_writes_structured_asset_and_reverts_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20240504_fake_lunch_thought"
            zettel_path = archive_root / "zettels" / f"{zettel_id}.md"
            before_bytes = zettel_path.read_bytes()
            object_id = "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
            private_label = "Reviewed private source label"

            plan_code, plan_output = self.run_cli(
                [
                    "zettel-objet-link",
                    str(archive_root),
                    "--zettel-id",
                    zettel_id,
                    "--object-id",
                    object_id,
                    "--role",
                    "source_document",
                    "--label",
                    private_label,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(plan_code, 0, plan_output)
            self.assertNotIn(private_label, plan_output)
            plan = json.loads(plan_output)
            self.assertTrue(plan["ok"], plan)
            self.assertTrue(plan["summary"]["manifest_record_verified"])
            self.assertEqual(plan["summary"]["current_asset_count"], 0)

            apply_code, apply_output = self.run_cli(
                [
                    "zettel-objet-link",
                    str(archive_root),
                    "--zettel-id",
                    zettel_id,
                    "--object-id",
                    object_id,
                    "--role",
                    "source_document",
                    "--label",
                    private_label,
                    "--expected-plan-sha256",
                    plan["summary"]["plan_sha256"],
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(apply_code, 0, apply_output)
            self.assertNotIn(private_label, apply_output)
            applied = json.loads(apply_output)
            self.assertEqual(applied["state"], "written")
            frontmatter, _body = (
                completion_workflows.archive_services.require_readable_zettel_content(
                    zettel_path
                )
            )
            self.assertIn(
                {
                    "object_id": object_id,
                    "role": "source_document",
                    "label": private_label,
                },
                frontmatter["assets"],
            )
            self.assertEqual(
                completion_workflows.archive_services.validate_schema(
                    frontmatter,
                    "zettel-frontmatter.schema.json",
                ),
                [],
            )
            receipt_path = archive_root / applied["summary"]["receipt_path"]
            self.assert_schema_instance(
                "zettel-objet-link-receipt.schema.json",
                json.loads(receipt_path.read_text(encoding="utf-8")),
            )

            duplicate = completion_workflows.zettel_objet_link_plan(
                archive_root,
                zettel_id=zettel_id,
                object_id=object_id,
                role="evidence",
            )
            self.assertFalse(duplicate["ok"])
            self.assertIn("zettel_objet_link_already_present", duplicate["blockers"])

            revert_plan = completion_workflows.zettel_objet_link_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            self.assertTrue(revert_plan["ok"], revert_plan)
            reverted = completion_workflows.zettel_objet_link_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(zettel_path.read_bytes(), before_bytes)
            self.assert_schema_instance(
                "zettel-objet-link-revert-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / reverted["summary"]["revert_receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )

    def test_zettel_objet_link_revert_blocks_after_unrelated_zettel_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            zettel_id = "zet_20240504_fake_lunch_thought"
            object_id = "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
            plan = completion_workflows.zettel_objet_link_plan(
                archive_root,
                zettel_id=zettel_id,
                object_id=object_id,
                role="evidence",
            )
            applied = completion_workflows.zettel_objet_link_apply(
                archive_root,
                zettel_id=zettel_id,
                object_id=object_id,
                role="evidence",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            zettel_path = archive_root / "zettels" / f"{zettel_id}.md"
            zettel_path.write_bytes(zettel_path.read_bytes() + b"\nLater reviewed change.\n")

            revert_plan = completion_workflows.zettel_objet_link_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )

            self.assertFalse(revert_plan["ok"])
            self.assertIn(
                "zettel_objet_link_current_zettel_changed",
                revert_plan["blockers"],
            )

    def test_discard_unminted_draft_is_receipted_and_exactly_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            draft_relative = "inbox/zet_20260519_draft_ai_lunch_note.md"
            draft_path = archive_root / draft_relative
            before_bytes = draft_path.read_bytes()
            reason = "Human decided this captured note should not be published."

            plan_code, plan_output = self.run_cli(
                [
                    "discard-draft",
                    str(archive_root),
                    "--path",
                    draft_relative,
                    "--reason",
                    reason,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(plan_code, 0, plan_output)
            self.assertNotIn(reason, plan_output)
            plan = json.loads(plan_output)
            self.assertTrue(plan["ok"], plan)
            self.assertTrue(plan["summary"]["exact_byte_restore_supported"])

            apply_code, apply_output = self.run_cli(
                [
                    "discard-draft",
                    str(archive_root),
                    "--path",
                    draft_relative,
                    "--reason",
                    reason,
                    "--expected-plan-sha256",
                    plan["summary"]["plan_sha256"],
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(apply_code, 0, apply_output)
            self.assertNotIn(reason, apply_output)
            discarded = json.loads(apply_output)
            self.assertEqual(discarded["state"], "discarded")
            self.assertFalse(draft_path.exists())
            snapshot_path = archive_root / discarded["summary"]["snapshot_path"]
            self.assertEqual(snapshot_path.read_bytes(), before_bytes)
            receipt_path = archive_root / discarded["summary"]["receipt_path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["reason"], reason)
            self.assert_schema_instance("draft-discard-receipt.schema.json", receipt)

            audit = completion_workflows.archive_services.inbox_pipeline_audit(
                archive_root,
                dry_run=True,
            )
            self.assertEqual(
                audit["summary"]["intentionally_discarded_draft_receipt_count"],
                1,
            )

            restore_plan = completion_workflows.draft_discard_restore_plan(
                archive_root,
                receipt=discarded["summary"]["receipt_path"],
            )
            self.assertTrue(restore_plan["ok"], restore_plan)
            restored = completion_workflows.draft_discard_restore(
                archive_root,
                receipt=discarded["summary"]["receipt_path"],
                expected_plan_sha256=restore_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(restored["ok"], restored)
            self.assertEqual(draft_path.read_bytes(), before_bytes)
            restore_receipt = json.loads(
                (
                    archive_root
                    / restored["summary"]["restore_receipt_path"]
                ).read_text(encoding="utf-8")
            )
            self.assert_schema_instance(
                "draft-discard-restore-receipt.schema.json",
                restore_receipt,
            )

    def test_discard_draft_blocks_minted_twin_and_routes_to_retire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            draft_relative = "inbox/zet_20260519_draft_ai_lunch_note.md"
            retire_plan = (
                completion_workflows.archive_services.minted_draft_retirement_plan(
                    archive_root,
                    relative_path=draft_relative,
                )
            )
            self.assertFalse(retire_plan["ok"])
            self.assertTrue(
                any(
                    "discard-draft" in action
                    for action in retire_plan["next_safe_actions"]
                )
            )
            mint_receipt = (
                archive_root
                / "receipts"
                / "mint"
                / "zet_20260519_draft_ai_lunch_note.mint.json"
            )
            mint_receipt.parent.mkdir(parents=True, exist_ok=True)
            mint_receipt.write_text("{}\n", encoding="utf-8")

            discard = completion_workflows.draft_discard_plan(
                archive_root,
                relative_path=draft_relative,
                reason="This must use the minted draft retirement path.",
            )

            self.assertFalse(discard["ok"])
            self.assertIn(
                "discard_draft_mint_receipt_present_use_retire_draft",
                discard["blockers"],
            )
            self.assertTrue(
                any("retire-draft" in action for action in discard["next_safe_actions"])
            )

    def test_objet_capture_batch_preflights_synthetic_508_and_names_title_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            request_path = self.capture_batch_fixture(
                archive_root,
                count=508,
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["item_count"], 508)
            self.assertEqual(plan["summary"]["ready_item_count"], 508)
            self.assertEqual(plan["summary"]["would_capture"], 508)
            self.assertEqual(len(plan["items"]), 508)

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            request_path = self.capture_batch_fixture(
                archive_root,
                count=1,
                title_length=(
                    completion_workflows.OBJET_CAPTURE_BATCH_TITLE_MAX_CHARACTERS
                    + 1
                ),
            )
            blocked = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertFalse(blocked["ok"])
            self.assertIn("title_too_long", blocked["blockers"])
            self.assertNotIn(
                "T" * 100,
                json.dumps(blocked, ensure_ascii=False),
            )

    def test_markup_normalization_snapshots_applies_and_reverts_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            target = self.write_markup_zettel(
                archive_root,
                "zet_20260804_markup_normalization",
                "Before\n"
                "<empty-block/>\n"
                "<div><span class=\"migration\">Visible text</span></div>\n"
                "<strong>Compatible HTML remains</strong>\n",
            )
            before_bytes = target.read_bytes()
            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertTrue(plan["ok"], plan)
            selected = next(
                item
                for item in plan["items"]
                if item["zettel_id"]
                == "zet_20260804_markup_normalization"
            )
            self.assertEqual(selected["state"], "ready")
            self.assertEqual(selected["counts"]["empty_block"], 1)
            self.assertEqual(selected["counts"]["span"], 1)
            self.assertEqual(
                selected["counts"]["structural_container"],
                2,
            )
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after_text = target.read_text(encoding="utf-8")
            self.assertNotIn("<empty-block", after_text)
            self.assertNotIn("<span", after_text)
            self.assertNotIn("<div", after_text)
            self.assertIn("Visible text", after_text)
            self.assertIn(
                "<strong>Compatible HTML remains</strong>",
                after_text,
            )
            receipt = applied["summary"]["receipt_path"]
            self.assert_schema_instance(
                "markup-normalization-receipt.schema.json",
                json.loads(
                    (archive_root / receipt).read_text(encoding="utf-8")
                ),
            )
            self.assert_schema_instance(
                "markup-normalization-journal.schema.json",
                json.loads(
                    (
                        archive_root / applied["summary"]["journal_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            revert_plan = (
                completion_workflows.markup_normalization_revert_plan(
                    archive_root,
                    receipt=receipt,
                )
            )
            self.assertTrue(revert_plan["ok"], revert_plan)
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=receipt,
                expected_plan_sha256=revert_plan["summary"][
                    "plan_sha256"
                ],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assert_schema_instance(
                "markup-normalization-revert-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / reverted["summary"]["receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            self.assertEqual(target.read_bytes(), before_bytes)

    def test_markup_normalization_removes_exact_generated_toc_marker_and_reverts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            paths: list[Path] = []
            before_by_path: dict[Path, bytes] = {}
            expected_after_by_path: dict[Path, bytes] = {}
            for label, newline in (("lf", "\n"), ("crlf", "\r\n")):
                zettel_id = f"zet_20260809_generated_toc_{label}"
                path = archive_root / "zettels" / f"{zettel_id}.md"
                raw = (
                    "---"
                    + newline
                    + f"id: {zettel_id}"
                    + newline
                    + f"title: Generated TOC {label}"
                    + newline
                    + "status: canonical"
                    + newline
                    + "kind: note"
                    + newline
                    + "---"
                    + newline
                    + "<unknown:table_of_contents/>"
                    + newline
                    + "Authored body remains."
                    + newline
                ).encode("utf-8")
                path.write_bytes(raw)
                paths.append(path)
                before_by_path[path] = raw
                expected_after_by_path[path] = raw.replace(
                    ("<unknown:table_of_contents/>" + newline).encode(
                        "utf-8"
                    ),
                    b"",
                    1,
                )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertTrue(plan["ok"], plan)
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            for label in ("lf", "crlf"):
                item = by_id[f"zet_20260809_generated_toc_{label}"]
                self.assertEqual(item["state"], "ready")
                self.assertEqual(item["counts"]["table_of_contents"], 1)

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            for path in paths:
                after = path.read_bytes()
                self.assertEqual(after, expected_after_by_path[path])

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            for path in paths:
                self.assertEqual(path.read_bytes(), before_by_path[path])

    def test_markup_normalization_generated_toc_rule_is_narrow_and_context_safe(self) -> None:
        cases = {
            "attribute": '<unknown:table_of_contents color="blue"/>\n',
            "paired": "<unknown:table_of_contents></unknown:table_of_contents>\n",
            "inline": "Before <unknown:table_of_contents/> after\n",
            "repeated": (
                "<unknown:table_of_contents/>\n"
                "<unknown:table_of_contents/>\n"
            ),
            "mid_body": "Authored first.\n<unknown:table_of_contents/>\n",
            "empty_block_precedes": (
                "<empty-block/>\n<unknown:table_of_contents/>\nBody\n"
            ),
            "two_empty_blocks_precede": (
                "<empty-block/>\n<empty-block/>\n"
                "<unknown:table_of_contents/>\nBody\n"
            ),
            "indented": "\t<unknown:table_of_contents/>\n",
            "fenced": (
                "```html\n<unknown:table_of_contents/>\n```\n"
            ),
            "inline_code": "`<unknown:table_of_contents/>`\n",
            "comment": "<!-- <unknown:table_of_contents/> -->\n",
            "link_destination": (
                "[literal](https://example.test/<unknown:table_of_contents/>)\n"
            ),
        }
        for label, body in cases.items():
            with self.subTest(label=label):
                result = completion_workflows._normalize_markup_body(body)
                self.assertEqual(result["normalized_body"], body)
                self.assertFalse(result["changed"])
                self.assertTrue(result["blocker_codes"], result)
                self.assertEqual(result["counts"]["table_of_contents"], 0)

    def test_markup_normalization_only_ready_keeps_toc_with_other_unknown_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            safe_path = self.write_markup_zettel(
                archive_root,
                "zet_20260809_generated_toc_only_ready_safe",
                "<unknown:table_of_contents/>\nSafe body.\n",
            )
            blocked_path = self.write_markup_zettel(
                archive_root,
                "zet_20260809_generated_toc_only_ready_blocked",
                "<unknown:table_of_contents/>\n<unknown:synced_block/>\n",
            )
            safe_before = safe_path.read_bytes()
            blocked_before = blocked_path.read_bytes()

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "partial_ready")
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            blocked_item = by_id[
                "zet_20260809_generated_toc_only_ready_blocked"
            ]
            self.assertEqual(blocked_item["state"], "blocked")
            self.assertEqual(
                blocked_item["before_sha256"],
                blocked_item["after_sha256"],
            )

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertNotEqual(safe_path.read_bytes(), safe_before)
            self.assertNotIn(
                b"<unknown:table_of_contents/>",
                safe_path.read_bytes(),
            )
            self.assertEqual(blocked_path.read_bytes(), blocked_before)

    def test_markup_normalization_converts_reviewed_table_to_gfm_without_visible_text_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            target = self.write_markup_zettel(
                archive_root,
                "zet_20260807_table_normalization",
                "<columns><column>Before table</column></columns>\n"
                "<table class=\"notion-table\">\n"
                "<colgroup><col><col></colgroup>\n"
                "<thead><tr><th align=\"left\">Name</th><th style=\"text-align: right\">Value</th></tr></thead>\n"
                "<tbody><tr><td>Alpha | Beta</td><td>42</td></tr></tbody>\n"
                "</table>\n"
                "<mention-date start=\"2026-08-07\">August 7</mention-date>\n",
            )
            before = target.read_bytes()

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )

            self.assertTrue(plan["ok"], plan)
            item = next(
                row
                for row in plan["items"]
                if row["zettel_id"] == "zet_20260807_table_normalization"
            )
            self.assertEqual(item["state"], "ready")
            self.assertEqual(item["counts"]["table"], 1)
            self.assertEqual(item["counts"]["table_blocked"], 0)
            self.assertEqual(item["counts"]["mention_date"], 1)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = target.read_text(encoding="utf-8")
            self.assertIn("| Name | Value |", after)
            self.assertIn("| :--- | ---: |", after)
            self.assertIn(r"| Alpha \| Beta | 42 |", after)
            self.assertIn("Before table", after)
            self.assertIn("August 7", after)
            self.assertNotIn("<table", after)
            self.assertNotIn("<columns", after)
            self.assertNotIn("<mention-date", after)

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(target.read_bytes(), before)

    def test_markup_normalization_blocks_table_spans_and_nested_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            self.write_markup_zettel(
                archive_root,
                "zet_20260807_table_span_blocked",
                "<table><tr><td rowspan=\"2\">A</td><td>B</td></tr><tr><td>C</td></tr></table>\n",
            )
            self.write_markup_zettel(
                archive_root,
                "zet_20260807_nested_table_blocked",
                "<table><tr><td><table><tr><td>Nested</td></tr></table></td></tr></table>\n",
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )

            self.assertFalse(plan["ok"])
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            self.assertIn(
                "markup_table_span_unsupported",
                by_id["zet_20260807_table_span_blocked"]["blocker_codes"],
            )
            self.assertIn(
                "markup_table_nested_unsupported",
                by_id["zet_20260807_nested_table_blocked"]["blocker_codes"],
            )

    def test_markup_normalization_table_cells_preserve_span_inline_content_and_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            target = self.write_markup_zettel(
                archive_root,
                "zet_20260809_table_cell_safe_inline",
                '<table header-row="true">\n'
                '<tr><td>Kind</td><td>Value</td></tr>\n'
                '<tr><td>span</td><td><span color="red" underline="true" '
                'discussion-urls="https://example.test/discussion/1">'
                '<strong>Alpha | Beta</strong></span></td></tr>\n'
                '<tr><td>start</td><td><mention-date start="2026-08-09"/></td></tr>\n'
                '<tr><td>range</td><td><mention-date start="2026-08-09" '
                'end="2026-08-10"/></td></tr>\n'
                '<tr><td>entity</td><td>&lt;b&gt;Literal&lt;/b&gt;</td></tr>\n'
                '<tr><td>timed</td><td><mention-date start="2026-08-09" '
                'startTime="09:30" timeZone="Asia/Seoul"/></td></tr>\n'
                '<tr><td>full</td><td><mention-date start="2026-08-09" '
                'end="2026-08-10" startTime="09:30" endTime="10:45" '
                'timeZone="Asia/Seoul"/></td></tr>\n'
                '</table>\n',
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertTrue(plan["ok"], plan)
            item = next(
                row
                for row in plan["items"]
                if row["zettel_id"] == "zet_20260809_table_cell_safe_inline"
            )
            self.assertEqual(item["state"], "ready")
            self.assertEqual(item["counts"]["table"], 1)
            self.assertEqual(item["counts"]["table_blocked"], 0)

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = target.read_text(encoding="utf-8")
            self.assertIn(
                r"| span | <strong>Alpha \| Beta</strong> |",
                after,
            )
            self.assertIn("| start | 2026-08-09 |", after)
            self.assertIn("| range | 2026-08-09 – 2026-08-10 |", after)
            self.assertIn(
                "| entity | &lt;b&gt;Literal&lt;/b&gt; |",
                after,
            )
            self.assertNotIn("| entity | <b>Literal</b> |", after)
            self.assertIn(
                "| timed | 2026-08-09 09:30 (Asia/Seoul) |",
                after,
            )
            self.assertIn(
                "| full | 2026-08-09 09:30 – 2026-08-10 10:45 "
                "(Asia/Seoul) |",
                after,
            )
            self.assertNotIn("<span", after)
            self.assertNotIn("<mention-date", after)

    def test_markup_normalization_tables_require_standalone_blocks(self) -> None:
        table = "<table><tr><td>Visible</td></tr></table>"
        blocked_bodies = {
            "blockquote": f"> {table}\n",
            "list_item": f"- {table}\n",
            "unordered_list_continuation": f"- Item\n  {table}\n",
            "ordered_list_continuation": f"1. Item\n   {table}\n",
            "inline_prefix": f"Before {table}\n",
            "inline_suffix": f"{table} After\n",
            "indented_code": f"    {table}\n",
        }

        for label, body in blocked_bodies.items():
            with self.subTest(label=label):
                normalized, count, blockers = (
                    completion_workflows._normalize_gfm_tables(body)
                )
                self.assertEqual(normalized, body)
                self.assertEqual(count, 0)
                self.assertIn(
                    "markup_table_block_context_unsupported",
                    blockers,
                )

        ordinary_indented_raw_html = f"  {table}\n"
        normalized, count, blockers = (
            completion_workflows._normalize_gfm_tables(
                ordinary_indented_raw_html
            )
        )
        self.assertEqual(blockers, [])
        self.assertEqual(count, 1)
        self.assertIn("| Visible |", normalized)

        standalone_tab_table = (
            '\t<table class="notion-table">\n'
            "\t\t<tr><td>Visible</td></tr>\n"
            "\t</table>\n"
        )
        normalized, count, blockers = (
            completion_workflows._normalize_gfm_tables(standalone_tab_table)
        )
        self.assertEqual(normalized, standalone_tab_table)
        self.assertEqual(count, 0)
        self.assertIn("markup_table_block_context_unsupported", blockers)

        notion_raw_html = (
            "<columns>\n"
            '\t<table class="notion-table">\n'
            "\t\t<tr><td>Visible</td></tr>\n"
            "\t</table>\n"
            "</columns>\n"
        )
        normalized, count, blockers = (
            completion_workflows._normalize_gfm_tables(notion_raw_html)
        )
        self.assertEqual(blockers, [])
        self.assertEqual(count, 1)
        self.assertIn("| Visible |", normalized)

    def test_markup_normalization_tables_fail_closed_on_malformed_structure(self) -> None:
        blocked_bodies = {
            "trailing_orphan_table_close": (
                "<table><tr><td>A</td></tr></table></table>\n"
            ),
            "orphan_unknown_close_inside": (
                "<table><tr><td>A</td></tr></section></table>\n"
            ),
            "self_closing_row": (
                "<table><tr/><tr><td>A</td></tr></table>\n"
            ),
            "self_closing_section": (
                "<table><tbody/><tr><td>A</td></tr></table>\n"
            ),
            "empty_row": (
                "<table><tr></tr><tr><td>A</td></tr></table>\n"
            ),
            "malformed_table_close": (
                "<table><tr><td>A</td></tr></table extra>\n"
            ),
            "malformed_cell_close": (
                "<table><tr><td>A</td extra></tr></table>\n"
            ),
            "malformed_row_close": (
                "<table><tr><td>A</td></tr extra></table>\n"
            ),
            "self_closing_table": "<table/>\n",
        }

        for label, body in blocked_bodies.items():
            with self.subTest(label=label):
                normalized, count, blockers = (
                    completion_workflows._normalize_gfm_tables(body)
                )
                self.assertEqual(normalized, body)
                self.assertEqual(count, 0)
                self.assertIn("markup_table_structure_invalid", blockers)

    def test_markup_normalization_table_cells_preserve_unicode_space_attributes_and_breaks(self) -> None:
        body = (
            "<table><tr><td>\u00a0A\u2003B\u3000</td>"
            '<td><abbr title="Two  spaces">Label</abbr></td>'
            "<td>First<br><br/>Third</td>"
            "<td>Research &Development</td></tr></table>\n"
        )

        normalized, count, blockers = (
            completion_workflows._normalize_gfm_tables(body)
        )

        self.assertEqual(blockers, [])
        self.assertEqual(count, 1)
        self.assertIn("| \u00a0A\u2003B\u3000 |", normalized)
        self.assertIn('<abbr title="Two  spaces">Label</abbr>', normalized)
        self.assertIn("First<br><br>Third", normalized)
        self.assertIn("Research &amp;Development", normalized)

    def test_markup_normalization_table_cells_fail_closed_on_unterminated_entities(self) -> None:
        body = "<table><tr><td>A &amp B</td></tr></table>\n"

        normalized, count, blockers = (
            completion_workflows._normalize_gfm_tables(body)
        )

        self.assertEqual(normalized, body)
        self.assertEqual(count, 0)
        self.assertIn("markup_table_entity_unterminated", blockers)

    def test_markup_normalization_table_cells_fail_closed_on_invalid_pairs_and_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            fixtures = {
                "zet_20260809_table_span_unclosed": (
                    "<table><tr><td><span>Visible</td></tr></table>\n",
                    "markup_table_cell_markup_unbalanced",
                ),
                "zet_20260809_table_span_orphan": (
                    "<table><tr><td>Visible</span></td></tr></table>\n",
                    "markup_table_cell_markup_unbalanced",
                ),
                "zet_20260809_table_span_mismatch": (
                    "<table><tr><td><span><strong>Visible</span></strong>"
                    "</td></tr></table>\n",
                    "markup_table_cell_markup_unbalanced",
                ),
                "zet_20260809_table_mention_date_paired": (
                    '<table><tr><td><mention-date start="2026-08-09">'
                    "Visible</mention-date></td></tr></table>\n",
                    "markup_table_cell_markup_unsupported",
                ),
                "zet_20260809_table_mention_date_invalid": (
                    '<table><tr><td><mention-date start="2026-99-99"/>'
                    "</td></tr></table>\n",
                    "markup_mention_date_attributes_unsupported",
                ),
                "zet_20260809_table_duplicate_table_attribute": (
                    '<table header-row="true" header-row="false">'
                    "<tr><td>Visible</td></tr></table>\n",
                    "markup_table_attributes_duplicate",
                ),
                "zet_20260809_table_duplicate_cell_attribute": (
                    '<table><tr><td rowspan="2" rowspan="1">Visible</td>'
                    "</tr></table>\n",
                    "markup_table_attributes_duplicate",
                ),
                "zet_20260809_table_visible_text_outside_cell": (
                    "<table>VISIBLE<tr><td>A</td></tr>TAIL</table>\n",
                    "markup_table_structure_invalid",
                ),
                "zet_20260809_table_visible_text_in_section": (
                    "<table><thead>VISIBLE<tr><td>A</td></tr></thead>"
                    "</table>\n",
                    "markup_table_structure_invalid",
                ),
                "zet_20260809_table_section_attribute": (
                    '<table><tbody data-role="important"><tr><td>A</td>'
                    "</tr></tbody></table>\n",
                    "markup_table_structure_attributes_unsupported",
                ),
                "zet_20260809_table_row_attribute": (
                    '<table><tr data-role="important"><td>A</td></tr>'
                    "</table>\n",
                    "markup_table_structure_attributes_unsupported",
                ),
                "zet_20260809_table_col_inside_cell": (
                    '<table><tr><td>A<col width="5"></td></tr></table>\n',
                    "markup_table_structure_invalid",
                ),
                "zet_20260809_table_section_mismatch": (
                    "<table><thead><tr><td>A</td></tr></tfoot></table>\n",
                    "markup_table_structure_invalid",
                ),
                "zet_20260809_table_alignment_conflict": (
                    '<table><tr><td align="right" '
                    'style="text-align:left">A</td></tr></table>\n',
                    "markup_table_alignment_conflict",
                ),
            }
            before_by_id: dict[str, bytes] = {}
            path_by_id: dict[str, Path] = {}
            for zettel_id, (body, _blocker) in fixtures.items():
                path = self.write_markup_zettel(archive_root, zettel_id, body)
                path_by_id[zettel_id] = path
                before_by_id[zettel_id] = path.read_bytes()

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(plan["ok"], plan)
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            for zettel_id, (_body, blocker) in fixtures.items():
                with self.subTest(zettel_id=zettel_id):
                    self.assertEqual(by_id[zettel_id]["state"], "blocked")
                    self.assertIn(blocker, by_id[zettel_id]["blocker_codes"])
                    self.assertEqual(path_by_id[zettel_id].read_bytes(), before_by_id[zettel_id])

    def test_markup_normalization_table_cells_only_ready_keeps_unsafe_markup_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            ready = self.write_markup_zettel(
                archive_root,
                "zet_20260809_table_cell_ready_span",
                '<table><tr><td><span color="blue">Safe | text</span>'
                "</td></tr></table>\n",
            )
            blocked_bodies = {
                "zet_20260809_table_cell_input": (
                    '<table><tr><td><input type="text"></td></tr></table>\n'
                ),
                "zet_20260809_table_cell_script": (
                    "<table><tr><td><script>alert(1)</script></td></tr></table>\n"
                ),
                "zet_20260809_table_cell_mention_page": (
                    '<table><tr><td><mention-page ref="private"/>'
                    "</td></tr></table>\n"
                ),
                "zet_20260809_table_cell_blockquote": (
                    "<table><tr><td><blockquote>Block</blockquote>"
                    "</td></tr></table>\n"
                ),
                "zet_20260809_table_cell_unsafe_url": (
                    '<table><tr><td><a href="javascript:alert(1)" '
                    'onclick="alert(1)">Unsafe</a></td></tr></table>\n'
                ),
                "zet_20260809_table_cell_unsafe_span_attribute": (
                    '<table><tr><td><span onclick="alert(1)">Unsafe</span>'
                    "</td></tr></table>\n"
                ),
                "zet_20260809_table_cell_unsafe_discussion_url": (
                    '<table><tr><td><span discussion-urls="javascript:'
                    'alert(1)">Unsafe</span></td></tr></table>\n'
                ),
                "zet_20260809_table_cell_comment": (
                    "<table><tr><td>Before<!-- hidden -->After</td></tr></table>\n"
                ),
                "zet_20260809_table_cell_orphan_inline": (
                    "<table><tr><td>Before</strong>After</td></tr></table>\n"
                ),
            }
            blocked_paths: dict[str, Path] = {}
            blocked_before: dict[str, bytes] = {}
            for zettel_id, body in blocked_bodies.items():
                path = self.write_markup_zettel(archive_root, zettel_id, body)
                blocked_paths[zettel_id] = path
                blocked_before[zettel_id] = path.read_bytes()

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "partial_ready")
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            self.assertEqual(
                by_id["zet_20260809_table_cell_ready_span"]["state"],
                "ready",
            )
            for zettel_id in blocked_bodies:
                with self.subTest(zettel_id=zettel_id):
                    self.assertEqual(by_id[zettel_id]["state"], "blocked")
                    self.assertTrue(by_id[zettel_id]["blocker_codes"])

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertIn(r"Safe \| text", ready.read_text(encoding="utf-8"))
            self.assertNotIn("<span", ready.read_text(encoding="utf-8"))
            for zettel_id in blocked_bodies:
                with self.subTest(zettel_id=zettel_id):
                    self.assertEqual(
                        blocked_paths[zettel_id].read_bytes(),
                        blocked_before[zettel_id],
                    )

    def test_markup_normalization_blocks_unknown_and_binding_tags_but_preserve_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            self.write_markup_zettel(
                archive_root,
                "zet_20260804_markup_blocked",
                "<mention ref=\"opaque\"/>\n"
                "<custom-semantic>Do not delete me</custom-semantic>\n",
            )
            normalize = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(normalize["ok"])
            self.assertIn(
                "markup_reference_binding_required",
                normalize["blockers"],
            )
            self.assertIn(
                "unknown_semantic_markup",
                normalize["blockers"],
            )
            preserve = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="preserve",
                max_items=1000,
                max_changes=1000,
            )
            self.assertTrue(preserve["ok"], preserve)
            self.assertEqual(preserve["summary"]["ready_change_count"], 0)
            self.assertEqual(preserve["would_change"], [])
            self.assertGreaterEqual(
                preserve["summary"]["preserved_zettel_count"],
                1,
            )

    def test_markup_normalization_only_ready_applies_safe_subset_and_leaves_blocked_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            ready = self.write_markup_zettel(
                archive_root,
                "zet_20260807_only_ready_safe",
                "<span>Safe visible text</span>\n",
            )
            blocked = self.write_markup_zettel(
                archive_root,
                "zet_20260807_only_ready_blocked",
                "<custom-semantic>Keep exact blocked text</custom-semantic>\n",
            )
            blocked_before = blocked.read_bytes()

            strict = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(strict["ok"], strict)
            self.assertIsNone(strict["summary"]["plan_sha256"])

            selected = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
            )
            self.assertTrue(selected["ok"], selected)
            self.assertEqual(selected["state"], "partial_ready")
            self.assertEqual(selected["summary"]["selection_mode"], "ready_only")
            self.assertEqual(selected["summary"]["ready_change_count"], 1)
            self.assertEqual(selected["summary"]["blocked_zettel_count"], 1)
            self.assertIsNotNone(selected["summary"]["plan_sha256"])

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                only_ready=True,
                expected_plan_sha256=selected["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertNotIn("<span>", ready.read_text(encoding="utf-8"))
            self.assertEqual(blocked.read_bytes(), blocked_before)

    def test_markup_normalization_preserves_dates_synced_content_and_table_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            target = self.write_markup_zettel(
                archive_root,
                "zet_20260807_letter113_markup_shapes",
                '<mention-date start="2026-08-07" starttime="09:30" timezone="Asia/Seoul"/>\n'
                '<synced_block url="private-source">Primary synced text</synced_block>\n'
                '<synced_block_reference url="private-source">Reference snapshot</synced_block_reference>\n'
                '<table header-row="true" header-column="true">\n'
                '<colgroup><col width="160"><col width="320"></colgroup>\n'
                '<tr><td>Name</td><td>Value</td></tr>\n'
                '<tr><td>Alpha</td><td>42</td></tr>\n'
                '</table>\n',
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertTrue(plan["ok"], plan)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = target.read_text(encoding="utf-8")
            self.assertIn("2026-08-07 09:30 (Asia/Seoul)", after)
            self.assertIn("Primary synced text", after)
            self.assertIn("Reference snapshot", after)
            self.assertIn("| Name | Value |", after)
            self.assertIn("| **Alpha** | 42 |", after)
            for tag in (
                "mention-date",
                "synced_block",
                "synced_block_reference",
                "table",
                "colgroup",
            ):
                self.assertNotIn(f"<{tag}", after)

    def test_markup_normalization_binds_reviewed_locator_and_edge_without_leaking_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260804_markup_bindings"
            target_id = "zet_20260804_markup_binding_target"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                '<mention ref="private-person-coordinate"/>\n'
                '<file ref="private-file-coordinate"/>\n',
            )
            self.write_markup_zettel(
                archive_root,
                target_id,
                "Reviewed relation target.\n",
            )
            edge = completion_workflows.archive_services.zettel_edge_write(
                archive_root,
                from_zettel=source_id,
                target_ref=target_id,
                edge_type="continues",
                visibility="private",
                approve=True,
                reviewed_by="person:test",
            )
            self.assertTrue(edge["ok"], edge)
            locator_ref = "workspace-page:private-coordinate"
            locator_plan = completion_workflows.external_locator_plan(
                archive_root,
                zettel_id=source_id,
                locator_type="provider_page_id",
                locator_ref=locator_ref,
            )
            locator = completion_workflows.external_locator_record(
                archive_root,
                zettel_id=source_id,
                locator_type="provider_page_id",
                locator_ref=locator_ref,
                expected_plan_sha256=locator_plan["summary"][
                    "plan_sha256"
                ],
                reviewed_by="person:test",
            )
            self.assertTrue(locator["ok"], locator)

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row
                for row in unbound["items"]
                if row["zettel_id"] == source_id
            )
            tag_digests = {
                row["tag_name"]: row["tag_sha256"]
                for row in item["reference_tag_digests"]
            }
            manifest = {
                "schema": (
                    completion_workflows
                    .MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA
                ),
                "archive_id": (
                    completion_workflows.archive_services.read_archive_id(
                        archive_root
                    )
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_digests["mention"],
                        "binding_kind": "zettel_edge",
                        "binding_id": edge["edge_id"],
                    },
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_digests["file"],
                        "binding_kind": "external_locator",
                        "binding_id": locator["summary"]["locator_id"],
                    },
                ],
            }
            manifest_relative = "ops/markup-reference-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            self.assert_schema_instance(
                "markup-reference-binding-manifest.schema.json",
                manifest,
            )
            bound_plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(bound_plan["ok"], bound_plan)
            self.assertEqual(
                bound_plan["summary"]["reference_binding_count"],
                2,
            )
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=bound_plan["summary"][
                    "plan_sha256"
                ],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            result_text = source_path.read_text(encoding="utf-8")
            self.assertNotIn("<mention", result_text)
            self.assertNotIn("<file", result_text)
            self.assertNotIn(locator_ref, result_text)
            self.assertIn("wom-edge://sha256/", result_text)
            self.assertIn("wom-locator://sha256/", result_text)

    def test_markup_normalization_binds_file_audio_and_video_to_manifested_objet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260807_objet_reference_bindings"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                '<file ref="private-file-coordinate"/>\n'
                '<audio src="private-audio-coordinate"></audio>\n'
                '<video src="private-video-coordinate"></video>\n',
            )
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            tag_digests = {
                row["tag_name"]: row["tag_sha256"]
                for row in item["reference_tag_digests"]
            }
            self.assertEqual(set(tag_digests), {"file", "audio", "video"})
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_digests[tag_name],
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    }
                    for tag_name in ("file", "audio", "video")
                ],
            }
            self.assert_schema_instance(
                "markup-reference-binding-manifest.schema.json",
                manifest,
            )
            manifest_relative = "ops/markup-reference-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertEqual(after.count("wom-objet:sha256:"), 3)
            self.assertNotIn("private-file-coordinate", after)
            self.assertNotIn("private-audio-coordinate", after)
            self.assertNotIn("private-video-coordinate", after)

    def test_markup_normalization_binds_paired_file_as_one_manifested_objet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_paired_file_binding"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                '<file src="private-file-coordinate"></file>\n',
            )
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(
                [row["tag_name"] for row in item["reference_tag_digests"]],
                ["file"],
            )
            tag_sha256 = item["reference_tag_digests"][0]["tag_sha256"]
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_sha256,
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    }
                ],
            }
            manifest_relative = "ops/paired-file-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["reference_binding_count"], 1)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertEqual(after.count("wom-objet:sha256:"), 1)
            self.assertNotIn("private-file-coordinate", after)
            self.assertNotIn("<file", after)
            self.assertNotIn("</file>", after)

    def test_markup_normalization_binds_self_closing_mention_page_and_unknown_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_new_reference_tags"
            target_id = "zet_20260809_mentioned_page"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                '<mention-page url="private-page-coordinate"/>\n'
                '<unknown:audio/>\n',
            )
            self.write_markup_zettel(
                archive_root,
                target_id,
                "Reviewed page target.\n",
            )
            edge = completion_workflows.archive_services.zettel_edge_write(
                archive_root,
                from_zettel=source_id,
                target_ref=target_id,
                edge_type="continues",
                visibility="private",
                approve=True,
                reviewed_by="person:test",
            )
            self.assertTrue(edge["ok"], edge)
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            tag_digests = {
                row["tag_name"]: row["tag_sha256"]
                for row in item["reference_tag_digests"]
            }
            self.assertEqual(
                set(tag_digests),
                {"mention-page", "unknown:audio"},
            )
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_digests["mention-page"],
                        "binding_kind": "zettel_edge",
                        "binding_id": edge["edge_id"],
                    },
                    {
                        "zettel_id": source_id,
                        "tag_sha256": tag_digests["unknown:audio"],
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    },
                ],
            }
            manifest_relative = "ops/new-reference-tag-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["reference_binding_count"], 2)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertIn("wom-edge://sha256/", after)
            self.assertIn("wom-objet:sha256:", after)
            self.assertNotIn("private-page-coordinate", after)
            self.assertNotIn("<unknown:audio", after)

    def test_markup_normalization_binds_repeated_digest_by_one_based_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_repeated_file_occurrences"
            fragment = '<file src="same-private-coordinate"></file>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n" + fragment + "\n",
            )
            before = source_path.read_bytes()
            first_object = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            second_object = (
                "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
            )

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(
                item["reference_tag_digests"],
                [
                    {
                        "tag_name": "file",
                        "tag_sha256": hashlib.sha256(
                            fragment.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 1,
                    },
                    {
                        "tag_name": "file",
                        "tag_sha256": hashlib.sha256(
                            fragment.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 2,
                    },
                ],
            )
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": item["reference_tag_digests"][0][
                            "tag_sha256"
                        ],
                        "occurrence_index": occurrence_index,
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    }
                    for occurrence_index, object_id in (
                        (2, second_object),
                        (1, first_object),
                    )
                ],
            }
            self.assert_schema_instance(
                "markup-reference-binding-manifest.schema.json",
                manifest,
            )
            manifest_relative = "ops/repeated-file-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["reference_binding_count"], 2)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            first_link = (
                "[Attached objet](wom-objet:sha256:"
                + first_object.removeprefix("sha256:")
                + ")"
            )
            second_link = (
                "[Attached objet](wom-objet:sha256:"
                + second_object.removeprefix("sha256:")
                + ")"
            )
            self.assertLess(after.index(first_link), after.index(second_link))
            self.assertNotIn("same-private-coordinate", after)

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_blocks_unindexed_repeated_digest_fanout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_unindexed_repeated_file"
            fragment = '<file src="same-private-coordinate"></file>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n" + fragment + "\n",
            )
            before = source_path.read_bytes()
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            manifest = {
                "schema": "wom-kit/markup-reference-binding-manifest/v0.1",
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": digest,
                        "binding_kind": "objet",
                        "binding_id": (
                            "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
                        ),
                    }
                ],
            }
            manifest_relative = "ops/legacy-unindexed-repeated-file.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertFalse(plan["ok"])
            self.assertIn(
                "markup_reference_binding_occurrence_required",
                plan["blockers"],
            )
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_binding_manifest_validates_occurrence_selectors_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_occurrence_manifest_validation"
            fragment = '<file src="private-coordinate"></file>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            before = source_path.read_bytes()
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            base_row = {
                "zettel_id": source_id,
                "tag_sha256": digest,
                "binding_kind": "objet",
                "binding_id": object_id,
            }
            archive_id = completion_workflows.archive_services.read_archive_id(
                archive_root
            )
            invalid_rows = {
                "zero": {**base_row, "occurrence_index": 0},
                "negative": {**base_row, "occurrence_index": -1},
                "boolean": {**base_row, "occurrence_index": True},
                "string": {**base_row, "occurrence_index": "1"},
                "float": {**base_row, "occurrence_index": 1.0},
                "typo": {**base_row, "occurrence_indx": 1},
                "zettel_whitespace": {
                    **base_row,
                    "zettel_id": f" {source_id} ",
                },
                "uppercase_digest": {
                    **base_row,
                    "tag_sha256": digest.upper(),
                },
                "binding_kind_whitespace": {
                    **base_row,
                    "binding_kind": " OBJET ",
                },
                "binding_id_whitespace": {
                    **base_row,
                    "binding_id": f" {object_id} ",
                },
            }
            for label, row in invalid_rows.items():
                with self.subTest(label=label):
                    relative = f"ops/invalid-occurrence-{label}.json"
                    path = archive_root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(
                            {
                                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                                "archive_id": archive_id,
                                "bindings": [row],
                            }
                        ),
                        encoding="utf-8",
                    )
                    plan = completion_workflows.markup_normalization_plan(
                        archive_root,
                        policy="normalize",
                        max_items=1000,
                        max_changes=1000,
                        binding_manifest=relative,
                    )
                    self.assertFalse(plan["ok"], plan)
                    self.assertIn(
                        "markup_binding_manifest_invalid",
                        plan["blockers"],
                    )
                    self.assertEqual(source_path.read_bytes(), before)

            duplicate_member_relative = "ops/duplicate-json-member.json"
            (archive_root / duplicate_member_relative).write_text(
                '{"schema":"wom-kit/markup-reference-binding-manifest/v0.2",'
                f'"archive_id":"{archive_id}","bindings":[{{'
                f'"zettel_id":"{source_id}","tag_sha256":"{digest}",'
                '"occurrence_index":1,"occurrence_index":2,'
                f'"binding_kind":"objet","binding_id":"{object_id}"}}]}}',
                encoding="utf-8",
            )
            duplicate_member = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=duplicate_member_relative,
            )
            self.assertIn(
                "markup_binding_manifest_invalid",
                duplicate_member["blockers"],
            )

            for label, legacy_row in (
                (
                    "legacy_occurrence",
                    {**base_row, "occurrence_index": 1},
                ),
                (
                    "legacy_zettel_reference",
                    {
                        **base_row,
                        "binding_kind": "zettel_reference",
                        "binding_id": source_id,
                    },
                ),
            ):
                with self.subTest(label=label):
                    relative = f"ops/{label}.json"
                    (archive_root / relative).write_text(
                        json.dumps(
                            {
                                "schema": "wom-kit/markup-reference-binding-manifest/v0.1",
                                "archive_id": archive_id,
                                "bindings": [legacy_row],
                            }
                        ),
                        encoding="utf-8",
                    )
                    legacy_invalid = (
                        completion_workflows.markup_normalization_plan(
                            archive_root,
                            policy="normalize",
                            max_items=1000,
                            max_changes=1000,
                            binding_manifest=relative,
                        )
                    )
                    self.assertIn(
                        "markup_binding_manifest_invalid",
                        legacy_invalid["blockers"],
                    )

            unhashable_schema_relative = "ops/unhashable-schema-value.json"
            (archive_root / unhashable_schema_relative).write_text(
                json.dumps(
                    {
                        "schema": [],
                        "archive_id": archive_id,
                        "bindings": [base_row],
                    }
                ),
                encoding="utf-8",
            )
            unhashable_schema = (
                completion_workflows.markup_normalization_plan(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    binding_manifest=unhashable_schema_relative,
                )
            )
            self.assertIn(
                "markup_binding_manifest_invalid",
                unhashable_schema["blockers"],
            )

            for label, rows, expected in (
                (
                    "mixed",
                    [base_row, {**base_row, "occurrence_index": 1}],
                    "markup_binding_occurrence_mixed",
                ),
                (
                    "duplicate",
                    [
                        {**base_row, "occurrence_index": 1},
                        {**base_row, "occurrence_index": 1},
                    ],
                    "markup_binding_duplicate",
                ),
            ):
                with self.subTest(label=label):
                    relative = f"ops/occurrence-{label}.json"
                    (archive_root / relative).write_text(
                        json.dumps(
                            {
                                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                                "archive_id": archive_id,
                                "bindings": rows,
                            }
                        ),
                        encoding="utf-8",
                    )
                    plan = completion_workflows.markup_normalization_plan(
                        archive_root,
                        policy="normalize",
                        max_items=1000,
                        max_changes=1000,
                        binding_manifest=relative,
                    )
                    self.assertFalse(plan["ok"], plan)
                    self.assertIn(expected, plan["blockers"])
                    self.assertEqual(source_path.read_bytes(), before)

            legacy_relative = "ops/legacy-single-occurrence.json"
            (archive_root / legacy_relative).write_text(
                json.dumps(
                    {
                        "schema": "wom-kit/markup-reference-binding-manifest/v0.1",
                        "archive_id": archive_id,
                        "bindings": [base_row],
                    }
                ),
                encoding="utf-8",
            )
            legacy = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=legacy_relative,
            )
            self.assertTrue(legacy["ok"], legacy)
            self.assertEqual(legacy["summary"]["reference_binding_count"], 1)
            serialized = json.dumps(legacy, ensure_ascii=False)
            self.assertNotIn("private-coordinate", serialized)
            self.assertNotIn(object_id, serialized)

    def test_markup_normalization_blocks_incomplete_or_out_of_range_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_occurrence_bounds"
            fragment = '<file src="same-private-coordinate"></file>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n" + fragment + "\n",
            )
            before = source_path.read_bytes()
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            archive_id = completion_workflows.archive_services.read_archive_id(
                archive_root
            )
            for label, index, expected in (
                (
                    "incomplete",
                    1,
                    "markup_reference_binding_occurrence_incomplete",
                ),
                (
                    "out-of-range",
                    3,
                    "markup_reference_binding_occurrence_out_of_range",
                ),
            ):
                with self.subTest(label=label):
                    relative = f"ops/occurrence-{label}.json"
                    (archive_root / relative).write_text(
                        json.dumps(
                            {
                                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                                "archive_id": archive_id,
                                "bindings": [
                                    {
                                        "zettel_id": source_id,
                                        "tag_sha256": digest,
                                        "occurrence_index": index,
                                        "binding_kind": "objet",
                                        "binding_id": object_id,
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    plan = completion_workflows.markup_normalization_plan(
                        archive_root,
                        policy="normalize",
                        max_items=1000,
                        max_changes=1000,
                        binding_manifest=relative,
                    )
                    self.assertFalse(plan["ok"], plan)
                    self.assertIn(expected, plan["blockers"])
                    item = next(
                        row
                        for row in plan["items"]
                        if row["zettel_id"] == source_id
                    )
                    self.assertEqual(item["before_sha256"], item["after_sha256"])
                    self.assertEqual(
                        item["counts"]["reference_binding_applied"],
                        0,
                    )
                    self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_binds_reviewed_zettel_without_creating_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_direct_mention_source"
            target_id = "zet_20260809_direct_mention_target"
            fragment = '<mention-page url="private-page-coordinate"/>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            target_path = self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Reviewed canonical target.\n",
            )
            before = source_path.read_bytes()
            target_before = target_path.read_bytes()

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            digest = item["reference_tag_digests"][0]["tag_sha256"]
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": digest,
                        "occurrence_index": 1,
                        "binding_kind": "zettel_reference",
                        "binding_id": target_id,
                    }
                ],
            }
            self.assert_schema_instance(
                "markup-reference-binding-manifest.schema.json",
                manifest,
            )
            manifest_relative = "ops/direct-zettel-reference.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertIn(
                f"[Referenced zettel](wom-zettel:{target_id})",
                after,
            )
            self.assertNotIn("private-page-coordinate", after)
            self.assertNotIn("\nedges:", after)
            self.assertEqual(target_path.read_bytes(), target_before)

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_binds_repeated_mentions_to_distinct_reviewed_zettels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_repeated_direct_mentions"
            target_ids = (
                "zet_20260809_repeated_direct_target_a",
                "zet_20260809_repeated_direct_target_b",
            )
            fragment = '<mention-page url="private-page-coordinate"/>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n" + fragment + "\n",
            )
            source_before = source_path.read_bytes()
            target_paths = [
                self.write_schema_valid_markup_zettel(
                    archive_root,
                    target_id,
                    f"Reviewed target {index}.\n",
                )
                for index, target_id in enumerate(target_ids, start=1)
            ]
            target_bytes = [path.read_bytes() for path in target_paths]
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": digest,
                        "occurrence_index": occurrence_index,
                        "binding_kind": "zettel_reference",
                        "binding_id": target_id,
                    }
                    for occurrence_index, target_id in (
                        (2, target_ids[1]),
                        (1, target_ids[0]),
                    )
                ],
            }
            manifest_relative = "ops/repeated-direct-zettel-references.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["reference_binding_count"], 2)
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(
                [row["occurrence_index"] for row in item["reference_tag_digests"]],
                [1, 2],
            )
            serialized_plan = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn("private-page-coordinate", serialized_plan)
            for target_id in target_ids:
                self.assertNotIn(target_id, serialized_plan)

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            first_link = (
                f"[Referenced zettel](wom-zettel:{target_ids[0]})"
            )
            second_link = (
                f"[Referenced zettel](wom-zettel:{target_ids[1]})"
            )
            self.assertLess(after.index(first_link), after.index(second_link))
            self.assertNotIn("private-page-coordinate", after)
            self.assertNotIn("\nedges:", after)
            self.assertEqual(
                [path.read_bytes() for path in target_paths],
                target_bytes,
            )

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(source_path.read_bytes(), source_before)

    def test_markup_zettel_reference_target_validation_fails_closed(self) -> None:
        cases = (
            "missing",
            "draft",
            "archived",
            "redacted",
            "wrong_archive",
            "malformed",
            "invalid_utf8",
            "duplicate",
            "self_reference",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                source_id = f"zet_20260809_target_validation_source_{case}"
                target_id = (
                    source_id
                    if case == "self_reference"
                    else f"zet_20260809_target_validation_target_{case}"
                )
                fragment = '<mention-page url="private-target-coordinate"/>'
                source_path = self.write_markup_zettel(
                    archive_root,
                    source_id,
                    fragment + "\n",
                )
                before = source_path.read_bytes()
                if case == "draft":
                    self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "Draft target.\n",
                        status="draft",
                        folder="inbox",
                    )
                elif case in {"archived", "redacted"}:
                    self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "Unavailable target.\n",
                        status=case,
                    )
                elif case == "wrong_archive":
                    target_path = self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "Wrong archive target.\n",
                    )
                    target_path.write_text(
                        target_path.read_text(encoding="utf-8").replace(
                            "archive_id: archive:personal:fake-life",
                            "archive_id: archive:personal:other-life",
                        ),
                        encoding="utf-8",
                    )
                elif case == "malformed":
                    self.write_markup_zettel(
                        archive_root,
                        target_id,
                        "Schema-incomplete target.\n",
                    )
                elif case == "invalid_utf8":
                    target_path = self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "Initially valid target.\n",
                    )
                    target_path.write_bytes(
                        target_path.read_bytes() + b"\xff\n"
                    )
                elif case == "duplicate":
                    self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "First target.\n",
                    )
                    self.write_schema_valid_markup_zettel(
                        archive_root,
                        target_id,
                        "Second target.\n",
                        folder="inbox",
                    )

                digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
                manifest_relative = f"ops/invalid-target-{case}.json"
                manifest_path = archive_root / manifest_relative
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(
                    json.dumps(
                        {
                            "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                            "archive_id": completion_workflows.archive_services.read_archive_id(
                                archive_root
                            ),
                            "bindings": [
                                {
                                    "zettel_id": source_id,
                                    "tag_sha256": digest,
                                    "occurrence_index": 1,
                                    "binding_kind": "zettel_reference",
                                    "binding_id": target_id,
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                plan = completion_workflows.markup_normalization_plan(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    binding_manifest=manifest_relative,
                )
                self.assertFalse(plan["ok"], plan)
                self.assertIn(
                    "markup_zettel_reference_binding_unverified",
                    plan["blockers"],
                )
                self.assertEqual(source_path.read_bytes(), before)
                serialized = json.dumps(plan, ensure_ascii=False)
                self.assertNotIn("private-target-coordinate", serialized)
                if case != "self_reference":
                    self.assertNotIn(target_id, serialized)

    def test_markup_zettel_reference_rechecks_target_lifecycle_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_stale_target_source"
            target_id = "zet_20260809_stale_target_target"
            fragment = '<mention-page url="private-target-coordinate"/>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            source_before = source_path.read_bytes()
            target_path = self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Initially canonical.\n",
            )
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            manifest_relative = "ops/stale-target-reference.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                        "archive_id": completion_workflows.archive_services.read_archive_id(
                            archive_root
                        ),
                        "bindings": [
                            {
                                "zettel_id": source_id,
                                "tag_sha256": digest,
                                "occurrence_index": 1,
                                "binding_kind": "zettel_reference",
                                "binding_id": target_id,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            target_path.write_text(
                target_path.read_text(encoding="utf-8").replace(
                    "status: canonical",
                    "status: archived",
                ),
                encoding="utf-8",
            )

            blocked = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertFalse(blocked["ok"], blocked)
            self.assertIn(
                "markup_zettel_reference_binding_unverified",
                blocked["blockers"],
            )
            self.assertEqual(blocked["files_written"], [])
            self.assertEqual(source_path.read_bytes(), source_before)

    def test_markup_binding_rejects_duplicate_source_zettel_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_duplicate_binding_source"
            target_id = "zet_20260809_duplicate_binding_target"
            fragment = '<mention-page url="private-source-coordinate"/>'
            first_source = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            second_source = self.write_schema_valid_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
                folder="inbox",
            )
            self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Unique reviewed target.\n",
            )
            before = (first_source.read_bytes(), second_source.read_bytes())
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            manifest_relative = "ops/duplicate-binding-source.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                        "archive_id": completion_workflows.archive_services.read_archive_id(
                            archive_root
                        ),
                        "bindings": [
                            {
                                "zettel_id": source_id,
                                "tag_sha256": digest,
                                "occurrence_index": 1,
                                "binding_kind": "zettel_reference",
                                "binding_id": target_id,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertFalse(plan["ok"], plan)
            self.assertIn(
                "markup_binding_source_unverified",
                plan["blockers"],
            )
            self.assertEqual(plan["summary"]["ready_change_count"], 0)
            self.assertEqual(
                (first_source.read_bytes(), second_source.read_bytes()),
                before,
            )
            serialized = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn("private-source-coordinate", serialized)

    def test_markup_binding_source_path_authority_blocks_duplicate_race(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_binding_source_race"
            target_id = "zet_20260809_binding_source_race_target"
            fragment = '<mention-page url="private-race-coordinate"/>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Stable reviewed target.\n",
            )
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            manifest_relative = "ops/binding-source-race.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                        "archive_id": completion_workflows.archive_services.read_archive_id(
                            archive_root
                        ),
                        "bindings": [
                            {
                                "zettel_id": source_id,
                                "tag_sha256": digest,
                                "occurrence_index": 1,
                                "binding_kind": "zettel_reference",
                                "binding_id": target_id,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            duplicate_path = archive_root / "inbox" / f"{source_id}.md"
            duplicate_path.parent.mkdir(parents=True, exist_ok=True)
            strict_snapshots = (
                completion_workflows.archive_services.strict_local_zettel_snapshots
            )

            def inject_duplicate_after_snapshot(root: Path) -> list[object]:
                snapshots = strict_snapshots(root)
                duplicate_path.write_bytes(source_path.read_bytes())
                return snapshots

            with mock.patch.object(
                completion_workflows.archive_services,
                "strict_local_zettel_snapshots",
                side_effect=inject_duplicate_after_snapshot,
            ):
                plan = completion_workflows.markup_normalization_plan(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    binding_manifest=manifest_relative,
                )

            self.assertFalse(plan["ok"], plan)
            self.assertIn(
                "markup_binding_source_unverified",
                plan["blockers"],
            )
            matching_items = [
                item for item in plan["items"] if item["zettel_id"] == source_id
            ]
            self.assertEqual(len(matching_items), 2)
            self.assertEqual(
                sorted(
                    item["counts"]["reference_binding_applied"]
                    for item in matching_items
                ),
                [0, 1],
            )
            self.assertEqual(source_path.read_bytes(), duplicate_path.read_bytes())
            self.assertNotIn(
                "private-race-coordinate",
                json.dumps(plan, ensure_ascii=False),
            )

    def test_markup_zettel_reference_is_restricted_to_mention_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_direct_reference_kind_boundary"
            target_id = "zet_20260809_direct_reference_kind_target"
            fragments = [
                f'<{name} private="coordinate"/>'
                for name in (
                    "file",
                    "audio",
                    "video",
                    "media",
                    "mention",
                    "synced-ref",
                    "synced_ref",
                )
            ] + ["<unknown:audio/>"]
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                "\n".join(fragments) + "\n",
            )
            before = source_path.read_bytes()
            self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Valid target must not change tag semantics.\n",
            )
            manifest_relative = "ops/direct-reference-kind-boundary.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                        "archive_id": completion_workflows.archive_services.read_archive_id(
                            archive_root
                        ),
                        "bindings": [
                            {
                                "zettel_id": source_id,
                                "tag_sha256": hashlib.sha256(
                                    fragment.encode("utf-8")
                                ).hexdigest(),
                                "occurrence_index": 1,
                                "binding_kind": "zettel_reference",
                                "binding_id": target_id,
                            }
                            for fragment in fragments
                        ],
                    }
                ),
                encoding="utf-8",
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertIn(
                "markup_reference_binding_kind_mismatch",
                item["blocker_codes"],
            )
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_occurrences_support_identity_free_audio_lexical_variants(self) -> None:
        for label, tag in (
            ("space", "<unknown:audio />"),
            ("case", "<UNKNOWN:AUDIO/>"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                source_id = f"zet_20260809_audio_occurrence_{label}"
                source_path = self.write_markup_zettel(
                    archive_root,
                    source_id,
                    tag + "\n" + tag + "\n",
                )
                digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()
                object_ids = (
                    "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136",
                    "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647",
                )
                manifest_relative = f"ops/audio-occurrence-{label}.json"
                manifest_path = archive_root / manifest_relative
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(
                    json.dumps(
                        {
                            "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                            "archive_id": completion_workflows.archive_services.read_archive_id(
                                archive_root
                            ),
                            "bindings": [
                                {
                                    "zettel_id": source_id,
                                    "tag_sha256": digest,
                                    "occurrence_index": index,
                                    "binding_kind": "objet",
                                    "binding_id": object_id,
                                }
                                for index, object_id in enumerate(
                                    object_ids,
                                    start=1,
                                )
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                plan = completion_workflows.markup_normalization_plan(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    binding_manifest=manifest_relative,
                )
                self.assertTrue(plan["ok"], plan)
                self.assertEqual(
                    plan["summary"]["reference_binding_count"],
                    2,
                )
                applied = completion_workflows.markup_normalization_apply(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    binding_manifest=manifest_relative,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:test",
                )
                self.assertTrue(applied["ok"], applied)
                after = source_path.read_text(encoding="utf-8")
                self.assertEqual(after.count("wom-objet:sha256:"), 2)
                self.assertNotIn("unknown:audio", after.casefold())

    def test_markup_normalization_keeps_paired_mention_page_with_inner_text_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_paired_mention_page"
            target_id = "zet_20260809_paired_mention_target"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                '<mention-page url="private-page-coordinate">'
                "Visible page label"
                "</mention-page>\n",
            )
            self.write_markup_zettel(
                archive_root,
                target_id,
                "Reviewed page target.\n",
            )
            edge = completion_workflows.archive_services.zettel_edge_write(
                archive_root,
                from_zettel=source_id,
                target_ref=target_id,
                edge_type="continues",
                visibility="private",
                approve=True,
                reviewed_by="person:test",
            )
            self.assertTrue(edge["ok"], edge)
            before = source_path.read_bytes()

            unbound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
            )
            self.assertFalse(unbound["ok"])
            item = next(
                row for row in unbound["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["reference_tag_names"], ["mention-page"])
            self.assertEqual(item["unknown_tag_names"], [])
            self.assertIn(
                "markup_reference_binding_required",
                item["blocker_codes"],
            )
            self.assertEqual(len(item["reference_tag_digests"]), 2)
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": row["tag_sha256"],
                        "binding_kind": "zettel_edge",
                        "binding_id": edge["edge_id"],
                    }
                    for row in item["reference_tag_digests"]
                ],
            }
            manifest_relative = "ops/paired-mention-page-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            bound = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertFalse(bound["ok"])
            self.assertIn("markup_binding_unused", bound["blockers"])
            self.assertIn(
                "markup_reference_binding_required",
                bound["blockers"],
            )
            bound_item = next(
                row for row in bound["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(bound_item["state"], "blocked")
            self.assertEqual(
                bound_item["before_sha256"],
                bound_item["after_sha256"],
            )
            self.assertEqual(
                bound_item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_rejects_nonempty_paired_file_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_nonempty_paired_file"
            fragment = (
                '<file src="private-file-coordinate">'
                "Visible file label"
                "</file>"
            )
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            before = source_path.read_bytes()
            full_fragment_sha256 = hashlib.sha256(
                fragment.encode("utf-8")
            ).hexdigest()
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/nonempty-paired-file-bindings.json",
                [(source_id, full_fragment_sha256)],
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertIn(
                "markup_file_inner_content_unsupported",
                item["blocker_codes"],
            )
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_rejects_malformed_paired_file_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            fragments = {
                "zet_20260809_file_bad_attribute_token": "<file ???></file>",
                "zet_20260809_file_unquoted_attribute": (
                    "<file src=opaque></file>"
                ),
                "zet_20260809_file_duplicate_attribute": (
                    '<file src="a" src="b"></file>'
                ),
            }
            before_by_id: dict[str, bytes] = {}
            paths: dict[str, Path] = {}
            bindings: list[tuple[str, str]] = []
            for zettel_id, fragment in fragments.items():
                path = self.write_markup_zettel(
                    archive_root,
                    zettel_id,
                    fragment + "\n",
                )
                paths[zettel_id] = path
                before_by_id[zettel_id] = path.read_bytes()
                bindings.append(
                    (
                        zettel_id,
                        hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
                    )
                )
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/malformed-paired-file-bindings.json",
                bindings,
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            for zettel_id in fragments:
                with self.subTest(zettel_id=zettel_id):
                    item = by_id[zettel_id]
                    self.assertEqual(item["state"], "blocked")
                    self.assertIn(
                        "markup_file_attributes_unsupported",
                        item["blocker_codes"],
                    )
                    self.assertEqual(
                        item["counts"]["reference_binding_applied"],
                        0,
                    )
                    self.assertEqual(
                        item["before_sha256"],
                        item["after_sha256"],
                    )
                    self.assertEqual(
                        paths[zettel_id].read_bytes(),
                        before_by_id[zettel_id],
                    )

    def test_markup_normalization_rejects_self_closing_file_as_paired_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            fragments = {
                "zet_20260809_file_self_close_attrs": (
                    '<file src="a"/>VISIBLE</file>'
                ),
                "zet_20260809_file_self_close_space": (
                    "<file />VISIBLE</file>"
                ),
            }
            paths: dict[str, Path] = {}
            before_by_id: dict[str, bytes] = {}
            bindings: list[tuple[str, str]] = []
            full_fragment_sha256s: dict[str, str] = {}
            for zettel_id, fragment in fragments.items():
                path = self.write_markup_zettel(
                    archive_root,
                    zettel_id,
                    fragment + "\n",
                )
                paths[zettel_id] = path
                before_by_id[zettel_id] = path.read_bytes()
                digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
                full_fragment_sha256s[zettel_id] = digest
                bindings.append((zettel_id, digest))
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/self-closing-file-pair-bindings.json",
                bindings,
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            by_id = {item["zettel_id"]: item for item in plan["items"]}
            for zettel_id in fragments:
                with self.subTest(zettel_id=zettel_id):
                    item = by_id[zettel_id]
                    self.assertEqual(item["state"], "blocked")
                    self.assertIn(
                        "markup_paired_reference_self_closing_opener",
                        item["blocker_codes"],
                    )
                    self.assertNotIn(
                        full_fragment_sha256s[zettel_id],
                        {
                            row["tag_sha256"]
                            for row in item["reference_tag_digests"]
                        },
                    )
                    self.assertEqual(
                        item["before_sha256"],
                        item["after_sha256"],
                    )
                    self.assertEqual(
                        item["counts"]["reference_binding_applied"],
                        0,
                    )
                    self.assertEqual(
                        paths[zettel_id].read_bytes(),
                        before_by_id[zettel_id],
                    )

    def test_markup_normalization_rejects_ambiguous_unknown_audio_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_ambiguous_unknown_audio"
            tag = "<unknown:audio/>"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                tag + "\n" + tag + "\n",
            )
            before = source_path.read_bytes()
            tag_sha256 = hashlib.sha256(tag.encode("utf-8")).hexdigest()
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/ambiguous-unknown-audio-bindings.json",
                [(source_id, tag_sha256)],
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertIn(
                "markup_unknown_audio_binding_ambiguous",
                item["blocker_codes"],
            )
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_blocks_duplicate_manifest_binding_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_duplicate_binding_rows"
            tag = "<unknown:audio/>"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                tag + "\n",
            )
            before = source_path.read_bytes()
            tag_sha256 = hashlib.sha256(tag.encode("utf-8")).hexdigest()
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/duplicate-binding-rows.json",
                [
                    (source_id, tag_sha256),
                    (source_id, tag_sha256),
                ],
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_duplicate", plan["blockers"])
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_rejects_attributed_unknown_audio_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_attributed_unknown_audio"
            tag = '<unknown:audio title="Visible audio label"/>'
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                tag + "\n",
            )
            before = source_path.read_bytes()
            tag_sha256 = hashlib.sha256(tag.encode("utf-8")).hexdigest()
            manifest_relative = self.write_markup_objet_binding_manifest(
                archive_root,
                "ops/attributed-unknown-audio-bindings.json",
                [(source_id, tag_sha256)],
            )

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertIn(
                "markup_unknown_audio_attributes_unsupported",
                item["blocker_codes"],
            )
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(source_path.read_bytes(), before)
            serialized = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn("Visible audio label", serialized)

    def test_markup_normalization_requires_new_tag_specific_binding_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_reference_binding_kind_mismatch"
            target_id = "zet_20260809_reference_binding_kind_target"
            file_fragment = '<file src="private-file"></file>'
            mention_page = '<mention-page url="private-page"/>'
            unknown_audio = "<unknown:audio/>"
            source_path = self.write_markup_zettel(
                archive_root,
                source_id,
                file_fragment + "\n" + mention_page + "\n" + unknown_audio + "\n",
            )
            self.write_markup_zettel(
                archive_root,
                target_id,
                "Reviewed edge target.\n",
            )
            edge = completion_workflows.archive_services.zettel_edge_write(
                archive_root,
                from_zettel=source_id,
                target_ref=target_id,
                edge_type="continues",
                visibility="private",
                approve=True,
                reviewed_by="person:test",
            )
            self.assertTrue(edge["ok"], edge)
            before = source_path.read_bytes()
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            file_fragment.encode("utf-8")
                        ).hexdigest(),
                        "binding_kind": "zettel_edge",
                        "binding_id": edge["edge_id"],
                    },
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            mention_page.encode("utf-8")
                        ).hexdigest(),
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    },
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            unknown_audio.encode("utf-8")
                        ).hexdigest(),
                        "binding_kind": "zettel_edge",
                        "binding_id": edge["edge_id"],
                    },
                ],
            }
            manifest_relative = "ops/reference-binding-kind-mismatch.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )

            self.assertFalse(plan["ok"], plan)
            self.assertIn("markup_binding_unused", plan["blockers"])
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertIn(
                "markup_reference_binding_kind_mismatch",
                item["blocker_codes"],
            )
            self.assertEqual(
                item["counts"]["reference_binding_applied"],
                0,
            )
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_letter117_reference_matrix_preserves_whitespace(self) -> None:
        cases = (
            ("unknown:synced_block", "zettel_reference", ""),
            ("unknown:synced_block", "objet", "  "),
            ("unknown:transclusion_reference", "zettel_reference", "    "),
            ("unknown:transclusion_reference", "objet", ""),
            ("unknown:transclusion_container", "zettel_reference", "  "),
            ("unknown:transclusion_container", "objet", "    "),
        )
        for tag_name, binding_kind, indentation in cases:
            with self.subTest(tag_name=tag_name, binding_kind=binding_kind):
                fragment = f"<{tag_name}/>"
                tag_sha256 = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
                body = f"Context\r\n{indentation}{fragment}\r\nAfter\r\n"
                result = completion_workflows._normalize_markup_body(
                    body,
                    bindings={
                        tag_sha256: {
                            "binding_kind": binding_kind,
                            "binding_id": (
                                "zet_20260809_reviewed_target"
                                if binding_kind == "zettel_reference"
                                else "sha256:" + ("a" * 64)
                            ),
                            "replacement": "[BOUND]",
                        }
                    },
                )
                self.assertTrue(result["changed"], result)
                self.assertEqual(result["blocker_codes"], [])
                self.assertEqual(
                    result["normalized_body"],
                    f"Context\r\n{indentation}[BOUND]\r\nAfter\r\n",
                )
                self.assertEqual(
                    result["reference_tag_digests"],
                    [
                        {
                            "tag_name": tag_name,
                            "tag_sha256": tag_sha256,
                            "occurrence_index": 1,
                        }
                    ],
                )

        protected_fragment = "<unknown:synced_block/>"
        protected_body = f"`{protected_fragment}`\r\n"
        protected = completion_workflows._normalize_markup_body(
            protected_body,
            bindings={
                hashlib.sha256(protected_fragment.encode("utf-8")).hexdigest(): {
                    "binding_kind": "zettel_reference",
                    "binding_id": "zet_20260809_reviewed_target",
                    "replacement": "[BOUND]",
                }
            },
        )
        self.assertEqual(protected["normalized_body"], protected_body)
        self.assertFalse(protected["changed"])
        self.assertEqual(protected["reference_tag_digests"], [])
        self.assertEqual(
            protected["blocker_codes"],
            ["markup_protected_context_unsupported"],
        )

    def test_markup_normalization_binds_reviewed_unknown_content_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_letter117_unknown_reference_source"
            target_ids = (
                "zet_20260809_letter117_unknown_reference_a",
                "zet_20260809_letter117_unknown_reference_b",
                "zet_20260809_letter117_transclusion_target",
            )
            synced = "<unknown:synced_block/>"
            transclusion_reference = "<unknown:transclusion_reference/>"
            transclusion_container = "<unknown:transclusion_container/>"
            source_path = self.write_schema_valid_markup_zettel(
                archive_root,
                source_id,
                "\n".join(
                    (
                        synced,
                        synced,
                        transclusion_reference,
                        transclusion_container,
                        "",
                    )
                ),
            )
            source_before = source_path.read_bytes()
            target_paths = [
                self.write_schema_valid_markup_zettel(
                    archive_root,
                    target_id,
                    f"Reviewed static target {index}.\n",
                )
                for index, target_id in enumerate(target_ids, start=1)
            ]
            target_bytes = [path.read_bytes() for path in target_paths]
            object_id = (
                "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    *[
                        {
                            "zettel_id": source_id,
                            "tag_sha256": hashlib.sha256(
                                synced.encode("utf-8")
                            ).hexdigest(),
                            "occurrence_index": occurrence_index,
                            "binding_kind": "zettel_reference",
                            "binding_id": target_id,
                        }
                        for occurrence_index, target_id in enumerate(
                            target_ids[:2], start=1
                        )
                    ],
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            transclusion_reference.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 1,
                        "binding_kind": "zettel_reference",
                        "binding_id": target_ids[2],
                    },
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            transclusion_container.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 1,
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    },
                ],
            }
            self.assert_schema_instance(
                "markup-reference-binding-manifest.schema.json",
                manifest,
            )
            manifest_relative = "ops/letter117-unknown-content-bindings.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["summary"]["reference_binding_count"], 4)
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "ready")
            self.assertEqual(
                sorted(
                    {row["tag_name"] for row in item["reference_tag_digests"]}
                ),
                [
                    "unknown:synced_block",
                    "unknown:transclusion_container",
                    "unknown:transclusion_reference",
                ],
            )
            self.assertEqual(
                [
                    row["occurrence_index"]
                    for row in item["reference_tag_digests"]
                    if row["tag_name"] == "unknown:synced_block"
                ],
                [1, 2],
            )
            serialized_plan = json.dumps(plan, ensure_ascii=False)
            for private_value in (*target_ids, object_id):
                self.assertNotIn(private_value, serialized_plan)

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertNotIn("<unknown:", after)
            self.assertLess(
                after.index(f"wom-zettel:{target_ids[0]}"),
                after.index(f"wom-zettel:{target_ids[1]}"),
            )
            self.assertIn(f"wom-zettel:{target_ids[2]}", after)
            self.assertIn(f"wom-objet:{object_id}", after)
            self.assertNotIn("wom-edge:", after)
            self.assertEqual(
                [path.read_bytes() for path in target_paths],
                target_bytes,
            )

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(source_path.read_bytes(), source_before)

    def test_markup_normalization_binds_empty_database_to_reviewed_zettel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_letter117_database_source"
            target_id = "zet_20260809_letter117_database_target"
            fragment = (
                '<database data-source-url="private-data-source" '
                'inline="false" url="private-database"></database>'
            )
            source_path = self.write_schema_valid_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n",
            )
            source_before = source_path.read_bytes()
            target_path = self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Reviewed database target.\n",
            )
            target_before = target_path.read_bytes()
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            fragment.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 1,
                        "binding_kind": "zettel_reference",
                        "binding_id": target_id,
                    }
                ],
            }
            manifest_relative = "ops/letter117-database-binding.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
            )
            self.assertTrue(plan["ok"], plan)
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "ready")
            self.assertEqual(
                {row["tag_name"] for row in item["reference_tag_digests"]},
                {"database"},
            )
            serialized_plan = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn("private-data-source", serialized_plan)
            self.assertNotIn("private-database", serialized_plan)
            self.assertNotIn(target_id, serialized_plan)

            applied = completion_workflows.markup_normalization_apply(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(applied["ok"], applied)
            after = source_path.read_text(encoding="utf-8")
            self.assertNotIn("<database", after)
            self.assertIn(f"wom-zettel:{target_id}", after)
            self.assertNotIn("wom-edge:", after)
            self.assertEqual(target_path.read_bytes(), target_before)

            revert_plan = completion_workflows.markup_normalization_revert_plan(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
            )
            reverted = completion_workflows.markup_normalization_revert(
                archive_root,
                receipt=applied["summary"]["receipt_path"],
                expected_plan_sha256=revert_plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(source_path.read_bytes(), source_before)

    def test_markup_normalization_rejects_unsafe_letter117_reference_shapes_and_kinds(self) -> None:
        def digest(fragment: str) -> str:
            return hashlib.sha256(fragment.encode("utf-8")).hexdigest()

        def binding(kind: str) -> dict[str, str]:
            return {
                "binding_kind": kind,
                "binding_id": (
                    "zet_20260809_reviewed_target"
                    if kind == "zettel_reference"
                    else "sha256:" + ("a" * 64)
                    if kind == "objet"
                    else "edge:" + ("b" * 64)
                    if kind == "zettel_edge"
                    else "locator:sha256:" + ("c" * 64)
                ),
                "replacement": "[BOUND]",
            }

        cases = (
            (
                '<unknown:synced_block source="opaque"/>',
                "zettel_reference",
                "markup_unknown_content_reference_shape_unsupported",
            ),
            (
                "<unknown:synced_block />",
                "zettel_reference",
                "markup_unknown_content_reference_shape_unsupported",
            ),
            (
                "<UNKNOWN:SYNCED_BLOCK/>",
                "zettel_reference",
                "markup_unknown_content_reference_shape_unsupported",
            ),
            (
                "<unknown:transclusion_reference></unknown:transclusion_reference>",
                "zettel_reference",
                "markup_unknown_content_reference_shape_unsupported",
            ),
            (
                "<unknown:transclusion_container/>",
                "zettel_edge",
                "markup_reference_binding_kind_mismatch",
            ),
            (
                "<unknown:transclusion_container/>",
                "external_locator",
                "markup_reference_binding_kind_mismatch",
            ),
            (
                '<database inline="false" url="opaque">Visible title</database>',
                "zettel_reference",
                "markup_database_inner_content_unsupported",
            ),
            (
                '<database icon="star" inline="false" url="opaque"></database>',
                "zettel_reference",
                "markup_database_attributes_unsupported",
            ),
            (
                '<database inline="maybe" url="opaque"></database>',
                "zettel_reference",
                "markup_database_attributes_unsupported",
            ),
            (
                '<database inline="false" url="opaque"></database>',
                "objet",
                "markup_reference_binding_kind_mismatch",
            ),
            (
                '<database inline="false" url="opaque"/>',
                "zettel_reference",
                "markup_database_shape_unsupported",
            ),
        )
        for fragment, kind, expected_blocker in cases:
            with self.subTest(fragment=fragment, kind=kind):
                result = completion_workflows._normalize_markup_body(
                    fragment,
                    bindings={digest(fragment): binding(kind)},
                )
                self.assertEqual(result["normalized_body"], fragment)
                self.assertFalse(result["changed"])
                self.assertIn(expected_blocker, result["blocker_codes"])
                self.assertEqual(
                    result["counts"]["reference_binding_applied"],
                    0,
                )

        repeated = "<unknown:synced_block/>\n<unknown:synced_block/>\n"
        repeated_digest = digest("<unknown:synced_block/>")
        incomplete = completion_workflows._normalize_markup_body(
            repeated,
            bindings={
                repeated_digest: {1: binding("zettel_reference")}
            },
        )
        self.assertEqual(incomplete["normalized_body"], repeated)
        self.assertFalse(incomplete["changed"])
        self.assertIn(
            "markup_reference_binding_occurrence_incomplete",
            incomplete["blocker_codes"],
        )
        self.assertEqual(
            incomplete["reference_tag_names"],
            ["unknown:synced_block"],
        )
        self.assertEqual(
            {
                row["tag_name"]
                for row in incomplete["reference_tag_digests"]
            },
            {"unknown:synced_block"},
        )

    def test_markup_normalization_restores_bound_letter117_reference_when_coblocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260809_letter117_coblocked_source"
            target_id = "zet_20260809_letter117_coblocked_target"
            fragment = "<unknown:synced_block/>"
            source_path = self.write_schema_valid_markup_zettel(
                archive_root,
                source_id,
                fragment + "\n<unknown:unsupported/>\n",
            )
            before = source_path.read_bytes()
            self.write_schema_valid_markup_zettel(
                archive_root,
                target_id,
                "Reviewed target.\n",
            )
            manifest = {
                "schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                "archive_id": completion_workflows.archive_services.read_archive_id(
                    archive_root
                ),
                "bindings": [
                    {
                        "zettel_id": source_id,
                        "tag_sha256": hashlib.sha256(
                            fragment.encode("utf-8")
                        ).hexdigest(),
                        "occurrence_index": 1,
                        "binding_kind": "zettel_reference",
                        "binding_id": target_id,
                    }
                ],
            }
            manifest_relative = "ops/letter117-coblocked-binding.json"
            manifest_path = archive_root / manifest_relative
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=1000,
                max_changes=1000,
                binding_manifest=manifest_relative,
                only_ready=True,
            )
            self.assertFalse(plan["ok"], plan)
            item = next(
                row for row in plan["items"] if row["zettel_id"] == source_id
            )
            self.assertEqual(item["state"], "blocked")
            self.assertEqual(item["before_sha256"], item["after_sha256"])
            self.assertIn("unknown_semantic_markup", item["blocker_codes"])
            self.assertEqual(plan["would_change"], [])
            self.assertEqual(source_path.read_bytes(), before)

    def test_markup_normalization_keeps_letter117_display_and_structure_gaps_fail_closed(self) -> None:
        cases = {
            "callout": (
                '<callout icon="star" color="yellow_background">\n'
                "\tVisible content\n"
                "</callout>\n"
            ),
            "unknown_columns": (
                "<unknown:column_list/>\n"
                "<unknown:column/>\n"
                "    Visible child content\n"
            ),
            "unknown_unsupported": "<unknown:unsupported/>\n",
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                result = completion_workflows._normalize_markup_body(body)
                self.assertEqual(result["normalized_body"], body)
                self.assertFalse(result["changed"])
                self.assertIn(
                    "unknown_semantic_markup",
                    result["blocker_codes"],
                )

        database = '<database inline="false" url="opaque"></database>\n'
        unbound_database = completion_workflows._normalize_markup_body(database)
        self.assertEqual(unbound_database["normalized_body"], database)
        self.assertFalse(unbound_database["changed"])
        self.assertIn(
            "markup_reference_binding_required",
            unbound_database["blocker_codes"],
        )

        guide = completion_workflows.markup_style_guide()
        rules = {row["markup"]: row for row in guide["rules"]}
        self.assertEqual(
            rules["unknown_synced_and_transclusion_placeholders"]["action"],
            "require_reviewed_static_zettel_or_objet_binding",
        )
        self.assertEqual(
            rules["database"]["action"],
            "require_reviewed_zettel_reference_for_empty_strict_pair",
        )
        self.assertFalse(
            guide["truth_boundaries"][
                "protected_context_is_actionable_migration_debt"
            ]
        )

    def test_markup_normalization_protects_literal_markup_contexts(self) -> None:
        def digest(fragment: str) -> str:
            return hashlib.sha256(fragment.encode("utf-8")).hexdigest()

        def binding(kind: str) -> dict[str, str]:
            return {
                "binding_kind": kind,
                "binding_id": (
                    "edge:" + ("a" * 64)
                    if kind == "zettel_edge"
                    else "zet_20260809_reviewed_target"
                    if kind == "zettel_reference"
                    else "sha256:" + ("a" * 64)
                ),
                "replacement": "[BOUND]",
            }

        cases = [
            (
                '`<file src="inline"></file>`',
                '<file src="inline"></file>',
                "objet",
            ),
            (
                "```html\n<mention-page url=\"fenced\"/>\n```",
                '<mention-page url="fenced"/>',
                "zettel_edge",
            ),
            (
                '- ```html\n  <file src="list-fenced"></file>\n  ```',
                '<file src="list-fenced"></file>',
                "objet",
            ),
            (
                '1. ~~~html\n   <file src="ordered-fenced"></file>\n   ~~~',
                '<file src="ordered-fenced"></file>',
                "objet",
            ),
            (
                '10. item\n    ~~~html\n    <span color="red">ordered continuation</span>\n    ~~~',
                "",
                "objet",
            ),
            (
                '-    item\n     ~~~html\n     <span color="red">bullet continuation</span>\n     ~~~',
                "",
                "objet",
            ),
            (
                "<!-- <unknown:audio/> -->",
                "<unknown:audio/>",
                "objet",
            ),
            (
                '<pre><file src="pre"></file></pre>',
                '<file src="pre"></file>',
                "objet",
            ),
            (
                '>     <span color="red">blockquote code</span>',
                "",
                "objet",
            ),
            (
                '<?target instruction <span color="red">pi</span> ?>',
                "",
                "objet",
            ),
            (
                '<![CDATA[<span color="red">cdata</span>]]>',
                "",
                "objet",
            ),
            (
                '<script><span color="red">script literal</span></script>',
                "",
                "objet",
            ),
            (
                '<a title=\'before <span color="red">attribute literal</span> after\'>Link</a>',
                "",
                "objet",
            ),
            (
                '<pre data-note=\'before <span color="red">pre attribute literal</span> after\'>\nplain\n</pre>',
                "",
                "objet",
            ),
            (
                '<blockquote>\n<span color="red">raw block literal</span>\n</blockquote>',
                "",
                "objet",
            ),
            (
                '<a>\n<span color="red">type seven raw block literal</span>\n</a>\n',
                "",
                "objet",
            ),
            (
                '<a>\n<unknown:synced_block/>\n</a>\n',
                "<unknown:synced_block/>",
                "zettel_reference",
            ),
            (
                '</blockquote>\n<span color="red">closing raw block literal</span>\n',
                "",
                "objet",
            ),
            (
                '> <a>\n> <span color="red">quoted type seven raw block</span>\n> </a>\n>',
                "",
                "objet",
            ),
            (
                '> <blockquote>\n> <span color="red">nested type six raw block</span>\n> </blockquote>\n>',
                "",
                "objet",
            ),
            (
                '- <a>\n  <span color="red">list type seven raw block</span>\n  </a>\n',
                "",
                "objet",
            ),
            (
                '1. <a>\n   <span color="red">ordered type seven raw block</span>\n   </a>\n',
                "",
                "objet",
            ),
            (
                '[\nfoo\n]: /url "<span color=red>multiline label literal</span>"\n\n[foo]',
                "",
                "objet",
            ),
            (
                '[foo]: /url\n"<span color=red>next line title literal</span>"\n\n[foo]',
                "",
                "objet",
            ),
            (
                '> [foo]: /url "<span color=red>quoted reference title</span>"\n>\n> [foo]',
                "",
                "objet",
            ),
            (
                '- [foo]: /url "<span color=red>list reference title</span>"',
                "",
                "objet",
            ),
            (
                '\\<file src="escaped"></file>',
                '<file src="escaped"></file>',
                "objet",
            ),
            (
                '`<table><tr><td>Literal</td></tr></table>`',
                "",
                "objet",
            ),
            (
                '`a\n<span color="red">multiline literal</span>\nb`',
                "",
                "objet",
            ),
            (
                '```text\n- ```\n<span color="red">fake close</span>\n```',
                "",
                "objet",
            ),
            (
                '~~~text\n> ~~~\n<span color="red">fake quote close</span>\n~~~',
                "",
                "objet",
            ),
            (
                ('> ' * 16) + '```html\n' + ('> ' * 16)
                + '<span color="red">deep fence</span>\n',
                "",
                "objet",
            ),
            (
                '<!DOCTYPE demo [ <!ENTITY x "<span>literal</span>"> ]>',
                "",
                "objet",
            ),
            (
                '[x](https://example.test/<span>path</span>)',
                "",
                "objet",
            ),
            (
                '[x](https://example.test/path "<span>title</span>")',
                "",
                "objet",
            ),
            (
                '[x](https://example.test/path "before ) <span color=red>literal</span>")',
                "",
                "objet",
            ),
            (
                '[x](foo(bar)<span>literal</span>)',
                "",
                "objet",
            ),
            (
                '![x](https://example.test/path "before ) <span>image title</span>")',
                "",
                "objet",
            ),
            (
                '[x](https://example.test/path\n  "<span>multiline title</span>")',
                "",
                "objet",
            ),
            (
                '![x](https://example.test/<span>image</span>)',
                "",
                "objet",
            ),
            (
                '[ref]: https://example.test/<span>reference</span>',
                "",
                "objet",
            ),
            (
                '[ref]: https://example.test/path\n  "<span>reference title</span>"',
                "",
                "objet",
            ),
            (
                '[ref]: /url "title\n  more\n  <span color=red>continued reference title</span>"\n\n[x][ref]',
                "",
                "objet",
            ),
            (
                '    <span color="red">root code</span>',
                "",
                "objet",
            ),
            (
                '    first code line\n    <span color="red">continued code</span>',
                "",
                "objet",
            ),
            (
                '-     <span color="red">list code</span>',
                "",
                "objet",
            ),
            (
                '1.     <span color="red">ordered code</span>',
                "",
                "objet",
            ),
            (
                '- item\n\n      <span color="red">nested list code</span>',
                "",
                "objet",
            ),
            (
                ('> ' * 16) + '    <span color="red">deep quote code</span>',
                "",
                "objet",
            ),
        ]
        for body, fragment, kind in cases:
            with self.subTest(body=body):
                bindings = (
                    {digest(fragment): binding(kind)} if fragment else None
                )
                result = completion_workflows._normalize_markup_body(
                    body,
                    bindings=bindings,
                )
                self.assertEqual(result["normalized_body"], body)
                self.assertFalse(result["changed"])
                self.assertIn(
                    "markup_protected_context_unsupported",
                    result["blocker_codes"],
                )
                self.assertEqual(
                    result["counts"]["reference_binding_applied"],
                    0,
                )
                self.assertEqual(result["reference_tag_digests"], [])

        ordinary = 'Use `literal` here.\n\n<file src="actual"></file>'
        actual_fragment = '<file src="actual"></file>'
        ordinary_result = completion_workflows._normalize_markup_body(
            ordinary,
            bindings={digest(actual_fragment): binding("objet")},
        )
        self.assertNotIn(
            "markup_protected_context_unsupported",
            ordinary_result["blocker_codes"],
        )
        self.assertIn("Use `literal` here.", ordinary_result["normalized_body"])
        self.assertIn("[BOUND]", ordinary_result["normalized_body"])

        raw_html_container = (
            '<details>\n\t<span color="red">Actual</span>\n</details>'
        )
        raw_html_result = completion_workflows._normalize_markup_body(
            raw_html_container,
            bindings=None,
        )
        self.assertNotIn(
            "markup_protected_context_unsupported",
            raw_html_result["blocker_codes"],
        )
        self.assertTrue(raw_html_result["changed"])
        self.assertIn("Actual", raw_html_result["normalized_body"])

        adversarial_label = "[" + ("\\" * 32) + "x\n<span>Live</span>"
        started = time.perf_counter()
        self.assertFalse(
            completion_workflows._reference_definition_contains_normalizable_markup(
                adversarial_label
            )
        )
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_markup_protected_container_prefix_scan_is_linear(self) -> None:
        nested = ("> " * 200_000) + "<span>Literal</span>"
        started = time.perf_counter()
        payload = completion_workflows._markdown_container_payload(nested)
        elapsed = time.perf_counter() - started
        self.assertEqual(payload, "<span>Literal</span>")
        self.assertLess(elapsed, 0.75)

        definitions = "[a]: /x\n" * 10_000
        started = time.perf_counter()
        self.assertFalse(
            completion_workflows._reference_definition_contains_normalizable_markup(
                definitions
            )
        )
        self.assertLess(time.perf_counter() - started, 1.0)

        unmatched_links = ("](" * 10_000) + "plain\n"
        started = time.perf_counter()
        self.assertFalse(
            completion_workflows._protected_markup_context_present(
                unmatched_links
            )
        )
        self.assertLess(time.perf_counter() - started, 1.0)

        for adversarial_links in (
            "<span>Live</span>\n" + ("](" * 10_000) + "plain\n",
            ("](" * 10_000)
            + (")" * 10_000)
            + "<span>Live</span>",
        ):
            started = time.perf_counter()
            self.assertFalse(
                completion_workflows._protected_markup_context_present(
                    adversarial_links
                )
            )
            self.assertLess(time.perf_counter() - started, 1.0)

    def test_markup_normalization_rejects_paired_media_fallback_content(self) -> None:
        def digest(fragment: str) -> str:
            return hashlib.sha256(fragment.encode("utf-8")).hexdigest()

        binding = {
            "binding_kind": "objet",
            "binding_id": "sha256:" + ("a" * 64),
            "replacement": "[BOUND]",
        }
        for name in ("audio", "video"):
            fragment = f'<{name} src="opaque">Visible fallback</{name}>'
            with self.subTest(name=name):
                result = completion_workflows._normalize_markup_body(
                    fragment,
                    bindings={digest(fragment): binding},
                )
                self.assertEqual(result["normalized_body"], fragment)
                self.assertIn(
                    f"markup_{name}_inner_content_unsupported",
                    result["blocker_codes"],
                )
                self.assertEqual(
                    result["counts"]["reference_binding_applied"],
                    0,
                )

    def test_markup_normalization_file_reference_regex_edge_cases(self) -> None:
        def digest(fragment: str) -> str:
            return hashlib.sha256(fragment.encode("utf-8")).hexdigest()

        def binding(replacement: str) -> dict[str, str]:
            return {
                "binding_kind": "objet",
                "binding_id": "sha256:" + ("a" * 64),
                "replacement": replacement,
            }

        first = '<file src="a"></file>'
        second = '<file src="b"></file>'
        adjacent = completion_workflows._normalize_markup_body(
            first + second,
            bindings={
                digest(first): binding("[A]"),
                digest(second): binding("[B]"),
            },
        )
        self.assertEqual(adjacent["normalized_body"], "[A][B]")
        self.assertEqual(adjacent["counts"]["reference_binding_applied"], 2)
        self.assertEqual(adjacent["blocker_codes"], [])

        self_closing = '<file src="self"/>'
        standalone = completion_workflows._normalize_markup_body(
            self_closing,
            bindings={digest(self_closing): binding("[SELF]")},
        )
        self.assertEqual(standalone["normalized_body"], "[SELF]")
        self.assertEqual(standalone["counts"]["reference_binding_applied"], 1)
        self.assertEqual(standalone["blocker_codes"], [])

        varied = '<FiLe   src="a"  > \n </fIlE   >'
        case_and_whitespace = completion_workflows._normalize_markup_body(
            varied,
            bindings={digest(varied): binding("[VARIED]")},
        )
        self.assertEqual(case_and_whitespace["normalized_body"], "[VARIED]")
        self.assertEqual(
            case_and_whitespace["counts"]["reference_binding_applied"],
            1,
        )
        self.assertEqual(case_and_whitespace["blocker_codes"], [])

        for malformed in (
            '<file src="a">VISIBLE',
            'VISIBLE</file>',
            '<file src="a">VISIBLE</audio>',
        ):
            with self.subTest(malformed=malformed):
                result = completion_workflows._normalize_markup_body(malformed)
                self.assertEqual(result["normalized_body"], malformed)
                self.assertEqual(
                    result["counts"]["reference_binding_applied"],
                    0,
                )
                self.assertIn(
                    "markup_reference_binding_required",
                    result["blocker_codes"],
                )

    def test_markup_normalization_scales_to_synthetic_3514_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            for folder in ("zettels", "inbox"):
                for path in (archive_root / folder).glob("*.md"):
                    path.unlink()
            for index in range(3514):
                self.write_markup_zettel(
                    archive_root,
                    f"zet_20260804_scale_{index:04d}",
                    f"Row {index}\n<empty-block/>\n",
                )
            plan = completion_workflows.markup_normalization_plan(
                archive_root,
                policy="normalize",
                max_items=4000,
                max_changes=4000,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(
                plan["summary"]["scanned_zettel_count"],
                3514,
            )
            self.assertEqual(
                plan["summary"]["candidate_zettel_count"],
                3514,
            )
            self.assertEqual(
                plan["summary"]["ready_change_count"],
                3514,
            )

    def test_markup_normalization_recovery_resumes_or_rolls_back_exact_bytes(self) -> None:
        for mode in ("resume", "rollback"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                targets = [
                    self.write_markup_zettel(
                        archive_root,
                        f"zet_20260804_recovery_{mode}_{index}",
                        f"Before {index}\n<empty-block/>\n",
                    )
                    for index in range(2)
                ]
                before_bytes = [path.read_bytes() for path in targets]
                plan = completion_workflows.markup_normalization_plan(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                )
                applied = completion_workflows.markup_normalization_apply(
                    archive_root,
                    policy="normalize",
                    max_items=1000,
                    max_changes=1000,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:test",
                )
                self.assertTrue(applied["ok"], applied)
                after_bytes = [path.read_bytes() for path in targets]
                journal_relative = applied["summary"]["journal_path"]
                journal_path = archive_root / journal_relative
                journal = json.loads(
                    journal_path.read_text(encoding="utf-8")
                )
                journal["state"] = "interrupted"
                journal["applied_count"] = 1
                second_before_snapshot = (
                    archive_root
                    / journal["items"][1]["before_snapshot_path"]
                )
                targets[1].write_bytes(second_before_snapshot.read_bytes())
                receipt_path = (
                    archive_root / applied["summary"]["receipt_path"]
                )
                receipt_path.unlink()
                journal_path.write_text(
                    json.dumps(journal),
                    encoding="utf-8",
                )

                recovery_plan = (
                    completion_workflows.markup_normalization_recovery_plan(
                        archive_root,
                        journal=journal_relative,
                        mode=mode,
                    )
                )
                self.assertTrue(recovery_plan["ok"], recovery_plan)
                recovered = (
                    completion_workflows.markup_normalization_recover(
                        archive_root,
                        journal=journal_relative,
                        mode=mode,
                        expected_plan_sha256=recovery_plan["summary"][
                            "plan_sha256"
                        ],
                        reviewed_by="person:test",
                    )
                )
                self.assertTrue(recovered["ok"], recovered)
                expected_bytes = (
                    after_bytes if mode == "resume" else before_bytes
                )
                self.assertEqual(
                    [path.read_bytes() for path in targets],
                    expected_bytes,
                )
                recovered_journal = json.loads(
                    journal_path.read_text(encoding="utf-8")
                )
                self.assertEqual(
                    recovered_journal["state"],
                    "committed" if mode == "resume" else "rolled_back",
                )
                self.assert_schema_instance(
                    "markup-normalization-journal.schema.json",
                    recovered_journal,
                )
                self.assertTrue(
                    (
                        archive_root
                        / recovered["summary"]["recovery_receipt_path"]
                    ).is_file()
                )
                self.assert_schema_instance(
                    "markup-normalization-recovery-receipt.schema.json",
                    json.loads(
                        (
                            archive_root
                            / recovered["summary"][
                                "recovery_receipt_path"
                            ]
                        ).read_text(encoding="utf-8")
                    ),
                )
                if mode == "resume":
                    self.assertTrue(receipt_path.is_file())

    def test_relation_candidate_rejection_memory_is_durable_and_suppressible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260804_series_source"
            target_id = "zet_20260804_series_target"
            self.write_relation_zettel(
                archive_root,
                source_id,
                title="Reviewed Program Session One",
                recurring_series="program:reviewed-series",
                sequence_index=1,
            )
            self.write_relation_zettel(
                archive_root,
                target_id,
                title="Reviewed Program Session Two",
                recurring_series="program:reviewed-series",
                sequence_index=2,
            )
            plan = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertIsNotNone(plan["advisory"])
            self.assertFalse(plan["advisory"]["blocking"])
            candidate = next(
                item
                for item in plan["candidates"]
                if item["target"]["zettel_id"] == target_id
            )
            self.assertIn(
                "continues",
                candidate["suggested_edge_types"],
            )
            self.assertTrue(candidate["edge_type_requires_human_confirmation"])
            self.assertEqual(
                candidate["recommendation_origin"],
                "deterministic_local_metadata",
            )
            self.assertIn("Session Two", candidate["target"]["title"])

            rejected = completion_workflows.relation_candidate_decide(
                archive_root,
                from_zettel=source_id,
                candidate_id=candidate["candidate_id"],
                decision="reject",
                edge_type=None,
                visibility="private",
                reason="Reviewed pair is recurring context but not one continuing work.",
                confidence="high",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(rejected["ok"], rejected)
            self.assertTrue(
                rejected["verification"]["rejection_memory_verified"]
            )
            self.assert_schema_instance(
                "relation-judgment.schema.json",
                json.loads(
                    (
                        archive_root / rejected["judgment_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            self.assert_schema_instance(
                "relation-judgment-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / rejected["judgment_receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            after = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
            )
            self.assertNotIn(
                candidate["candidate_id"],
                [item["candidate_id"] for item in after["candidates"]],
            )
            self.assertGreaterEqual(
                after["summary"]["rejected_suppressed_count"],
                1,
            )
            included = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
                include_rejected=True,
            )
            resurfaced = next(
                item
                for item in included["candidates"]
                if item["candidate_id"] == candidate["candidate_id"]
            )
            self.assertTrue(resurfaced["prior_rejected"])

    def test_relation_candidate_uses_beta_archive_time_and_category_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260807_coordinate_source"
            target_id = "zet_20260807_coordinate_target"
            for zettel_id, title in (
                (source_id, "Alpha Unique Record"),
                (target_id, "Beta Distinct Memo"),
            ):
                (archive_root / "zettels" / f"{zettel_id}.md").write_text(
                    "---\n"
                    f"id: {zettel_id}\n"
                    f"title: {title}\n"
                    "status: canonical\n"
                    "kind: note\n"
                    "facets:\n"
                    "  notion_event_time_start: 2026-08-07T10:30:00+09:00\n"
                    "  source_category: private-category-value\n"
                    "---\n"
                    "Body values are irrelevant to relation projection.\n",
                    encoding="utf-8",
                )

            plan = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
            )

            self.assertTrue(plan["ok"], plan)
            candidate = next(
                item
                for item in plan["candidates"]
                if item["target"]["zettel_id"] == target_id
            )
            signal_kinds = {item["kind"] for item in candidate["signals"]}
            self.assertIn("shared_event_date_coordinate", signal_kinds)
            self.assertIn("shared_archive_category_coordinate", signal_kinds)
            serialized = json.dumps(candidate, ensure_ascii=False)
            self.assertNotIn("private-category-value", serialized)
            self.assertNotIn("2026-08-07T10:30:00", serialized)

    def test_relation_candidate_accept_writes_and_verifies_existing_edge_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            source_id = "zet_20260804_accept_source"
            target_id = "zet_20260804_accept_target"
            source_path = self.write_relation_zettel(
                archive_root,
                source_id,
                title="Accepted Sequence Part One",
                recurring_series="program:accepted-series",
                sequence_index=1,
            )
            self.write_relation_zettel(
                archive_root,
                target_id,
                title="Accepted Sequence Part Two",
                recurring_series="program:accepted-series",
                sequence_index=2,
            )
            plan = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
            )
            candidate = next(
                item
                for item in plan["candidates"]
                if item["target"]["zettel_id"] == target_id
            )
            accepted = completion_workflows.relation_candidate_decide(
                archive_root,
                from_zettel=source_id,
                candidate_id=candidate["candidate_id"],
                decision="accept",
                edge_type="continues",
                visibility="private",
                reason="Human confirmed the target is the next installment in the same work.",
                confidence="high",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(accepted["ok"], accepted)
            self.assertTrue(
                accepted["verification"]["durable_edge_verified"]
            )
            self.assertTrue(
                accepted["verification"]["durable_judgment_verified"]
            )
            written = source_path.read_text(encoding="utf-8")
            self.assertIn("type: continues", written)
            self.assertIn(f"target: {target_id}", written)
            self.assertTrue(
                (
                    archive_root
                    / accepted["judgment_path"]
                ).is_file()
            )
            self.assertTrue(
                (
                    archive_root
                    / accepted["judgment_receipt_path"]
                ).is_file()
            )
            self.assert_schema_instance(
                "relation-judgment.schema.json",
                json.loads(
                    (
                        archive_root / accepted["judgment_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            self.assert_schema_instance(
                "relation-judgment-receipt.schema.json",
                json.loads(
                    (
                        archive_root
                        / accepted["judgment_receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )

    def test_sequence_is_active_manual_semantics_and_writes_only_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            types_path = archive_root / "zettel-kasten" / "types.yml"
            types_doc = completion_workflows.archive_services.load_yaml(
                types_path.read_text(encoding="utf-8")
            )
            types_doc["link_types"] = [
                item
                for item in types_doc["link_types"]
                if item.get("id") != "sequence"
            ]
            types_path.write_text(
                completion_workflows.archive_services.dump_yaml(types_doc),
                encoding="utf-8",
            )
            dry_sync = completion_workflows.archive_services.migrate_archive(
                archive_root,
                target="base-link-types",
                dry_run=True,
                approve=False,
                selected_link_types=["sequence"],
            )
            self.assertTrue(dry_sync["ok"], dry_sync)
            self.assertEqual(
                dry_sync["appended_link_type_ids"],
                ["sequence"],
            )
            approved_sync = (
                completion_workflows.archive_services.migrate_archive(
                    archive_root,
                    target="base-link-types",
                    dry_run=False,
                    approve=True,
                    reviewed_by="person:test",
                    selected_link_types=["sequence"],
                )
            )
            self.assertTrue(approved_sync["ok"], approved_sync)

            source_id = "zet_20260804_process_step_one"
            target_id = "zet_20260804_process_step_two"
            source_path = archive_root / "zettels" / f"{source_id}.md"
            target_path = archive_root / "zettels" / f"{target_id}.md"
            for path, zettel_id, index in (
                (source_path, source_id, 1),
                (target_path, target_id, 2),
            ):
                path.write_text(
                    "---\n"
                    f"id: {zettel_id}\n"
                    f"title: Administrative Step {index}\n"
                    "status: canonical\n"
                    "kind: note\n"
                    "facets:\n"
                    "  process_sequence: application:2026\n"
                    f"  sequence_index: {index}\n"
                    "edges: []\n"
                    "---\n"
                    "Synthetic body.\n",
                    encoding="utf-8",
                )
            plan = completion_workflows.relation_candidate_plan(
                archive_root,
                from_zettel=source_id,
            )
            candidate = next(
                item
                for item in plan["candidates"]
                if item["target"]["zettel_id"] == target_id
            )
            self.assertIn("sequence", candidate["suggested_edge_types"])
            semantics = completion_workflows.relation_semantics_guide()
            sequence = next(
                item
                for item in semantics["distinctions"]
                if item["concept"] == "sequence"
            )
            self.assertEqual(sequence["canonical_edge_type"], "sequence")
            self.assertEqual(
                semantics["rules"]["same_course_next_week_edge"],
                "continues",
            )
            self.assertEqual(
                completion_workflows.archive_services.zettel_edge_batch_item_policy_state(
                    {
                        "edge_type": "sequence",
                        "requires_human_review": False,
                        "review_status": "policy_candidate",
                        "confidence_rank": 4,
                    },
                    {
                        "auto_write_edge_types": ["sequence"],
                        "minimum_confidence_rank": 1,
                    },
                ),
                ("review_queue", "manual_single_edge_review_required"),
            )
            accepted = completion_workflows.relation_candidate_decide(
                archive_root,
                from_zettel=source_id,
                candidate_id=candidate["candidate_id"],
                decision="accept",
                edge_type="sequence",
                visibility="private",
                reason="Human confirmed the next administrative step.",
                confidence="high",
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(accepted["ok"], accepted)
            self.assertIn(
                "type: sequence",
                source_path.read_text(encoding="utf-8"),
            )

    def test_base_link_type_sync_can_partially_revert_only_unused_exact_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            types_path = archive_root / "zettel-kasten" / "types.yml"
            types_doc = completion_workflows.archive_services.load_yaml(
                types_path.read_text(encoding="utf-8")
            )
            types_doc["link_types"] = [
                item
                for item in types_doc["link_types"]
                if item.get("id") != "sequence"
            ]
            types_path.write_text(
                completion_workflows.archive_services.dump_yaml(types_doc),
                encoding="utf-8",
            )
            applied = completion_workflows.archive_services.migrate_archive(
                archive_root,
                target="base-link-types",
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                selected_link_types=["sequence"],
            )
            self.assertTrue(applied["ok"], applied)
            preview = completion_workflows.archive_services.migrate_archive(
                archive_root,
                target="base-link-types",
                dry_run=True,
                approve=False,
                revert=True,
                selected_link_types=["sequence"],
            )
            self.assertTrue(preview["ok"], preview)
            self.assertEqual(
                preview["removable_link_type_ids"],
                ["sequence"],
            )
            reverted = completion_workflows.archive_services.migrate_archive(
                archive_root,
                target="base-link-types",
                dry_run=False,
                approve=True,
                revert=True,
                reviewed_by="person:test",
                selected_link_types=["sequence"],
            )
            self.assertTrue(reverted["ok"], reverted)
            final_types = completion_workflows.archive_services.load_yaml(
                types_path.read_text(encoding="utf-8")
            )
            self.assertNotIn(
                "sequence",
                {
                    item.get("id")
                    for item in final_types["link_types"]
                    if isinstance(item, dict)
                },
            )
            self.assertTrue(
                (archive_root / reverted["revert_receipt_path"]).is_file()
            )
            readopted = completion_workflows.archive_services.migrate_archive(
                archive_root,
                target="base-link-types",
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                selected_link_types=["sequence"],
            )
            self.assertTrue(readopted["ok"], readopted)
            self.assertEqual(readopted["adoption_generation"], 1)
            self.assertNotEqual(
                readopted["receipt_path"],
                applied["receipt_path"],
            )
            second_revert = (
                completion_workflows.archive_services.migrate_archive(
                    archive_root,
                    target="base-link-types",
                    dry_run=False,
                    approve=True,
                    revert=True,
                    reviewed_by="person:test",
                    selected_link_types=["sequence"],
                )
            )
            self.assertTrue(second_revert["ok"], second_revert)
            self.assertNotEqual(
                second_revert["revert_receipt_path"],
                reverted["revert_receipt_path"],
            )

    def test_registered_third_party_principal_can_be_indexed_and_targeted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            principal_id = "company:reviewed-institution"
            plan = completion_workflows.principal_registration_plan(
                archive_root,
                principal_id=principal_id,
                kind="company",
                display_name="Reviewed Institution",
            )
            self.assertTrue(plan["ok"], plan)
            self.assertNotIn(
                "display_name",
                plan["principal"],
            )
            registered = completion_workflows.principal_register(
                archive_root,
                principal_id=principal_id,
                kind="company",
                display_name="Reviewed Institution",
                expected_plan_sha256=plan["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(registered["ok"], registered)
            record = completion_workflows.archive_services.load_yaml(
                (archive_root / registered["record_path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assert_schema_instance(
                "principal-record.schema.json",
                record,
            )
            self.assert_schema_instance(
                "principal-registration-receipt.schema.json",
                json.loads(
                    (archive_root / registered["receipt_path"]).read_text(
                        encoding="utf-8"
                    )
                ),
            )
            listed = completion_workflows.principal_list(archive_root)
            self.assertTrue(listed["ok"], listed)
            listed_principal = next(
                item
                for item in listed["principals"]
                if item["principal_id"] == principal_id
            )
            self.assertNotIn("display_name", listed_principal)

            source_id = "zet_20260804_principal_source"
            source_path = self.write_relation_zettel(
                archive_root,
                source_id,
                title="Institution-linked record",
                recurring_series="program:principal-test",
                sequence_index=1,
            )
            edge = completion_workflows.archive_services.zettel_edge_write(
                archive_root,
                from_zettel=source_id,
                target_ref=principal_id,
                edge_type="applies_to",
                visibility="private",
                approve=True,
                reviewed_by="person:test",
            )
            self.assertTrue(edge["ok"], edge)
            self.assertEqual(
                edge["entity_type_contract"]["target_entity_type"],
                "Principal",
            )
            self.assertIn(
                f"target: {principal_id}",
                source_path.read_text(encoding="utf-8"),
            )
            indexed = completion_workflows.archive_services.index_archive(
                archive_root
            )
            self.assertTrue(indexed["ok"], indexed)
            self.assertEqual(indexed["principals"], 2)
            with closing(
                sqlite3.connect(
                    archive_root / "db" / "archive-index.sqlite"
                )
            ) as connection:
                row = connection.execute(
                    "SELECT kind, display_name FROM principals "
                    "WHERE principal_id = ?",
                    (principal_id,),
                ).fetchone()
            self.assertEqual(row, ("company", "Reviewed Institution"))

            blocked_removal = (
                completion_workflows.principal_unregistration_plan(
                    archive_root,
                    principal_id=principal_id,
                )
            )
            self.assertFalse(blocked_removal["ok"])
            self.assertIn(
                "principal_is_referenced_by_zettel_edge",
                blocked_removal["blockers"],
            )

    def test_unused_registered_principal_can_be_unregistered_with_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            principal_id = "role:reviewed-coordinator"
            plan = completion_workflows.principal_registration_plan(
                archive_root,
                principal_id=principal_id,
                kind="role",
                display_name="Reviewed Coordinator",
            )
            registered = completion_workflows.principal_register(
                archive_root,
                principal_id=principal_id,
                kind="role",
                display_name="Reviewed Coordinator",
                expected_plan_sha256=plan["plan_sha256"],
                reviewed_by="person:test",
            )
            record_path = archive_root / registered["record_path"]
            removal_plan = (
                completion_workflows.principal_unregistration_plan(
                    archive_root,
                    principal_id=principal_id,
                )
            )
            self.assertTrue(removal_plan["ok"], removal_plan)
            removed = completion_workflows.principal_unregister(
                archive_root,
                principal_id=principal_id,
                expected_plan_sha256=removal_plan["plan_sha256"],
                reviewed_by="person:test",
            )
            self.assertTrue(removed["ok"], removed)
            self.assertFalse(record_path.exists())
            self.assert_schema_instance(
                "principal-unregistration-receipt.schema.json",
                json.loads(
                    (archive_root / removed["receipt_path"]).read_text(
                        encoding="utf-8"
                    )
                ),
            )

    def test_principal_cli_runs_reviewed_register_list_unregister_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            principal_id = "team:reviewed-operations"
            common = [
                str(archive_root),
                "--principal-id",
                principal_id,
            ]
            plan_code, plan_output = self.run_cli(
                [
                    "principal-register-plan",
                    *common,
                    "--kind",
                    "team",
                    "--display-name",
                    "Reviewed Operations",
                    "--dry-run",
                ]
            )
            self.assertEqual(plan_code, 0, plan_output)
            plan = json.loads(plan_output)
            register_code, register_output = self.run_cli(
                [
                    "principal-register",
                    *common,
                    "--kind",
                    "team",
                    "--display-name",
                    "Reviewed Operations",
                    "--expected-plan-sha256",
                    plan["plan_sha256"],
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(register_code, 0, register_output)
            listed_code, listed_output = self.run_cli(
                ["principal-list", str(archive_root)]
            )
            self.assertEqual(listed_code, 0, listed_output)
            listed = json.loads(listed_output)
            listed_row = next(
                item
                for item in listed["principals"]
                if item["principal_id"] == principal_id
            )
            self.assertNotIn("display_name", listed_row)
            removal_code, removal_output = self.run_cli(
                [
                    "principal-unregister-plan",
                    *common,
                    "--dry-run",
                ]
            )
            self.assertEqual(removal_code, 0, removal_output)
            removal_plan = json.loads(removal_output)
            unregister_code, unregister_output = self.run_cli(
                [
                    "principal-unregister",
                    *common,
                    "--expected-plan-sha256",
                    removal_plan["plan_sha256"],
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                ]
            )
            self.assertEqual(unregister_code, 0, unregister_output)

    def test_project_bytecode_repair_removes_only_derived_untracked_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror, bytecode, source_bytes = self.project_mirror_fixture(
                project_root
            )
            source = (
                mirror
                / "wom-kit"
                / "src"
                / "wom_kit"
                / "archive_cli.py"
            )
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "ready")
            self.assertEqual(plan["summary"]["bytecode_file_count"], 1)
            self.assertFalse(plan["summary"]["source_files_modified"])
            self.assertFalse(
                plan["privacy_guards"]["bytecode_filenames_echoed"]
            )
            repaired = completion_workflows.project_bytecode_repair(
                project_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:test",
                affirm_external_writers_quiescent=True,
            )
            self.assertTrue(repaired["ok"], repaired)
            self.assertFalse(bytecode.exists())
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(repaired["summary"]["removed_count"], 1)
            self.assertFalse(repaired["summary"]["source_files_modified"])
            self.assertTrue(
                (project_root / repaired["summary"]["receipt_path"]).is_file()
            )
            self.assert_schema_instance(
                "project-bytecode-repair-receipt.schema.json",
                json.loads(
                    (
                        project_root
                        / repaired["summary"]["receipt_path"]
                    ).read_text(encoding="utf-8")
                ),
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=mirror,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(status, "")

    def test_project_bytecode_repair_refuses_tracked_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source_bytes = self.project_mirror_fixture(
                project_root,
                tracked_bytecode=True,
            )
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            self.assertFalse(plan["ok"])
            self.assertIn(
                "project_bytecode_tracked_file_refused",
                plan["blockers"],
            )
            self.assertTrue(bytecode.is_file())


if __name__ == "__main__":
    unittest.main()
