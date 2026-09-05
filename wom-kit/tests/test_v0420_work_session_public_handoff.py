"""Real CLI/MCP handoff-to-accept journeys with synthetic native/key input."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, command_status, mcp_server
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import work_session_actor as actor
from wom_kit import work_session_command as routing
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registration as registration
from wom_kit import work_session_service as service
import test_v0420_work_session_execution as fixture
import test_v0420_work_session_public_management as public_fixture


class PublicHandoffJourneyTests(unittest.TestCase):
    cli = public_fixture.WorkSessionPublicManagementTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-public-handoff-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "fake-life-archive", self.root)
        self.outputs = []
        self.native = fixture.SessionNative()
        for change in (mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native),
                       mock.patch.object(workflow, "_production_key_provider", return_value=fixture._Key()),
                       mock.patch.dict(mcp_server.os.environ, {mcp_server.MCP_ALLOWED_ROOTS_ENV: str(self.root)})):
            change.start()
            self.addCleanup(change.stop)
        apps = []
        for label in ("SYNTHETIC_PRIVATE_SENDING_APP", "SYNTHETIC_PRIVATE_RECEIVING_APP"):
            preview = self.command("--action", "register-app", "--dry-run", "--request-stdin", request={"label": label})
            self.command("--action", "register-app", "--apply", "--request-stdin",
                         request={"selection": preview, "label": label})
            apps.append(preview["client_app_ref"])
        self.app, self.target = apps
        self.route = self.command("--action", "request-init", "--client-app-ref", self.app)["task_route_ref"]
        self.next_route = self.command("--action", "request-init", "--client-app-ref", self.target)["task_route_ref"]
        self.refs = ("--client-app-ref", self.app, "--task-route-ref", self.route)
        created = self.command("--action", "create", "--approve", "--request-stdin", *self.refs,
            request={"label": "SYNTHETIC_PRIVATE_TASK", "reviewer_claim": "person:synthetic-public-reviewer"})
        self.session = created["work_session_binding"]["work_session_ref"]
        self.command("--action", "claim", "--apply", *self.refs, "--work-session-ref", self.session)
        self.store = registration._store(self.root)
        self.original_claim = self.store.read()._document["sessions"][self.session]["claim_ref"]
        self.handoff_refs = (*self.refs, "--work-session-ref", self.session, "--target-app-ref", self.target)

    def command(self, *flags, request=None, ok=True):
        code, result, errors = self.cli(self.root, *flags, request=request)
        self.assertEqual(code == 0, ok, result)
        self.assertEqual(result["ok"], ok)
        self.assertEqual(errors, "")
        self.outputs.append(result)
        return result["result"] if ok else result

    def mcp(self, *, ok=True, **arguments):
        result = mcp_server.handle_tools_call({"name": "archive_work_session_manage",
            "arguments": {"archive_root": str(self.root), **arguments}})
        self.assertEqual(result.get("isError", False), not ok, result)
        self.assertEqual(result["structuredContent"]["ok"], ok)
        self.outputs.append(result)
        return result["structuredContent"]["result"] if ok else result["structuredContent"]

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def assert_private_output(self):
        output = json.dumps(self.outputs)
        for private in ("SYNTHETIC_PRIVATE", str(self.root), self.original_claim):
            self.assertNotIn(private, output)
        for row in self.store.read()._document["sessions"].values():
            if row["claim_ref"] is not None:
                self.assertNotIn(row["claim_ref"], output)

    def test_two_public_apps_handoff_accept_claim_pause_resume_complete_without_legacy_transfer(self):
        before_archive = (self.root / "archive.yml").read_bytes()
        sent = self.command("--action", "handoff", "--approve", "--request-stdin", *self.handoff_refs,
                            request={"reviewer_claim": "person:synthetic-public-reviewer"})
        self.assertFalse(sent["ownership_transferred"])
        self.assertFalse(sent["artifact_responsibility_transferred"])
        before = self.files()
        replay = self.mcp(action="handoff", resume=True, client_app_ref=self.app, task_route_ref=self.route,
                          work_session_ref=self.session, target_app_ref=self.target)
        self.assertTrue(replay["original_operation_already_completed"])
        self.assertEqual(self.files(), before)
        accepted = self.mcp(action="accept", approve=True, client_app_ref=self.target,
            task_route_ref=self.next_route, work_session_ref=self.session,
            request={"reviewer_claim": "person:synthetic-public-reviewer"})
        successor = accepted["work_session_binding"]["work_session_ref"]
        self.assertTrue(accepted["claim_required"])
        self.assertNotEqual(successor, self.session)
        next_refs = ("--client-app-ref", self.target, "--task-route-ref", self.next_route)
        before = self.files()
        self.command("--action", "accept", "--resume", *next_refs)
        self.assertEqual(self.files(), before)
        stale = self.command("--action", "handoff", "--resume", *self.handoff_refs, ok=False)
        self.assertTrue(stale["original_commit_verified"])
        self.assertEqual(self.files(), before)
        claimed = self.command("--action", "claim", "--apply", *next_refs, "--work-session-ref", successor)
        self.assertTrue(claimed["current_claim_ownership_verified"])
        paused = self.mcp(action="pause", apply=True, client_app_ref=self.target,
                          task_route_ref=self.next_route, work_session_ref=successor)
        self.assertEqual(paused["state"], "paused")
        self.command("--action", "resume", "--apply", *next_refs, "--work-session-ref", successor)
        done = self.mcp(action="complete", apply=True, client_app_ref=self.target,
                        task_route_ref=self.next_route, work_session_ref=successor)
        self.assertEqual(done["state"], "completed")
        self.assertEqual(self.native.calls, 3)
        self.assertEqual((self.root / "archive.yml").read_bytes(), before_archive)
        self.assert_private_output()

    def test_public_preclaim_handoff_rereview_and_started_accept_resume_keep_originals(self):
        original = actor.WorkSessionActorStore.save

        def cut(store, **arguments):
            result = original(store, **arguments)
            if arguments.get("pending_manifest_sha256") is not None:
                raise OSError("SYNTHETIC_PRIVATE_PRECLAIM_CUT")
            return result

        with mock.patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.command("--action", "handoff", "--approve", "--request-stdin", *self.handoff_refs,
                          request={"reviewer_claim": "person:synthetic-public-reviewer"}, ok=False)
        before = self.files()
        self.mcp(action="handoff", resume=True, client_app_ref=self.app, task_route_ref=self.route,
                  work_session_ref=self.session, target_app_ref=self.target, ok=False)
        self.assertEqual(self.files(), before)
        self.mcp(action="handoff", approve=True, review_original=True, client_app_ref=self.app,
                  task_route_ref=self.route, work_session_ref=self.session, target_app_ref=self.target)
        next_refs = ("--client-app-ref", self.target, "--task-route-ref", self.next_route)
        with mock.patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("SYNTHETIC_PRIVATE_STARTED_CUT")):
            self.command("--action", "accept", "--approve", "--request-stdin", *next_refs,
                "--work-session-ref", self.session, request={"reviewer_claim": "person:synthetic-public-reviewer"}, ok=False)
        calls = self.native.calls
        accepted = self.mcp(action="accept", resume=True, client_app_ref=self.target, task_route_ref=self.next_route)
        self.assertTrue(accepted["independent_post_verification"])
        self.assertEqual(self.native.calls, calls)
        self.assertEqual(len(self.store.read()._document["sessions"]), 2)
        self.assert_private_output()


class PublicHandoffGrammarTests(unittest.TestCase):
    def test_new_human_modes_share_capability_and_invocation_classification(self):
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        for action in ("accept", "handoff"):
            for flags, native in ((("--approve",), True), (("--resume",), False),
                                  (("--approve", "--review-original"), True)):
                with self.subTest(action=action, flags=flags):
                    args = parser.parse_args(["work-session", "synthetic-archive", "--action", action, *flags])
                    effects = command_status.resolve_namespace_invocation_effects(parser, args)
                    self.assertEqual(effects["entry_gate"], "passed")
                    self.assertEqual(effects["human_approval_requirement"], "required" if native else "not_required")
                    available = command_status.resolve_namespace_capability_availability(parser, inventory, args)
                    self.assertTrue(available["available"], available)

    def test_invalid_target_replacement_and_secret_inputs_are_refused_before_service(self):
        common = dict(client_app_ref="client_app_" + "a" * 32, task_route_ref="task_route_" + "b" * 32)
        session, target = "work_session_" + "c" * 32, "client_app_" + "d" * 32
        cases = [dict(action="accept", resume=True, work_session_ref=session),
                 dict(action="accept", approve=True, target_app_ref=target, work_session_ref=session),
                 dict(action="handoff", approve=True, work_session_ref=session),
                 dict(action="create", approve=True, target_app_ref=target),
                 dict(action="handoff", resume=True, work_session_ref=session, target_app_ref=target,
                      request={"reviewer_claim": "SYNTHETIC_PRIVATE_REPLACEMENT"}),
                 dict(action="accept", approve=True, work_session_ref=session,
                      request={"reviewer_claim": "person:synthetic", "key_provider": "SYNTHETIC_PRIVATE_KEY"})]
        with mock.patch.object(service, "_write", side_effect=AssertionError("invalid request entered writer")):
            for case in cases:
                with self.subTest(action=case["action"]):
                    result = routing.dispatch_work_session_management("synthetic-archive", **common, **case)
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["reason_code"], "work_session_request_invalid")
                    self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
