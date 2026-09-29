"""Provider outputs enter the real intake planner without hand-edited JSON."""
from io import BytesIO
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_services, objet_capture_batch_exact, source_intake_batch_exact
from wom_kit import provider_artifacts as artifacts, provider_tiro
from wom_kit.provider_notion_media import fetch_media
from wom_kit.source_intake_batch_exact import plan_source_intake_batch
import test_v0410_objet_capture_batch_exact as approval_helpers


class Stream(BytesIO):
    status = 200


class IntakeInteropTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)

    def check_requests(self, result):
        for path in result["intake_requests"]:
            plan = plan_source_intake_batch(self.root, path)
            self.assertTrue(plan.approveable, plan.public_document())
            self.assertIsNotNone(plan.prepared_capture_request)

    def capture_requests(self, result):
        """Use real approval receipts and writers, with synthetic UI/key only."""
        archive_services.index_archive(self.root)
        native = approval_helpers._Native(approved=True)
        workflow = approval_helpers.ObjetCaptureBatchExactTests._workflow(
            native, approval_helpers._KeyProvider())
        expected_bytes, selected_ids = {}, set()
        for path in result["intake_requests"]:
            request = json.loads((self.root / path).read_text())
            for item in request["items"]:
                raw = (self.root / item["local_path"]).read_bytes()
                expected_bytes[artifacts.digest(raw)] = raw
            intake = plan_source_intake_batch(self.root, path)
            self.assertTrue(intake.approveable, intake.public_document())
            with mock.patch.object(source_intake_batch_exact, "_execute_exact_human_approved_write", side_effect=workflow):
                received = source_intake_batch_exact.execute_source_intake_batch(
                    intake, expected_plan_sha256=intake.manifest.manifest_sha256,
                    reviewer_claim=approval_helpers.REVIEWER)
            self.assertTrue(received["ok"], received)
            capture = objet_capture_batch_exact.plan_objet_capture_batch(
                self.root, self.root / intake.prepared_capture_request.relative_path,
                intake_execution_sha256=received["execution_sha256"],
                claim_key_provider=approval_helpers._ReadKeyProvider())
            self.assertTrue(capture.approveable, capture.public_document())
            selected_ids.update(item["approved_object_id"] for item in capture.selection_document["items"])
            with mock.patch.object(objet_capture_batch_exact, "_execute_exact_human_approved_write", side_effect=workflow):
                captured = objet_capture_batch_exact.execute_objet_capture_batch(
                    capture, expected_plan_sha256=capture.batch_plan_sha256,
                    reviewer_claim=approval_helpers.REVIEWER)
            self.assertTrue(captured["ok"], captured)
            self.assertEqual(captured["summary"]["terminal_item_count"], len(request["items"]))
        manifest = [json.loads(line) for line in (self.root / "objects/manifests/files.jsonl").read_text().splitlines() if line.strip()]
        actual = [row for row in manifest if row["object_id"] in selected_ids]
        self.assertEqual(len(actual), len(selected_ids))
        # Inspect preserved canonical bytes, not just success flags or counts.
        preserved = {}
        for item in (self.root / "objects").rglob("*"):
            if item.is_file() and item.parent.name != "manifests":
                raw = item.read_bytes()
                sha = artifacts.digest(raw)
                if sha in expected_bytes:
                    preserved[sha] = raw
        self.assertEqual(preserved, expected_bytes)
        self.assertEqual(native.calls, 2 * len(result["intake_requests"]))

    def test_notion_duplicate_media_occurrences_do_not_duplicate_physical_intake_source(self):
        def read(kind, object_id, cursor):
            if kind == "page":
                return {}
            return {"results": [{"id": str(index), "image": {"type": "file", "file": {"url": "https://example.invalid/same"}}} for index in range(2)], "has_more": False}
        result = fetch_media(self.root, page_ids=["synthetic"], batch_id="interop", read=read, download=lambda _: Stream(b"same"))
        self.check_requests(result)
        receipt = json.loads((self.root / result["receipt_path"]).read_text())
        self.assertEqual(len(receipt["items"]), 2)
        self.assertEqual(len(receipt["intake_item_aliases"]), 1)
        self.capture_requests(result)

    def test_tiro_bundle_audio_and_derivations_enter_actual_capture_preparation(self):
        raw = json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA, "notes": [{"guid": "note"}],
            "paragraphs_by_note": {"note": [{"content": "synthetic"}]}}).encode()
        (self.root / "synthetic.wav").write_bytes(b"synthetic-audio")
        result = provider_tiro.stage_bundle(self.root, raw_bundle=raw, batch_id="interop", audio_sources=[{
            "note_guid": "note", "local_path": "synthetic.wav", "source_sha256": artifacts.digest(b"synthetic-audio")}])
        self.check_requests(result)
        self.capture_requests(result)

    def test_real_intake_limit_is_split_with_occurrence_aliases(self):
        items = [{"item_id": f"item-{index}", "local_path": f"workbench/synthetic-{index}.txt"} for index in range(1001)]
        paths, aliases = artifacts.write_intake_requests(self.root, "workbench/synthetic", "synthetic", items + [{"item_id": "alias", "local_path": items[0]["local_path"]}])
        self.assertEqual(len(paths), 2)
        self.assertEqual([len(json.loads((self.root / path).read_text())["items"]) for path in paths], [1000, 1])
        self.assertEqual(aliases, {"alias": "item-0"})
