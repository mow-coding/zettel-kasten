"""Source CLI intake-to-Git proof, not installed or source-custody acceptance.

Native input/key and the existing isolated local-bare-remote transport are
synthetic. Its legacy handoff planning prerequisite is synthetic/read-only;
session establishment, approvals, intake effects, Git commits and pushes are
real. No claimed actor, registry state, producer proof or writer is seeded.
"""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

import test_git_backup_writer as git_fixture
from test_v0420_work_session_execution import SessionNative
from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_actor as actor
from wom_kit import work_session_git_bundle as git_bundle
from wom_kit import work_session_git_terminal as terminal
from wom_kit import work_session_intake_git_provenance as intake_provenance
from wom_kit import work_session_registration as registration
from wom_kit import work_session_source_intake_bundle as intake_bundle
from wom_kit import work_session_source_intake_inventory as intake_inventory


class _ActiveSyntheticKey(git_fixture._KeyProvider):
    def __init__(self):
        super().__init__()
        self.active = False

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            raise AssertionError("nested synthetic key consumer")
        self.active = True
        try:
            return super().use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.active = False


class SessionIntakeGitPublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = git_fixture.GitBackupWriterTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.git = lambda *args, **kwargs: self.fixture.git(self.root, *args, **kwargs)
        self.git("config", "core.autocrlf", "false")
        self.assertFalse((self.root / "profiles").exists())
        self.native, self.key = SessionNative(), _ActiveSyntheticKey()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for seam in (*self.fixture.patches(),
                     patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native),
                     patch.object(broker, "_production_key_provider", return_value=self.key)):
            self.stack.enter_context(seam)
        self.outputs = []
        self.store = registration._store(self.root)

    def call(self, command, *flags, request=None, ok=True):
        output, errors = io.StringIO(), io.StringIO()
        supplied = io.StringIO("" if request is None else json.dumps(request))
        progress_flags = () if command == "git-backup-reconcile-plan" else ("--no-progress",)
        with patch.object(cli.sys, "stdin", supplied), redirect_stdout(output), redirect_stderr(errors):
            code = cli.main([command, str(self.root), "--format", "json", *progress_flags, *flags])
        result = json.loads(output.getvalue())
        if ok is not None:  # None: the caller inspects the outcome itself
            self.assertEqual(code == 0, ok, result)
            self.assertIs(result["ok"], ok, result)
        if command == "git-backup-reconcile-plan":
            # This in-process StringIO embedding is explicitly non-live. Its
            # real fixed observer still emits closed progress at callbacks.
            for line in errors.getvalue().splitlines():
                self.assertFalse(json.loads(line)["completion_verified"])
        else:
            self.assertEqual(errors.getvalue(), "")
        self.outputs.extend((result, errors.getvalue()))
        return result

    def session_call(self, *flags, request=None):
        return self.call("work-session", *flags, request=request)["result"]

    def establish(self, name):
        label = "SYNTHETIC_PRIVATE_APP_" + name
        preview = self.session_call("--action", "register-app", "--dry-run", "--request-stdin",
                                    request={"label": label})
        self.session_call("--action", "register-app", "--apply", "--request-stdin",
                          request={"selection": preview, "label": label})
        app = preview["client_app_ref"]
        route = self.session_call("--action", "request-init", "--client-app-ref", app)["task_route_ref"]
        refs = ("--client-app-ref", app, "--task-route-ref", route)
        created = self.session_call("--action", "create", "--approve", "--request-stdin", *refs,
            request={"label": "SYNTHETIC_PRIVATE_TASK_" + name,
                     "reviewer_claim": "person:synthetic-session-reviewer"})
        session = created["work_session_binding"]["work_session_ref"]
        claimed = self.session_call("--action", "claim", "--apply", *refs, "--work-session-ref", session)
        self.assertTrue(claimed["current_claim_ownership_verified"])
        return {"app": app, "route": route, "refs": refs, "session": session, "created": created}

    def routing(self, task):
        # Read-only assertion handle; public lifecycle calls establish authority.
        return actor.WorkSessionActorStore(self.store,
            client_app_ref=task["app"], task_route_ref=task["route"])

    @staticmethod
    def common_path(result):
        return "receipts/ops/exact-operations/" + result["execution_sha256"][7:] + ".json"

    def intake(self, task, name):
        items, sources = [], []
        for ordinal in (1, 2):
            relative = f"staging/incoming/{name}-source-{ordinal}.bin"
            source = self.root / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(f"SYNTHETIC_PRIVATE_{name}_SOURCE_{ordinal}\n".encode("ascii"))
            sources.append(relative)
            items.append({"item_id": f"{name}-source-{ordinal}", "local_path": relative,
                          "source_role": "primary_source"})
        request = self.root.parent / (name + "-private-request.json")
        request.write_text(json.dumps({"schema": "wom-kit/source-intake-batch-request/v0.1",
            "batch_id": "batch-" + name, "items": items}), encoding="utf-8")
        result = self.call("source-intake-batch", *task["refs"], "--work-session-ref", task["session"],
            "--manifest", str(request), "--approve", "--reviewed-by", "person:synthetic-intake-reviewer")
        self.assertTrue(result["original_completion_verified"])
        self.assertTrue(result["completion_authentication_verified"])
        self.assertFalse(result["artifact_capture_performed"])
        selected = self.routing(task)._read(current=False)
        pointer = selected.document()["last_completed_operation"]
        self.assertIsNone(selected.pending_operation())
        self.assertEqual(pointer["kind"], "source_intake_batch")
        with exact.ExactOperationWriterLock(self.root) as held:
            original = intake_bundle._load_original_source_intake_context_held(self.root,
                manifest_sha256=pointer["manifest_sha256"], held=held)
        plan = original.prepared.plan
        self.assertEqual(plan.manifest.work_session_binding, self.store.read().binding(task["session"]))
        outputs = {item.receipt_relative_path: item.receipt_bytes for item in plan.items}
        capture = plan.prepared_capture_request
        outputs[capture.relative_path] = capture.request_bytes
        for path, raw in outputs.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
        self.assertEqual(len(outputs), 3)
        return {"result": result, "original": original, "outputs": outputs,
                "sources": sources, "capture": capture.relative_path, "request": request}

    def assert_exclusions(self):
        self.assertEqual({path: (self.root / path).read_bytes() for path in self.excluded}, self.excluded)
        self.assertEqual(self.git("ls-files", "--stage", "--", *sorted(self.excluded)).stdout,
                         self.excluded_index)
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all", "--ignored",
                                 "--", *sorted(self.excluded)).stdout, self.excluded_status)
        self.assertEqual(self.git("check-ignore", "--", "legacy-ignored/old.bin").stdout.strip(),
                         "legacy-ignored/old.bin")

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
                and ".git" not in path.relative_to(self.root).parts and path.name != ".writer.lock"}

    def original_git(self, task):
        selected = self.routing(task)._read(current=False)
        pointer = (selected.pending_operation().document() if selected.pending_operation() is not None
                   else selected.document()["last_completed_operation"])
        self.assertEqual(pointer["kind"], "git_backup")
        with exact.ExactOperationWriterLock(self.root) as held:
            original = git_bundle._load_original_git_context_held(self.root, held=held,
                manifest_sha256=pointer["manifest_sha256"])
        return original, pointer

    def prepare_two_intakes(self):
        task_a, task_b = self.establish("A"), self.establish("B")
        intake_a, intake_b = self.intake(task_a, "A"), self.intake(task_b, "B")
        a_outputs = intake_a["outputs"]
        a_common = self.common_path(intake_a["result"])
        b_common = self.common_path(intake_b["result"])
        baseline_paths = (self.common_path(task_a["created"]), self.common_path(task_b["created"]), a_common)
        baseline_bytes = {path: (self.root / path).read_bytes() for path in baseline_paths}
        # Fixture history only: A's authentic final is already tracked, while
        # NONE of its three intake outputs is. Discovery cannot rely on a
        # changed-common-receipt filename to find the original intake.
        self.git("add", "--", *baseline_paths)
        self.git("commit", "-m", "Synthetic baseline authenticated receipts")
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("push", str(self.fixture.remote), "HEAD:refs/heads/main")
        self.assertEqual(self.git("show", "HEAD:" + a_common).stdout.encode("utf-8"), baseline_bytes[a_common])
        for path in a_outputs:
            self.assertNotEqual(self.git("cat-file", "-e", "HEAD:" + path, check=False).returncode, 0)

        generic = "receipts/sources/source-intake-aaaaaaaaaaaaaaaa.source-intake-plan.json"
        self.assertNotIn(generic, {*a_outputs, *intake_b["outputs"]})
        (self.root / generic).write_bytes(next(iter(a_outputs.values())))
        (self.root / "notes.md").write_bytes(b"SYNTHETIC_PRIVATE_STAGED_DOCUMENT\n")
        (self.root / ".gitignore").write_bytes(b"profiles/local/\nlegacy-ignored/\n")
        (self.root / "legacy-ignored").mkdir()
        (self.root / "legacy-ignored/old.bin").write_bytes(b"SYNTHETIC_PRIVATE_IGNORED\n")
        b_first = next(iter(intake_b["outputs"]))
        a_first = next(iter(a_outputs))
        self.git("add", "--", "tracked.txt", "notes.md", b_first, a_first)
        (self.root / "tracked.txt").write_bytes(b"SYNTHETIC_PRIVATE_UNSTAGED_DOCUMENT\n")
        (self.root / "notes.md").write_bytes(b"SYNTHETIC_PRIVATE_UNSTAGED_NOTES\n")
        exclusions = {"archive.yml", ".gitignore", "tracked.txt", "notes.md", "new-private.txt",
                      "legacy-ignored/old.bin", generic, b_common,
                      *intake_b["outputs"], *intake_a["sources"], *intake_b["sources"]}
        self.excluded = {path: (self.root / path).read_bytes() for path in exclusions}
        self.excluded_index = self.git("ls-files", "--stage", "--", *sorted(exclusions)).stdout
        self.excluded_status = self.git("status", "--porcelain", "--untracked-files=all", "--ignored",
                                        "--", *sorted(exclusions)).stdout
        b_actor = self.routing(task_b)._read(current=False)._raw
        registry_before = self.store.read().sha256
        claims_before = set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
        return {"task_a": task_a, "task_b": task_b, "intake_a": intake_a, "intake_b": intake_b,
                "baseline": baseline, "baseline_paths": baseline_paths, "baseline_bytes": baseline_bytes,
                "b_common": b_common, "generic": generic, "b_actor": b_actor,
                "registry_before": registry_before, "claims_before": claims_before}

    def test_baseline_common_receipt_still_selects_only_owned_intake_outputs_then_original_resume(self):
        case = self.prepare_two_intakes()
        task_a, task_b = case["task_a"], case["task_b"]
        intake_a, intake_b = case["intake_a"], case["intake_b"]
        a_outputs, baseline = intake_a["outputs"], case["baseline"]

        # A real commit is allowed to finish, then the synthetic transport cut
        # prevents the push. This is an interruption oracle, not a power loss.
        with patch.object(writer._GitBackupBackend, "_push",
                          side_effect=RuntimeError("SYNTHETIC_PRIVATE_PUSH_CUT")) as cut:
            interrupted = self.call("git-backup-reconcile-plan", *task_a["refs"],
                "--work-session-ref", task_a["session"], "--approve", "--credential-mode", "stored",
                "--reviewed-by", "person:synthetic-git-reviewer", ok=False)
        self.assertEqual(cut.call_count, 1, interrupted)
        cut.assert_called_once()
        self.assertEqual(interrupted["reason_code"], "exact_human_approval_state_unknown")
        self.assertFalse(interrupted["backup_completion_verified"])
        committed = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(committed, baseline)
        self.assertEqual(self.git("rev-parse", "HEAD^").stdout.strip(), baseline)
        self.assertEqual(set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines()),
                         set(a_outputs))
        self.assertEqual(self.fixture.git_dir(self.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), baseline)
        self.assert_exclusions()
        original, pointer = self.original_git(task_a)
        self.assertEqual({path for group in original.prepared.groups for path in group.paths}, set(a_outputs))
        scope = original.prepared.session_scope.document()
        self.assertEqual(scope["schema"], "wom-kit/git-backup-session-scope/v2")
        self.assertEqual(scope["selected_change_count"], 3)
        b_proofs = [proof for proof in scope["producer_proofs"]
                    if proof["original_work_session_binding"]["work_session_ref"] == task_b["session"]]
        self.assertEqual(len(b_proofs), 4)
        excluded = {row["private_change"]["path"]: row for row in original.prepared.excluded_changes}
        for path in {*intake_b["outputs"], case["b_common"]}:
            self.assertEqual(excluded[path]["scope"], "other_session")
        self.assertEqual(excluded[case["generic"]]["scope"], "unknown")
        self.assertEqual(excluded["notes.md"]["scope"], "unknown")
        claims_after_cut = set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertEqual(len(claims_after_cut - case["claims_before"]), 1)

        with patch.object(writer._GitBackupBackend, "_commit_group", side_effect=AssertionError("second commit")), \
             patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("new plan")), \
             patch.object(git_bundle, "_save_original_git_context_held", side_effect=AssertionError("context rewrite")), \
             patch.object(intake_inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("hint rediscovery")), \
             patch.object(intake_provenance, "_select_intake_output_changes_held", side_effect=AssertionError("new intake selection")), \
             patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("new native decision")), \
             patch.object(broker, "_claim_exact_human_approval_core", side_effect=AssertionError("new claim")):
            result = self.call("git-backup-reconcile-plan", *task_a["refs"], "--resume")
        self.assertTrue(result["original_commit_verified"])
        self.assertTrue(result["current_claim_ownership_verified"] and result["actor_completion_published"])
        self.assertEqual(result["selected_output_count"], 3)
        self.assertEqual(result["selected_receipt_count"], 2)
        self.assertEqual(result["selected_intake_output_count"], 3)
        self.assertFalse(result["receipt_only"] or result["artifact_backup_complete"])
        self.assertEqual(result["commit_count"], 1)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), committed)
        self.assertEqual(self.fixture.git_dir(self.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), committed)
        for path, raw in a_outputs.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
            blob = self.git("hash-object", "--", path).stdout.strip()
            self.assertEqual(self.git("rev-parse", "HEAD:" + path).stdout.strip(), blob)
            self.assertEqual(self.fixture.git_dir(self.fixture.remote, "rev-parse", "refs/heads/main:" + path).stdout.strip(), blob)
        for path in {*intake_b["outputs"], case["b_common"], case["generic"], "notes.md",
                     *intake_a["sources"], *intake_b["sources"]}:
            self.assertNotEqual(self.git("cat-file", "-e", "HEAD:" + path, check=False).returncode, 0)
        self.assert_exclusions()
        self.assertEqual({path: (self.root / path).read_bytes() for path in case["baseline_paths"]}, case["baseline_bytes"])
        self.assertEqual(self.original_git(task_a)[0]._raw, original._raw)
        self.assertIsNone(self.routing(task_a)._read(current=False).pending_operation())
        self.assertEqual(self.routing(task_a)._read(current=False).document()["last_completed_operation"], pointer)
        self.assertEqual(self.routing(task_b)._read(current=False)._raw, case["b_actor"])
        self.assertEqual(self.store.read().sha256, case["registry_before"])
        self.assertEqual(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), claims_after_cut)
        self.assertEqual(self.native.calls, 5)  # A/B creation, A/B intake, one Git review.
        self.assertEqual(len(self.fixture.transport_commands), 1)

        before_replay = self.files()
        with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer replay")), \
             patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("replan replay")), \
             patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("resign replay")), \
             patch.object(intake_inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("hint replay")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor replay")), \
             patch.object(windows, "_CtypesTaskDialogNative", side_effect=AssertionError("native replay")):
            replay = self.call("git-backup-reconcile-plan", *task_a["refs"], "--resume")
        self.assertTrue(replay["original_operation_already_completed"] and replay["original_commit_verified"])
        self.assertFalse(replay["domain_writer_reentered"])
        self.assertEqual(self.files(), before_replay)
        self.assertFalse(self.key.active)
        public = json.dumps(self.outputs)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.fixture.remote), case["generic"],
                       self.routing(task_a)._read(current=False).document()["claim_ref"],
                       self.routing(task_b)._read(current=False).document()["claim_ref"]):
            self.assertNotIn(marker, public)

    def test_missing_git_claim_original_review_reuses_saved_intake_proofs_without_hint_discovery(self):
        case = self.prepare_two_intakes()
        task_a, task_b = case["task_a"], case["task_b"]
        outputs = case["intake_a"]["outputs"]
        with patch.object(broker, "_claim_exact_human_approval_core",
                          side_effect=RuntimeError("SYNTHETIC_PRIVATE_PRECLAIM_CUT")) as cut:
            interrupted = self.call("git-backup-reconcile-plan", *task_a["refs"],
                "--work-session-ref", task_a["session"], "--approve", "--credential-mode", "stored",
                "--reviewed-by", "person:synthetic-git-reviewer", ok=False)
        self.assertEqual(cut.call_count, 1, interrupted)
        cut.assert_called_once()
        self.assertFalse(interrupted["backup_completion_verified"])
        original, pointer = self.original_git(task_a)
        pending_raw = self.routing(task_a)._read(current=False)._raw
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), case["baseline"])
        self.assertEqual(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")), case["claims_before"])
        self.assert_exclusions()
        observed_contexts = []
        request_approval = broker._request_exact_human_approval_core

        def observe_review(context, **options):
            observed_contexts.append(approval.exact_human_approval_context_sha256(context))
            self.assertEqual(self.routing(task_a)._read(current=False)._raw, pending_raw)
            return request_approval(context, **options)

        with patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("new plan")), \
             patch.object(git_bundle, "_save_original_git_context_held", side_effect=AssertionError("new context")), \
             patch.object(intake_inventory, "_capture_source_intake_context_inventory_held", side_effect=AssertionError("hint rediscovery")), \
             patch.object(intake_provenance, "_select_intake_output_changes_held", side_effect=AssertionError("new intake selection")), \
             patch.object(broker, "_request_exact_human_approval_core", side_effect=observe_review):
            result = self.call("git-backup-reconcile-plan", *task_a["refs"], "--approve", "--review-original")
        self.assertTrue(result["original_commit_verified"] and result["native_approval_redisplayed"])
        self.assertEqual(observed_contexts, [pointer["context_sha256"]])
        self.assertEqual(result["selected_output_count"], 3)
        self.assertEqual(result["selected_receipt_count"], 2)
        self.assertEqual(result["selected_intake_output_count"], 3)
        self.assertFalse(result["artifact_backup_complete"] or result["receipt_only"])
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.git("rev-parse", "HEAD^").stdout.strip(), case["baseline"])
        self.assertEqual(self.fixture.git_dir(self.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip(), head)
        self.assertEqual(set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines()), set(outputs))
        self.assertEqual(self.original_git(task_a)[0]._raw, original._raw)
        self.assertEqual(self.routing(task_a)._read(current=False).document()["last_completed_operation"], pointer)
        self.assertIsNone(self.routing(task_a)._read(current=False).pending_operation())
        self.assertEqual(self.routing(task_b)._read(current=False)._raw, case["b_actor"])
        self.assertEqual(self.store.read().sha256, case["registry_before"])
        self.assert_exclusions()
        self.assertEqual(self.native.calls, 6)  # Four session/intake decisions, first Git, original re-review.
        self.assertEqual(len(self.fixture.transport_commands), 1)
        self.assertEqual(len(set(self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")) - case["claims_before"]), 1)
        self.assertFalse(self.key.active)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.fixture.remote), case["generic"]):
            self.assertNotIn(marker, json.dumps(self.outputs))


if __name__ == "__main__":
    unittest.main()
