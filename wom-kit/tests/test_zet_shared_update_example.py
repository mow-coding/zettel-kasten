from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any


KIT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = KIT_ROOT / "examples" / "zet-shared-update-record" / "shared-update.example.json"


def iter_items(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key, nested
            yield from iter_items(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_items(nested)


class SharedUpdateExampleTests(unittest.TestCase):
    def test_example_is_dry_run_body_free_and_non_mutating(self) -> None:
        data = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

        self.assertTrue(data["dry_run"])
        self.assertFalse(data["body_included"])

        for key, value in iter_items(data):
            if key.endswith(("_performed", "_created")):
                self.assertIs(value, False, key)

    def test_example_contains_no_private_paths_urls_or_token_like_values(self) -> None:
        serialized = EXAMPLE_PATH.read_text(encoding="utf-8")

        unsafe_patterns = [
            re.compile(r"[A-Za-z]:[\\/]"),
            re.compile(r"/(?:Users|home)/"),
            re.compile(r"https?://"),
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        ]
        for pattern in unsafe_patterns:
            self.assertIsNone(pattern.search(serialized), pattern.pattern)

        for token_prefix in ("gh" + "p_", "github_" + "pat_", "sk" + "-"):
            self.assertNotIn(token_prefix, serialized)
        self.assertNotIn("BEGIN " + "PRIVATE KEY", serialized)


if __name__ == "__main__":
    unittest.main()
