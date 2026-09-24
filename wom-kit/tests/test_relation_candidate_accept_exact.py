"""v0.4.41 (letter 108): accepting a relation candidate writes the edge.

Until v0.4.40 `relation-candidate-decide --decision accept` was fixed closed:
accepting writes an edge and a judgment record together and no approval
covered both. Now one exact approval binds the relation plan, the chosen edge
and the edge writer's own item digests; the service re-derives them under its
lock and narrows the approval to that one edge. The native dialog and the
archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, completion_workflows, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

SOURCE = "zet_20260925_accept_source"
TARGET = "zet_20260925_accept_target"
REVIEWER = "person:synthetic-relation-reviewer"


def _zettel(root: Path, zettel_id: str, title: str, index: int) -> Path:
    path = root / "zettels" / f"{zettel_id}.md"
    path.write_text(
        "---\n"
        f"id: {zettel_id}\n"
        f"title: {title}\n"
        "status: canonical\n"
        "kind: note\n"
        "facets:\n"
        "  recurring_series: program:synthetic-accept\n"
        f"  sequence_index: {index}\n"
        "---\n"
        "Synthetic body.\n",
        encoding="utf-8",
    )
    return path


class RelationCandidateAcceptExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-relation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.source = _zettel(self.root, SOURCE, "Accept Part One", 1)
        _zettel(self.root, TARGET, "Accept Part Two", 2)
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        self.assertTrue(archive_services.index_archive(self.root)["index_complete"])
        plan = completion_workflows.relation_candidate_plan(self.root, from_zettel=SOURCE)
        self.assertTrue(plan["ok"], plan)
        self.plan_sha256 = plan["summary"]["plan_sha256"]
        self.candidate = next(item["candidate_id"] for item in plan["candidates"]
                              if item["target"]["zettel_id"] == TARGET)

    def run_cli(self, *args: str) -> tuple[int, dict | None]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        try:
            return code, json.loads(out.getvalue())
        except json.JSONDecodeError:
            return code, None

    def accept(self, *extra: str) -> tuple[int, dict]:
        return self.run_cli(
            "relation-candidate-decide", str(self.root), "--from-zettel", SOURCE,
            "--candidate-id", self.candidate, "--decision", "accept", "--edge-type", "continues",
            "--visibility", "private", "--reason", "Synthetic: the target continues the source.",
            "--confidence", "high", "--expected-plan-sha256", self.plan_sha256,
            "--approve", "--reviewed-by", REVIEWER, *extra,
        )

    def test_accept_writes_edge_and_judgment_after_one_dialog(self) -> None:
        code, result = self.accept()
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertTrue(result["judgment_path"])
        self.assertTrue((self.root / result["judgment_path"]).is_file())
        self.assertIn("continues", self.source.read_text(encoding="utf-8"))
        # The accepted pair leaves the candidate plan, so a repeat is refused
        # before any dialog and writes nothing.
        code, again = self.accept()
        self.assertEqual(code, 1)
        self.assertIn("relation_candidate_not_in_plan", again["blockers"])
        self.assertEqual(self.native.calls, 1)

    def test_a_declined_dialog_writes_nothing(self) -> None:
        before = self.source.read_bytes()
        self.native.approve = False
        code, _error = self.accept()
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.source.read_bytes(), before)

    def test_a_changed_relation_plan_never_opens_the_dialog(self) -> None:
        self.plan_sha256 = "0" * 64
        code, error = self.accept()
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["relation_candidate_accept_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = completion_workflows.relation_candidate_decide(
            self.root, from_zettel=SOURCE, candidate_id=self.candidate, decision="accept",
            edge_type="continues", visibility="private", reason="Synthetic.", confidence="high",
            expected_plan_sha256=self.plan_sha256, reviewed_by=REVIEWER,
        )
        self.assertEqual(result["blockers"], ["compound_exact_human_approval_binding_required"])
        self.assertNotIn("continues", self.source.read_text(encoding="utf-8"))

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertIn(windows.ExactHumanApprovalOperation.relation_candidate_accept,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
