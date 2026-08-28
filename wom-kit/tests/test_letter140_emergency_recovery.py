from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from jsonschema import Draft202012Validator

from wom_kit import archive_cli


class Letter140StructuredRootFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "cli-error-v0.1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.error_validator = Draft202012Validator(schema)

    def assert_cli_error_schema(self, payload: dict[str, object]) -> None:
        errors = sorted(
            self.error_validator.iter_errors(payload),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual(errors, [])

    def run_cli(self, values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    def assert_json_root_failure(
        self,
        command: str,
        *,
        lifecycle_action: str,
        reason_code: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing_root = Path(temporary) / "missing-private-root"
            code, stdout, stderr = self.run_cli(
                [command, str(missing_root), "--format", "json"]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assert_cli_error_schema(payload)
        self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(payload["status_class"], "blocked")
        self.assertEqual(payload["command"], command)
        self.assertEqual(payload["lifecycle_action"], lifecycle_action)
        self.assertEqual(payload["error_class"], "precondition")
        self.assertEqual(payload["reason_codes"], [reason_code])
        self.assertEqual(payload["exit_code"], code)
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)
        self.assertNotIn(str(missing_root), stdout)

    def test_facet_vocabulary_invalid_root_is_json(self) -> None:
        self.assert_json_root_failure(
            "facet-vocabulary",
            lifecycle_action="facet_vocabulary",
            reason_code="facet_vocabulary_unavailable",
        )

    def test_index_invalid_root_is_json(self) -> None:
        self.assert_json_root_failure(
            "index",
            lifecycle_action="index",
            reason_code="archive_root_invalid",
        )

    def test_text_mode_keeps_fixed_stderr_without_path_echo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing_root = Path(temporary) / "missing-private-root"
            code, stdout, stderr = self.run_cli(
                ["index", str(missing_root), "--format", "text"]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Archive root does not exist or is not a directory.\n",
        )
        self.assertNotIn(str(missing_root), stderr)

    def test_usage_error_uses_same_schema_with_exit_two(self) -> None:
        code, stdout, stderr = self.run_cli(
            ["facet-vocabulary", "--format", "json"]
        )

        self.assertEqual(code, 2)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assert_cli_error_schema(payload)
        self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["status_class"], "blocked")
        self.assertEqual(payload["command"], "facet-vocabulary")
        self.assertEqual(payload["lifecycle_action"], "cli_argument_validation")
        self.assertEqual(payload["error_class"], "usage")
        self.assertEqual(payload["exit_code"], code)
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)

    def test_link_approval_preconditions_fail_before_private_root_read(self) -> None:
        code, stdout, stderr = self.run_cli(
            [
                "zettel-objet-link",
                "private-root",
                "--zettel",
                "private-zettel",
                "--object-id",
                "sha256:" + "a" * 64,
                "--role",
                "source",
                "--approve",
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assert_cli_error_schema(payload)
        self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["status_class"], "blocked")
        self.assertEqual(payload["command"], "zettel-objet-link")
        self.assertEqual(payload["lifecycle_action"], "zettel_objet_link_apply")
        self.assertEqual(payload["error_class"], "precondition")
        self.assertEqual(
            payload["reason_codes"],
            ["zettel_objet_link_workflow_precondition_failed"],
        )
        self.assertEqual(payload["exit_code"], code)
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)
        self.assertNotIn("private-root", stdout)
        self.assertNotIn("private-zettel", stdout)

    def test_revert_remains_fixed_closed_with_policy_contract(self) -> None:
        code, stdout, stderr = self.run_cli(
            [
                "zettel-objet-link-revert",
                "private-root",
                "--receipt",
                "private-receipt.json",
                "--approve",
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assert_cli_error_schema(payload)
        self.assertEqual(payload["schema"], "wom-kit/cli-error/v0.1")
        self.assertEqual(payload["command"], "zettel-objet-link-revert")
        self.assertEqual(payload["error_class"], "policy")
        self.assertEqual(
            payload["reason_codes"],
            ["compound_exact_human_approval_binding_required"],
        )
        self.assertEqual(payload["effects_state"], "none")
        self.assertEqual(payload["files_written"], [])
        self.assertIs(payload["private_values_echoed"], False)
        self.assertNotIn("private-root", stdout)
        self.assertNotIn("private-receipt", stdout)

    def test_link_missing_mode_is_usage_exit_two_json(self) -> None:
        code, stdout, stderr = self.run_cli(
            [
                "zettel-objet-link",
                "private-root",
                "--zettel-id",
                "private-zettel",
                "--object-id",
                "sha256:" + "a" * 64,
                "--role",
                "source",
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 2)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assert_cli_error_schema(payload)
        self.assertEqual(payload["error_class"], "usage")
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(
            payload["reason_codes"],
            ["zettel_objet_link_mode_required"],
        )
        self.assertNotIn("private-root", stdout)
        self.assertNotIn("private-zettel", stdout)

    def test_link_parser_errors_are_content_free_for_canonical_and_alias(self) -> None:
        private_label = "PRIVATE_LETTER140_MALFORMED_LABEL"
        private_extra = "PRIVATE_LETTER140_UNRECOGNIZED_VALUE"
        for command in ("zettel-objet-link", "zet-objet-link"):
            for output_format in ("text", "json"):
                with self.subTest(command=command, output_format=output_format):
                    code, stdout, stderr = self.run_cli(
                        [
                            command,
                            "PRIVATE_LETTER140_ARCHIVE_ROOT",
                            "--zettel-id",
                            "PRIVATE_LETTER140_ZETTEL_ID",
                            "--object-id",
                            "sha256:" + "a" * 64,
                            "--role",
                            "source",
                            "--label",
                            private_label,
                            private_extra,
                            "--dry-run",
                            "--format",
                            output_format,
                        ]
                    )

                    self.assertEqual(code, 2)
                    combined = stdout + stderr
                    for private_value in (
                        private_label,
                        private_extra,
                        "PRIVATE_LETTER140_ARCHIVE_ROOT",
                        "PRIVATE_LETTER140_ZETTEL_ID",
                    ):
                        self.assertNotIn(private_value, combined)
                    if output_format == "text":
                        self.assertEqual(stdout, "")
                        self.assertEqual(
                            stderr,
                            "Command arguments are invalid; private argument "
                            "values were not echoed.\n",
                        )
                    else:
                        self.assertEqual(stderr, "")
                        payload = json.loads(stdout)
                        self.assert_cli_error_schema(payload)
                        self.assertEqual(payload["command"], command)
                        self.assertEqual(payload["error_class"], "usage")
                        self.assertEqual(payload["effects_state"], "none")
                        self.assertEqual(payload["files_written"], [])
                        self.assertIs(payload["private_values_echoed"], False)


if __name__ == "__main__":
    unittest.main()
