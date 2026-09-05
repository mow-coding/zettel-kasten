"""Source public CLI through real synthetic Git; not an installed-wheel claim.

Only the native dialog/key and isolated bare-remote/handoff seams are supplied
by the existing synthetic fixture. Runtime guard, locking, CLI, broker, common
writer, private storage and actor completion use their real implementations.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

import test_v0420_work_session_git_workflow as fixtures
from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval_windows as native
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_actor as actor
from wom_kit import work_session_git_terminal as terminal


class SessionGitPublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SessionGitWorkflowTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def call(self, *mode_arguments, live_progress=False):
        fixture = self.fixture
        output, progress = io.StringIO(), io.StringIO()
        arguments = ["git-backup-reconcile-plan", str(fixture.root),
                     "--client-app-ref", fixture.app, "--task-route-ref", fixture.route,
                     "--format", "json", *mode_arguments]
        self.live_events = []
        if live_progress:
            read_fd, write_fd = os.pipe()
            reader = os.fdopen(read_fd, "r", encoding="utf-8")
            stream = os.fdopen(write_fd, "w", encoding="utf-8", buffering=1)
            failures = []

            def drain():
                try:
                    for line in reader:
                        self.live_events.append((time.monotonic(), line))
                except Exception as error:
                    failures.append(type(error).__name__)
                finally:
                    reader.close()

            worker = threading.Thread(target=drain, daemon=True)
            worker.start()
            try:
                with redirect_stdout(output), redirect_stderr(stream):
                    code = cli.main(arguments)
            finally:
                stream.close()
                worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), "progress child retained output after command")
            self.assertFalse(failures)
            progress.write("".join(line for _stamp, line in self.live_events))
        else:
            with redirect_stdout(output), redirect_stderr(progress):
                code = cli.main(arguments)
        for private in (str(fixture.root), str(fixture.fixture.remote),
                        "Synthetic task", "Synthetic app", "new-private.txt"):
            self.assertNotIn(private, output.getvalue() + progress.getvalue())
        return code, json.loads(output.getvalue()), progress.getvalue()

    def test_cli_preview_real_backup_then_identifier_free_original_resume(self):
        fixture = self.fixture
        before = fixture.evidence()
        args = ["--work-session-ref", fixture.session, "--credential-mode", "stored"]
        code, preview, _progress = self.call("--dry-run", *args)
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["selected_receipt_count"], 1)
        self.assertFalse(preview["backup_performed"])
        self.assertEqual(fixture.evidence(), before)
        stalled_mutations = []

        def delayed_transport(*values, **options):
            started = time.monotonic()
            time.sleep(11.2)
            finished = time.monotonic()
            stalled_mutations.append((started, finished))
            return fixture.fixture.transport_runner(*values, **options)

        command_started = time.monotonic()
        with patch.object(native, "_CtypesTaskDialogNative", return_value=fixture.native), \
             patch.object(writer.planning, "_run_transport_capped", side_effect=delayed_transport):
            code, result, progress = self.call("--approve", *args,
                                               "--reviewed-by", "person:synthetic-reviewer", live_progress=True)
        command_finished = time.monotonic()
        self.assertEqual(code, 0, result)
        self.assertTrue(result["original_commit_verified"])
        self.assertTrue(result["receipt_only"])
        self.assertFalse(result["artifact_backup_complete"])
        self.assertEqual(fixture.native.calls, 1)
        self.assertTrue(progress)
        self.assertTrue(result["progress_observation"]["live_heartbeat_used"])
        self.assertTrue(result["progress_observation"]["observer_closed"])
        self.assertEqual(len(stalled_mutations), 1)
        self.assertLessEqual(self.live_events[0][0] - command_started, 2)
        stamps = [stamp for stamp, _line in self.live_events] + [command_finished]
        self.assertLessEqual(max(right - left for left, right in zip(stamps, stamps[1:])), 10)
        during = [json.loads(line) for stamp, line in self.live_events
                  if stalled_mutations[0][0] <= stamp <= stalled_mutations[0][1]]
        self.assertGreaterEqual(sum(row["event"] == "heartbeat" for row in during), 2)
        for _stamp, line in self.live_events:
            self.assertFalse(json.loads(line)["completion_verified"])
        local_head = fixture.git("rev-parse", "HEAD").stdout.strip()
        remote_head = fixture.fixture.git_dir(fixture.fixture.remote, "rev-parse", "refs/heads/main").stdout.strip()
        self.assertEqual(local_head, remote_head)
        self.assertNotEqual(local_head, fixture.fixture.initial_head)
        committed = fixture.git("show", "--format=", "--name-only", "HEAD").stdout.splitlines()
        self.assertEqual(committed, [
            "receipts/ops/exact-operations/" + fixture.original["execution_sha256"][7:] + ".json",
        ])
        self.assertEqual((fixture.root / "tracked.txt").read_text(), "after\n")
        self.assertEqual((fixture.root / "new-private.txt").read_text(), "new bytes\n")
        self.assertIsNone(fixture.routing.read().pending_operation())
        retained = fixture.evidence()
        with patch.object(writer, "_run_git_backup_exact_operation", side_effect=AssertionError("writer reentered")), \
             patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("new plan")), \
             patch.object(terminal, "_build_git_terminal_record", side_effect=AssertionError("new signature")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("actor rewritten")), \
             patch.object(native, "_CtypesTaskDialogNative", side_effect=AssertionError("new approval")):
            code, resumed, _progress = self.call("--resume")
        self.assertEqual(code, 0, resumed)
        self.assertTrue(resumed["original_operation_already_completed"])
        self.assertTrue(resumed["original_commit_verified"])
        self.assertFalse(resumed["domain_writer_reentered"])
        self.assertEqual(fixture.evidence(), retained)
        self.assertEqual(fixture.git("rev-parse", "HEAD").stdout.strip(), local_head)
