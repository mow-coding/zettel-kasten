from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import archive_cli, command_status, operation_control


class OperationControlAvailabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()
        cls.inventory = archive_cli._parser_capability_inventory(cls.parser)

    def argv(self, action: str, mode: str, root: str = "synthetic-root") -> list[str]:
        return ["operation-control", root, "--operation-ref", "op:sha256:" + "a" * 64,
                "--action", action, mode, "--format", "json"]

    def invoke(self, argv: list[str]) -> tuple[int, str, str]:
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(argv)
        return code, output.getvalue(), errors.getvalue()

    def test_inventory_and_projection_distinguish_unsupported_writer(self) -> None:
        row = next(row for row in self.inventory["commands"]
                   if row["canonical_path"] == "operation-control")
        self.assertEqual(row["approval_status"], "approval_fixed_closed")
        self.assertEqual(row["approval_reason_code"], "operation_cancel_not_supported")
        self.assertTrue(row["dry_run_exposed"])
        self.assertNotIn("operation-control", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        projection = command_status.build_capability_availability_projection(self.inventory)
        projected = next(row for row in projection["rows"]
                         if row["canonical_path"] == "operation-control")
        self.assertEqual(projected["dry_run"]["state"], "available")
        self.assertEqual(projected["approve_without_arguments"]["state"], "writer_unavailable")
        self.assertEqual(projected["approve_without_arguments"]["detail_reason_code"],
                         "operation_cancel_not_supported")
        counts = self.inventory["counts"]
        self.assertEqual(counts["approval_fixed_closed_command_count"],
                         counts["matched_fixed_closed_command_count"] + 1)
        self.assertEqual(counts["unmatched_fixed_closed_command_count"], 0)

    def test_parsed_modes_and_suggestions_share_reason(self) -> None:
        for action, mode, expected in (
            ("status", "--dry-run", "available"),
            ("wait", "--dry-run", "available"),
            ("recovery-plan", "--dry-run", "available"),
            ("cancel", "--approve", "writer_unavailable"),
        ):
            with self.subTest(action=action):
                argv = self.argv(action, mode)
                actual = command_status.resolve_namespace_capability_availability(
                    self.parser, self.inventory, self.parser.parse_args(argv))
                suggested = command_status.resolve_suggested_command_mode(
                    self.inventory, "archive " + " ".join(argv), trusted_parser=self.parser)
                self.assertEqual(actual["state"], expected)
                self.assertEqual(suggested["capability_availability"], actual)
                if expected == "writer_unavailable":
                    self.assertEqual(suggested["requested_mode_reason_code"],
                                     "operation_cancel_not_supported")

    def test_help_and_doctor_suggestion_do_not_claim_compound_gap(self) -> None:
        leaf = command_status._subparser_actions(self.parser)[0].choices["operation-control"]
        text = " ".join(leaf.format_help().split())
        self.assertIn("Writer unavailable: cancel is unsupported", text)
        self.assertNotIn("compound", text)
        doctor = object.__new__(archive_cli.Doctor)
        doctor.diagnostics = [archive_cli.Diagnostic(
            "warning", "synthetic_control", "Synthetic status suggestion.",
            suggested_command="archive " + " ".join(self.argv("cancel", "--approve")),
        )]
        doctor._attach_suggested_command_statuses()
        status = doctor.diagnostics[0].suggested_command_status
        self.assertEqual(status["requested_mode_reason_code"], "operation_cancel_not_supported")
        self.assertEqual(status["capability_availability"]["state"], "writer_unavailable")

    def test_cancel_dispatch_refuses_before_control_reads_and_echoes_no_inputs(self) -> None:
        private_marker = "PRIVATE_CONTROL_VALUE_MUST_NOT_BE_ECHOED"
        argv = self.argv("cancel", "--approve", private_marker)
        argv[argv.index("--operation-ref") + 1] = private_marker
        with mock.patch.object(operation_control, "unsupported_cancel",
                               side_effect=AssertionError("control_handler_must_not_run")):
            code, output, errors = self.invoke(argv)
            self.assertEqual(code, 1)
            self.assertEqual(errors, "")
            result = json.loads(output)
            self.assertEqual(result["capability_state"], "writer_unavailable")
            self.assertEqual(result["reason_codes"], ["operation_cancel_not_supported"])
            self.assertEqual(result["effects_state"], "none")
            self.assertEqual(result["files_written"], [])
            self.assertNotIn(private_marker, output)
            self.assertNotIn("compound_exact", output)
            argv[-1] = "text"
            code, output, errors = self.invoke(argv)
            self.assertEqual(code, 1)
            self.assertEqual(output, "")
            self.assertIn("cancel is unsupported", errors)
            self.assertNotIn("compound", errors)
            self.assertNotIn(private_marker, errors)

    def test_actual_read_actions_retain_complete_read_only_domain_results(self) -> None:
        # A missing synthetic journal is a real read-only domain outcome, not
        # a mocked success. Preserve its guidance/control fields and no writes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = "op:sha256:" + "a" * 64
            for action in ("status", "wait", "recovery-plan"):
                with self.subTest(action=action):
                    if action == "status":
                        expected = operation_control.inspect_operation(root, reference, action="status")
                    elif action == "wait":
                        expected = operation_control.wait_operation(root, reference, 60)
                    else:
                        expected = operation_control.recovery_plan(root, reference)
                    code, output, errors = self.invoke(self.argv(action, "--dry-run", str(root)))
                    self.assertEqual(json.loads(output), expected)
                    self.assertEqual(code, 0 if expected["ok"] else 1)
                    self.assertEqual(errors, "")
                    self.assertEqual(list(root.iterdir()), [])

    def test_schema_and_reader_keep_historical_documents_and_bind_new_reason(self) -> None:
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" /
                             "command-approval-status-inventory-v0.2.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(self.inventory)), [])
        legacy = copy.deepcopy(self.inventory)
        for row in legacy["commands"]:
            row.pop("approval_exposure_history", None)
            if row["canonical_path"] == "operation-control":
                row["approval_status"] = "approval_available"
                row["approval_reason_code"] = None
        self.assertEqual(list(validator.iter_errors(legacy)), [])
        command_status._validated_inventory_commands(legacy)
        for path, reason in (("operation-control", "PRIVATE_REASON"),
                             ("mint-zet", "operation_cancel_not_supported"),
                             ("operation-control", {"PRIVATE_REASON": True})):
            with self.subTest(path=path, reason_type=type(reason).__name__):
                changed = copy.deepcopy(self.inventory)
                row = next(row for row in changed["commands"] if row["canonical_path"] == path)
                row.update(approval_status="approval_fixed_closed", approval_reason_code=reason)
                self.assertTrue(list(validator.iter_errors(changed)))
                with self.assertRaisesRegex(ValueError, "^command_status_inventory_invalid$"):
                    command_status._validated_inventory_commands(changed)
