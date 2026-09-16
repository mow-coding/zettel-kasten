"""Actual public single-record to Git; synthetic native/key/local-bare transport.

Uses public A/B establishment and actual metadata recording, exact approvals,
Git commit/push, original resume and independent remote objects. A deliberate
exception is an interruption oracle, not a native power-loss/installed test.
"""

from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

import test_v0420_session_intake_git_public_workflow as public_fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_git_bundle as git_bundle
from wom_kit import work_session_git_terminal as terminal
from wom_kit import work_session_intake_git_provenance as provenance
from wom_kit import work_session_source_intake_inventory as inventory
from wom_kit import work_session_source_intake_record_bundle as bundle


class SingleRecordGitPublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Composition, not inheritance: do not silently rerun the batch cases.
        self.base = public_fixture.SessionIntakeGitPublicWorkflowTests("runTest")
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.root, self.git, self.call = self.base.root, self.base.git, self.base.call

    def record(self, task, name):
        source = "staging/incoming/" + name + "-single-source.bin"
        path = self.root / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("SYNTHETIC_PRIVATE_" + name + "_SOURCE\n").encode("ascii"))
        # The existing source planner resolves local_path against process cwd,
        # not archive_root. Supply the actual fixture file's absolute path.
        planned = archive_services.source_intake_plan(self.root, local_path=path, redact_local_paths=True)
        self.assertTrue(planned["ok"])
        request = self.root.parent / (name + "-single-private-plan.json")
        request.write_text(json.dumps(planned), encoding="utf-8")
        result = self.call("source-intake-record", *task["refs"], "--work-session-ref", task["session"],
            "--source-intake-plan", str(request), "--approve", "--reviewed-by", "person:synthetic-record-reviewer")
        self.assertTrue(result["original_completion_verified"] and result["completion_authentication_verified"])
        self.assertFalse(result["source_bytes_retained"] or result["prepared_capture_request_created"])
        selected = self.base.routing(task)._read(current=False)
        pointer = selected.document()["last_completed_operation"]
        self.assertEqual(pointer["kind"], "source_intake_record")
        self.assertIsNone(selected.pending_operation())
        with exact.ExactOperationWriterLock(self.root) as held:
            original = bundle._load_original_source_intake_record_context_held(self.root,
                manifest_sha256=pointer["manifest_sha256"], held=held)
        plan = original.prepared.plan
        common = self.base.common_path(result)
        outputs = {plan.receipt_relative_path: plan.receipt_bytes, common: (self.root / common).read_bytes()}
        self.assertEqual((self.root / plan.receipt_relative_path).read_bytes(), plan.receipt_bytes)
        self.assertEqual(plan.manifest.work_session_binding, self.base.store.read().binding(task["session"]))
        request.unlink()  # Only this fixture-owned caller input, never original context.
        return {"result": result, "original": original, "outputs": outputs, "common": common,
                "source": source, "request": request}

    def prepare(self, *, common_tracked):
        a, b = self.base.establish("single-A"), self.base.establish("single-B")
        intake_a, intake_b = self.record(a, "single-A"), self.record(b, "single-B")
        baseline_paths = [self.base.common_path(a["created"]), self.base.common_path(b["created"])]
        if common_tracked:
            baseline_paths.append(intake_a["common"])
        baseline_bytes = {path: (self.root / path).read_bytes() for path in baseline_paths}
        self.git("add", "--", *baseline_paths)
        self.git("commit", "-m", "Synthetic baseline original metadata evidence")
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("push", str(self.base.fixture.remote), "HEAD:refs/heads/main")
        selected = {path: raw for path, raw in intake_a["outputs"].items() if path not in baseline_paths}
        self.assertEqual(len(selected), 1 if common_tracked else 2)
        for path in selected:
            self.assertNotEqual(self.git("cat-file", "-e", "HEAD:" + path, check=False).returncode, 0)
        generic = "receipts/sources/source-intake-aaaaaaaaaaaaaaaa.source-intake-plan.json"
        self.assertNotIn(generic, {*intake_a["outputs"], *intake_b["outputs"]})
        (self.root / generic).write_bytes(next(iter(intake_a["outputs"].values())))
        (self.root / "notes.md").write_bytes(b"SYNTHETIC_PRIVATE_STAGED_NOTE\n")
        (self.root / ".gitignore").write_bytes(b"profiles/local/\nlegacy-ignored/\n")
        (self.root / "legacy-ignored").mkdir()
        (self.root / "legacy-ignored/old.bin").write_bytes(b"SYNTHETIC_PRIVATE_IGNORED\n")
        self.git("add", "--", "tracked.txt", "notes.md", next(iter(intake_b["outputs"])), next(iter(selected)))
        (self.root / "tracked.txt").write_bytes(b"SYNTHETIC_PRIVATE_UNSTAGED_DOCUMENT\n")
        (self.root / "notes.md").write_bytes(b"SYNTHETIC_PRIVATE_UNSTAGED_NOTE\n")
        excluded_paths = {"archive.yml", ".gitignore", "tracked.txt", "notes.md", "new-private.txt",
            "legacy-ignored/old.bin", generic, *intake_b["outputs"], intake_a["source"], intake_b["source"]}
        self.base.excluded = {path: (self.root / path).read_bytes() for path in excluded_paths}
        self.base.excluded_index = self.git("ls-files", "--stage", "--", *sorted(excluded_paths)).stdout
        self.base.excluded_status = self.git("status", "--porcelain", "--untracked-files=all", "--ignored",
                                            "--", *sorted(excluded_paths)).stdout
        return {"a": a, "b": b, "intake_a": intake_a, "intake_b": intake_b, "selected": selected,
            "baseline": baseline, "baseline_bytes": baseline_bytes, "generic": generic,
            "b_actor": self.base.routing(b)._read(current=False)._raw,
            "registry": self.base.store.read().sha256,
            "claims": set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))}

    def forbid_discovery(self):
        stack = ExitStack()
        for owner, name in ((writer.planning, "git_backup_plan"), (git_bundle, "_save_original_git_context_held"),
                            (inventory, "_capture_source_intake_context_inventory_held"),
                            (inventory, "_capture_source_intake_record_context_inventory_held"),
                            (provenance, "_select_intake_output_changes_held"), (record, "plan_source_intake_record")):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original evidence must not be replaced")))
        return stack

    def verify_original_and_exclusions(self, case):
        original, pointer = self.base.original_git(case["a"])
        self.assertEqual({path for group in original.prepared.groups for path in group.paths}, set(case["selected"]))
        scope = original.prepared.session_scope.document()
        self.assertEqual(scope["schema"], "wom-kit/git-backup-session-scope/v2")
        self.assertEqual(scope["selected_change_count"], len(case["selected"]))
        self.assertTrue(all(proof["producer"] == "authenticated_source_intake_record_output"
                            for proof in scope["producer_proofs"]))
        self.assertEqual({proof["output_kind"] for proof in scope["producer_proofs"]},
                         {"source_intake_receipt", "common_completion_receipt"})
        other = [proof for proof in scope["producer_proofs"]
                 if proof["original_work_session_binding"]["work_session_ref"] == case["b"]["session"]]
        self.assertEqual(len(other), 2)
        exclusions = {row["private_change"]["path"]: row for row in original.prepared.excluded_changes}
        for path in case["intake_b"]["outputs"]:
            self.assertEqual(exclusions[path]["scope"], "other_session")
        for path in (case["generic"], "notes.md", case["intake_a"]["source"], case["intake_b"]["source"]):
            self.assertEqual(exclusions[path]["scope"], "unknown")
        self.base.assert_exclusions()
        return original, pointer

    def verify_finished(self, case, result, original, pointer):
        self.assertTrue(result["original_commit_verified"] and result["current_claim_ownership_verified"])
        self.assertEqual(result["selected_output_count"], len(case["selected"]))
        self.assertEqual(result["selected_receipt_count"], len(case["selected"]))
        self.assertTrue(result["receipt_only"])
        self.assertFalse(result["artifact_backup_complete"] or result["artifact_capture_performed"] or result["source_bytes_backed_up"])
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.git("rev-parse", "HEAD^").stdout.strip(), case["baseline"])
        self.assertEqual(self.base.fixture.git_dir(self.base.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), head)
        self.assertEqual(set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines()),
                         set(case["selected"]))
        for path, raw in case["selected"].items():
            self.assertEqual((self.root / path).read_bytes(), raw)
            blob = self.git("hash-object", "--", path).stdout.strip()
            self.assertEqual(self.git("rev-parse", "HEAD:" + path).stdout.strip(), blob)
            self.assertEqual(self.base.fixture.git_dir(self.base.fixture.remote, "rev-parse", "refs/heads/main:" + path).stdout.strip(), blob)
        self.base.assert_exclusions()
        self.assertEqual({path: (self.root / path).read_bytes() for path in case["baseline_bytes"]}, case["baseline_bytes"])
        self.assertEqual(self.base.original_git(case["a"])[0]._raw, original._raw)
        self.assertEqual(self.base.routing(case["a"])._read(current=False).document()["last_completed_operation"], pointer)
        self.assertIsNone(self.base.routing(case["a"])._read(current=False).pending_operation())
        self.assertEqual(self.base.routing(case["b"])._read(current=False)._raw, case["b_actor"])
        self.assertEqual(self.base.store.read().sha256, case["registry"])
        self.assertEqual(len(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")) - case["claims"]), 1)
        self.assertEqual(len(self.base.fixture.transport_commands), 1)
        self.assertFalse(self.base.key.active)
        return head

    def test_tracked_common_final_still_discovers_single_receipt_then_pre_push_resume_and_replay(self):
        case = self.prepare(common_tracked=True)
        with patch.object(writer._GitBackupBackend, "_push", side_effect=RuntimeError("SYNTHETIC_PRIVATE_PUSH_CUT")) as cut:
            interrupted = self.call("git-backup-reconcile-plan", *case["a"]["refs"], "--work-session-ref", case["a"]["session"],
                "--approve", "--credential-mode", "stored", "--reviewed-by", "person:synthetic-git-reviewer", ok=False)
        cut.assert_called_once()
        self.assertFalse(interrupted["backup_completion_verified"])
        committed = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(committed, case["baseline"])
        self.assertEqual(self.base.fixture.git_dir(self.base.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), case["baseline"])
        original, pointer = self.verify_original_and_exclusions(case)
        with self.forbid_discovery(), \
             patch.object(writer._GitBackupBackend, "_commit_group", side_effect=AssertionError("second commit")), \
             patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("new native decision")), \
             patch.object(broker, "_claim_exact_human_approval_core", side_effect=AssertionError("new claim")):
            result = self.call("git-backup-reconcile-plan", *case["a"]["refs"], "--resume")
        self.assertEqual(self.verify_finished(case, result, original, pointer), committed)
        self.assertEqual(self.base.native.calls, 5)
        for intake in (case["intake_a"], case["intake_b"]):
            self.assertFalse(intake["request"].exists())
            (self.root / intake["source"]).unlink()  # Fixture-owned inputs only, after exact Git finishes.
        before = self.base.files()
        with self.forbid_discovery(), \
             patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer replay")), \
             patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("terminal signing replay")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor replay")), \
             patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("native replay")), \
             patch.object(broker, "_claim_exact_human_approval_core", side_effect=AssertionError("claim replay")):
            replay = self.call("git-backup-reconcile-plan", *case["a"]["refs"], "--resume")
        self.assertTrue(replay["original_operation_already_completed"] and replay["original_commit_verified"])
        self.assertFalse(replay["domain_writer_reentered"])
        self.assertEqual(self.base.files(), before)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.base.fixture.remote), case["generic"]):
            self.assertNotIn(marker, json.dumps(self.base.outputs))

    def test_original_preclaim_review_backs_up_both_single_outputs_without_rediscovery(self):
        case = self.prepare(common_tracked=False)
        with patch.object(broker, "_claim_exact_human_approval_core", side_effect=RuntimeError("SYNTHETIC_PRIVATE_PRECLAIM_CUT")) as cut:
            interrupted = self.call("git-backup-reconcile-plan", *case["a"]["refs"], "--work-session-ref", case["a"]["session"],
                "--approve", "--credential-mode", "stored", "--reviewed-by", "person:synthetic-git-reviewer", ok=False)
        cut.assert_called_once()
        self.assertFalse(interrupted["backup_completion_verified"])
        original, pointer = self.verify_original_and_exclusions(case)
        pending = self.base.routing(case["a"])._read(current=False)._raw
        self.assertEqual(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), case["claims"])
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), case["baseline"])
        observed, guard_failures = [], []
        request_native = broker._request_exact_human_approval_core

        def review(context, **options):
            observed.append(approval.exact_human_approval_context_sha256(context))
            try:
                self.assertEqual(self.base.routing(case["a"])._read(current=False)._raw, pending)
            except AssertionError as error:
                # The workflow maps a guard failure to the opaque
                # exact_human_approval_state_unknown; keep the detail visible.
                guard_failures.append(str(error))
                raise
            return request_native(context, **options)

        with self.forbid_discovery(), patch.object(broker, "_request_exact_human_approval_core", side_effect=review):
            result = self.call("git-backup-reconcile-plan", *case["a"]["refs"], "--approve", "--review-original",
                               ok=None)
        self.assertEqual(guard_failures, [])
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["native_approval_redisplayed"])
        self.assertEqual(observed, [pointer["context_sha256"]])
        self.verify_finished(case, result, original, pointer)
        self.assertEqual(self.base.native.calls, 6)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.base.fixture.remote), case["generic"]):
            self.assertNotIn(marker, json.dumps(self.base.outputs))


if __name__ == "__main__":
    unittest.main()
