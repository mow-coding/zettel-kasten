from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wom_kit import archive_cli, duplicate_object_reconciliation


class IntegrityProgressTruthTests(unittest.TestCase):
    def test_duplicate_cli_starts_before_slow_plan_and_heartbeats_content_free(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            root.mkdir()
            (root / "archive.yml").write_text(
                "archive_id: archive:test:v048-progress-truth\n",
                encoding="utf-8",
            )
            private_marker = "private-duplicate-progress-marker"
            digest = "a" * 64
            row = {
                "object_id": "sha256:" + digest,
                "sha256": digest,
                "logical_key": "private/duplicate/progress/path",
                "mime": "text/plain",
                "size_bytes": 1,
                "locations": [],
                "provenance": {"private_marker": private_marker},
            }
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            encoded = json.dumps(row, separators=(",", ":")) + "\n"
            manifest.write_text(encoded + encoded, encoding="utf-8")

            original_reporter = archive_cli.CommandProgressReporter
            original_plan = (
                duplicate_object_reconciliation
                ._plan_duplicate_object_reconciliation_core
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            planner_observed_start = False

            def fast_reporter(enabled, **kwargs):
                kwargs["heartbeat_interval_seconds"] = 0.01
                return original_reporter(enabled, **kwargs)

            def slow_plan(*args, **kwargs):
                nonlocal planner_observed_start
                planner_observed_start = "duplicate-plan: start" in stderr.getvalue()
                deadline = time.monotonic() + 1.0
                while (
                    "duplicate-plan: heartbeat" not in stderr.getvalue()
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.005)
                return original_plan(*args, **kwargs)

            with (
                mock.patch.object(
                    archive_cli,
                    "CommandProgressReporter",
                    side_effect=fast_reporter,
                ),
                mock.patch.object(
                    duplicate_object_reconciliation,
                    "_plan_duplicate_object_reconciliation_core",
                    side_effect=slow_plan,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = archive_cli.main(
                    [
                        "duplicate-object-reconcile",
                        str(root),
                        "--dry-run",
                        "--progress",
                        "--format",
                        "json",
                    ]
                )

            progress = stderr.getvalue()
            self.assertEqual(code, 0, progress)
            self.assertTrue(planner_observed_start, progress)
            self.assertIn("duplicate-plan: start", progress)
            self.assertIn("duplicate-plan: heartbeat", progress)
            self.assertLess(
                progress.index("duplicate-plan: start"),
                progress.index("duplicate-plan: heartbeat"),
            )
            for forbidden in (
                str(root),
                private_marker,
                "private/duplicate/progress/path",
                "sha256:" + digest,
            ):
                self.assertNotIn(forbidden, progress)


if __name__ == "__main__":
    unittest.main()
