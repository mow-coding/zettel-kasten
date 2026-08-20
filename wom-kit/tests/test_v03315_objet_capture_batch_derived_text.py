from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, archive_services, completion_workflows


class ObjetCaptureBatchDerivedTextTests(unittest.TestCase):
    def setUp(self) -> None:
        # These are pre-v0.4 durability/recovery fixtures. Keep the public
        # approval surfaces fixed-closed and opt this test class into the two
        # underscore-only historical engines explicitly.
        batch_apply = mock.patch.object(
            completion_workflows,
            "objet_capture_batch_apply",
            completion_workflows._objet_capture_batch_apply_legacy_core,
        )
        derived_register = mock.patch.object(
            archive_services,
            "_derived_text_register",
            archive_services._derived_text_register_legacy_core,
        )
        batch_apply.start()
        derived_register.start()
        self.addCleanup(derived_register.stop)
        self.addCleanup(batch_apply.stop)

    def fake_archive(self, target: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", target)
        (target / ".wom-sandbox").write_text(
            "sandbox\n",
            encoding="utf-8",
        )
        return target

    def source_receipt(self, archive_root: Path) -> str:
        relative = "receipts/sources/letter128.source-intake-plan.json"
        path = archive_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "lifecycle_action": "source_intake_plan",
                    "blockers": [],
                    "content_access": dict(
                        archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
                    ),
                    "source_refs_for_draft": [],
                }
            ),
            encoding="utf-8",
        )
        return relative

    def paired_item(
        self,
        archive_root: Path,
        *,
        index: int = 0,
        korean: bool = False,
    ) -> dict[str, object]:
        prefix = "한국어 문서" if korean else f"letter128-{index:02d}"
        staged_path = f"staging/incoming/{prefix}.pdf"
        derived_path = f"staging/incoming/{prefix}-파생.txt"
        source = archive_root / staged_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            b"%PDF-1.4\n% letter128 fixture "
            + str(index).encode("ascii")
            + b"\n"
        )
        (archive_root / derived_path).write_text(
            f"한국어 파생 텍스트 {index}\n",
            encoding="utf-8",
        )
        return {
            "item_id": f"item-{index:02d}",
            "staged_path": staged_path,
            "source_intake_receipt_path": self.source_receipt(archive_root),
            "derived_text_staged_path": derived_path,
            "derivation_kind": "parser",
            "tool_name": "letter128-parser",
            "tool_version": "1.0.0",
            "review_status": "unreviewed",
            # `model` is the exact legacy v0.1 spelling published before the
            # adapter began preserving the paired half.
            "model": "letter128-model",
            "confidence": 0.95,
            "language": "ko",
            "born_digital": True,
        }

    def plain_item(
        self,
        archive_root: Path,
        *,
        index: int,
    ) -> dict[str, object]:
        staged_path = f"staging/incoming/plain-{index:02d}.pdf"
        source = archive_root / staged_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            b"%PDF-1.4\n% plain fixture "
            + str(index).encode("ascii")
            + b"\n"
        )
        return {
            "item_id": f"plain-{index:02d}",
            "staged_path": staged_path,
            "source_intake_receipt_path": self.source_receipt(archive_root),
        }

    def write_request(
        self,
        archive_root: Path,
        items: list[object],
        *,
        batch_id: str = "letter128-batch",
    ) -> tuple[Path, bytes]:
        request = {
            "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
            "batch_id": batch_id,
            "items": items,
        }
        encoded = json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        path = archive_root / "staging" / f"{batch_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        return path, encoded

    @staticmethod
    def line_count(path: Path) -> int:
        if not path.exists():
            return 0
        return len(
            [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )

    @staticmethod
    def file_snapshot(archive_root: Path) -> dict[str, str]:
        return {
            path.relative_to(archive_root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in archive_root.rglob("*")
            if path.is_file()
        }

    def assert_completion_partition(
        self,
        summary: dict[str, object],
        *,
        approve: bool,
    ) -> None:
        original_write_key = (
            "original_written_item_count"
            if approve
            else "original_would_write_item_count"
        )
        derived_write_key = (
            "derived_text_written_item_count"
            if approve
            else "derived_text_ready_item_count"
        )
        self.assertEqual(
            summary["original_requested_item_count"],
            summary[original_write_key]
            + summary["original_skipped_item_count"]
            + summary["original_blocked_item_count"],
        )
        self.assertEqual(
            summary["derived_text_requested_item_count"],
            summary[derived_write_key]
            + summary["derived_text_skipped_item_count"]
            + summary["derived_text_blocked_item_count"],
        )

    def assert_capture_outcome_unverified(
        self,
        result: dict[str, object],
    ) -> None:
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["state"], "recovery_required")
        self.assertEqual(
            result["blockers"],
            ["batch_capture_outcome_unverified"],
        )
        self.assertTrue(result["outcome_unverified"])
        self.assertTrue(result["writes_may_have_occurred"])
        summary = result["summary"]
        self.assertIsInstance(summary, dict)
        self.assertIsNone(summary["capture_receipt_path"])
        self.assertIsNone(summary["batch_receipt_path"])
        self.assertNotIn("original_written_item_count", summary)
        self.assertNotIn("derived_text_written_item_count", summary)
        self.assertEqual(result["items"], [])
        self.assertEqual(
            result["next_safe_actions"],
            completion_workflows.OBJET_CAPTURE_BATCH_OUTCOME_UNVERIFIED_NEXT_SAFE_ACTIONS,
        )

    def validate_schema(self, name: str, value: dict[str, object]) -> None:
        schema = json.loads(
            (KIT_ROOT / "schemas" / name).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(value)

    def seed_v0314_plain_selection(
        self,
        archive_root: Path,
        items: list[dict[str, object]],
    ) -> dict[str, object]:
        selected_items = []
        for item in items:
            selection_result = archive_services.objet_capture_selection_manifest(
                archive_root,
                staged_path=str(item["staged_path"]),
                source_intake_receipt=str(
                    item["source_intake_receipt_path"]
                ),
                item_id=str(item["item_id"]),
                dry_run=True,
            )
            self.assertTrue(selection_result["ok"], selection_result)
            selected_items.append(
                selection_result["selection_manifest"]["items"][0]
            )
        selection = {
            "manifest_id": "selection:letter128-v0314-originals-only",
            "schema": archive_services.OBJET_CAPTURE_SELECTION_SCHEMA,
            "action": archive_services.OBJET_CAPTURE_SELECTION_ACTION,
            "archive_id": archive_services.read_archive_id(archive_root),
            "created_at": None,
            "created_by": None,
            "project_intake_receipt_path": None,
            "items": selected_items,
            "privacy_guards": {
                key: True
                for key in archive_services.OBJET_CAPTURE_REQUIRED_PRIVACY_GUARDS
            },
        }
        selection_path = archive_root / "staging" / "v0314.selection.json"
        selection_path.write_text(
            json.dumps(selection, ensure_ascii=False),
            encoding="utf-8",
        )
        applied = archive_services._objet_capture_run(
            archive_root,
            selection_path,
            approve=True,
            reviewed_by="person:letter128-v0314",
        )
        self.assertTrue(applied["ok"], applied)
        return applied

    def test_legacy_v01_korean_bom_free_pair_is_preserved_and_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            request_item = self.paired_item(
                archive_root,
                korean=True,
            )
            request_path, request_bytes = self.write_request(
                archive_root,
                [request_item],
            )
            request = json.loads(request_bytes.decode("utf-8"))
            self.validate_schema(
                "objet-capture-batch-request.schema.json",
                request,
            )
            self.assertFalse(request_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertIn("한국어", request_bytes.decode("utf-8"))

            plan, private = completion_workflows._batch_plan_core(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            self.assert_completion_partition(plan["summary"], approve=False)
            self.assertEqual(
                private["selection"]["schema"],
                archive_services.OBJET_CAPTURE_SELECTION_SCHEMA_WITH_DERIVED_TEXT,
            )
            self.assertEqual(
                private["selection"]["action"],
                archive_services.OBJET_CAPTURE_SELECTION_ACTION_WITH_DERIVED_TEXT,
            )
            derived = private["selection"]["items"][0]["derived_text"]
            self.assertEqual(derived["model_name"], "letter128-model")
            self.assertEqual(derived["confidence"], 0.95)
            self.assertEqual(
                plan["summary"]["original_would_write_item_count"],
                1,
            )
            self.assertEqual(
                plan["summary"]["derived_text_ready_item_count"],
                1,
            )
            self.assertEqual(
                plan["items"][0]["derived_text"]["item_status"],
                "ready",
            )
            public_plan = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn(str(request_item["staged_path"]), public_plan)
            self.assertNotIn(
                str(request_item["derived_text_staged_path"]),
                public_plan,
            )

            files_before = self.file_snapshot(archive_root)
            applied = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["next_safe_actions"], [])
            files_after = self.file_snapshot(archive_root)
            actual_delta = {
                path
                for path in set(files_before) | set(files_after)
                if files_before.get(path) != files_after.get(path)
                and not path.endswith(".lock")
            }
            self.assertEqual(set(applied["files_written"]), actual_delta)
            self.assertEqual(
                len(applied["files_written"]),
                len(set(applied["files_written"])),
            )
            self.assertFalse(
                any(path.endswith(".lock") for path in applied["files_written"])
            )
            self.assertIn(private["selection_relative"], actual_delta)
            self.assertTrue(
                any(
                    path.startswith("objects/sha256/")
                    for path in applied["files_written"]
                )
            )
            self.assertTrue(
                any(
                    path.startswith(
                        f"{archive_services.DERIVED_TEXT_STORE_PREFIX}/"
                    )
                    for path in applied["files_written"]
                )
            )
            self.assertTrue(
                any(
                    path.startswith(
                        f"{archive_services.DERIVED_TEXT_CAPTURE_RECEIPTS_DIR}/"
                    )
                    for path in applied["files_written"]
                )
            )
            self.assertIn("objects/manifests/files.jsonl", actual_delta)
            self.assertIn(
                archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH,
                actual_delta,
            )
            self.assertIn(
                applied["summary"]["capture_receipt_path"],
                actual_delta,
            )
            self.assertIn(
                applied["summary"]["batch_receipt_path"],
                actual_delta,
            )
            public_applied = json.dumps(applied, ensure_ascii=False)
            self.assertNotIn(str(request_item["staged_path"]), public_applied)
            self.assertNotIn(
                str(request_item["derived_text_staged_path"]),
                public_applied,
            )
            self.assert_completion_partition(applied["summary"], approve=True)
            self.assertEqual(
                applied["summary"]["original_written_item_count"],
                1,
            )
            self.assertEqual(
                applied["summary"]["derived_text_written_item_count"],
                1,
            )
            self.assertEqual(
                applied["items"][0]["derived_text"]["item_status"],
                "written",
            )
            batch_receipt = json.loads(
                (
                    archive_root
                    / applied["summary"]["batch_receipt_path"]
                ).read_text(encoding="utf-8")
            )
            self.validate_schema(
                "objet-capture-batch-receipt.schema.json",
                batch_receipt,
            )
            self.assertEqual(batch_receipt["derived_text_written_item_count"], 1)

    def test_v0314_ten_originals_reconcile_without_original_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            paired_items = [
                self.paired_item(archive_root, index=index)
                for index in range(10)
            ]
            self.seed_v0314_plain_selection(archive_root, paired_items)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_lines_before = self.line_count(files_manifest)
            derived_lines_before = self.line_count(derived_manifest)
            object_files_before = {
                path.relative_to(archive_root).as_posix()
                for path in (archive_root / "objects" / "sha256").rglob("*")
                if path.is_file()
            }
            request_path, _ = self.write_request(
                archive_root,
                paired_items,
                batch_id="letter128-reconcile-ten",
            )

            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            self.assert_completion_partition(plan["summary"], approve=False)
            self.assertEqual(plan["summary"]["would_skip"], 10)
            self.assertEqual(
                plan["summary"]["would_register_derived_text"],
                10,
            )
            self.assertEqual(
                plan["summary"]["derived_text_blocked_item_count"],
                0,
            )

            applied = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-reconcile",
            )
            self.assertTrue(applied["ok"], applied)
            self.assert_completion_partition(applied["summary"], approve=True)
            self.assertEqual(
                applied["summary"]["original_written_item_count"],
                0,
            )
            self.assertEqual(
                applied["summary"]["original_skipped_item_count"],
                10,
            )
            self.assertEqual(
                applied["summary"]["derived_text_written_item_count"],
                10,
            )
            self.assertEqual(self.line_count(files_manifest), original_lines_before)
            self.assertEqual(
                self.line_count(derived_manifest) - derived_lines_before,
                10,
            )
            object_files_after = {
                path.relative_to(archive_root).as_posix()
                for path in (archive_root / "objects" / "sha256").rglob("*")
                if path.is_file()
            }
            self.assertEqual(object_files_after, object_files_before)

    def test_mixed_paired_and_plain_items_keep_one_paired_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            items = [
                self.paired_item(archive_root, index=1),
                self.plain_item(archive_root, index=2),
            ]
            request_path, _ = self.write_request(
                archive_root,
                items,
                batch_id="letter128-mixed",
            )
            plan, private = completion_workflows._batch_plan_core(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            self.assert_completion_partition(plan["summary"], approve=False)
            self.assertEqual(
                private["selection"]["action"],
                archive_services.OBJET_CAPTURE_SELECTION_ACTION_WITH_DERIVED_TEXT,
            )
            self.assertEqual(
                plan["summary"]["original_would_write_item_count"],
                2,
            )
            self.assertEqual(
                plan["summary"]["derived_text_requested_item_count"],
                1,
            )
            self.assertEqual(
                [item["derived_text_requested"] for item in plan["items"]],
                [True, False],
            )

    def test_invalid_or_unknown_paired_fields_block_before_selection_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            base = self.paired_item(archive_root)
            cases: list[tuple[str, dict[str, object], str]] = []

            unknown = dict(base)
            unknown["future_payload"] = "must-not-drop"
            cases.append(("unknown", unknown, "batch_item_unknown_field"))

            missing = dict(base)
            missing.pop("tool_version")
            cases.append(
                (
                    "missing-required",
                    missing,
                    "derived_text_required_field_missing",
                )
            )

            metadata_only = self.plain_item(archive_root, index=9)
            metadata_only["derivation_kind"] = "parser"
            cases.append(
                (
                    "metadata-without-path",
                    metadata_only,
                    "derived_text_staged_path_required",
                )
            )

            invalid_confidence = dict(base)
            invalid_confidence["confidence"] = "high"
            cases.append(
                ("invalid-confidence", invalid_confidence, "confidence_invalid")
            )

            out_of_range_confidence = dict(base)
            out_of_range_confidence["confidence"] = 1.01
            cases.append(
                (
                    "out-of-range-confidence",
                    out_of_range_confidence,
                    "confidence_invalid",
                )
            )

            with mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
            ) as selection:
                for label, item, expected in cases:
                    with self.subTest(label=label):
                        selection.reset_mock()
                        request_path, _ = self.write_request(
                            archive_root,
                            [item],
                            batch_id=f"letter128-{label}",
                        )
                        plan = completion_workflows.objet_capture_batch_plan(
                            archive_root,
                            manifest_path=request_path,
                        )
                        self.assertFalse(plan["ok"], plan)
                        self.assertIn(expected, plan["blockers"])
                        selection.assert_not_called()
                        self.assertIsNone(plan["summary"]["plan_sha256"])

    def test_derived_text_drift_changes_plan_and_blocks_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-drift",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            files_before = self.line_count(files_manifest)
            (archive_root / str(item["derived_text_staged_path"])).write_text(
                "changed after review\n",
                encoding="utf-8",
            )
            blocked = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128",
            )
            self.assertFalse(blocked["ok"], blocked)
            self.assertIn("batch_plan_changed", blocked["blockers"])
            self.assertEqual(self.line_count(files_manifest), files_before)
            self.assertFalse(blocked["files_written"])

    def test_selection_swap_captures_only_reviewed_memory_and_requires_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            reviewed = self.paired_item(archive_root, index=1)
            attacker = self.plain_item(archive_root, index=2)
            request_path, _ = self.write_request(
                archive_root,
                [reviewed],
                batch_id="letter128-selection-swap",
            )
            plan, private = completion_workflows._batch_plan_core(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            attacker_selection = archive_services.objet_capture_selection_manifest(
                archive_root,
                staged_path=str(attacker["staged_path"]),
                source_intake_receipt=str(
                    attacker["source_intake_receipt_path"]
                ),
                item_id=str(attacker["item_id"]),
                dry_run=True,
            )["selection_manifest"]
            attacker_selection_bytes = completion_workflows._canonical_json_bytes(
                attacker_selection
            )
            real_apply = archive_services._objet_capture_run
            passed_selection_document: dict[str, object] = {}

            def swap_then_apply(
                root: Path | str,
                selection_relative: Path | str,
                **kwargs: object,
            ) -> dict[str, object]:
                selection_document = kwargs.get("selection_document")
                if isinstance(selection_document, dict):
                    passed_selection_document.update(selection_document)
                selection_path = archive_services.archive_internal_path(
                    Path(root).resolve(),
                    str(selection_relative),
                )
                selection_path.write_bytes(attacker_selection_bytes)
                return real_apply(
                    root,
                    selection_relative,
                    **kwargs,
                )

            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            with mock.patch.object(
                archive_services,
                "_objet_capture_run",
                side_effect=swap_then_apply,
            ):
                applied = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128-audit",
                )

            self.assertEqual(passed_selection_document, private["selection"])
            self.assertFalse(applied["ok"], applied)
            self.assertEqual(applied["state"], "recovery_required")
            self.assertIn(
                "batch_selection_evidence_drift_after_capture",
                applied["blockers"],
            )
            self.assertFalse(
                applied["summary"]["selection_evidence_verified"]
            )
            self.assertTrue(applied["summary"]["recovery_required"])
            self.assertTrue(applied["writes_may_have_occurred"])
            self.assertEqual(
                applied["next_safe_actions"],
                completion_workflows.OBJET_CAPTURE_BATCH_SELECTION_RECOVERY_NEXT_SAFE_ACTIONS,
            )
            self.assertEqual(
                applied["summary"]["next_safe_action"],
                "inspect_selection_collision_then_fresh_dry_run",
            )
            self.assertEqual(
                [item["item_id"] for item in applied["items"]],
                [reviewed["item_id"]],
            )
            self.assertEqual(
                applied["summary"]["original_written_item_count"],
                1,
            )
            self.assertEqual(
                applied["summary"]["derived_text_written_item_count"],
                1,
            )
            rendered = json.dumps(applied, ensure_ascii=False)
            self.assertNotIn(str(attacker["item_id"]), rendered)
            self.assertNotIn(str(attacker["staged_path"]), rendered)
            self.assertNotIn(str(archive_root), rendered)

            reviewed_digest = hashlib.sha256(
                (archive_root / str(reviewed["staged_path"])).read_bytes()
            ).hexdigest()
            attacker_digest = hashlib.sha256(
                (archive_root / str(attacker["staged_path"])).read_bytes()
            ).hexdigest()
            object_ids = {
                str(record.get("object_id") or "")
                for record in archive_services.load_manifest_records(
                    archive_root
                )
            }
            self.assertIn(f"sha256:{reviewed_digest}", object_ids)
            self.assertNotIn(f"sha256:{attacker_digest}", object_ids)
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)
            batch_receipt_path = (
                archive_root / applied["summary"]["batch_receipt_path"]
            )
            batch_receipt = json.loads(
                batch_receipt_path.read_text(encoding="utf-8")
            )
            self.assertFalse(batch_receipt["ok"])
            self.assertEqual(
                batch_receipt["status_class"],
                "evidence_incomplete",
            )

            # Simulate explicit operator inspection and restoration of the
            # reviewed content-addressed selection evidence. The next approved
            # run must converge via skips without duplicating either half.
            restored_selection_path = archive_services.archive_internal_path(
                archive_root,
                private["selection_relative"],
            )
            restored_selection_path.write_bytes(private["selection_bytes"])
            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-recovery",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(
                replay["summary"]["original_skipped_item_count"],
                1,
            )
            self.assertEqual(
                replay["summary"]["derived_text_skipped_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_case_alias_and_hardlink_targets_block_before_source_reads(self) -> None:
        for alias_kind in ("case", "hardlink"):
            with self.subTest(alias_kind=alias_kind), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                first = self.paired_item(archive_root, index=1)
                second = self.paired_item(archive_root, index=2)
                first_text = archive_root / str(
                    first["derived_text_staged_path"]
                )
                second_text = archive_root / str(
                    second["derived_text_staged_path"]
                )
                shared = first_text.with_name("Transcript.txt")
                first_text.replace(shared)
                first["derived_text_staged_path"] = shared.relative_to(
                    archive_root
                ).as_posix()
                second_text.unlink()
                if alias_kind == "case":
                    second["derived_text_staged_path"] = (
                        shared.with_name("transcript.txt")
                        .relative_to(archive_root)
                        .as_posix()
                    )
                else:
                    hardlink = shared.with_name("transcript-hardlink.txt")
                    os.link(shared, hardlink)
                    second["derived_text_staged_path"] = hardlink.relative_to(
                        archive_root
                    ).as_posix()
                request_path, _ = self.write_request(
                    archive_root,
                    [first, second],
                    batch_id=f"letter128-alias-{alias_kind}",
                )
                with mock.patch.object(
                    archive_services,
                    "objet_capture_selection_manifest",
                ) as selection:
                    plan = completion_workflows.objet_capture_batch_plan(
                        archive_root,
                        manifest_path=request_path,
                    )
                self.assertFalse(plan["ok"], plan)
                self.assertIn("duplicate_selection_target", plan["blockers"])
                selection.assert_not_called()

    def test_paired_staged_text_growth_hits_cumulative_cap_plus_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            relative = "staging/incoming/growing-transcript.txt"
            source = archive_root / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"12345678")
            real_read = os.read
            read_count = 0

            def grow_after_first_read(fd: int, count: int) -> bytes:
                nonlocal read_count
                data = real_read(fd, count)
                read_count += 1
                if read_count == 1 and data:
                    with source.open("ab") as handle:
                        handle.write(b"9")
                        handle.flush()
                        os.fsync(handle.fileno())
                return data

            with (
                mock.patch.object(
                    archive_services,
                    "DERIVED_TEXT_MAX_SOURCE_BYTES",
                    8,
                ),
                mock.patch.object(
                    archive_services.os,
                    "read",
                    side_effect=grow_after_first_read,
                ),
            ):
                raw, blockers = (
                    archive_services._objet_capture_read_staged_text_bytes(
                        archive_root,
                        relative,
                    )
                )
            self.assertIsNone(raw)
            self.assertEqual(blockers, ["text_file_too_large"])
            self.assertEqual(read_count, 2)

    def test_standalone_reader_blocks_initial_over_cap_and_under_cap_growth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "standalone-transcript.txt"
            source.write_bytes(b"123456789")
            real_read = os.read
            with (
                mock.patch.object(
                    archive_services,
                    "DERIVED_TEXT_MAX_SOURCE_BYTES",
                    8,
                ),
                mock.patch.object(
                    archive_services.os,
                    "read",
                    wraps=real_read,
                ) as read_mock,
            ):
                raw, blockers = archive_services._derived_text_read_source_file(
                    source
                )
            self.assertIsNone(raw)
            self.assertEqual(blockers, ["text_file_too_large"])
            read_mock.assert_not_called()

            source.write_bytes(b"1234")
            read_count = 0

            def grow_below_cap(fd: int, count: int) -> bytes:
                nonlocal read_count
                data = real_read(fd, count)
                read_count += 1
                if read_count == 1 and data:
                    with source.open("ab") as handle:
                        handle.write(b"5")
                        handle.flush()
                        os.fsync(handle.fileno())
                return data

            with (
                mock.patch.object(
                    archive_services,
                    "DERIVED_TEXT_MAX_SOURCE_BYTES",
                    8,
                ),
                mock.patch.object(
                    archive_services.os,
                    "read",
                    side_effect=grow_below_cap,
                ),
            ):
                raw, blockers = archive_services._derived_text_read_source_file(
                    source
                )
            self.assertIsNone(raw)
            self.assertEqual(blockers, ["text_file_changed_during_read"])
            self.assertGreaterEqual(read_count, 2)

    def test_unsafe_metadata_probe_is_fixed_blocker_without_exception_or_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-unsafe-probe",
            )
            rejected_relative = str(item["staged_path"])
            real_internal_path = archive_services.archive_internal_path

            def reject_reparse_target(
                root: Path | str,
                relative: Path | str,
            ) -> Path:
                if str(relative).replace("\\", "/") == rejected_relative:
                    raise archive_services.ArchiveServiceError(
                        r"private path C:\outside\must-not-echo"
                    )
                return real_internal_path(root, relative)

            with (
                mock.patch.object(
                    archive_services,
                    "archive_internal_path",
                    side_effect=reject_reparse_target,
                ),
                mock.patch.object(
                    archive_services,
                    "objet_capture_selection_manifest",
                ) as selection,
            ):
                plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
            self.assertFalse(plan["ok"], plan)
            self.assertIn("batch_selection_path_unsafe", plan["blockers"])
            self.assertNotIn("C:\\outside", json.dumps(plan))
            selection.assert_not_called()

    def test_duplicate_json_members_fail_closed_before_source_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request = {
                "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
                "batch_id": "letter128-duplicate-json",
                "items": [item],
            }
            encoded = json.dumps(
                request,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            needle = '"tool_name":"letter128-parser"'
            self.assertIn(needle, encoded)
            encoded = encoded.replace(
                needle,
                '"tool_name":"first","tool_name":"letter128-parser"',
                1,
            )
            request_path = archive_root / "staging" / "duplicate-json.json"
            request_path.write_bytes(encoded.encode("utf-8"))
            with mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
            ) as selection:
                plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
            self.assertFalse(plan["ok"], plan)
            self.assertEqual(plan["blockers"], ["input_duplicate_json_member"])
            selection.assert_not_called()

    def test_batch_request_read_is_bounded_stable_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            request_path = archive_root / "staging" / "private-request.json"
            request_path.parent.mkdir(parents=True, exist_ok=True)

            request_path.write_bytes(b"PRIVATE99")
            with (
                mock.patch.object(
                    completion_workflows,
                    "OBJET_CAPTURE_BATCH_REQUEST_MAX_BYTES",
                    8,
                ),
                mock.patch.object(completion_workflows.json, "loads") as loads,
            ):
                too_large = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
            self.assertEqual(too_large["blockers"], ["input_file_too_large"])
            loads.assert_not_called()
            rendered = json.dumps(too_large)
            self.assertNotIn("PRIVATE99", rendered)
            self.assertNotIn(str(request_path), rendered)

            request_path.write_bytes(b'{"schema":"x"}')
            real_read = archive_services.os.read
            mutated = False

            def grow_during_read(fd: int, size: int) -> bytes:
                nonlocal mutated
                chunk = real_read(fd, size)
                if chunk and not mutated:
                    mutated = True
                    with request_path.open("ab") as handle:
                        handle.write(b" ")
                return chunk

            with (
                mock.patch.object(
                    completion_workflows,
                    "OBJET_CAPTURE_BATCH_REQUEST_MAX_BYTES",
                    64,
                ),
                mock.patch.object(
                    archive_services.os,
                    "read",
                    side_effect=grow_during_read,
                ),
                mock.patch.object(completion_workflows.json, "loads") as loads,
            ):
                changed = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
            self.assertTrue(mutated)
            self.assertEqual(
                changed["blockers"],
                ["input_file_changed_during_read"],
            )
            loads.assert_not_called()
            self.assertNotIn(str(request_path), json.dumps(changed))

    def test_project_receipt_alias_is_exclusive_and_top_level_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.plain_item(archive_root, index=3)
            receipt = str(item["source_intake_receipt_path"])
            schema = json.loads(
                (
                    KIT_ROOT
                    / "schemas"
                    / "objet-capture-batch-request.schema.json"
                ).read_text(encoding="utf-8")
            )
            validator = Draft202012Validator(schema)

            for field in (
                "project_intake_receipt",
                "project_intake_receipt_path",
            ):
                request = {
                    "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
                    "batch_id": f"letter128-{field}",
                    field: receipt,
                    "items": [item],
                }
                validator.validate(request)
                path = archive_root / "staging" / f"{field}.json"
                path.write_text(json.dumps(request), encoding="utf-8")
                with mock.patch.object(
                    archive_services,
                    "objet_capture_selection_manifest",
                    wraps=archive_services.objet_capture_selection_manifest,
                ) as selection:
                    plan = completion_workflows.objet_capture_batch_plan(
                        archive_root,
                        manifest_path=path,
                    )
                self.assertNotIn("batch_request_unknown_field", plan["blockers"])
                self.assertNotIn(
                    "project_intake_receipt_fields_conflict",
                    plan["blockers"],
                )
                self.assertEqual(
                    selection.call_args.kwargs["project_intake_receipt"],
                    receipt,
                )

            for field in (
                "project_intake_receipt",
                "project_intake_receipt_path",
            ):
                empty = {
                    "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
                    "batch_id": f"letter128-empty-{field}",
                    field: "",
                    "items": [item],
                }
                self.assertTrue(list(validator.iter_errors(empty)))
                empty_path = archive_root / "staging" / f"empty-{field}.json"
                empty_path.write_text(json.dumps(empty), encoding="utf-8")
                with mock.patch.object(
                    archive_services,
                    "objet_capture_selection_manifest",
                ) as selection:
                    empty_plan = completion_workflows.objet_capture_batch_plan(
                        archive_root,
                        manifest_path=empty_path,
                    )
                self.assertFalse(empty_plan["ok"])
                self.assertIn(
                    "project_intake_receipt_invalid",
                    empty_plan["blockers"],
                )
                selection.assert_not_called()

            conflicting = {
                "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
                "batch_id": "letter128-project-conflict",
                "project_intake_receipt": receipt,
                "project_intake_receipt_path": receipt,
                "items": [item],
            }
            self.assertTrue(list(validator.iter_errors(conflicting)))
            conflict_path = archive_root / "staging" / "project-conflict.json"
            conflict_path.write_text(json.dumps(conflicting), encoding="utf-8")
            with mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
            ) as selection:
                conflict_plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=conflict_path,
                )
            self.assertFalse(conflict_plan["ok"])
            self.assertIn(
                "project_intake_receipt_fields_conflict",
                conflict_plan["blockers"],
            )
            selection.assert_not_called()

            unknown = {
                "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
                "batch_id": "letter128-top-unknown",
                "items": [item],
                "future_payload": "must-not-drop",
            }
            self.assertTrue(list(validator.iter_errors(unknown)))
            unknown_path = archive_root / "staging" / "top-unknown.json"
            unknown_path.write_text(json.dumps(unknown), encoding="utf-8")
            with mock.patch.object(
                archive_services,
                "objet_capture_selection_manifest",
            ) as selection:
                unknown_plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=unknown_path,
                )
            self.assertFalse(unknown_plan["ok"])
            self.assertIn("batch_request_unknown_field", unknown_plan["blockers"])
            selection.assert_not_called()

    def test_partial_derived_failure_is_non_success_with_durable_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-partial",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            real_pair = archive_services._objet_capture_paired_derived_text

            def fail_only_approval(*args: object, **kwargs: object) -> dict[str, object]:
                if kwargs.get("approve") is not True:
                    return real_pair(*args, **kwargs)
                blocked = archive_services._objet_capture_derived_text_initial_subresult()
                blocked["item_status"] = "blocked"
                blocked["blockers"] = ["synthetic_derived_failure"]
                return blocked

            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            derived_before = self.line_count(derived_manifest)
            with mock.patch.object(
                archive_services,
                "_objet_capture_paired_derived_text",
                side_effect=fail_only_approval,
            ):
                applied = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )
            self.assertFalse(applied["ok"], applied)
            self.assert_completion_partition(applied["summary"], approve=True)
            self.assertEqual(applied["state"], "partial")
            self.assertEqual(
                applied["next_safe_actions"],
                archive_services.OBJET_CAPTURE_PARTIAL_NEXT_SAFE_ACTIONS,
            )
            self.assertIn(
                "batch_derived_text_completion_incomplete",
                applied["blockers"],
            )
            self.assertEqual(
                applied["summary"]["original_written_item_count"],
                1,
            )
            self.assertEqual(
                applied["summary"]["derived_text_blocked_item_count"],
                1,
            )
            self.assertEqual(self.line_count(derived_manifest), derived_before)
            source_digest = hashlib.sha256(
                (archive_root / str(item["staged_path"])).read_bytes()
            ).hexdigest()
            self.assertTrue(
                (
                    archive_root
                    / "objects"
                    / "sha256"
                    / source_digest[:2]
                    / source_digest
                ).is_file()
            )
            batch_receipt = json.loads(
                (
                    archive_root
                    / applied["summary"]["batch_receipt_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertFalse(batch_receipt["ok"])
            self.assertEqual(batch_receipt["original_written_item_count"], 1)
            self.assertEqual(batch_receipt["derived_text_blocked_item_count"], 1)
            self.validate_schema(
                "objet-capture-batch-receipt.schema.json",
                batch_receipt,
            )

            files_manifest = archive_root / "objects/manifests/files.jsonl"
            original_lines_after_partial = self.line_count(files_manifest)
            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            self.assertEqual(
                replay_plan["summary"]["plan_sha256"],
                plan["summary"]["plan_sha256"],
            )
            self.assertEqual(replay_plan["summary"]["would_skip"], 1)
            self.assertEqual(
                replay_plan["summary"]["would_register_derived_text"],
                1,
            )
            repaired = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-repair",
            )
            self.assertTrue(repaired["ok"], repaired)
            self.assert_completion_partition(repaired["summary"], approve=True)
            self.assertNotEqual(
                repaired["summary"]["batch_receipt_path"],
                applied["summary"]["batch_receipt_path"],
            )
            repaired_receipt = json.loads(
                (
                    archive_root
                    / repaired["summary"]["batch_receipt_path"]
                ).read_text(encoding="utf-8")
            )
            self.assertTrue(repaired_receipt["ok"])
            self.assertEqual(repaired_receipt["original_skipped_item_count"], 1)
            self.assertEqual(repaired_receipt["derived_text_written_item_count"], 1)
            self.assertNotEqual(
                repaired_receipt["attempt_sha256"],
                batch_receipt["attempt_sha256"],
            )
            self.assertFalse(batch_receipt["ok"])
            self.assertEqual(
                self.line_count(files_manifest),
                original_lines_after_partial,
            )
            self.assertEqual(
                self.line_count(derived_manifest) - derived_before,
                1,
            )

    def test_batch_receipt_failure_is_evidence_incomplete_and_replay_converges(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-batch-receipt-failure",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            real_create = archive_services._write_bytes_create_if_absent

            def fail_batch_receipt(path: Path, payload: bytes) -> None:
                if "receipts/objet-capture-batches/" in Path(path).as_posix():
                    raise OSError("synthetic batch receipt failure")
                real_create(path, payload)

            with mock.patch.object(
                archive_services,
                "_write_bytes_create_if_absent",
                side_effect=fail_batch_receipt,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )

            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "evidence_incomplete")
            self.assertEqual(
                failed["next_safe_actions"],
                completion_workflows.OBJET_CAPTURE_BATCH_EVIDENCE_INCOMPLETE_NEXT_SAFE_ACTIONS,
            )
            self.assertIn("batch_receipt_write_failed", failed["blockers"])
            self.assertIsNone(failed["summary"]["batch_receipt_path"])
            self.assertTrue(failed["summary"]["batch_receipt_proposed_path"])
            self.assertTrue(failed["summary"]["recovery_required"])
            self.assertEqual(
                failed["summary"]["next_safe_action"],
                "fresh_dry_run_then_replay",
            )
            self.assertTrue(failed["summary"]["capture_receipt_path"])
            self.assertTrue(
                (
                    archive_root
                    / failed["summary"]["capture_receipt_path"]
                ).is_file()
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            self.assertEqual(replay_plan["summary"]["would_skip"], 1)
            self.assertEqual(
                replay_plan["summary"]["would_skip_derived_text"],
                1,
            )
            recovered = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-recovery",
            )
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["state"], "written")
            self.assertTrue(recovered["summary"]["batch_receipt_path"])
            self.assertNotEqual(
                recovered["summary"]["batch_receipt_path"],
                failed["summary"]["batch_receipt_proposed_path"],
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_derived_receipt_failure_preserves_exact_delta_and_replay_converges(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-derived-receipt-failure",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            files_before = self.file_snapshot(archive_root)

            with mock.patch.object(
                archive_services,
                "_derived_text_write_receipt",
                side_effect=OSError(
                    r"private C:\outside\derived-receipt must-not-echo"
                ),
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )

            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "partial")
            self.assertFalse(failed.get("outcome_unverified", False))
            self.assertFalse(failed.get("writes_may_have_occurred", False))
            self.assertEqual(
                failed["next_safe_actions"],
                archive_services.OBJET_CAPTURE_PARTIAL_NEXT_SAFE_ACTIONS,
            )
            self.assertEqual(
                failed["items"][0]["derived_text"]["blockers"],
                ["derived_text_receipt_write_failed"],
            )
            self.assertEqual(
                failed["summary"]["derived_text_blocked_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)
            self.assertTrue(failed["summary"]["capture_receipt_path"])
            self.assertTrue(failed["summary"]["batch_receipt_path"])

            files_after = self.file_snapshot(archive_root)
            actual_delta = {
                path
                for path in set(files_before) | set(files_after)
                if files_before.get(path) != files_after.get(path)
                and not path.endswith(".lock")
            }
            self.assertEqual(set(failed["files_written"]), actual_delta)
            self.assertIn(
                archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH,
                actual_delta,
            )
            self.assertTrue(
                any(
                    path.startswith(
                        f"{archive_services.DERIVED_TEXT_STORE_PREFIX}/"
                    )
                    for path in actual_delta
                )
            )
            self.assertFalse(
                any(
                    path.startswith(
                        f"{archive_services.DERIVED_TEXT_CAPTURE_RECEIPTS_DIR}/"
                    )
                    for path in actual_delta
                )
            )
            self.assertNotIn("must-not-echo", json.dumps(failed))

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-recovery",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["state"], "written")
            self.assertEqual(replay["summary"]["original_skipped_item_count"], 1)
            self.assertEqual(
                replay["summary"]["derived_text_skipped_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)
            self.assertTrue(
                any(
                    path.startswith(
                        f"{archive_services.DERIVED_TEXT_CAPTURE_RECEIPTS_DIR}/"
                    )
                    for path in replay["files_written"]
                )
            )

    def test_post_publication_exception_matrix_reobserves_exact_and_replays(
        self,
    ) -> None:
        cases = (
            "original-object",
            "derived-object",
            "original-manifest",
            "derived-manifest",
            "selection-receipt",
            "derived-receipt",
            "objet-receipt",
            "batch-receipt",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                failure_type = (
                    RuntimeError
                    if case
                    in (
                        "original-object",
                        "original-manifest",
                        "selection-receipt",
                        "objet-receipt",
                    )
                    else OSError
                )
                archive_root = self.fake_archive(Path(tmp) / "archive")
                canonical_root = archive_services.require_existing_archive_root(
                    archive_root
                )
                item = self.paired_item(archive_root)
                request_path, _ = self.write_request(
                    archive_root,
                    [item],
                    batch_id=f"letter128-post-publish-{case}",
                )
                plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
                self.assertTrue(plan["ok"], plan)
                files_manifest = archive_root / "objects/manifests/files.jsonl"
                derived_manifest = (
                    archive_root
                    / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
                )
                original_before = self.line_count(files_manifest)
                derived_before = self.line_count(derived_manifest)
                files_before = self.file_snapshot(archive_root)
                triggered = False

                if case in ("original-object", "derived-object"):
                    real_operation = archive_services.os.replace

                    def replace_then_raise(
                        source: Path | str,
                        destination: Path | str,
                    ) -> None:
                        nonlocal triggered
                        real_operation(source, destination)
                        relative = archive_services.archive_relative_path(
                            Path(destination),
                            canonical_root,
                        )
                        is_derived = relative.startswith(
                            f"{archive_services.DERIVED_TEXT_STORE_PREFIX}/"
                        )
                        matches = (
                            case == "derived-object" and is_derived
                        ) or (
                            case == "original-object"
                            and relative.startswith("objects/sha256/")
                        )
                        if matches and not triggered:
                            triggered = True
                            raise failure_type(f"private post-publish {case}")

                    patcher = mock.patch.object(
                        archive_services.os,
                        "replace",
                        side_effect=replace_then_raise,
                    )
                elif case in ("original-manifest", "derived-manifest"):
                    real_operation = archive_services._append_bytes_once

                    def append_then_raise(path: Path, payload: bytes) -> None:
                        nonlocal triggered
                        real_operation(path, payload)
                        relative = archive_services.archive_relative_path(
                            path,
                            canonical_root,
                        )
                        expected = (
                            archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
                            if case == "derived-manifest"
                            else "objects/manifests/files.jsonl"
                        )
                        if relative == expected and not triggered:
                            triggered = True
                            raise failure_type(f"private post-append {case}")

                    patcher = mock.patch.object(
                        archive_services,
                        "_append_bytes_once",
                        side_effect=append_then_raise,
                    )
                else:
                    real_operation = archive_services._write_bytes_create_if_absent

                    def create_then_raise(path: Path, payload: bytes) -> None:
                        nonlocal triggered
                        real_operation(path, payload)
                        relative = archive_services.archive_relative_path(
                            path,
                            canonical_root,
                        )
                        prefixes = {
                            "selection-receipt": (
                                f"{archive_services.OBJET_CAPTURE_SELECTION_MANIFESTS_DIR}/"
                            ),
                            "derived-receipt": (
                                f"{archive_services.DERIVED_TEXT_CAPTURE_RECEIPTS_DIR}/"
                            ),
                            "objet-receipt": (
                                f"{archive_services.OBJET_CAPTURE_RECEIPTS_DIR}/"
                            ),
                            "batch-receipt": (
                                f"{completion_workflows.OBJET_CAPTURE_BATCH_RECEIPTS_DIR}/"
                            ),
                        }
                        if relative.startswith(prefixes[case]) and not triggered:
                            triggered = True
                            raise failure_type(f"private post-hardlink {case}")

                    patcher = mock.patch.object(
                        archive_services,
                        "_write_bytes_create_if_absent",
                        side_effect=create_then_raise,
                    )

                with patcher:
                    applied = completion_workflows.objet_capture_batch_apply(
                        archive_root,
                        manifest_path=request_path,
                        expected_plan_sha256=plan["summary"]["plan_sha256"],
                        reviewed_by="person:letter128-post-publish",
                    )

                self.assertTrue(triggered, case)
                self.assertTrue(applied["ok"], applied)
                self.assertEqual(applied["state"], "written")
                self.assertNotIn("private post-", json.dumps(applied))
                files_after = self.file_snapshot(archive_root)
                actual_delta = {
                    path
                    for path in set(files_before) | set(files_after)
                    if files_before.get(path) != files_after.get(path)
                    and not path.endswith(".lock")
                }
                self.assertEqual(set(applied["files_written"]), actual_delta)
                self.assertEqual(
                    self.line_count(files_manifest),
                    original_before + 1,
                )
                self.assertEqual(
                    self.line_count(derived_manifest),
                    derived_before + 1,
                )

                replay_plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
                replay = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128-post-publish-replay",
                )
                self.assertTrue(replay["ok"], replay)
                self.assertEqual(
                    replay["summary"]["original_skipped_item_count"],
                    1,
                )
                self.assertEqual(
                    replay["summary"]["derived_text_skipped_item_count"],
                    1,
                )
                self.assertEqual(
                    self.line_count(files_manifest),
                    original_before + 1,
                )
                self.assertEqual(
                    self.line_count(derived_manifest),
                    derived_before + 1,
                )

    def test_ambiguous_selection_publication_reports_uncertainty_and_recovers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            canonical_root = archive_services.require_existing_archive_root(
                archive_root
            )
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-ambiguous-selection",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            files_before = self.file_snapshot(archive_root)
            real_create = archive_services._write_bytes_create_if_absent
            uncertain_relative: str | None = None

            def create_tamper_then_raise(path: Path, payload: bytes) -> None:
                nonlocal uncertain_relative
                real_create(path, payload)
                relative = archive_services.archive_relative_path(
                    path,
                    canonical_root,
                )
                if relative.startswith(
                    f"{archive_services.OBJET_CAPTURE_SELECTION_MANIFESTS_DIR}/"
                ):
                    uncertain_relative = relative
                    path.write_bytes(b"tampered-selection-evidence")
                    raise RuntimeError(
                        "private ambiguous selection publication"
                    )

            with mock.patch.object(
                archive_services,
                "_write_bytes_create_if_absent",
                side_effect=create_tamper_then_raise,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128-ambiguous-selection",
                )

            self.assertIsNotNone(uncertain_relative)
            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "recovery_required")
            self.assertFalse(failed["approved"])
            self.assertEqual(
                failed["blockers"],
                ["batch_selection_publication_outcome_unverified"],
            )
            self.assertTrue(failed["outcome_unverified"])
            self.assertTrue(failed["writes_may_have_occurred"])
            self.assertEqual(failed["files_written"], [])
            self.assertEqual(failed["items"], [])
            self.assertNotIn("private ambiguous", json.dumps(failed))
            files_after = self.file_snapshot(archive_root)
            actual_delta = {
                path
                for path in set(files_before) | set(files_after)
                if files_before.get(path) != files_after.get(path)
                and not path.endswith(".lock")
            }
            self.assertEqual(actual_delta, {uncertain_relative})
            self.assertNotIn("objects/manifests/files.jsonl", actual_delta)
            self.assertNotIn(
                archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH,
                actual_delta,
            )

            # Test-only operator repair of the explicitly identified corrupt
            # evidence path; the production result never retries automatically.
            (archive_root / str(uncertain_relative)).unlink()
            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-ambiguous-selection-recovery",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["state"], "written")

    def test_ambiguous_batch_receipt_excludes_uncertain_path_and_replays(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            canonical_root = archive_services.require_existing_archive_root(
                archive_root
            )
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-ambiguous-batch-receipt",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            files_before = self.file_snapshot(archive_root)
            real_create = archive_services._write_bytes_create_if_absent
            uncertain_relative: str | None = None

            def create_tamper_then_raise(path: Path, payload: bytes) -> None:
                nonlocal uncertain_relative
                real_create(path, payload)
                relative = archive_services.archive_relative_path(
                    path,
                    canonical_root,
                )
                if relative.startswith(
                    f"{completion_workflows.OBJET_CAPTURE_BATCH_RECEIPTS_DIR}/"
                ):
                    uncertain_relative = relative
                    path.write_bytes(b"tampered-batch-receipt-evidence")
                    raise OSError("private ambiguous batch receipt")

            with mock.patch.object(
                archive_services,
                "_write_bytes_create_if_absent",
                side_effect=create_tamper_then_raise,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128-ambiguous-batch-receipt",
                )

            self.assertIsNotNone(uncertain_relative)
            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "recovery_required")
            self.assertEqual(
                failed["blockers"],
                ["batch_receipt_outcome_unverified"],
            )
            self.assertTrue(failed["outcome_unverified"])
            self.assertTrue(failed["writes_may_have_occurred"])
            self.assertIsNone(failed["summary"]["batch_receipt_path"])
            self.assertEqual(
                failed["summary"]["batch_receipt_proposed_path"],
                uncertain_relative,
            )
            self.assertNotIn("private ambiguous", json.dumps(failed))
            files_after = self.file_snapshot(archive_root)
            actual_delta = {
                path
                for path in set(files_before) | set(files_after)
                if files_before.get(path) != files_after.get(path)
                and not path.endswith(".lock")
            }
            self.assertEqual(
                set(failed["files_written"]),
                actual_delta - {str(uncertain_relative)},
            )
            self.assertNotIn(uncertain_relative, failed["files_written"])
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-ambiguous-batch-recovery",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["state"], "written")
            self.assertEqual(replay["summary"]["original_skipped_item_count"], 1)
            self.assertEqual(
                replay["summary"]["derived_text_skipped_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_lower_receipt_no_write_preserves_exact_delta_and_reconciles(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-lower-receipt-failure",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            files_before = self.file_snapshot(archive_root)

            with mock.patch.object(
                archive_services,
                "_objet_capture_write_receipt",
                side_effect=OSError("synthetic lower receipt failure"),
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )

            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "evidence_incomplete")
            self.assertIn(
                "objet_capture_receipt_write_failed",
                failed["blockers"],
            )
            self.assertFalse(failed.get("outcome_unverified", False))
            self.assertFalse(failed.get("writes_may_have_occurred", False))
            self.assertTrue(failed["summary"]["recovery_required"])
            self.assertIsNone(failed["summary"]["capture_receipt_path"])
            self.assertTrue(failed["summary"]["batch_receipt_path"])
            self.assertEqual(
                failed["summary"]["original_written_item_count"],
                1,
            )
            self.assertEqual(
                failed["summary"]["derived_text_written_item_count"],
                1,
            )
            self.assertEqual(
                failed["next_safe_actions"],
                completion_workflows.OBJET_CAPTURE_BATCH_EVIDENCE_INCOMPLETE_NEXT_SAFE_ACTIONS,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)
            files_after = self.file_snapshot(archive_root)
            actual_delta = {
                path
                for path in set(files_before) | set(files_after)
                if files_before.get(path) != files_after.get(path)
                and not path.endswith(".lock")
            }
            self.assertEqual(set(failed["files_written"]), actual_delta)
            self.assertFalse(
                any(
                    path.startswith(
                        f"{archive_services.OBJET_CAPTURE_RECEIPTS_DIR}/"
                    )
                    for path in actual_delta
                )
            )
            batch_receipts_dir = (
                archive_root / completion_workflows.OBJET_CAPTURE_BATCH_RECEIPTS_DIR
            )
            self.assertTrue(any(batch_receipts_dir.glob("*.json")))

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            self.assertEqual(replay_plan["summary"]["would_skip"], 1)
            self.assertEqual(
                replay_plan["summary"]["would_skip_derived_text"],
                1,
            )
            recovered = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-recovery",
            )
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["state"], "written")
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_runtime_error_after_lower_write_is_unverified_and_replay_converges(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-runtime-after-write",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            real_apply = archive_services._objet_capture_run

            def apply_then_raise(
                *args: object,
                **kwargs: object,
            ) -> dict[str, object]:
                result = real_apply(*args, **kwargs)
                if kwargs.get("approve") is True:
                    raise RuntimeError(
                        r"private C:\outside\must-not-echo after durable write"
                    )
                return result

            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            with mock.patch.object(
                archive_services,
                "_objet_capture_run",
                side_effect=apply_then_raise,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )
            self.assert_capture_outcome_unverified(failed)
            self.assertNotIn("must-not-echo", json.dumps(failed))
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128-recovery",
            )
            self.assertTrue(replay["ok"], replay)
            self.assertEqual(replay["summary"]["original_skipped_item_count"], 1)
            self.assertEqual(
                replay["summary"]["derived_text_skipped_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_invalid_lower_shape_or_count_never_claims_completion(self) -> None:
        for case_name in ("non-dict", "count-mismatch"):
            with self.subTest(case_name=case_name), tempfile.TemporaryDirectory() as tmp:
                archive_root = self.fake_archive(Path(tmp) / "archive")
                item = self.paired_item(archive_root)
                request_path, _ = self.write_request(
                    archive_root,
                    [item],
                    batch_id=f"letter128-shape-{case_name}",
                )
                plan = completion_workflows.objet_capture_batch_plan(
                    archive_root,
                    manifest_path=request_path,
                )
                real_apply = archive_services._objet_capture_run
                if case_name == "non-dict":

                    def invalid_apply_result(
                        *args: object,
                        **kwargs: object,
                    ) -> object:
                        if kwargs.get("approve") is True:
                            return ["invalid-lower-result"]
                        return real_apply(*args, **kwargs)

                    side_effect: object = invalid_apply_result
                else:

                    def corrupt_count(
                        *args: object,
                        **kwargs: object,
                    ) -> dict[str, object]:
                        value = real_apply(*args, **kwargs)
                        if kwargs.get("approve") is True:
                            value["summary"] = {
                                **value["summary"],
                                "captured": value["summary"].get(
                                    "captured", 0
                                )
                                + 1,
                            }
                        return value

                    side_effect = corrupt_count
                with mock.patch.object(
                    archive_services,
                    "_objet_capture_run",
                    side_effect=(
                        side_effect if callable(side_effect) else None
                    ),
                    return_value=(
                        side_effect if not callable(side_effect) else mock.DEFAULT
                    ),
                ):
                    failed = completion_workflows.objet_capture_batch_apply(
                        archive_root,
                        manifest_path=request_path,
                        expected_plan_sha256=plan["summary"]["plan_sha256"],
                        reviewed_by="person:letter128",
                    )
                self.assert_capture_outcome_unverified(failed)

    def test_attempt_receipt_runtime_error_before_publication_is_exact_no_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-attempt-finalization",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            real_create = archive_services._write_bytes_create_if_absent

            def fail_attempt_receipt(path: Path, payload: bytes) -> None:
                if "receipts/objet-capture-batches/" in Path(path).as_posix():
                    raise RuntimeError("private finalization detail")
                real_create(path, payload)

            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            with mock.patch.object(
                archive_services,
                "_write_bytes_create_if_absent",
                side_effect=fail_attempt_receipt,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )
            self.assertFalse(failed["ok"], failed)
            self.assertEqual(failed["state"], "evidence_incomplete")
            self.assertIn("batch_receipt_write_failed", failed["blockers"])
            self.assertFalse(failed.get("outcome_unverified", False))
            self.assertFalse(failed.get("writes_may_have_occurred", False))
            self.assertIsNone(failed["summary"]["batch_receipt_path"])
            self.assertTrue(failed["summary"]["capture_receipt_path"])
            self.assertNotIn("finalization detail", json.dumps(failed))
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_completion_count_runtime_error_never_guesses_after_lower_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-count-finalization",
            )
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_before = self.line_count(files_manifest)
            derived_before = self.line_count(derived_manifest)
            real_counts = completion_workflows._batch_completion_counts

            def fail_apply_counts(
                *args: object,
                **kwargs: object,
            ) -> dict[str, int]:
                if kwargs.get("approve") is True:
                    raise RuntimeError("private count exception")
                return real_counts(*args, **kwargs)

            with mock.patch.object(
                completion_workflows,
                "_batch_completion_counts",
                side_effect=fail_apply_counts,
            ):
                failed = completion_workflows.objet_capture_batch_apply(
                    archive_root,
                    manifest_path=request_path,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter128",
                )
            self.assert_capture_outcome_unverified(failed)
            self.assertNotIn("count exception", json.dumps(failed))
            self.assertEqual(self.line_count(files_manifest), original_before + 1)
            self.assertEqual(self.line_count(derived_manifest), derived_before + 1)

    def test_cli_apply_is_fixed_closed_before_partial_service_projection(
        self,
    ) -> None:
        args = SimpleNamespace(
            dry_run=False,
            approve=True,
            reviewed_by="person:letter128",
            expected_plan_sha256="a" * 64,
            archive_root="unused",
            manifest="unused.json",
            format="text",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                completion_workflows,
                "objet_capture_batch_apply",
                return_value={"ok": True, "files_written": ["unexpected"]},
            ) as service,
            mock.patch.object(sys, "stdout", stdout),
            mock.patch.object(sys, "stderr", stderr),
        ):
            return_code = archive_cli.command_objet_capture_batch(args)
        self.assertEqual(return_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            "Exact compound human-approval binding is not implemented for "
            "this command; the write did not start. Use its dry-run or plan "
            "mode only.\n",
        )
        service.assert_not_called()

    def test_cli_apply_json_is_fixed_closed_before_recovery_service_projection(
        self,
    ) -> None:
        args = SimpleNamespace(
            dry_run=False,
            approve=True,
            reviewed_by="person:letter128",
            expected_plan_sha256="c" * 64,
            archive_root="unused",
            manifest="unused.json",
            format="json",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                completion_workflows,
                "objet_capture_batch_apply",
                return_value={"ok": True, "files_written": ["unexpected"]},
            ) as service,
            mock.patch.object(sys, "stdout", stdout),
            mock.patch.object(sys, "stderr", stderr),
        ):
            return_code = archive_cli.command_objet_capture_batch(args)
        self.assertEqual(return_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "ok": False,
                "state": "blocked",
                "lifecycle_action": "objet_capture_batch",
                "reason_codes": [
                    "compound_exact_human_approval_binding_required"
                ],
                "files_written": [],
                "private_values_echoed": False,
            },
        )
        service.assert_not_called()

    def test_cli_dry_run_text_keeps_ready_blocked_projection(self) -> None:
        plan_result = {
            "ok": True,
            "state": "ready",
            "summary": {
                "batch_id": "letter128-cli-plan",
                "item_count": 2,
                "ready_item_count": 2,
                "blocked_item_count": 0,
                "convergence_model": "bounded_per_item_with_replay",
                "plan_sha256": "b" * 64,
            },
            "blockers": [],
            "warnings": [],
        }
        args = SimpleNamespace(
            dry_run=True,
            approve=False,
            reviewed_by=None,
            expected_plan_sha256=None,
            archive_root="unused",
            manifest="unused.json",
            format="text",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                completion_workflows,
                "objet_capture_batch_plan",
                return_value=plan_result,
            ),
            mock.patch.object(sys, "stdout", stdout),
            mock.patch.object(sys, "stderr", stderr),
        ):
            return_code = archive_cli.command_objet_capture_batch(args)
        rendered = stdout.getvalue()
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("- ready/blocked: 2/0", rendered)
        self.assertNotIn("written/skipped/blocked", rendered)

    def test_replay_is_idempotent_and_reports_both_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.fake_archive(Path(tmp) / "archive")
            item = self.paired_item(archive_root)
            request_path, _ = self.write_request(
                archive_root,
                [item],
                batch_id="letter128-idempotent",
            )
            first_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            first = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=first_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128",
            )
            self.assertTrue(first["ok"], first)
            files_manifest = archive_root / "objects/manifests/files.jsonl"
            derived_manifest = (
                archive_root
                / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
            )
            original_lines = self.line_count(files_manifest)
            derived_lines = self.line_count(derived_manifest)

            replay_plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(replay_plan["ok"], replay_plan)
            self.assert_completion_partition(
                replay_plan["summary"],
                approve=False,
            )
            self.assertEqual(
                replay_plan["summary"]["plan_sha256"],
                first_plan["summary"]["plan_sha256"],
            )
            self.assertEqual(replay_plan["summary"]["would_skip"], 1)
            self.assertEqual(
                replay_plan["summary"]["would_skip_derived_text"],
                1,
            )
            replay = completion_workflows.objet_capture_batch_apply(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=replay_plan["summary"]["plan_sha256"],
                reviewed_by="person:letter128",
            )
            self.assertTrue(replay["ok"], replay)
            self.assert_completion_partition(replay["summary"], approve=True)
            self.assertEqual(
                replay["summary"]["original_skipped_item_count"],
                1,
            )
            self.assertEqual(
                replay["summary"]["derived_text_skipped_item_count"],
                1,
            )
            self.assertEqual(self.line_count(files_manifest), original_lines)
            self.assertEqual(self.line_count(derived_manifest), derived_lines)

    def test_schema_mirrors_match_and_old_receipt_remains_valid(self) -> None:
        for name in (
            "objet-capture-batch-request.schema.json",
            "objet-capture-batch-receipt.schema.json",
        ):
            self.assertEqual(
                (KIT_ROOT / "schemas" / name).read_bytes(),
                (KIT_ROOT / "src" / "wom_kit" / "_resources" / "schemas" / name).read_bytes(),
            )
        old_receipt = {
            "schema": completion_workflows.OBJET_CAPTURE_BATCH_RECEIPT_SCHEMA,
            "archive_id": "archive:test",
            "batch_id": "old-receipt",
            "request_sha256": "a" * 64,
            "selection_sha256": "b" * 64,
            "plan_sha256": "c" * 64,
            "selection_path": "receipts/objet-capture-selections/old.json",
            "capture_receipt_path": None,
            "status_class": "written",
            "ok": True,
            "reviewed_by": "person:test",
            "created_at": "2026-08-11T00:00:00Z",
            "convergence_model": "bounded_per_item_with_replay",
            "all_or_nothing_claimed": False,
            "privacy": {
                "manifest_values_included": False,
                "staged_paths_included": False,
                "titles_included": False,
            },
        }
        self.validate_schema(
            "objet-capture-batch-receipt.schema.json",
            old_receipt,
        )


if __name__ == "__main__":
    unittest.main()
