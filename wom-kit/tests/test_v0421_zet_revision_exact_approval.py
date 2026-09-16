"""v0.4.21 LR-01: zet-revision-write and zet-revision-restore-write reopened
through operation-specific exact human approval (semantic revision and
restore; beta letters 157-160).

Synthetic archive only; the native dialog and archive key are injected. The
result documents never echo the zettel id, paths, or proposal text; the
dialog receives the id as a local-only identity from the CLI argument.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import operation_approval_binding as binding_module
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-revision-reviewer"
TITLE_MARKER = "PRIVATE_REVISED_TITLE_SYNTHETIC"
ABSTRACT_MARKER = "PRIVATE_REVISED_ABSTRACT_SYNTHETIC"
BODY_MARKER = "PRIVATE_REVISED_BODY_SYNTHETIC"


class _Native:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.contexts: list[dict[str, object]] = []

    def show(self, **kwargs: object) -> tuple[int, bool]:
        self.calls += 1
        self.contexts.append(dict(kwargs))
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class ZetRevisionExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0421-revision-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.native = _Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=_KeyProvider()))
        self.outputs: list[str] = []
        self.fixture = self.create_proposal()

    def create_proposal(self) -> dict:
        canonical_path = sorted((self.root / "zettels").glob("*.md"))[0]
        frontmatter, body = archive_services.split_zettel_text(canonical_path.read_text(encoding="utf-8"))
        frontmatter["abstract"] = "Current reviewed first read."
        canonical_path.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body.rstrip() + "\n",
                                  encoding="utf-8")
        original_bytes = canonical_path.read_bytes()
        proposed = json.loads(json.dumps(frontmatter))
        proposed["title"] = TITLE_MARKER
        proposed["abstract"] = ABSTRACT_MARKER
        proposal_relative = ".wom-scratch/revisions/private-reviewed-revision.md"
        proposal_path = self.root / proposal_relative
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text("---\n" + archive_cli.dump_yaml(proposed) + "---\n\n" + body.rstrip()
                                 + f"\n\n{BODY_MARKER}\n", encoding="utf-8")
        plan = archive_services.zet_revision_plan(self.root, zettel_id=frontmatter["id"],
                                                  proposal_path=proposal_relative, dry_run=True)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["approval_status"], command_status.APPROVAL_AVAILABLE)
        self.assertEqual(plan["status"], "ready_for_human_review")
        return {"canonical_path": canonical_path, "original_bytes": original_bytes,
                "zettel_id": frontmatter["id"], "proposal_relative": proposal_relative, "plan": plan}

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def revision_args(self) -> list[str]:
        plan = self.fixture["plan"]
        return ["zet-revision-write", str(self.root), "--zettel-id", self.fixture["zettel_id"],
                "--proposal", self.fixture["proposal_relative"],
                "--expected-canonical-sha256", plan["canonical"]["sha256"],
                "--expected-proposal-sha256", plan["proposal"]["sha256"],
                "--expected-proposal-semantic-sha256", plan["proposal"]["semantic_sha256"],
                "--expected-plan-digest", plan["plan_digest"],
                "--revision-at", "2026-09-16T12:00:00Z"]

    def approve_revision(self) -> dict:
        code, preview = self.run_cli(*self.revision_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["status"], "ready_to_apply")
        code, result = self.run_cli(*self.revision_args(), "--approve", "--reviewed-by", REVIEWER,
                                    "--affirm-revision-reviewed", "--affirm-abstract-body-pair-reviewed")
        self.assertEqual(code, 0, result)
        return result

    def assert_private_free(self) -> None:
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        for marker in (TITLE_MARKER, ABSTRACT_MARKER, BODY_MARKER, str(self.root)):
            self.assertNotIn(marker, rendered)
        # the reviewer claim is shown to the person in the local dialog only
        self.assertNotIn(REVIEWER, "".join(self.outputs))

    def test_revision_write_applies_through_the_native_boundary(self) -> None:
        result = self.approve_revision()
        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["approved"])
        self.assertEqual(self.native.calls, 1)
        canonical = self.fixture["canonical_path"].read_text(encoding="utf-8")
        self.assertIn(TITLE_MARKER, canonical)
        self.assertIn(BODY_MARKER, canonical)
        receipt = json.loads((self.root / result["receipt"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["exact_human_approval"]["operation"], "zet_revision_write")
        self.assertEqual(receipt["reviewed_by"], REVIEWER)
        self.assertEqual(receipt["revision_at"], "2026-09-16T12:00:00Z")
        # the dialog saw the zet id as a local identity only
        self.assertIn(self.fixture["zettel_id"], json.dumps(self.native.contexts, ensure_ascii=False))
        self.assertNotIn(self.fixture["zettel_id"], "".join(self.outputs))
        self.assert_private_free()
        # the same approval cannot be replayed: a second approve re-derives
        # the plan against the revised canonical and blocks before the dialog
        code, error = self.run_cli(*self.revision_args(), "--approve", "--reviewed-by", REVIEWER,
                                   "--affirm-revision-reviewed", "--affirm-abstract-body-pair-reviewed")
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["zet_revision_write_preflight_blocked"])
        self.assertEqual(self.native.calls, 1)

    def test_cancel_and_missing_reviewer_write_nothing(self) -> None:
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.native.approve = False
        code, error = self.run_cli(*self.revision_args(), "--approve", "--reviewed-by", REVIEWER,
                                   "--affirm-revision-reviewed", "--affirm-abstract-body-pair-reviewed")
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["zet_revision_write_workflow_precondition_failed"])
        self.assertEqual(self.native.calls, 1)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual({k: v for k, v in after.items() if "exact-human-approvals" not in k},
                         {k: v for k, v in before.items() if "exact-human-approvals" not in k})
        code, error = self.run_cli(*self.revision_args(), "--approve")
        self.assertEqual(error["reason_codes"], ["zet_revision_write_reviewer_required"])
        self.assertEqual(self.native.calls, 1)
        self.assert_private_free()

    def test_unbound_service_calls_fail_before_any_read(self) -> None:
        plan = self.fixture["plan"]
        # these writers keep their content-free document contract: an unbound
        # approve call returns a blocked document without reading anything
        with patch.object(archive_services, "require_existing_archive_root",
                          side_effect=AssertionError("archive read before approval inputs")):
            unbound = archive_services.zet_revision_write(
                self.root, zettel_id=self.fixture["zettel_id"], proposal_path=self.fixture["proposal_relative"],
                expected_canonical_sha256=plan["canonical"]["sha256"],
                expected_proposal_sha256=plan["proposal"]["sha256"],
                expected_proposal_semantic_sha256=plan["proposal"]["semantic_sha256"],
                expected_plan_digest=plan["plan_digest"], approve=True, reviewed_by=REVIEWER)
            self.assertEqual(unbound["blockers"], ["exact_human_approval_required"])
            self.assertEqual(unbound["files_written"], [])
            unbound_restore = archive_services.zet_revision_restore_write(
                self.root, receipt_path="receipts/revisions/canonical/x.json",
                expected_receipt_sha256="sha256:" + "0" * 64, restore_proposal_path=".wom-scratch/revisions/restores/x.md",
                expected_current_sha256="sha256:" + "0" * 64, expected_restore_proposal_sha256="sha256:" + "0" * 64,
                expected_restore_proposal_semantic_sha256="sha256:" + "0" * 64,
                expected_restore_plan_digest="sha256:" + "0" * 64, approve=True, reviewed_by=REVIEWER)
            self.assertEqual(unbound_restore["blockers"], ["exact_human_approval_required"])
        # a non-boolean approve still gets the content-free blocked document
        blocked = archive_services.zet_revision_write(
            self.root, zettel_id=self.fixture["zettel_id"], proposal_path=self.fixture["proposal_relative"],
            expected_canonical_sha256=plan["canonical"]["sha256"], expected_proposal_sha256=plan["proposal"]["sha256"],
            expected_proposal_semantic_sha256=plan["proposal"]["semantic_sha256"],
            expected_plan_digest=plan["plan_digest"], approve=0)  # type: ignore[arg-type]
        self.assertEqual(blocked["state"], "blocked")

    def test_restore_write_returns_the_exact_previous_bytes_under_one_dialog(self) -> None:
        applied = self.approve_revision()
        receipt_relative = applied["receipt"]["path"]
        receipt_bytes = (self.root / receipt_relative).read_bytes()
        receipt_sha = "sha256:" + hashlib.sha256(receipt_bytes).hexdigest()
        restore_relative = ".wom-scratch/revisions/restores/private-exact-restore.md"
        restore_path = self.root / restore_relative
        restore_path.parent.mkdir(parents=True, exist_ok=True)
        restore_path.write_bytes(self.fixture["original_bytes"])
        restore_plan = archive_services.zet_revision_restore_plan(
            self.root, receipt_path=receipt_relative, expected_receipt_sha256=receipt_sha,
            restore_proposal_path=restore_relative, dry_run=True)
        self.assertTrue(restore_plan["ok"], restore_plan)
        args = ["zet-revision-restore-write", str(self.root), "--receipt", receipt_relative,
                "--expected-receipt-sha256", receipt_sha, "--restore-proposal", restore_relative,
                "--expected-current-sha256", restore_plan["current"]["state"]["file_sha256"],
                "--expected-restore-proposal-sha256", restore_plan["restore_proposal"]["state"]["file_sha256"],
                "--expected-restore-proposal-semantic-sha256", restore_plan["restore_proposal"]["state"]["semantic_sha256"],
                "--expected-restore-plan-digest", restore_plan["plan_digest"],
                "--revision-at", "2026-09-16T13:00:00Z"]
        code, preview = self.run_cli(*args, "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["status"], "ready_to_apply")
        binding = binding_module.zet_revision_restore_write_approval_binding(preview, preview_identity="x")
        self.assertIs(binding.operation, windows.ExactHumanApprovalOperation.zet_revision_restore_write)
        code, result = self.run_cli(*args, "--approve", "--reviewed-by", REVIEWER,
                                    "--affirm-restore-reviewed", "--affirm-abstract-body-pair-reviewed")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(self.native.calls, 2)
        self.assertEqual(self.fixture["canonical_path"].read_bytes(), self.fixture["original_bytes"])
        restore_receipt = json.loads((self.root / result["receipt"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(restore_receipt["exact_human_approval"]["operation"], "zet_revision_restore_write")
        self.assertEqual((self.root / receipt_relative).read_bytes(), receipt_bytes)  # source receipt preserved
        self.assert_private_free()

    def test_inventory_reports_both_writers_available(self) -> None:
        rows = {row["canonical_path"]: row for row in archive_cli._parser_capability_inventory(
            archive_cli.build_parser())["commands"]}
        for name in ("zet-revision-write", "zet-revision-restore-write"):
            self.assertEqual(rows[name]["approval_status"], command_status.APPROVAL_AVAILABLE, rows[name])
        self.assertNotIn("zet-revision-plan", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_PLAN_WRITERS)


if __name__ == "__main__":
    unittest.main()
