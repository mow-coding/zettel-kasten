"""Audited effects feed the existing runtime guard without closing plain reads."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli, command_status


class InvocationEffectDispatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-invocation-effects-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.parser = archive_cli.build_parser()

    def arguments(self, command, *extra):
        return [command, str(self.root), *extra]

    def blocked_runtime(self):
        return {"blocked": True, "reason_code": "project_runtime_mismatch",
                "project_runtime_argv": archive_cli.project_runtime.project_runtime_argv(),
                "private_values_echoed": False}

    def guard(self, argv):
        args = self.parser.parse_args(argv)
        args._wom_invocation_effects = command_status.resolve_namespace_invocation_effects(self.parser, args)
        blocker = self.blocked_runtime()
        with patch.object(archive_cli.project_runtime, "project_write_guard", return_value=blocker) as gate:
            result = archive_cli._project_write_runtime_guard(args, argv)
        return result, gate.call_count

    def test_optional_output_is_runtime_guarded_but_plain_reads_are_unchanged(self):
        cases = (
            ("doctor", [], ["--output", "synthetic-diagnostic.json"]),
            ("doctor", [], ["--progress-log", "synthetic-progress.jsonl"]),
            ("ai-start-here", ["--dry-run"], ["--output", "synthetic-start.json"]),
            ("index-health", ["--dry-run"], ["--output", "synthetic-index.json"]),
            ("upgrade-check", ["--dry-run"], ["--output", "synthetic-upgrade.json"]),
        )
        for command, base, output in cases:
            with self.subTest(command=command, option=output[0]):
                self.assertEqual(self.guard(self.arguments(command, *base)), (None, 0))
                result, calls = self.guard(self.arguments(command, *base, *output))
                self.assertIsNotNone(result)
                self.assertEqual(calls, 1)

    def test_index_and_required_catalog_output_still_require_runtime_alignment(self):
        for argv in (self.arguments("index"), self.arguments("zet-catalog-pass", "--dry-run", "--output", "pass.jsonl")):
            with self.subTest(command=argv[0]):
                result, calls = self.guard(argv)
                self.assertIsNotNone(result)
                self.assertEqual(calls, 1)

    def test_missing_dry_run_does_not_turn_early_refusal_into_runtime_work(self):
        self.assertEqual(self.guard(self.arguments("index-health", "--output", "synthetic.json")), (None, 0))

    def test_unknown_effects_preserve_explicit_write_guard_instead_of_read_only_fallback(self):
        argv = self.arguments("index")
        args = self.parser.parse_args(argv)
        args._wom_invocation_effects = {"coverage": "unknown", "effects": None}
        with patch.object(archive_cli.project_runtime, "project_write_guard", return_value=self.blocked_runtime()) as gate:
            self.assertIsNotNone(archive_cli._project_write_runtime_guard(args, argv))
        self.assertEqual(gate.call_count, 1)

    def test_actual_dispatch_blocks_output_before_domain_or_journal_and_attaches_fixed_effects(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        blocker = self.blocked_runtime()
        observed = []
        original_guard = archive_cli._project_write_runtime_guard

        def observe(args, raw):
            observed.append(args._wom_invocation_effects)
            return original_guard(args, raw)

        with patch.object(archive_cli, "_project_write_runtime_guard", side_effect=observe), patch.object(
            archive_cli.project_runtime, "project_write_guard", return_value=blocker,
        ), patch.object(archive_cli.archive_services, "index_health", side_effect=AssertionError("domain reached")), redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(self.arguments("index-health", "--dry-run", "--output", "PRIVATE_RESULT.json", "--format", "json"))
        self.assertEqual(code, 3)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["reason_codes"], ["project_runtime_mismatch"])
        self.assertEqual(result["lifecycle_action"], "project_runtime_guard")
        self.assertEqual(result["effects_state"], "none")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(observed[0]["coverage"], "audited")
        self.assertNotIn("PRIVATE_RESULT", json.dumps(observed))
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
