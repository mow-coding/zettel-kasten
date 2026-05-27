from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKER_PATH = KIT_ROOT / "tools" / "check_public_privacy.py"

spec = importlib.util.spec_from_file_location("check_public_privacy", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_public_privacy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_public_privacy
spec.loader.exec_module(check_public_privacy)


class PublicPrivacyHygieneTests(unittest.TestCase):
    def assert_problem_contains(self, problems, needle: str) -> None:
        formatted = "\n".join(problem.format() for problem in problems)
        self.assertIn(needle, formatted)

    def test_full_checker_passes_current_repository(self) -> None:
        problems = check_public_privacy.check_public_privacy(REPO_ROOT)
        self.assertEqual([problem.format() for problem in problems], [])

    def test_windows_user_path_with_non_placeholder_user_fails(self) -> None:
        text = "C:" + "\\Users\\" + "private-person" + "\\Documents\\dev\\zettel-kasten"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assert_problem_contains(problems, "Local Windows user-home path")

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
                self.assert_problem_contains(problems, "user-home path")

    def test_token_like_strings_fail(self) -> None:
        examples = [
            "ghp_" + ("A" * 32),
            "github_pat_" + ("B" * 32),
            "sk-" + ("C" * 32),
        ]
        for text in examples:
            with self.subTest(text=text[:10]):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assert_problem_contains(problems, "pattern")

    def test_placeholder_token_examples_are_allowed(self) -> None:
        examples = [
            "ghp_" + "EXAMPLE" + ("0" * 33),
            "github" + "_pat_" + "EXAMPLE" + ("0" * 33),
            "sk-" + "EXAMPLE" + ("0" * 33),
        ]
        for text in examples:
            with self.subTest(text=text[:12]):
                problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
                self.assertEqual(problems, [])

    def test_private_key_block_header_fails(self) -> None:
        text = "BEGIN " + "RSA PRIVATE KEY"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=text)
        self.assert_problem_contains(problems, "Private key block header")

    def test_seed_phrase_text_fails_unless_placeholder_only(self) -> None:
        bad = "seed " + "phrase: alpha beta gamma delta epsilon zeta eta theta"
        problems = check_public_privacy.check_text_for_privacy(path="docs/example.md", text=bad)
        self.assert_problem_contains(problems, "Seed phrase")

        ok = "seed " + "phrase: <never put a real seed phrase here>"
        self.assertEqual(check_public_privacy.check_text_for_privacy(path="docs/example.md", text=ok), [])

        phrase_value = "mne" + "mon" + "ic" + ": alpha beta gamma delta epsilon zeta"
        self.assert_problem_contains(
            check_public_privacy.check_text_for_privacy(path="docs/example.md", text=phrase_value),
            "Seed phrase",
        )

        recovery = "recovery " + "phrase: alpha beta gamma delta epsilon zeta"
        self.assert_problem_contains(
            check_public_privacy.check_text_for_privacy(path="docs/example.md", text=recovery),
            "Seed phrase",
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
                self.assert_problem_contains(problems, "Private/local provider URL")

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
                self.assert_problem_contains(problems, "Credential-bearing URL")
                formatted = "\n".join(problem.format() for problem in problems)
                self.assertNotIn("password", formatted)
                self.assertNotIn("secret", formatted)

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
