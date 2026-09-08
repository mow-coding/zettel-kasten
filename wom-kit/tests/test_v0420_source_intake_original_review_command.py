"""Explicit original-review grammar/held routing, not native writer acceptance."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import cli_entry
from wom_kit import exact_human_approval_windows as native
from wom_kit import exact_operation_manifest as exact
from wom_kit import mcp_server as mcp
from wom_kit import _mcp_session_transport as transport
from wom_kit import source_intake_batch_exact as legacy
from wom_kit import source_intake_session_command as command
from wom_kit import work_session_source_intake_workflow as batch_workflow
from wom_kit import work_session_source_intake_record_workflow as record_workflow


APP = "client_app_" + "a" * 32
ROUTE = "task_route_" + "b" * 32
SESSION = "work_session_" + "c" * 32
DIGEST = "sha256:" + "d" * 64
PRIVATE = "SYNTHETIC_PRIVATE_ORIGINAL_REVIEW"
FAMILIES = (
    ("batch", "source-intake-batch", "source_intake_batch", "manifest", "request_path", "dispatch_session_source_intake", batch_workflow),
    ("record", "source-intake-record", "source_intake_record", "source_intake_plan", "plan_path", "dispatch_session_source_intake_record", record_workflow),
)


def complete():
    return {"ok": True, "original_completion_verified": True, "completion_authentication_verified": True,
            "independent_verification": True, "execution_sha256": DIGEST, "common_final_receipt_sha256": DIGEST,
            "native_approval_redisplayed": True, "original_context_preserved": True,
            "artifact_capture_performed": False}


def arguments(root, **changes):
    value = dict(archive_root=str(root), mode="review_original", client_app_ref=APP, task_route_ref=ROUTE)
    value.update(changes)
    return value


def message(tool, values):
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": values}}


class OriginalReviewCliTests(unittest.TestCase):
    def call(self, name, flags, *, output_format="json"):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([name, PRIVATE, "--format", output_format, "--no-progress", *flags])
        return code, out.getvalue(), err.getvalue()

    def test_explicit_approve_review_uses_only_original_route_and_optional_session(self):
        for _family, name, _tool, _input, path_key, dispatch_name, _workflow in FAMILIES:
            for optional in ([], ["--work-session-ref=" + SESSION]):
                with patch.object(command, dispatch_name, return_value=complete()) as dispatch:
                    code, out, err = self.call(name, ["--client-app-ref=" + APP, "--task-route-ref=" + ROUTE,
                        "--approve", "--review-original", *optional])
                self.assertEqual(code, 0, out)
                dispatch.assert_called_once()
                values = dispatch.call_args.kwargs
                self.assertEqual(values["mode"], "review_original")
                self.assertEqual(values["work_session_ref"], SESSION if optional else None)
                self.assertIsNone(values[path_key])
                self.assertIsNone(values["reviewer_claim"])
                self.assertFalse(set(values) & {"native", "key_provider", "context", "claim", "approval_id"})
                self.assertNotIn(PRIVATE, out + err)

    def test_conflicting_modes_replacement_inputs_and_legacy_selectors_never_dispatch(self):
        for _family, name, _tool, input_key, _path, dispatch_name, _workflow in FAMILIES:
            base = ["--client-app-ref", APP, "--task-route-ref", ROUTE, "--review-original"]
            invalid = [[], ["--dry-run"], ["--resume"], ["--approve", "--resume"], ["--approve", "--dry-run"],
                       ["--approve", "--" + input_key.replace("_", "-"), PRIVATE],
                       ["--approve", "--reviewed-by", PRIVATE], ["--approve", "--expected-plan-sha256", PRIVATE],
                       ["--approve", "--resume-approval-id", PRIVATE], ["--approve", "--execution-sha256", PRIVATE],
                       ["--approve", "--reconcile"], ["--approve", "--native", PRIVATE]]
            for extra in invalid:
                with patch.object(command, dispatch_name) as dispatch:
                    code, out, err = self.call(name, base + extra)
                self.assertNotEqual(code, 0)
                dispatch.assert_not_called()
                self.assertNotIn(PRIVATE, out + err)

    def test_new_flag_is_private_scoped_selection_even_without_refs_and_startup_has_no_values(self):
        parser = cli.build_parser()
        for _family, name, _tool, _input, _path, _dispatch, _workflow in FAMILIES:
            parsed = parser.parse_args([name, PRIVATE, "--approve", "--review-original"])
            self.assertTrue(cli._source_intake_session_selected(parsed))
            with patch.object(native, "_CtypesTaskDialogNative", side_effect=AssertionError("missing refs opened native")):
                code, out, err = self.call(name, ["--approve", "--review-original"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["reason_code"], "work_session_task_context_required")
            self.assertNotIn(PRIVATE, out + err)
            code, out, err = self.call(name, ["--review-original", PRIVATE], output_format="text")
            self.assertEqual(code, 2)
            self.assertNotIn(PRIVATE, out + err)
            self.assertIn("private argument values were not echoed", err)
            self.assertTrue(cli_entry.startup_progress_requested([name, PRIVATE, "--approve", "--review-original"]))
            for silence in ("--no-progress", "--help", "--version"):
                self.assertFalse(cli_entry.startup_progress_requested([name, "--review-original", silence]))
        self.assertFalse(cli_entry.startup_progress_requested(["source-intake-record", "--", "--review-original"]))

    def test_unscoped_batch_resume_and_old_missing_input_error_order_stay_legacy(self):
        marker = object()
        with patch.object(command, "dispatch_session_source_intake") as dispatch, \
             patch.object(legacy, "plan_source_intake_batch", return_value=marker) as planner, \
             patch.object(legacy, "resume_source_intake_batch_auto", return_value={"ok": True}) as resume:
            code, out, err = self.call("source-intake-batch", ["--manifest", PRIVATE, "--resume", "--reviewed-by", "person:synthetic-reviewer"])
        self.assertEqual(code, 0, out)
        self.assertEqual(err, "")
        dispatch.assert_not_called()
        planner.assert_called_once()
        self.assertIs(resume.call_args.args[0], marker)
        for _family, name, _tool, input_key, _path, dispatch_name, _workflow in FAMILIES:
            for flags in (["--dry-run"], ["--resume"], ["--client-app-ref", APP, "--approve"]):
                with patch.object(command, dispatch_name) as dispatch:
                    code, out, _err = self.call(name, flags)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out)["missing_arguments"], ["--" + input_key.replace("_", "-")])
                dispatch.assert_not_called()


class OriginalReviewMcpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.server = mcp.JsonRpcMcpServer()

    def test_existing_two_tools_route_fourth_mode_without_fresh_inputs_or_new_callbacks(self):
        context = transport.SessionRequest("progress", lambda _value: True)
        token = transport._SESSION_REQUEST.set(context)
        self.addCleanup(lambda: transport._SESSION_REQUEST.reset(token))
        for _family, _name, tool, _input, path_key, dispatch_name, _workflow in FAMILIES:
            definition = next(row for row in mcp.TOOL_DEFINITIONS if row["name"] == tool)
            self.assertEqual(definition["inputSchema"]["properties"]["mode"]["enum"], ["preview", "apply", "resume", "review_original"])
            self.assertIn("normal resume never opens a new approval dialog", definition["description"])
            for optional in ({}, {"work_session_ref": SESSION}):
                public = command._public_result(complete(), mode="review_original")
                with patch.object(command, dispatch_name, return_value=public) as dispatch:
                    request = message(tool, arguments(self.root, **optional))
                    response = self.server.handle_message(request)
                self.assertTrue(transport._managed_mutation(request))
                dispatch.assert_called_once()
                values = dispatch.call_args.kwargs
                self.assertEqual(values["mode"], "review_original")
                self.assertEqual(values["work_session_ref"], optional.get("work_session_ref"))
                self.assertIsNone(values[path_key])
                self.assertIsNone(values["reviewer_claim"])
                self.assertEqual(values["progress"], context.progress)
                self.assertEqual(values["cancel_requested"], context.cancel_requested)
                self.assertIs(response["result"]["structuredContent"], public)
                self.assertNotIn(str(self.root), json.dumps(response))

    def test_original_presence_forbidden_and_authority_knobs_fail_before_both_adapters(self):
        for _family, _name, tool, input_key, _path, _dispatch, _workflow in FAMILIES:
            for mode in ("resume", "review_original"):
                for key in (input_key, "reviewed_by", "manifest", "source_intake_plan", "family", "native", "key_provider",
                            "claim", "context", "approval_id", "expected_plan_sha256", "execution_sha256", "progress", "cancel_requested"):
                    for value in (None, PRIVATE):
                        with patch.object(command, "dispatch_session_source_intake") as batch, \
                             patch.object(command, "dispatch_session_source_intake_record") as record:
                            response = self.server.handle_message(message(tool, arguments(self.root, mode=mode, **{key: value})))
                        self.assertEqual(response["error"]["code"], -32602)
                        batch.assert_not_called()
                        record.assert_not_called()
                        self.assertNotIn(PRIVATE, json.dumps(response))


class OriginalReviewHeldRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:original-review-command\n", encoding="utf-8")

    def call(self, dispatch_name, *, mode="review_original", **changes):
        values = dict(mode=mode, client_app_ref=APP, task_route_ref=ROUTE)
        values.update(changes)
        return getattr(command, dispatch_name)(self.root, **values)

    def test_exact_family_original_review_uses_real_held_runtime_and_optional_session(self):
        roots, helds = [], []
        guard = command.sessions._runtime_guard
        def observed_guard(root):
            roots.append(root)
            return guard(root)
        for family, _name, _tool, _input, _path, dispatch_name, workflow in FAMILIES:
            wrapper = "_review_original_session_source_intake_" + family + "_held"
            def run(root, *, held, **kwargs):
                self.assertEqual(root, self.root)
                self.assertIs(type(held), exact.ExactOperationWriterLock)
                held.verify_held()
                helds.append(held)
                self.assertEqual(set(kwargs), {"client_app_ref", "task_route_ref", "work_session_ref", "progress_hook"})
                return complete()
            for optional in ({}, {"work_session_ref": SESSION}):
                with patch.object(workflow, wrapper, side_effect=run, create=True) as review, \
                     patch.object(command.sessions, "_runtime_guard", side_effect=observed_guard):
                    result = self.call(dispatch_name, **optional)
                review.assert_called_once()
                self.assertTrue(result["original_completion_verified"])
                self.assertTrue(result["native_approval_redisplayed"])
                self.assertTrue(result["original_context_preserved"])
        self.assertEqual(roots, [self.root] * 4)
        for held in helds:
            with self.assertRaises(exact.ExactOperationManifestError):
                held.verify_held()

    def test_normal_resume_missing_claim_never_calls_original_review_or_native(self):
        for family, _name, _tool, _input, _path, dispatch_name, workflow in FAMILIES:
            with patch.object(workflow, "_resume_session_source_intake_" + family + "_held",
                    side_effect=workflow.WorkSessionIntakeWorkflowError("work_session_intake_original_approval_missing")) as resume, \
                 patch.object(workflow, "_review_original_session_source_intake_" + family + "_held", create=True) as review, \
                 patch.object(native, "_CtypesTaskDialogNative", side_effect=AssertionError("automatic native approval")) as dialog:
                result = self.call(dispatch_name, mode="resume")
            resume.assert_called_once()
            review.assert_not_called()
            dialog.assert_not_called()
            self.assertEqual(result["reason_code"], "work_session_intake_original_approval_missing")
            self.assertFalse(result["original_completion_verified"])

    def test_input_refusal_runtime_and_cancellation_happen_before_original_domain(self):
        for family, _name, _tool, _input, path_key, dispatch_name, workflow in FAMILIES:
            with patch.object(workflow, "_review_original_session_source_intake_" + family + "_held", create=True) as review:
                for changes in ({path_key: PRIVATE}, {"reviewer_claim": PRIVATE}, {"client_app_ref": None}, {"work_session_ref": PRIVATE}):
                    self.assertFalse(self.call(dispatch_name, **changes)["ok"])
                with patch.object(command.sessions, "_runtime_guard", side_effect=command.sessions.WorkSessionServiceError("project_runtime_mismatch")):
                    self.assertEqual(self.call(dispatch_name)["reason_code"], "project_runtime_mismatch")
                self.assertEqual(self.call(dispatch_name, cancel_requested=lambda: True)["reason_code"], "work_session_wait_cancelled")
                review.assert_not_called()

    def test_new_display_flags_do_not_relax_completed_authentication_requirements(self):
        for key in ("original_completion_verified", "completion_authentication_verified", "independent_verification",
                    "execution_sha256", "common_final_receipt_sha256"):
            value = complete()
            del value[key]
            with self.assertRaises(ValueError):
                command._public_result(value, mode="review_original")
        for key in ("native_approval_redisplayed", "original_context_preserved"):
            for invalid in (1, "true", None, [], {}):
                with self.assertRaises(ValueError):
                    command._public_result({**complete(), key: invalid}, mode="review_original")
        old = complete()
        del old["native_approval_redisplayed"], old["original_context_preserved"]
        self.assertNotIn("native_approval_redisplayed", command._public_result(old, mode="resume"))


if __name__ == "__main__":
    unittest.main()
