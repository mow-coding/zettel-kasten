"""Public argument routing over synthetic archives; not native approval proof."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from wom_kit import archive_cli, archive_services


class FeedbackCompletionCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-feedback-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)

    def run_command(self, *arguments):
        args = archive_cli.build_parser().parse_args(list(arguments))
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = args.func(args)
        return code, json.loads(output.getvalue())

    def test_index_publishes_queryable_generation_and_reindex_reuses_content(self):
        first = archive_services.index_archive(self.root)
        self.assertTrue(first["ok"])
        code, page = self.run_command("title-diagnostics", str(self.root), "--page-size", "1")
        self.assertEqual(code, 0)
        self.assertEqual(page["snapshot_ref"], first["title_snapshot"]["snapshot_ref"])
        second = archive_services.index_archive(self.root)
        self.assertTrue(second["ok"])
        # Immutable first-generation evidence stays usable after index refresh.
        code, old = self.run_command("title-diagnostics", str(self.root),
                                    "--snapshot-ref", page["snapshot_ref"], "--page-size", "1")
        self.assertEqual(code, 0)
        self.assertEqual(old["snapshot_ref"], page["snapshot_ref"])

    def test_relation_page_and_private_request_reach_batch_preview(self):
        archive_services.index_archive(self.root)
        from wom_kit import relation_batch
        _root, snapshot, generation = relation_batch._read(self.root)
        source, target = list(generation["entries"])[:2]
        source_path = self.root / generation["entries"][source]["path"]
        source_path.write_bytes(source_path.read_bytes() + ("\n" + target + "\n").encode())
        archive_services.index_archive(self.root)
        _root, snapshot, generation = relation_batch._read(self.root)
        code, page = self.run_command("relation-candidate-plan", str(self.root), "--from-zettel", source,
                                     "--paged", "--dry-run", "--page-size", "1", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(page["snapshot_ref"], snapshot)
        self.assertTrue(page["items"])
        request = {"schema": relation_batch.REQUEST_SCHEMA, "snapshot_ref": snapshot,
            "reviewed_by": "person:synthetic-reviewer", "decisions": [{"from_zettel": source,
                "candidate_id": page["items"][0]["candidate_id"], "decision": "defer", "edge_type": None,
                "visibility": "private", "reason": "Compare synthetic sources first.", "confidence": "low"}]}
        path = self.root / "workbench/synthetic-decisions.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(request), encoding="utf-8")
        before = {p: p.read_bytes() for p in (self.root / "zettels").rglob("*.md")}
        code, preview = self.run_command("relation-candidate-decide", str(self.root),
                                        "--request", str(path), "--dry-run", "--format", "json")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["domain"], "relation_batch")
        self.assertFalse(preview["writes"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_capture_resume_rejects_fresh_selection_without_creating_operation(self):
        code, result = self.run_command("objet-capture-batch", str(self.root), "--approve", "--resume",
            "--approval-id", "synthetic-approval", "--execution-sha256", "sha256:" + "a" * 64,
            "--source-intake-execution-sha256", "sha256:" + "b" * 64,
            "--reviewed-by", "person:synthetic-reviewer", "--format", "json", "--no-progress")
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertNotIn("operation_ref", result)
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_relation_semantics_and_draft_history_are_read_only_public_routes(self):
        from wom_kit import relation_batch
        archive_services.index_archive(self.root)
        _root, _snapshot, generation = relation_batch._read(self.root)
        identity = next(iter(generation["entries"]))
        code, semantics = self.run_command("relation-candidate-plan", str(self.root),
                                          "--semantics", "--dry-run", "--format", "json")
        self.assertEqual(code, 0, semantics)
        self.assertEqual(semantics, relation_batch.semantics(self.root))
        code, history = self.run_command("draft-disposition", str(self.root),
                                        "--history", "--zettel-id", identity)
        self.assertEqual(code, 0, history)
        self.assertEqual(history["event_count"], 0)
        self.assertFalse(history["current_document_status_checked"])
        self.assertFalse(history["conditions_are_delete_authority"])
        code, mixed = self.run_command("draft-disposition", str(self.root),
                                      "--inspect", "--resume", "--zettel-id", identity)
        self.assertEqual(code, 1)
        self.assertFalse(mixed["ok"])


if __name__ == "__main__":
    unittest.main()
