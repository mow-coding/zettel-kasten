from __future__ import annotations

import argparse
import copy
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import types
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, command_status


class InvocationEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def arguments(self, command: str, *extra: str) -> list[str]:
        required = {
            "staged-cleanup-check": ["--staged", "synthetic-stage"],
            "zet-catalog-pass": ["--output", "synthetic-catalog.jsonl"],
            "zet-catalog-pass-read": ["--input", "synthetic-catalog.jsonl"],
        }
        return [command, "synthetic-archive", *required.get(command, []), *extra]

    def resolve(self, command: str, *extra: str) -> dict[str, object]:
        namespace = self.parser.parse_args(self.arguments(command, *extra))
        return command_status.resolve_namespace_invocation_effects(
            self.parser, namespace
        )

    def effects(self, result: dict[str, object]) -> set[tuple[str, str]]:
        self.assertEqual(result["coverage"], "audited")
        return {(row["kind"], row["scope"]) for row in result["effects"]}

    def test_bounded_cohort_is_audited_without_claiming_execution_authority(self) -> None:
        for command in command_status._AUDITED_INVOCATION_OPTIONS:
            with self.subTest(command=command):
                leaf = command_status._subparser_actions(self.parser)[0].choices[command]
                flags = {flag for action in leaf._actions for flag in action.option_strings}
                extra = ["--dry-run"] if "--dry-run" in flags else []
                result = self.resolve(command, *extra)
                self.assertEqual(result["coverage"], "audited")
                self.assertEqual(result["intent"], "fresh")
                self.assertEqual(result["human_approval_requirement"], "not_required")
                for key in (
                    "session_requirement_evaluated", "lock_requirement_evaluated",
                    "intent_authority_verified", "prerequisites_evaluated",
                    "execution_authorized", "effects_performed", "private_values_echoed",
                ):
                    self.assertIs(result[key], False)

    def test_index_is_a_write_despite_no_native_approval_option(self) -> None:
        result = self.resolve("index")
        self.assertEqual(self.effects(result), {
            ("local_read", "archive"),
            ("generated_index_write", "archive_generated_index"),
        })
        inventory = archive_cli._parser_capability_inventory(self.parser)
        index = next(row for row in inventory["commands"] if row["canonical_path"] == "index")
        self.assertEqual(index["approval_status"], "approval_not_exposed")
        self.assertNotIn("effects", index)

    def test_output_adds_scratch_effect_and_only_audited_tracking(self) -> None:
        for command in sorted(command_status._AUDITED_SCRATCH_OUTPUT_COMMANDS):
            with self.subTest(command=command):
                mode = [] if command == "index" else ["--dry-run"]
                before = self.effects(self.resolve(command, *mode))
                after = self.effects(self.resolve(command, *mode, "--output", "private-result.json"))
                difference = {("private_artifact_write", "archive_scratch")}
                if command in {"index", "index-health", "staged-cleanup-check"}:
                    difference.add(("operational_metadata_write", "archive_operation_journal"))
                self.assertEqual(after - before, difference)

    def test_dry_run_catalogue_is_a_file_writer(self) -> None:
        self.assertEqual(self.effects(self.resolve("zet-catalog-pass", "--dry-run")), {
            ("local_read", "archive"),
            ("private_artifact_write", "archive_scratch"),
        })
        # Unlike optional --output, this required output is passed to the
        # writer unconditionally; validity of an empty path is a later check.
        self.assertIn(("private_artifact_write", "archive_scratch"), self.effects(
            self.resolve("zet-catalog-pass", "--dry-run", "--output=")
        ))

    def test_staged_deferred_input_uses_final_truthy_value_without_echo(self) -> None:
        private_input = "PRIVATE-DEFERRED-INPUT.json"
        for options, expected in (
            ([], False),
            (["--deferred", private_input], True),
            (["--deferred", private_input, "--deferred="], False),
            (["--deferred=", "--deferred", private_input], True),
        ):
            with self.subTest(selected=expected, option_count=len(options)):
                result = self.resolve("staged-cleanup-check", "--dry-run", *options)
                self.assertEqual(
                    ("local_read", "explicit_input_file") in self.effects(result),
                    expected,
                )
                self.assertNotIn(private_input, json.dumps(result) + repr(result))

    def test_staged_deferred_input_and_tracked_output_keep_separate_effects(self) -> None:
        options = ["--deferred=PRIVATE-DEFERRED-INPUT.json", "--output=PRIVATE-RESULT.json"]
        result = self.resolve("staged-cleanup-check", "--dry-run", *options)
        self.assertEqual(self.effects(result), {
            ("local_read", "archive"),
            ("local_read", "explicit_input_file"),
            ("private_artifact_write", "archive_scratch"),
            ("operational_metadata_write", "archive_operation_journal"),
        })
        self.assertNotIn("PRIVATE-", json.dumps(result) + repr(result))
        rejected = self.resolve("staged-cleanup-check", *options)
        self.assertEqual(rejected["entry_gate"], "required_dry_run_missing")
        self.assertEqual(rejected["effects"], [])

    def test_doctor_memory_cache_and_explicit_output_scopes_are_distinct(self) -> None:
        self.assertEqual(self.effects(self.resolve("doctor")), {("local_read", "archive")})
        result = self.resolve(
            "doctor", "--output", "private-result.json", "--no-progress",
            "--progress-log", "private-log.jsonl",
        )
        self.assertEqual(self.effects(result), {
            ("local_read", "archive"),
            ("private_artifact_write", "archive_relative_new_file"),
            ("operational_metadata_write", "outside_archive_new_file"),
        })
        # The handler uses `is not None`, not truthiness, for progress logs.
        self.assertIn(("operational_metadata_write", "outside_archive_new_file"),
                      self.effects(self.resolve("doctor", "--progress-log=")))

    def test_ordinary_local_reads_do_not_invent_provider_or_cache_writes(self) -> None:
        for command in ("index-health", "notion-objet-link-index",
                        "object-storage-upload-verify", "zet-catalog-pass-read"):
            with self.subTest(command=command):
                self.assertEqual(self.effects(self.resolve(command, "--dry-run")), {
                    ("local_read", "archive"),
                })

    def test_credential_verify_reads_only_existing_archive_authentication_key(self) -> None:
        self.assertEqual(self.effects(self.resolve("credential-secure-list")), {
            ("local_read", "archive"),
        })
        self.assertEqual(self.effects(self.resolve("credential-secure-list", "--verify")), {
            ("local_read", "archive"),
            ("credential_store_read", "archive_authentication_key"),
        })

    def test_known_early_dry_run_rejection_is_not_unknown_or_a_write(self) -> None:
        for command in command_status._AUDITED_INVOCATION_OPTIONS:
            leaf = command_status._subparser_actions(self.parser)[0].choices[command]
            if not any("--dry-run" in action.option_strings for action in leaf._actions):
                continue
            with self.subTest(command=command):
                result = self.resolve(command)
                self.assertEqual(result["coverage"], "audited")
                self.assertEqual(result["entry_gate"], "required_dry_run_missing")
                self.assertEqual(result["effects"], [])
                self.assertFalse(result["execution_authorized"])

    def test_alias_uses_canonical_parser_and_final_repeated_option_value(self) -> None:
        canonical = self.resolve("zet-catalog-pass", "--dry-run")
        namespace = self.parser.parse_args([
            "catalog-pass", "synthetic-archive", "--dry-run",
            "--output=synthetic-catalog.jsonl",
        ])
        self.assertEqual(command_status.resolve_namespace_invocation_effects(
            self.parser, namespace
        ), canonical)
        for command in ("index", "index-health", "ai-start-here", "doctor"):
            with self.subTest(command=command):
                mode = ["--dry-run"] if command in {"index-health", "ai-start-here"} else []
                empty_last = self.resolve(command, *mode, "--output=private-first.json", "--output=")
                full_last = self.resolve(command, *mode, "--output=", "--output=private-last.json")
                self.assertNotIn("private_artifact_write", {kind for kind, _ in self.effects(empty_last)})
                self.assertIn("private_artifact_write", {kind for kind, _ in self.effects(full_last)})

    def test_unaudited_commands_keep_unknown_effects_independent_of_approval(self) -> None:
        for argv in (
            ["create-draft", "synthetic-archive", "--approve"],
            ["create-draft", "synthetic-archive", "--dry-run"],
            ["version", "synthetic-archive"],
        ):
            with self.subTest(command=argv[0], mode=argv[-1]):
                result = command_status.resolve_namespace_invocation_effects(
                    self.parser, self.parser.parse_args(argv)
                )
                self.assertEqual(result["coverage"], "unknown")
                self.assertIsNone(result["effects"])
                self.assertEqual(result["human_approval_requirement"], "not_evaluated")
                self.assertEqual(result["intent"], "fresh")

    def test_resume_and_bootstrap_are_requests_not_unknown_effect_exemptions(self) -> None:
        for extra, intent in ((["--dry-run"], "bootstrap_candidate"), (["--resume"], "existing_resume")):
            with self.subTest(intent=intent):
                namespace = self.parser.parse_args([
                    "project-version-update", "synthetic-project", *extra,
                ])
                result = command_status.resolve_namespace_invocation_effects(self.parser, namespace)
                self.assertEqual(result["intent"], intent)
                self.assertEqual(result["coverage"], "unknown")
                self.assertIsNone(result["effects"])
                self.assertFalse(result["intent_authority_verified"])
                self.assertFalse(result["execution_authorized"])
        namespace = self.parser.parse_args(["index", "synthetic-archive"])
        namespace.resume = True  # not exposed by this leaf: cannot change intent
        namespace._wom_project_runtime_effect = "bootstrap_update"
        result = command_status.resolve_namespace_invocation_effects(self.parser, namespace)
        self.assertEqual(result["intent"], "fresh")

    def test_parser_or_handler_drift_invalidates_audited_coverage(self) -> None:
        parser = copy.deepcopy(self.parser)
        leaf = command_status._subparser_actions(parser)[0].choices["index"]
        leaf.add_argument("--repair", action="store_true")
        result = command_status.resolve_namespace_invocation_effects(
            parser, parser.parse_args(["index", "synthetic-archive", "--repair"])
        )
        self.assertEqual(result["reason_code"], "invocation_effect_parser_contract_changed")
        self.assertIsNone(result["effects"])
        namespace = self.parser.parse_args(["index", "synthetic-archive"])
        namespace.func = lambda _: self.fail("handler must never execute")
        result = command_status.resolve_namespace_invocation_effects(self.parser, namespace)
        self.assertEqual(result["coverage"], "unknown")
        self.assertIsNone(result["effects"])

    def test_same_real_handler_defined_by_module_entry_keeps_coverage(self) -> None:
        parser = copy.deepcopy(self.parser)
        leaf = command_status._subparser_actions(parser)[0].choices["index"]
        handler = leaf._defaults["func"]
        module_entry_handler = types.FunctionType(
            handler.__code__, {**handler.__globals__, "__name__": "__main__"},
            handler.__name__, handler.__defaults__, handler.__closure__,
        )
        leaf.set_defaults(func=module_entry_handler)
        namespace = parser.parse_args(["index", "synthetic-archive"])
        result = command_status.resolve_namespace_invocation_effects(parser, namespace)
        self.assertEqual(self.effects(result), self.effects(self.resolve("index")))

    def test_resolution_has_no_io_and_never_projects_private_values(self) -> None:
        marker = "PRIVATE-INVOCATION-MARKER"
        namespace = self.parser.parse_args([
            "ai-start-here", marker, "--dry-run", "--output", marker,
            "--expected-archive-id", marker,
        ])
        before = dict(vars(namespace))
        stdout, stderr = io.StringIO(), io.StringIO()
        with ExitStack() as stack, redirect_stdout(stdout), redirect_stderr(stderr):
            for target in ("builtins.open", "os.open", "os.stat", "os.lstat",
                           "socket.socket", "sqlite3.connect", "subprocess.Popen"):
                stack.enter_context(mock.patch(target, side_effect=AssertionError("effect resolver performed IO")))
            stack.enter_context(mock.patch.object(Path, "mkdir", side_effect=AssertionError("filesystem write")))
            stack.enter_context(mock.patch.object(archive_services, "ai_start_here", side_effect=AssertionError("handler called")))
            result = command_status.resolve_namespace_invocation_effects(self.parser, namespace)
        self.assertNotIn(marker, json.dumps(result) + repr(result) + stdout.getvalue() + stderr.getvalue())
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        self.assertEqual(vars(namespace), before)

    def test_private_unexpected_value_is_rejected_without_stringification(self) -> None:
        class PrivateValue:
            def __str__(self) -> str:
                raise AssertionError("private value stringified")

            def __bool__(self) -> bool:
                raise AssertionError("private value coerced")

        namespace = self.parser.parse_args(["index", "synthetic-archive"])
        namespace.output = PrivateValue()
        with self.assertRaisesRegex(ValueError, "^invocation_effect_namespace_value_invalid$") as caught:
            command_status.resolve_namespace_invocation_effects(self.parser, namespace)
        self.assertIsNone(caught.exception.__context__)

    def test_callers_cannot_mutate_later_effect_results(self) -> None:
        first = self.resolve("index")
        first["effects"][0]["kind"] = "private-poison"
        first["effects"].append({"kind": "extra", "scope": "private"})
        self.assertNotIn("private-poison", json.dumps(self.resolve("index")))
        self.assertEqual(len(self.resolve("index")["effects"]), 2)


if __name__ == "__main__":
    unittest.main()
