"""Public recovery of an exact task; only synthetic native/key input is fake."""

import json
import unittest
from unittest import mock

from wom_kit import archive_cli, command_status, mcp_server
from wom_kit import work_session_actor as actor
from wom_kit import work_session_command as routing
from wom_kit import work_session_operation as operation
from wom_kit import work_session_recovery as recovery
from wom_kit import work_session_service as service
import test_v0420_work_session_public_handoff as fixture


class PublicRecoveryJourneyTests(unittest.TestCase):
    # Reuse setup/helpers, not inherited tests or a second collected TestCase.
    cli = fixture.PublicHandoffJourneyTests.cli
    setUp = fixture.PublicHandoffJourneyTests.setUp
    command = fixture.PublicHandoffJourneyTests.command
    mcp = fixture.PublicHandoffJourneyTests.mcp
    files = fixture.PublicHandoffJourneyTests.files
    assert_private_output = fixture.PublicHandoffJourneyTests.assert_private_output

    def selection(self):
        return dict(client_app_ref=self.app, task_route_ref=self.route, work_session_ref=self.session)

    def test_public_recovery_replay_then_pause_resume_complete_preserves_session_and_originals(self):
        archive_before = (self.root / "archive.yml").read_bytes()
        selected = self.selection()
        result = self.mcp(action="recover", approve=True, **selected,
                          request={"reviewer_claim": "person:synthetic-public-reviewer"})
        current = self.store.read()._document["sessions"][self.session]
        self.assertTrue(result["current_claim_ownership_verified"])
        self.assertTrue(result["independent_post_verification"])
        self.assertFalse(result["ownership_transferred"])
        self.assertNotEqual(current["claim_ref"], self.original_claim)
        self.assertEqual(len(self.store.read()._document["sessions"]), 1)
        before, calls = self.files(), self.native.calls
        replay = self.command("--action", "recover", "--resume", *self.refs, "--work-session-ref", self.session)
        self.assertTrue(replay["original_operation_already_completed"])
        self.mcp(action="recover", approve=True, review_original=True, **selected)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.native.calls, calls)
        self.mcp(action="pause", apply=True, **selected)
        self.command("--action", "resume", "--apply", *self.refs, "--work-session-ref", self.session)
        done = self.mcp(action="complete", apply=True, **selected)
        self.assertEqual(done["state"], "completed")
        self.assertEqual((self.root / "archive.yml").read_bytes(), archive_before)
        self.assert_private_output()

    def test_public_preclaim_review_and_started_resume_do_not_replace_original_recovery(self):
        original = actor.WorkSessionActorStore.save
        selected = self.selection()

        def cut(store, **arguments):
            result = original(store, **arguments)
            if arguments.get("pending_manifest_sha256") is not None:
                raise OSError("SYNTHETIC_PRIVATE_RECOVERY_CUT")
            return result

        with mock.patch.object(actor.WorkSessionActorStore, "save", new=cut):
            self.mcp(action="recover", approve=True, **selected,
                      request={"reviewer_claim": "person:synthetic-public-reviewer"}, ok=False)
        before = self.files()
        self.mcp(action="recover", resume=True, **selected, ok=False)
        self.assertEqual(self.files(), before)
        reviewed = self.command("--action", "recover", "--approve", "--review-original",
                                *self.refs, "--work-session-ref", self.session)
        self.assertTrue(reviewed["current_claim_ownership_verified"])
        with mock.patch.object(operation, "apply_session_decision_with_claim",
                               side_effect=OSError("SYNTHETIC_PRIVATE_STARTED_CUT")):
            self.command("--action", "recover", "--approve", "--request-stdin", *self.refs,
                          "--work-session-ref", self.session,
                          request={"reviewer_claim": "person:synthetic-public-reviewer"}, ok=False)
        calls = self.native.calls
        resumed = self.mcp(action="recover", resume=True, **selected)
        self.assertTrue(resumed["independent_post_verification"])
        self.assertEqual(self.native.calls, calls)
        self.assertEqual(len(self.store.read()._document["sessions"]), 1)
        self.assert_private_output()

    def test_runtime_mismatch_blocks_all_public_recovery_routes_before_held_facade(self):
        metadata = self.root.parent / ".zettel-kasten"
        metadata.mkdir()
        (metadata / "installed-version.txt").write_text("v9.9.9\n", encoding="utf-8")
        before, calls = self.files(), self.native.calls
        with mock.patch.object(recovery, "_recover_task_held", side_effect=AssertionError("blocked facade")) as writer, \
             mock.patch.object(recovery, "_review_original_recovery_held", side_effect=AssertionError("blocked facade")) as review:
            for flags in ({"approve": True, "request": {"reviewer_claim": "person:synthetic-public-reviewer"}},
                          {"resume": True}, {"approve": True, "review_original": True}):
                result = self.mcp(action="recover", **self.selection(), **flags, ok=False)
                self.assertEqual(result["reason_code"], "project_runtime_mismatch")
            writer.assert_not_called()
            review.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.native.calls, calls)


class PublicRecoveryGrammarTests(unittest.TestCase):
    def test_mcp_description_advertises_supported_recovery_and_original_input_contract(self):
        tool = next(item for item in mcp_server.TOOL_DEFINITIONS if item["name"] == "archive_work_session_manage")
        self.assertIn("recover", tool["inputSchema"]["properties"]["action"]["enum"])
        description = tool["description"]
        for required in ("Recover approve", "explicit app/task/session references", "no target_app_ref",
                         "Recover resume/review_original", "no replacement reviewer", "Review_original requires approve"):
            self.assertIn(required, description)
        self.assertNotIn("recover are not supported", description)
        self.assertNotIn("Recover is not exposed", description)

    def test_capability_effect_and_mode_agree_on_all_recovery_modes(self):
        parser = archive_cli.build_parser()
        inventory = archive_cli._parser_capability_inventory(parser)
        for flags, native in ((("--approve",), True), (("--resume",), False),
                              (("--approve", "--review-original"), True)):
            with self.subTest(flags=flags):
                args = parser.parse_args(["work-session", "synthetic-archive", "--action", "recover", *flags])
                effects = command_status.resolve_namespace_invocation_effects(parser, args)
                self.assertEqual(effects["entry_gate"], "passed")
                self.assertEqual(effects["human_approval_requirement"], "required" if native else "not_required")
                self.assertTrue(command_status.resolve_namespace_capability_availability(parser, inventory, args)["available"])

    def test_invalid_target_claim_reviewer_and_missing_session_fail_before_any_mutation(self):
        common = dict(action="recover", client_app_ref="client_app_" + "a" * 32,
                      task_route_ref="task_route_" + "b" * 32)
        session = "work_session_" + "c" * 32
        cases = [dict(approve=True), dict(resume=True), dict(approve=True, review_original=True),
                 dict(approve=True, work_session_ref=session, target_app_ref="client_app_" + "d" * 32),
                 dict(apply=True, work_session_ref=session),
                 dict(resume=True, work_session_ref=session, request={"reviewer_claim": "SYNTHETIC_PRIVATE"}),
                 dict(approve=True, review_original=True, work_session_ref=session,
                      request={"reviewer_claim": "SYNTHETIC_PRIVATE"}),
                 dict(approve=True, work_session_ref=session,
                      request={"reviewer_claim": "person:synthetic", "claim_ref": "SYNTHETIC_PRIVATE"})]
        with mock.patch.object(service, "_write", side_effect=AssertionError("invalid request entered writer")):
            for case in cases:
                result = routing.dispatch_work_session_management("synthetic-archive", **common, **case)
                self.assertFalse(result["ok"])
                self.assertIn(result["reason_code"], {"work_session_request_invalid", "work_session_mode_unavailable"})
                self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
