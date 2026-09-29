"""A17 (letter 176): a registered objet is found again by its original filename.

Staging an external original prepares one private name intake per copy;
after capture, `objet-source-metadata-write --intake-batch` writes every
prepared name under one exact approval; `index` then `find-objet` locate the
objet by the original name. Names never reach receipts, the object manifest
or public results.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import PurePosixPath
from unittest import mock

import test_v0410_objet_capture_batch_exact as fixtures
from wom_kit import archive_cli, archive_services as services
from wom_kit import objet_capture_batch_exact as batch
from wom_kit import source_intake_batch_exact as intake
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import private_objet_metadata_writer_contract as contract

_Native, _KeyProvider, _ReadKeyProvider, REVIEWER = (
    fixtures._Native, fixtures._KeyProvider, fixtures._ReadKeyProvider, fixtures.REVIEWER)
NAMES = ("회의록 2026-09-27.txt", "Report-Final v2.pdf", "notes.md")


class OriginalNameDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ObjetCaptureBatchExactTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.keys = _KeyProvider()
        self.parser = archive_cli.build_parser()
        # The example archive's object manifest carries one blank line; the
        # v0.3.296 private writer refuses blank rows, so the copy is normalized.
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        rows = [line for line in manifest.read_bytes().split(b"\n") if line]
        manifest.write_bytes(b"\n".join(rows) + b"\n")
        self.assertTrue(services.index_archive(self.root)["ok"])

    def tearDown(self):
        self.fixture.tearDown()

    def invoke(self, argv):
        args = self.parser.parse_args(argv)
        with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
            code = args.func(args)
        return code, json.loads(output.getvalue())

    def stage(self):
        originals = []
        items = []
        for index, name in enumerate(NAMES):
            original = self.fixture.workspace / name
            original.write_bytes(f"synthetic external {index}".encode())
            originals.append(original)
            items.append({"item_id": f"external-{index:02d}", "local_path": str(original),
                          "source_role": "primary_source"})
        request = self.fixture.workspace / "external-names.json"
        request.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA,
            "batch_id": "synthetic-external-names", "items": items}), encoding="utf-8")
        common = ["source-intake-batch", str(self.root), "--manifest", str(request), "--stage-external",
                  "--format", "json", "--no-progress"]
        code, preview = self.invoke([*common, "--dry-run"])
        self.assertEqual(code, 0, preview)
        native = _Native(approved=True)
        with mock.patch.object(intake, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(native, self.keys)):
            code, prepared = self.invoke([*common, "--approve", "--reviewed-by", REVIEWER,
                                          "--expected-plan-sha256", preview["plan_sha256"]])
        self.assertEqual(code, 0, prepared)
        self.assertEqual(native.calls, 1)
        return originals, prepared

    def capture(self, prepared):
        plan = batch.plan_objet_capture_batch(self.root,
            intake_execution_sha256=prepared["execution_sha256"], claim_key_provider=_ReadKeyProvider())
        self.assertTrue(plan.approveable, plan.public_document())
        native = _Native(approved=True)
        with (mock.patch.object(workflow, "_production_key_provider", return_value=_ReadKeyProvider()),
              mock.patch.object(batch, "_execute_exact_human_approved_write",
                                side_effect=self.fixture._workflow(native, self.keys))):
            code, result = self.invoke(["objet-capture-batch", str(self.root), "--format", "json", "--no-progress",
                "--approve", "--reviewed-by", REVIEWER,
                "--source-intake-execution-sha256", prepared["execution_sha256"],
                "--expected-plan-sha256", plan.batch_plan_sha256])
        self.assertEqual(code, 0, result)
        self.assertEqual(native.calls, 1)
        return plan

    def name_batch(self, execution, *extra):
        argv = ["objet-source-metadata-write", str(self.root), "--intake-batch", execution, "--format", "json", *extra]
        return self.invoke(argv)

    def test_staging_prepares_one_private_name_intake_per_external_copy(self):
        originals, prepared = self.stage()
        self.assertEqual(prepared["prepared_name_intake_count"], len(NAMES), prepared)
        self.assertIn("--intake-batch", prepared["name_write_command"])
        relative = intake.prepared_name_intake_relative_dir(prepared["execution_sha256"])
        directory = self.root.joinpath(*relative.split("/"))
        files = sorted(directory.glob("*.json"))
        self.assertEqual(len(files), len(NAMES))
        seen = set()
        for path in files:
            document = json.loads(path.read_bytes())
            self.assertTrue(contract.validate_private_metadata_intake(document)["accepted"], document)
            seen.add(document["name_observation"]["original_filename"])
            self.assertRegex(document["object_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(seen, set(NAMES))
        for original in originals:
            self.assertTrue(original.exists())

    @unittest.skipUnless(os.name == "nt", "the private metadata writer applies rows on Windows only")
    def test_one_approval_writes_every_prepared_name_and_find_objet_finds_each(self):
        originals, prepared = self.stage()
        plan = self.capture(prepared)
        execution = prepared["execution_sha256"]

        code, batch_plan = self.name_batch(execution, "--dry-run")
        self.assertEqual(code, 0, batch_plan)
        self.assertEqual((batch_plan["item_count"], batch_plan["append_count"]), (len(NAMES), len(NAMES)), batch_plan)
        self.assertNotIn(NAMES[0], json.dumps(batch_plan, ensure_ascii=False))

        native = _Native(approved=True)
        with mock.patch.object(archive_cli, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(native, self.keys)):
            code, written = self.name_batch(execution, "--approve", "--reviewed-by", REVIEWER,
                "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent",
                "--expected-plan-sha256", batch_plan["plan_sha256"])
        self.assertEqual(code, 0, written)
        self.assertEqual(native.calls, 1)
        self.assertEqual((written["written_count"], written["remaining_count"]), (len(NAMES), 0), written)

        # A second plan has nothing left to write and opens no dialog.
        code, again = self.name_batch(execution, "--dry-run")
        self.assertEqual(again["append_count"], 0, again)
        with mock.patch.object(archive_cli, "_execute_exact_human_approved_write",
                               side_effect=self.fixture._workflow(native, self.keys)):
            code, noop = self.name_batch(execution, "--approve", "--reviewed-by", REVIEWER,
                "--affirm-private-metadata-reviewed", "--affirm-external-writers-quiescent",
                "--expected-plan-sha256", again["plan_sha256"])
        self.assertEqual(native.calls, 1, noop)

        indexed = services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        by_name = {}
        for name in NAMES:
            with redirect_stdout(output := io.StringIO()), redirect_stderr(io.StringIO()):
                rc = archive_cli.main(["find-objet", str(self.root), "--audience", "private_archive",
                    "--query-profile", "literal_unicode", "--query", name, "--format", "json"])
            found = json.loads(output.getvalue())
            self.assertEqual(rc, 0, found)
            self.assertEqual(found["status"], "found", found)
            self.assertEqual(len(found["results"]), 1, found)
            by_name[name] = found["results"][0]["object_id"]
        expected = {item["approved_object_id"] for item in plan.selection_document["items"]}
        self.assertEqual(set(by_name.values()), expected)

        # Names stay private: receipts, the object manifest and public results carry none.
        public_text = (self.root / "objects" / "manifests" / "files.jsonl").read_text(encoding="utf-8")
        for receipt in (self.root / "receipts" / "ops" / "source-intake-batches").rglob("*.json"):
            public_text += receipt.read_text(encoding="utf-8")
        for name in NAMES:
            self.assertNotIn(name, public_text)
            self.assertNotIn(name, json.dumps(written, ensure_ascii=False))
        private_manifest = self.root.joinpath(*PurePosixPath(contract.PRIVATE_MANIFEST_PATH).parts)
        self.assertTrue(private_manifest.exists())

    def test_batch_plan_refuses_an_unknown_execution_without_echoing_anything(self):
        code, result = self.name_batch("f" * 64, "--dry-run")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["blockers"], ["private_objet_source_metadata_batch_intakes_missing"])
        code, result = self.name_batch("not-a-digest", "--dry-run")
        self.assertEqual(result["blockers"], ["private_objet_source_metadata_batch_execution_invalid"])


if __name__ == "__main__":
    unittest.main()
