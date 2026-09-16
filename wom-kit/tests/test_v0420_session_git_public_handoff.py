"""One joined source CLI journey; not installed-wheel or document-custody proof.

Only native input/key and the existing isolated bare-remote transport seams are
synthetic. The Git planner's legacy read-only handoff prerequisite is fixed by
that fixture; the new work-session handoff, actor/claim authorities, runtime
guard, broker, exact writers, receipts and both actual Git pushes remain real.
No claimed actor or registry generation is seeded through a private API.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

import test_git_backup_writer as git_fixture
import test_v0420_work_session_execution as session_fixture
import test_v0420_work_session_public_management as public_fixture
from wom_kit import archive_cli
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import work_session_registration as registration


class SessionGitPublicHandoffTests(unittest.TestCase):
    cli = public_fixture.WorkSessionPublicManagementTests.cli

    def setUp(self):
        self.git_fixture = git_fixture.GitBackupWriterTests()
        self.git_fixture.setUp()
        self.addCleanup(self.git_fixture.tearDown)
        self.root = self.git_fixture.root
        self.git = lambda *args, **kwargs: self.git_fixture.git(self.root, *args, **kwargs)
        self.git("config", "core.autocrlf", "false")
        self.assertFalse((self.root / "profiles").exists())
        self.native, self.key = session_fixture.SessionNative(), git_fixture._KeyProvider()
        for seam in (*self.git_fixture.patches(),
                     patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native),
                     patch.object(broker, "_production_key_provider", return_value=self.key)):
            seam.start()
            self.addCleanup(seam.stop)
        # These are unrelated pre-existing bytes, never inferred session work.
        self.git("add", "tracked.txt")
        (self.root / "tracked.txt").write_bytes(b"SYNTHETIC_PRIVATE_UNSTAGED\n")
        (self.root / ".gitignore").write_bytes(b"profiles/local/\nlegacy-ignored/\n")
        (self.root / "legacy-ignored").mkdir()
        (self.root / "legacy-ignored" / "old.txt").write_bytes(b"SYNTHETIC_PRIVATE_IGNORED\n")
        (self.root / "receipts").mkdir()
        (self.root / "receipts" / "legacy-unattributed.json").write_bytes(
            b'{"legacy":"SYNTHETIC_PRIVATE_NO_AUTHORSHIP"}\n')
        self.excluded_paths = ("archive.yml", ".gitignore", "tracked.txt", "new-private.txt",
                               "legacy-ignored/old.txt", "receipts/legacy-unattributed.json")
        self.excluded = {path: (self.root / path).read_bytes() for path in self.excluded_paths}
        self.staged = self.git("ls-files", "--stage", "--", *self.excluded_paths).stdout
        self.outputs = []

    def command(self, *flags, request=None):
        code, result, errors = self.cli(self.root, *flags, request=request)
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(errors, "")
        self.outputs.append(result)
        return result["result"]

    def backup(self, app, route, session, *, ok=True):
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress):
            code = archive_cli.main([
                "git-backup-reconcile-plan", str(self.root), "--approve",
                "--client-app-ref", app, "--task-route-ref", route,
                "--work-session-ref", session, "--credential-mode", "stored",
                "--reviewed-by", "person:synthetic-public-reviewer", "--format", "json",
            ])
        result = json.loads(output.getvalue())
        self.assertEqual(code == 0, ok, result)
        self.assertIs(result["ok"], ok)
        self.outputs.extend((result, progress.getvalue()))
        return result

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(self.root).parts
                and path.name != ".writer.lock"}

    def assert_excluded_unchanged(self):
        self.assertEqual({path: (self.root / path).read_bytes() for path in self.excluded_paths}, self.excluded)
        self.assertEqual(self.git("ls-files", "--stage", "--", *self.excluded_paths).stdout, self.staged)
        self.assertNotEqual(self.git("ls-files", "--error-unmatch", "--",
                                    "receipts/legacy-unattributed.json", check=False).returncode, 0)
        self.assertEqual(self.git("check-ignore", "--", "legacy-ignored/old.txt").stdout.strip(),
                         "legacy-ignored/old.txt")

    @staticmethod
    def receipt_path(result):
        return "receipts/ops/exact-operations/" + result["execution_sha256"][7:] + ".json"

    def assert_backup_commit(self, result, receipt_path, previous_head):
        self.assertTrue(result["original_commit_verified"])
        self.assertTrue(result["current_claim_ownership_verified"])
        self.assertTrue(result["actor_completion_published"])
        self.assertTrue(result["receipt_only"])
        self.assertFalse(result["artifact_backup_complete"])
        self.assertFalse(result["document_provenance_evaluated"])
        self.assertEqual(result["selected_receipt_count"], 1)
        self.assertEqual(result["commit_count"], 1)
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(head, previous_head)
        self.assertEqual(self.git("rev-parse", "HEAD^").stdout.strip(), previous_head)
        self.assertEqual(self.git_fixture.git_dir(self.git_fixture.remote, "rev-parse",
                                                 "refs/heads/main").stdout.strip(), head)
        committed = self.git("show", "--format=", "--name-only", "HEAD").stdout.splitlines()
        self.assertEqual([path for path in committed if path], [receipt_path])
        self.assert_excluded_unchanged()
        return head

    def test_public_create_backup_handoff_accept_stale_refusal_and_successor_backup(self):
        apps = []
        for label in ("SYNTHETIC_PRIVATE_APP_A", "SYNTHETIC_PRIVATE_APP_B"):
            preview = self.command("--action", "register-app", "--dry-run", "--request-stdin",
                                   request={"label": label})
            self.command("--action", "register-app", "--apply", "--request-stdin",
                         request={"selection": preview, "label": label})
            apps.append(preview["client_app_ref"])
        app_a, app_b = apps
        route_a = self.command("--action", "request-init", "--client-app-ref", app_a)["task_route_ref"]
        refs_a = ("--client-app-ref", app_a, "--task-route-ref", route_a)
        created = self.command("--action", "create", "--approve", "--request-stdin", *refs_a,
            request={"label": "SYNTHETIC_PRIVATE_TASK_A", "reviewer_claim": "person:synthetic-public-reviewer"})
        session_a = created["work_session_binding"]["work_session_ref"]
        claimed_a = self.command("--action", "claim", "--apply", *refs_a, "--work-session-ref", session_a)
        self.assertTrue(claimed_a["current_claim_ownership_verified"])
        created_path = self.receipt_path(created)
        created_raw = (self.root / created_path).read_bytes()
        head_a = self.assert_backup_commit(self.backup(app_a, route_a, session_a), created_path,
                                          self.git_fixture.initial_head)
        sent = self.command("--action", "handoff", "--approve", "--request-stdin", *refs_a,
            "--work-session-ref", session_a, "--target-app-ref", app_b,
            request={"reviewer_claim": "person:synthetic-public-reviewer"})
        self.assertFalse(sent["ownership_transferred"])
        self.assertFalse(sent["artifact_responsibility_transferred"])
        handoff_path = self.receipt_path(sent)
        handoff_raw = (self.root / handoff_path).read_bytes()
        route_b = self.command("--action", "request-init", "--client-app-ref", app_b)["task_route_ref"]
        refs_b = ("--client-app-ref", app_b, "--task-route-ref", route_b)
        accepted = self.command("--action", "accept", "--approve", "--request-stdin", *refs_b,
            "--work-session-ref", session_a, request={"reviewer_claim": "person:synthetic-public-reviewer"})
        session_b = accepted["work_session_binding"]["work_session_ref"]
        self.assertNotEqual(session_b, session_a)
        workstream = created["work_session_binding"]["workstream_ref"]
        self.assertEqual(accepted["work_session_binding"]["workstream_ref"], workstream)
        self.assertTrue(accepted["claim_required"])
        claimed_b = self.command("--action", "claim", "--apply", *refs_b, "--work-session-ref", session_b)
        self.assertTrue(claimed_b["current_claim_ownership_verified"])
        # A successor must belong to this actual handoff, not an unrelated task.
        successor_state = registration._store(self.root).read()._document
        self.assertEqual(successor_state["sessions"][session_b]["predecessor_ref"], session_a)
        self.assertEqual(successor_state["sessions"][session_b]["client_app_ref"], app_b)
        self.assertEqual(successor_state["sessions"][session_b]["state"], "claimed")
        self.assertIsNotNone(successor_state["sessions"][session_b]["claim_ref"])
        self.assertEqual(successor_state["sessions"][session_a]["state"], "handed_off")
        self.assertIsNone(successor_state["sessions"][session_a]["claim_ref"])
        self.assertEqual(successor_state["workstreams"][workstream]["active_session_ref"], session_b)

        # A valid old app/route/session cannot authorize a new effect after handoff.
        before = self.files()
        calls = (self.native.calls, len(self.key.create_if_missing), len(self.git_fixture.transport_commands))
        stale = self.backup(app_a, route_a, session_a, ok=False)
        self.assertEqual(stale["reason_code"], "work_session_git_unavailable")
        self.assertFalse(stale["backup_completion_verified"])
        self.assertEqual(self.files(), before)
        self.assertEqual((self.native.calls, len(self.key.create_if_missing),
                          len(self.git_fixture.transport_commands)), calls)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), head_a)

        head_b = self.assert_backup_commit(self.backup(app_b, route_b, session_b),
                                          self.receipt_path(accepted), head_a)
        self.assertEqual((self.root / created_path).read_bytes(), created_raw)
        self.assertEqual((self.root / handoff_path).read_bytes(), handoff_raw)
        self.assertNotEqual(self.git("ls-files", "--error-unmatch", "--", handoff_path, check=False).returncode, 0)
        self.assertEqual(len(self.git_fixture.transport_commands), 2)
        self.assertEqual(self.native.calls, 5)  # create, A Git, handoff, accept, B Git
        self.assertEqual(self.git("rev-list", "--count", self.git_fixture.initial_head + ".." + head_b).stdout.strip(), "2")
        # Read existing state only for the privacy oracle; do not seed or repair it.
        store = registration._store(self.root)
        public = json.dumps(self.outputs)
        private_values = ["SYNTHETIC_PRIVATE", str(self.root), str(self.git_fixture.remote), "new-private.txt"]
        private_values += [row["claim_ref"] for row in store.read()._document["sessions"].values()
                           if row["claim_ref"] is not None]
        for private in private_values:
            self.assertNotIn(private, public)


if __name__ == "__main__":
    unittest.main()
