from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, command_status, mcp_server
from wom_kit import work_session_command as routing
from wom_kit import work_session_registration as registration
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as workflow
import test_v0420_work_session_execution as fixture


class WorkSessionPublicManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = archive_cli.build_parser()
        cls.inventory = archive_cli._parser_capability_inventory(cls.parser)

    def cli(self, root, *flags, request=None):
        output, errors = io.StringIO(), io.StringIO()
        source = io.StringIO(json.dumps(request) if request is not None else "")
        with mock.patch.object(archive_cli.sys, "stdin", source), redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(["work-session", str(root), "--no-progress", *flags])
        return code, json.loads(output.getvalue()), errors.getvalue()

    def test_cli_and_mcp_share_registration_create_claim_pause_resume_and_private_output(self):
        private_label = "SYNTHETIC_PRIVATE_APP_LABEL"
        with tempfile.TemporaryDirectory(prefix="wom-public-session-") as directory:
            root = Path(directory) / "archive"
            shutil.copytree(Path(__file__).resolve().parents[1] / "examples" / "fake-life-archive", root)
            code, preview, errors = self.cli(root, "--action", "register-app", "--dry-run", "--request-stdin",
                                             request={"label": private_label})
            self.assertEqual(code, 0)
            self.assertTrue(preview["ok"])
            self.assertEqual(errors, "")
            selection = preview["result"]
            original = {"selection": selection, "label": private_label}
            code, applied, errors = self.cli(root, "--action", "register-app", "--apply", "--request-stdin", request=original)
            self.assertEqual(code, 0, applied)
            self.assertTrue(applied["ok"])
            self.assertFalse(applied["result"]["routing_is_write_authority"])
            self.assertEqual(errors, "")
            with mock.patch.dict(mcp_server.os.environ, {mcp_server.MCP_ALLOWED_ROOTS_ENV: str(root)}):
                resumed = mcp_server.handle_tools_call({"name": "archive_work_session_manage", "arguments": {
                    "archive_root": str(root), "action": "register-app", "resume": True, "request": original,
                }})
            self.assertFalse(resumed.get("isError", False), resumed)
            self.assertTrue(resumed["structuredContent"]["ok"])
            self.assertEqual(resumed["structuredContent"]["result"]["client_app_ref"], selection["client_app_ref"])
            self.assertNotIn(private_label, json.dumps([preview, applied, resumed]))
            code, listed, _ = self.cli(root, "--kind", "app")
            self.assertEqual(code, 0)
            self.assertTrue(listed["ok"])

            native, key = fixture.SessionNative(), fixture._Key()
            before_request = {str(path.relative_to(root)): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}
            code, prepared, _ = self.cli(root, "--action", "request-init", "--client-app-ref", selection["client_app_ref"])
            self.assertEqual(code, 0, prepared)
            self.assertFalse(prepared["result"]["routing_is_write_authority"])
            self.assertTrue(prepared["result"]["read_only"])
            self.assertEqual(before_request, {str(path.relative_to(root)): path.read_bytes()
                                            for path in root.rglob("*") if path.is_file()})
            route = prepared["result"]["task_route_ref"]  # AI retains the public response before mutation.
            refs = ["--client-app-ref", selection["client_app_ref"], "--task-route-ref", route]
            with mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=native), \
                 mock.patch.object(workflow, "_production_key_provider", return_value=key):
                code, created, _ = self.cli(root, "--action", "create", "--approve", "--request-stdin", *refs,
                    request={"label": private_label, "reviewer_claim": "person:synthetic-public-reviewer"})
                self.assertEqual(code, 0, created)
                session = created["result"]["work_session_binding"]["work_session_ref"]
                code, continued, _ = self.cli(root, "--action", "create", "--resume", *refs)
                self.assertEqual(code, 0, continued)
                with mock.patch.dict(mcp_server.os.environ, {mcp_server.MCP_ALLOWED_ROOTS_ENV: str(root)}):
                    claimed = mcp_server.handle_tools_call({"name": "archive_work_session_manage", "arguments": {
                        "archive_root": str(root), "action": "claim", "apply": True,
                        "client_app_ref": selection["client_app_ref"], "task_route_ref": route,
                        "work_session_ref": session,
                    }})
                self.assertTrue(claimed["structuredContent"]["ok"], claimed)
                code, resumed_claim, _ = self.cli(root, "--action", "claim", "--resume", *refs,
                                                 "--work-session-ref", session)
                self.assertEqual(code, 0, resumed_claim)
                store = registration._store(root)
                original_claim = store.read()._document["sessions"][session]["claim_ref"]
                code, paused, _ = self.cli(root, "--action", "pause", "--apply", *refs,
                                         "--work-session-ref", session)
                self.assertEqual(code, 0, paused)
                self.assertEqual(paused["result"]["state"], "paused")
                self.assertFalse(paused["result"]["current_claim_ownership_verified"])
                paused_snapshot = store.read()
                self.assertIsNone(paused_snapshot._document["sessions"][session]["claim_ref"])
                with mock.patch.dict(mcp_server.os.environ, {mcp_server.MCP_ALLOWED_ROOTS_ENV: str(root)}):
                    replay = mcp_server.handle_tools_call({"name": "archive_work_session_manage", "arguments": {
                        "archive_root": str(root), "action": "pause", "resume": True,
                        "client_app_ref": selection["client_app_ref"], "task_route_ref": route,
                        "work_session_ref": session,
                    }})
                    self.assertTrue(replay["structuredContent"]["ok"], replay)
                    self.assertTrue(replay["structuredContent"]["result"]["original_operation_already_completed"])
                    self.assertEqual(store.read().sha256, paused_snapshot.sha256)
                    # A new paused-session resume is not a request to replay pause.
                    resumed_state = mcp_server.handle_tools_call({"name": "archive_work_session_manage", "arguments": {
                        "archive_root": str(root), "action": "resume", "apply": True,
                        "client_app_ref": selection["client_app_ref"], "task_route_ref": route,
                        "work_session_ref": session,
                    }})
                self.assertTrue(resumed_state["structuredContent"]["ok"], resumed_state)
                self.assertEqual(resumed_state["structuredContent"]["result"]["state"], "claimed")
                after_resume = store.read()
                self.assertNotEqual(after_resume._document["sessions"][session]["claim_ref"], original_claim)
                code, resumed_again, _ = self.cli(root, "--action", "resume", "--resume", *refs,
                                                "--work-session-ref", session)
                self.assertEqual(code, 0, resumed_again)
                self.assertTrue(resumed_again["result"]["original_operation_already_completed"])
                self.assertEqual(store.read().sha256, after_resume.sha256)
                code, wrong_original, _ = self.cli(root, "--action", "pause", "--resume", *refs,
                                                 "--work-session-ref", session)
                self.assertNotEqual(code, 0)
                self.assertFalse(wrong_original["ok"])
                self.assertEqual(store.read().sha256, after_resume.sha256)
            self.assertEqual(native.calls, 1)
            public_results = json.dumps([created, continued, claimed, resumed_claim, paused,
                                         replay, resumed_state, resumed_again, wrong_original])
            self.assertNotIn(private_label, public_results)
            self.assertNotIn(original_claim, public_results)
            self.assertNotIn(after_resume._document["sessions"][session]["claim_ref"], public_results)

    def test_supported_write_modes_are_not_mistaken_for_required_dry_run(self):
        for action, mode, native in (("register-app", "--apply", False), ("register-app", "--resume", False),
                                     ("create", "--approve", True), ("create", "--resume", False),
                                     ("claim", "--apply", False), ("claim", "--resume", False),
                                     ("pause", "--apply", False), ("pause", "--resume", False),
                                     ("resume", "--apply", False), ("resume", "--resume", False)):
            with self.subTest(action=action, mode=mode):
                args = self.parser.parse_args(["work-session", "synthetic-archive", "--action", action, mode])
                effects = command_status.resolve_namespace_invocation_effects(self.parser, args)
                self.assertEqual(effects["coverage"], "audited")
                self.assertEqual(effects["entry_gate"], "passed")
                self.assertIn("operational_metadata_write", [item["kind"] for item in effects["effects"]])
                self.assertEqual(effects["human_approval_requirement"], "required" if native else "not_required")
                availability = command_status.resolve_namespace_capability_availability(self.parser, self.inventory, args)
                self.assertTrue(availability["available"])

    def test_create_dry_run_is_consistently_unavailable_before_input_or_archive_access(self):
        argv = ["work-session", "synthetic-archive", "--action", "create", "--dry-run"]
        args = self.parser.parse_args(argv)
        availability = command_status.resolve_namespace_capability_availability(self.parser, self.inventory, args)
        self.assertFalse(availability["available"])
        self.assertEqual(availability["reason_code"], "work_session_mode_unavailable")
        suggested = command_status.resolve_suggested_command_mode(
            self.inventory, "archive work-session synthetic-archive --action create --dry-run",
            trusted_parser=self.parser)
        self.assertFalse(suggested["requested_mode_available"])
        self.assertEqual(suggested["capability_availability"]["reason_code"], "work_session_mode_unavailable")
        with mock.patch.object(routing, "dispatch_work_session_management", side_effect=AssertionError("no-dispatch")):
            code, result, _ = self.cli("synthetic-archive", "--action", "create", "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])
        result = routing.dispatch_work_session_management("synthetic-archive", action="create", dry_run=True)
        self.assertEqual(result["reason_code"], "work_session_mode_unavailable")

    def test_inventory_only_does_not_claim_action_dependent_modes_are_available(self):
        for action in ("list", "register-app", "request-init", "create", "claim", "pause", "resume"):
            with self.subTest(action=action):
                result = command_status.resolve_capability_availability(
                    self.inventory, "work-session", requested_mode="dry_run",
                    argument_tokens=("--action", action),
                )
                self.assertFalse(result["available"])
                self.assertFalse(result["argument_scope_evaluated"])
                self.assertEqual(result["reason_code"], "work_session_argument_scope_required")
        projection = command_status.build_capability_availability_projection(self.inventory)
        row = next(item for item in projection["rows"] if item["canonical_path"] == "work-session")
        self.assertFalse(row["dry_run"]["available"])
        self.assertEqual(row["dry_run"]["reason_code"], "work_session_argument_scope_required")
        unresolved = command_status.resolve_suggested_command_mode(
            self.inventory, "archive work-session synthetic-archive --action create --dry-run")
        self.assertFalse(unresolved["requested_mode_available"])
        self.assertEqual(unresolved["requested_mode_reason_code"], "work_session_argument_scope_required")
        for flags in (("--action", "list"), ("--action", "register-app", "--dry-run"),
                      ("--action", "request-init"), ("--action", "request-init", "--dry-run"),
                      ("--action", "create", "--approve"),
                      ("--action", "create", "--approve", "--review-original")):
            with self.subTest(flags=flags):
                args = self.parser.parse_args(["work-session", "synthetic-archive", *flags])
                result = command_status.resolve_namespace_capability_availability(self.parser, self.inventory, args)
                self.assertTrue(result["available"], result)
                self.assertTrue(result["argument_scope_evaluated"])
        for suffix in ("", " --review-original"):
            suggested = command_status.resolve_suggested_command_mode(
                self.inventory, "archive work-session synthetic-archive --action create --approve" + suffix,
                trusted_parser=self.parser)
            self.assertTrue(suggested["requested_mode_available"], suggested)
            self.assertTrue(suggested["approval_mode_available_for_arguments"], suggested)
            self.assertIsNone(suggested["approval_mode_reason_code_for_arguments"])

    def test_request_init_is_read_only_and_rejects_replacement_selectors(self):
        for suffix in ([], ["--dry-run"]):
            args = self.parser.parse_args(["work-session", "synthetic-archive", "--action", "request-init", *suffix])
            effects = command_status.resolve_namespace_invocation_effects(self.parser, args)
            self.assertEqual(effects["entry_gate"], "passed")
            self.assertEqual(effects["effects"], [{"kind": "local_read", "scope": "archive"}])
            self.assertEqual(effects["human_approval_requirement"], "not_required")
        for extra in ({"task_route_ref": "task_route:replacement"}, {"work_session_ref": "work_session:replacement"},
                      {"request": {"label": "PRIVATE_NEW_LABEL"}}, {"request": {"approval_id": "PRIVATE_ID"}}):
            result = routing.dispatch_work_session_management("synthetic-archive", action="request-init",
                client_app_ref="client_app:synthetic", **extra)
            self.assertEqual(result["reason_code"], "work_session_request_invalid")
            self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_invalid_private_input_does_not_retain_payload_or_exception_context(self):
        samples = [b'{"label":"PRIVATE_A","label":"PRIVATE_B"}', b'{"secret":"PRIVATE_X",',
                   b'{"label":NaN}', b'[]', b'"PRIVATE_X"', b'\xff', b' ' * (routing.REQUEST_LIMIT_BYTES + 1)]
        for raw in samples:
            with self.subTest(size=len(raw)):
                with self.assertRaises(routing.WorkSessionRequestError) as caught:
                    routing.read_private_request(io.BytesIO(raw))
                self.assertEqual(str(caught.exception), "work_session_request_invalid")
                self.assertIsNone(caught.exception.__context__)
        self.assertEqual(routing.read_private_request(io.StringIO('{"label":"synthetic"}')), {"label": "synthetic"})

    def test_original_resume_rejects_new_label_context_or_approval_inputs(self):
        for request in ({"label": "PRIVATE_NEW_LABEL"}, {"context": {}}, {"approval_id": "PRIVATE_ID"}):
            result = routing.dispatch_work_session_management("synthetic-archive", action="create", resume=True,
                client_app_ref="client_app:synthetic", task_route_ref="task_route:synthetic", request=request)
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason_code"], "work_session_request_invalid")
            self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_management_tool_is_not_the_read_only_query_or_a_native_injection_surface(self):
        tools = {row["name"]: row for row in mcp_server.TOOL_DEFINITIONS}
        self.assertTrue(tools["archive_work_session"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["archive_work_session_manage"]["annotations"]["readOnlyHint"])
        for extra in ("native", "key_provider", "context", "approval_id", "running_archive_cli_module_path"):
            with self.subTest(extra=extra), self.assertRaises(mcp_server.InvalidParamsError):
                mcp_server.tool_archive_work_session_manage({"archive_root": "synthetic-archive", "action": "create",
                                                             "approve": True, extra: "PRIVATE_VALUE"})


if __name__ == "__main__":
    unittest.main()
