from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKER_PATH = KIT_ROOT / "tools" / "check_public_privacy.py"

spec = importlib.util.spec_from_file_location("check_public_privacy", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_public_privacy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_public_privacy
spec.loader.exec_module(check_public_privacy)


class PublicPrivacyHygieneTests(unittest.TestCase):
    def assert_problem_code(self, problems, code: str) -> None:
        self.assertIn(code, {problem.code for problem in problems})

    def init_repo(self, repo_root: Path) -> None:
        repo_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_full_checker_passes_current_repository(self) -> None:
        problems = check_public_privacy.check_public_privacy(REPO_ROOT)
        self.assertEqual([problem.format() for problem in problems], [])

    def test_git_listing_scans_forced_tracked_ignored_records_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            (repo_root / ".gitignore").write_text(
                "meeting-minutes/\narchive-infra-decision-log-*.md\n",
                encoding="utf-8",
            )
            meeting_minutes = repo_root / "meeting-minutes"
            meeting_minutes.mkdir()
            tracked_minute = meeting_minutes / "tracked-record.md"
            ignored_local_minute = meeting_minutes / "local-record.md"
            tracked_decision = repo_root / "archive-infra-decision-log-tracked.md"
            ignored_local_decision = repo_root / "archive-infra-decision-log-local.md"
            synthetic_home = "C:" + "\\Users\\" + "private-person" + "\\Documents\\archive"
            for path in (
                tracked_minute,
                ignored_local_minute,
                tracked_decision,
                ignored_local_decision,
            ):
                path.write_text(synthetic_home, encoding="utf-8")

            subprocess.run(
                [
                    "git",
                    "add",
                    "--force",
                    tracked_minute.relative_to(repo_root).as_posix(),
                    tracked_decision.relative_to(repo_root).as_posix(),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            problems = check_public_privacy.check_public_privacy(repo_root)
            problem_paths = {problem.file for problem in problems}
            self.assertEqual(
                problem_paths,
                {
                    "archive-infra-decision-log-tracked.md",
                    "meeting-minutes/tracked-record.md",
                },
            )

    def test_windows_user_path_with_non_placeholder_user_fails(self) -> None:
        text = "C:" + "\\Users\\" + "private-person" + "\\Documents\\dev\\zettel-kasten"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assert_problem_code(problems, "PRIV001")

    def test_windows_example_user_path_is_allowed(self) -> None:
        text = "C:" + "\\Users\\example\\dev\\zettel-kasten"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assertEqual(problems, [])

    def test_posix_home_paths_fail_for_non_placeholder_users(self) -> None:
        examples = [
            "/Users/" + "private-person" + "/dev/zettel-kasten",
            "/home/" + "private-person" + "/dev/zettel-kasten",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assert_problem_code(problems, "PRIV002")

    def test_token_like_strings_fail(self) -> None:
        examples = [
            ("ghp_" + ("A" * 32), "PRIV003"),
            ("github_pat_" + ("B" * 32), "PRIV004"),
            ("sk-" + ("C" * 32), "PRIV005"),
            ("AK" + "IA" + "D7F2H9J4L6N8P3R5", "PRIV006"),
            ("AWS_SECRET_ACCESS_KEY=" + ("E" * 40), "PRIV007"),
            ('{"aws_' + 'secret_access_key":"' + ("F" * 40) + '"}', "PRIV007"),
        ]
        for text, code in examples:
            with self.subTest(code=code):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assert_problem_code(problems, code)

    def test_placeholder_token_examples_are_allowed(self) -> None:
        examples = [
            "ghp_" + "EXAMPLE" + ("0" * 33),
            "github" + "_pat_" + "EXAMPLE" + ("0" * 33),
            "sk-" + "EXAMPLE" + ("0" * 33),
            "AK" + "IA" + "EXAMPLE" + ("0" * 9),
            "AWS_SECRET_ACCESS_KEY=" + "EXAMPLE" + ("0" * 33),
        ]
        for text in examples:
            with self.subTest(text=text[:12]):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assertEqual(problems, [])

    def test_private_key_block_header_fails(self) -> None:
        text = "BEGIN " + "RSA PRIVATE KEY"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assert_problem_code(problems, "PRIV008")

    def test_seed_phrase_text_fails_unless_placeholder_only(self) -> None:
        bad = "seed " + "phrase: alpha beta gamma delta epsilon zeta eta theta"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=bad)
        self.assert_problem_code(problems, "PRIV009")

        ok = "seed " + "phrase: <never put a real seed phrase here>"
        self.assertEqual(check_public_privacy.check_text_for_privacy(path="docs/example.md", text=ok), [])

        phrase_value = "mne" + "mon" + "ic" + ": alpha beta gamma delta epsilon zeta"
        self.assert_problem_code(
            check_public_privacy.check_text_for_privacy(path="docs/example.md", text=phrase_value), "PRIV009"
        )

        recovery = "recovery " + "phrase: alpha beta gamma delta epsilon zeta"
        self.assert_problem_code(
            check_public_privacy.check_text_for_privacy(path="docs/example.md", text=recovery), "PRIV009"
        )

    def test_private_local_provider_urls_fail(self) -> None:
        prefix = "http" + "://"
        examples = [
            prefix + "localhost:3000/private",
            prefix + "localhost:8000/api",
            prefix + "127.0.0.1:8080/private",
            prefix + "127.0.0.1:8000/api",
            prefix + "192.168.1.10/private",
            prefix + "192.168.1.5/provider",
            prefix + "10.0.0.5/private",
            prefix + "172.16.0.3/private",
            prefix + "172.31.255.254/private",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assert_problem_code(problems, "PRIV010")

    def test_placeholder_local_provider_urls_are_allowed(self) -> None:
        prefix = "http" + "://"
        examples = [
            prefix + "localhost:<port>/api",
            prefix + "<host>:<port>/api",
            prefix + "example.localhost:<port>/api",
            prefix + "localhost:8000/example-only",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assertEqual(problems, [])

    def test_credential_bearing_urls_fail_without_echoing_userinfo(self) -> None:
        examples = [
            "https" + "://user:password@example.com/private",
            "https" + "://token@example.com/private",
            "http" + "://admin:secret@192.168.1.5/provider",
        ]
        for text in examples:
            with self.subTest(text=text.split("@", 1)[-1]):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assert_problem_code(problems, "PRIV011")
                formatted = "\n".join(problem.format() for problem in problems)
                self.assertNotIn("password", formatted)
                self.assertNotIn("secret", formatted)

    def test_findings_never_retain_or_format_matched_values(self) -> None:
        github_value = "ghp_" + "R7Q2W9E4T6Y8U3I5O1P0L2K4J6H8G0F2"
        seed_words = "amber birch cedar drift ember frost grove harbor ivory juniper"
        text = github_value + "\nseed " + "phrase: " + seed_words
        problems = check_public_privacy.check_text_for_privacy(path="docs/leaks.md", text=text)

        self.assertEqual({problem.code for problem in problems}, {"PRIV003", "PRIV009"})
        formatted = "\n".join(problem.format() for problem in problems)
        for forbidden in (github_value, github_value[-12:], seed_words, "amber", "juniper"):
            self.assertNotIn(forbidden, formatted)

    def test_cli_detects_adversarial_tokens_without_echoing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            self.init_repo(repo_root)
            docs = repo_root / "docs"
            docs.mkdir()
            github_value = "ghp_" + "Q7W8E9R0T1Y2U3I4O5P6A7S8D9F0G1H2"
            openai_value = "sk-" + "N7M6B5V4C3X2Z1L0K9J8H7G6F5D4S3A2"
            aws_access_value = "AK" + "IA" + "Q7W8E9R0T1Y2U3I4"
            aws_secret_value = "R7tY9uI1oP3aS5dF7gH9jK2lZ4xC6vB8nM0qW2eR"
            seed_words = "acorn beacon canyon dune elm fern glacier hazel inlet jasper"
            leak_file = docs / "leaks.md"
            leak_file.write_text(
                "\n".join(
                    (
                        github_value,
                        openai_value,
                        aws_access_value,
                        "AWS_SECRET_ACCESS_KEY=" + aws_secret_value,
                        "recovery " + "phrase: " + seed_words,
                    )
                ),
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "docs/leaks.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            result = subprocess.run(
                [sys.executable, str(CHECKER_PATH), "--repo-root", str(repo_root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            combined = result.stdout + result.stderr
            for code in ("PRIV003", "PRIV005", "PRIV006", "PRIV007", "PRIV009"):
                self.assertIn("code=" + code, combined)
            for forbidden in (
                github_value,
                github_value[-12:],
                openai_value,
                openai_value[-12:],
                aws_access_value,
                aws_secret_value,
                aws_secret_value[-12:],
                seed_words,
                "acorn",
                "jasper",
            ):
                self.assertNotIn(forbidden, combined)
            self.assertNotIn("text:", combined)

    def test_sensitive_filename_is_redacted_from_finding_output(self) -> None:
        sensitive_name = "ghp_" + "Z9X8C7V6B5N4M3L2K1J0H9G8F7D6S5A4"
        display = check_public_privacy.safe_display_path("docs/" + sensitive_name + ".md")
        self.assertEqual(display, "<redacted-path>")
        self.assertNotIn(sensitive_name[-12:], display)

    def test_unicode_bidi_and_format_controls_are_redacted_from_output_paths(self) -> None:
        for codepoint in (0x202E, 0x2066, 0x2069, 0x200B):
            with self.subTest(codepoint=hex(codepoint)):
                control = chr(codepoint)
                path = "docs/report" + control + "safe.md"
                display = check_public_privacy.safe_display_path(path)
                formatted = check_public_privacy.PrivacyProblem(path, "PRIV012").format()
                self.assertEqual(display, "<redacted-path>")
                self.assertNotIn(control, formatted)
                self.assertIn("path=<redacted-path>", formatted)

    def test_sensitive_tracked_filename_is_detected_and_never_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            sensitive_name = "ghp_" + "T9R8E7W6Q5P4O3I2U1Y0A9S8D7F6G5H4"
            sensitive_path = repo_root / (sensitive_name + ".md")
            sensitive_path.write_text("safe content", encoding="utf-8")
            subprocess.run(
                ["git", "add", sensitive_path.name],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV003")
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertIn("path=<redacted-path>", formatted)
            self.assertNotIn(sensitive_name, formatted)
            self.assertNotIn(sensitive_name[-12:], formatted)

    def test_tracked_file_replaced_by_symlink_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            repo_root = base / "repo"
            self.init_repo(repo_root)
            docs = repo_root / "docs"
            docs.mkdir()
            tracked_path = docs / "linked.md"
            tracked_path.write_text("safe text", encoding="utf-8")
            subprocess.run(
                ["git", "add", "docs/linked.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            external_value = "ghp_" + "L9K8J7H6G5F4D3S2A1P0O9I8U7Y6T5R4"
            external_path = base / "outside.md"
            external_path.write_text(external_value, encoding="utf-8")
            tracked_path.unlink()
            try:
                tracked_path.symlink_to(external_path)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable on this platform: {type(exc).__name__}")

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV012")
            self.assertNotIn("PRIV003", {problem.code for problem in problems})
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertNotIn(external_value, formatted)
            self.assertNotIn(external_value[-12:], formatted)

    def test_tracked_file_beneath_reparse_or_symlink_directory_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            repo_root = base / "repo"
            self.init_repo(repo_root)
            docs = repo_root / "docs"
            docs.mkdir()
            tracked_path = docs / "linked.md"
            tracked_path.write_text("safe text", encoding="utf-8")
            subprocess.run(
                ["git", "add", "docs/linked.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            external_value = "sk-" + "J8H7G6F5D4S3A2P1O0I9U8Y7T6R5E4W3"
            outside_dir = base / "outside"
            outside_dir.mkdir()
            (outside_dir / "linked.md").write_text(external_value, encoding="utf-8")
            tracked_path.unlink()
            docs.rmdir()
            try:
                if sys.platform == "win32":
                    link_result = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(docs), str(outside_dir)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if link_result.returncode != 0:
                        self.skipTest("directory junctions are unavailable on this platform")
                else:
                    docs.symlink_to(outside_dir, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory links are unavailable on this platform: {type(exc).__name__}")

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV012")
            self.assertNotIn("PRIV005", {problem.code for problem in problems})
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertNotIn(external_value, formatted)
            self.assertNotIn(external_value[-12:], formatted)

    def test_staged_secret_is_detected_when_worktree_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            tracked_path = repo_root / "deleted.md"
            tracked_path.write_text("ghp_" + ("Q" * 32), encoding="utf-8")
            subprocess.run(
                ["git", "add", "deleted.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            tracked_path.unlink()

            self.assert_problem_code(check_public_privacy.check_public_privacy(repo_root), "PRIV003")

    def test_staged_secret_is_detected_when_worktree_file_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            tracked_path = repo_root / "staged.md"
            staged_value = "sk-" + "V8C7X6Z5L4K3J2H1G0F9D8S7A6P5O4I3"
            tracked_path.write_text(staged_value, encoding="utf-8")
            subprocess.run(
                ["git", "add", "staged.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            tracked_path.write_text("safe replacement", encoding="utf-8")

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV005")
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertNotIn(staged_value, formatted)
            self.assertNotIn(staged_value[-12:], formatted)

    def test_forced_tracked_dotenv_is_scanned_without_suffix_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            (repo_root / ".gitignore").write_text(".env\n", encoding="utf-8")
            dotenv = repo_root / ".env"
            token_value = "ghp_" + "C8V7B6N5M4L3K2J1H0G9F8D7S6A5P4O3"
            dotenv.write_text("TOKEN=" + token_value, encoding="utf-8")
            subprocess.run(
                ["git", "add", "--force", ".env"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV003")
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertNotIn(token_value, formatted)
            self.assertNotIn(token_value[-12:], formatted)

    def test_tracked_binary_blob_is_bounded_and_scanned_for_ascii_token_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            token_value = "ghp_" + "M8N7B6V5C4X3Z2L1K0J9H8G7F6D5S4A3"
            binary_path = repo_root / "artifact.bin"
            binary_path.write_bytes(b"\x00\x01prefix\x00" + token_value.encode("ascii") + b"\x00suffix")
            subprocess.run(
                ["git", "add", "artifact.bin"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            problems = check_public_privacy.check_public_privacy(repo_root)
            self.assert_problem_code(problems, "PRIV003")
            formatted = "\n".join(problem.format() for problem in problems)
            self.assertNotIn(token_value, formatted)
            self.assertNotIn(token_value[-12:], formatted)

    def test_index_blob_size_limit_fails_closed_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            staged_path = repo_root / "bounded.bin"
            staged_path.write_bytes(b"123456789")
            subprocess.run(
                ["git", "add", "bounded.bin"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            with mock.patch.object(check_public_privacy, "MAX_SINGLE_FILE_BYTES", 8):
                problems = check_public_privacy.check_public_privacy(repo_root)

            self.assertEqual([problem.code for problem in problems], ["PRIV017"])
            self.assertNotIn("123456789", problems[0].format())

    def test_git_subprocess_stdout_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(check_public_privacy.PrivacyScanError):
                check_public_privacy._run_bounded_process(
                    [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*4096)"],
                    cwd=Path(temp_dir),
                    payload=None,
                    max_stdout=8,
                    timeout_seconds=5,
                )

    def test_git_subprocess_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(check_public_privacy.PrivacyScanError):
                check_public_privacy._run_bounded_process(
                    [sys.executable, "-c", "import time;time.sleep(10)"],
                    cwd=Path(temp_dir),
                    payload=None,
                    max_stdout=8,
                    timeout_seconds=0.1,
                )

    def test_cat_file_calls_use_metadata_and_body_specific_output_caps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            content = b"safe bytes\n"
            tracked_path = repo_root / "bounded.txt"
            tracked_path.write_bytes(content)
            subprocess.run(
                ["git", "add", "bounded.txt"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            calls: list[tuple[tuple[str, ...], int]] = []
            original = check_public_privacy._run_bounded_process

            def recording_runner(command, **kwargs):
                calls.append((tuple(command), kwargs["max_stdout"]))
                return original(command, **kwargs)

            with mock.patch.object(check_public_privacy, "_run_bounded_process", side_effect=recording_runner):
                problems = check_public_privacy.check_public_privacy(repo_root)

            self.assertEqual(problems, [])
            batch_check_limits = [
                limit for command, limit in calls if any(argument.startswith("--batch-check=") for argument in command)
            ]
            batch_body_limits = [limit for command, limit in calls if command[-1] == "--batch"]
            self.assertEqual(batch_check_limits, [check_public_privacy.MAX_BATCH_CHECK_LINE_BYTES])
            self.assertEqual(
                batch_body_limits,
                [len(content) + check_public_privacy.MAX_BATCH_RESPONSE_OVERHEAD_BYTES],
            )

    def test_index_snapshot_drift_fails_closed_after_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self.init_repo(repo_root)
            tracked_path = repo_root / "stable.md"
            tracked_path.write_text("safe", encoding="utf-8")
            subprocess.run(
                ["git", "add", "stable.md"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            initial_entries = check_public_privacy.list_git_entries(repo_root)
            tracked_entry = next(entry for entry in initial_entries if entry.tracked)
            drifted_entry = check_public_privacy.GitPathEntry(
                path="late.md",
                tracked=True,
                mode=tracked_entry.mode,
                object_id=tracked_entry.object_id,
                stage=0,
            )

            with mock.patch.object(
                check_public_privacy,
                "list_git_entries",
                side_effect=[initial_entries, [*initial_entries, drifted_entry]],
            ):
                problems = check_public_privacy.check_public_privacy(repo_root)

            self.assertEqual([problem.code for problem in problems], ["PRIV020"])
            self.assertEqual(problems[0].format(), "code=PRIV020 type=index_snapshot_drift count=1 path=.")

    def test_placeholder_credential_bearing_urls_are_allowed(self) -> None:
        examples = [
            "https" + "://<user>:<password>@example.invalid/path",
            "https" + "://example:EXAMPLE@example.invalid/path",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assertEqual(problems, [])

    def test_example_invalid_url_is_allowed(self) -> None:
        text = "https://example.invalid/provider"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assertEqual(problems, [])

    def test_checker_source_has_no_network_or_provider_edit_behavior(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        banned = (
            "req" + "uests",
            "urllib" + ".request",
            "http" + ".client",
            "url" + "open",
            "provider" + "_api",
            "gh " + "release",
        )
        for needle in banned:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
