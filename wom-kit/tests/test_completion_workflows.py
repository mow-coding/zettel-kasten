from __future__ import annotations

import io
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

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
            "wom-kit/ai-command-path-routing/v0.12",
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
            self.assertEqual(stored["schema"], "wom-kit/external-locator-record/v0.2")
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
