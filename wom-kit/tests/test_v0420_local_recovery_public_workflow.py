"""Public title recovery uses real session lifecycle, planners and field writes.

Only the native human input and archive authentication key are synthetic.
The original source mirror may disappear after interruption; resume takes
the retained app/task rather than replacement inputs or an approval digest.
"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

import test_v0420_source_intake_session_public_workflow as session_fixture
import test_v045_local_locator_title_recovery as title_fixture
from wom_kit import archive_cli as cli
from wom_kit import archive_services
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_title_recovery as titles
from wom_kit import mcp_server as mcp
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import work_session_actor as actor


class PublicSessionTitleRecoveryTests(unittest.TestCase):
    def mcp_call(self, fixture, mode, *, ok=True, **extra):
        result = mcp.JsonRpcMcpServer().handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "zet_title_remap_write", "arguments": {
                "archive_root": str(fixture.root), "mode": mode,
                "client_app_ref": fixture.app, "task_route_ref": fixture.route, **extra}}})
        self.assertNotIn("error", result, result)
        body = result["result"]
        self.assertEqual(body.get("isError", False), not ok, body)
        public = body["structuredContent"]
        self.assertEqual(public["ok"], ok, public)
        fixture.outputs.append(public)
        return public

    def test_public_title_preview_interruption_original_resume_and_alias_replay(self):
        f = session_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)

        def title_call(command, *flags, ok=True):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                code = cli.main([command, str(f.root), "--format", "json", *flags])
            result = json.loads(output.getvalue())
            self.assertEqual(code == 0, ok, result)
            self.assertEqual(result["ok"], ok, result)
            self.assertEqual(errors.getvalue(), "")
            f.outputs.append(result)
            return result

        helper = title_fixture.V045LocalLocatorTitleRecoveryTests()
        helper.write_notion_zettel(f.root, title="a" * 32, body="SYNTHETIC_PRIVATE_RECOVERY_BODY\n")
        mirror_directory = f.root.parent / "synthetic-private-title-mirror"
        mirror_directory.mkdir()
        mirror = helper.write_title_mirrors(mirror_directory, source_title=title_fixture.HUMAN_TITLE,
                                            markdown="SYNTHETIC_PRIVATE_SOURCE_BODY\n")
        archive_services.index_archive(f.root)
        fresh_flags = (*f.refs, "--work-session-ref", f.session, "--source-mirror", str(mirror))
        before = f.files()
        preview = title_call("zet-title-remap-write", *fresh_flags, "--dry-run")
        self.assertTrue(preview["current_claim_ownership_verified"])
        self.assertFalse(preview["original_completion_verified"])
        self.assertEqual(f.files(), before)
        self.assertEqual(f.native.calls, 1)
        write = recovery._Writer.write_field
        cut_once = []

        def cut(writer, **kwargs):
            result = write(writer, **kwargs)
            if kwargs["target_kind"] == "zettel" and not cut_once:
                cut_once.append(True)
                raise OSError("synthetic post-title interruption")
            return result

        with patch.object(recovery._Writer, "write_field", new=cut):
            interrupted = title_call("zet-title-remap-write", *fresh_flags,
                "--approve", "--reviewed-by", "person:synthetic-title-reviewer", ok=False)
        self.assertEqual(cut_once, [True])
        self.assertEqual(interrupted["effects_state"], "unknown")
        pending = f.routing._read(current=False).pending_operation().document()
        self.assertEqual(pending["kind"], "local_recovery")
        original = recovery.load_local_recovery_plan(f.root, manifest_sha256=pending["manifest_sha256"])
        original_bytes = (f.root / recovery._control_relative(pending["manifest_sha256"])).read_bytes()
        f.register_unrelated_app()
        mirror.unlink()
        (mirror_directory / "pages.index.jsonl").unlink()
        with patch.object(titles, "zet_title_recovery_execution_plan", side_effect=AssertionError("original replan")), \
             patch.object(f.native, "show", side_effect=AssertionError("second title approval")):
            resumed = self.mcp_call(f, "resume")
            self.assertTrue(resumed["original_completion_verified"])
            self.assertTrue(resumed["index_current"])
            self.assertFalse(resumed["whole_document_ownership_verified"])
            self.assertEqual((f.root / recovery._control_relative(pending["manifest_sha256"])).read_bytes(), original_bytes)
            self.assertTrue(recovery.verify_local_recovery_state(original, state="post")["all_match"])
            before = f.files()
            with patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("completed actor write")), \
                 patch.object(recovery, "_execute_core", side_effect=AssertionError("completed domain write")):
                replay = title_call("title-remap-write", *f.refs, "--resume-recovery", "--approve")
            self.assertTrue(replay["original_operation_already_completed"])
            self.assertFalse(replay["actor_completion_published"])
            self.assertEqual(f.files(), before)
        self.assertEqual(f.native.calls, 2)
        rendered = json.dumps(f.outputs)
        for private in (title_fixture.HUMAN_TITLE, str(mirror), "SYNTHETIC_PRIVATE_RECOVERY_BODY",
                        "SYNTHETIC_PRIVATE_SOURCE_BODY"):
            self.assertNotIn(private, rendered)

    def test_mcp_preclaim_cut_cli_review_and_mcp_completed_replay(self):
        f = session_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)
        helper = title_fixture.V045LocalLocatorTitleRecoveryTests()
        helper.write_notion_zettel(f.root, title="b" * 32, body="SYNTHETIC_PRIVATE_REVIEW_BODY\n")
        directory = f.root.parent / "synthetic-private-review-mirror"
        directory.mkdir()
        mirror = helper.write_title_mirrors(directory, source_title=title_fixture.HUMAN_TITLE,
                                            markdown="SYNTHETIC_PRIVATE_REVIEW_SOURCE\n")
        archive_services.index_archive(f.root)
        fresh = dict(work_session_ref=f.session, source_mirror=str(mirror))
        before = f.files()
        preview = self.mcp_call(f, "preview", **fresh)
        self.assertEqual(preview["effects_state"], "none")
        self.assertEqual(f.files(), before)
        with patch.object(broker, "_claim_exact_human_approval_core", side_effect=OSError("synthetic preclaim cut")):
            self.mcp_call(f, "apply", reviewed_by="person:synthetic-review", ok=False, **fresh)
        original = f.routing._read(current=False).pending_operation().document()
        control = f.root / recovery._control_relative(original["manifest_sha256"])
        raw = control.read_bytes()
        before = f.files()
        calls = f.native.calls
        self.mcp_call(f, "resume", ok=False)
        self.assertEqual(f.files(), before)
        self.assertEqual(f.native.calls, calls)
        f.register_unrelated_app()
        mirror.unlink()
        (directory / "pages.index.jsonl").unlink()
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(titles, "zet_title_recovery_execution_plan", side_effect=AssertionError("original replan")), \
             redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(["zet-title-remap-write", str(f.root), "--format", "json", *f.refs,
                             "--review-original", "--approve"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0, result)
        self.assertEqual(errors.getvalue(), "")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["original_context_preserved"])
        self.assertTrue(result["native_approval_redisplayed"])
        self.assertEqual(control.read_bytes(), raw)
        f.outputs.append(result)
        before = f.files()
        with patch.object(f.native, "show", side_effect=AssertionError("duplicate native")), \
             patch.object(recovery, "_execute_core", side_effect=AssertionError("duplicate writer")):
            replay = self.mcp_call(f, "review_original")
        self.assertTrue(replay["original_operation_already_completed"])
        self.assertFalse(replay["native_approval_redisplayed"])
        self.assertEqual(f.files(), before)
        rendered = json.dumps(f.outputs)
        for private in (title_fixture.HUMAN_TITLE, str(mirror), "SYNTHETIC_PRIVATE_REVIEW_BODY",
                        "SYNTHETIC_PRIVATE_REVIEW_SOURCE"):
            self.assertNotIn(private, rendered)


class SessionTitleGrammarTests(unittest.TestCase):
    def test_abbreviated_session_options_do_not_echo_invalid_values(self):
        for command in ("zet-title-remap-write", "title-remap-write"):
            for formatting in ([], ["--format=json"]):
                output, errors = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    code = cli.main([command, "SYNTHETIC_PRIVATE_ROOT", *formatting,
                        "--client-app", "SYNTHETIC_PRIVATE_APP", "--task-route", "SYNTHETIC_PRIVATE_ROUTE",
                        "--max-items", "SYNTHETIC_PRIVATE_VALUE"])
                self.assertNotEqual(code, 0)
                self.assertNotIn("SYNTHETIC_PRIVATE", output.getvalue() + errors.getvalue())

    def test_malformed_private_session_arguments_are_not_echoed(self):
        for command in ("zet-title-remap-write", "title-remap-write"):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                code = cli.main([command, "SYNTHETIC_PRIVATE_ROOT", "--format", "json",
                    "--client-app-ref", "SYNTHETIC_PRIVATE_APP", "--task-route-ref"])
            self.assertNotEqual(code, 0)
            json.loads(output.getvalue())
            self.assertNotIn("SYNTHETIC_PRIVATE", output.getvalue() + errors.getvalue())


if __name__ == "__main__":
    unittest.main()
