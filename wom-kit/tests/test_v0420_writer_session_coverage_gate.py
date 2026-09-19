"""The writer-session coverage gate compares the real parser with the manifest."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT_ROOT / "tools"))

import check_writer_session_coverage as subject  # noqa: E402


class WriterSessionCoverageGateTests(unittest.TestCase):
    def test_manifest_matches_parser_and_denominator_stays_honest(self):
        problems, counts = subject.check()
        self.assertEqual(problems, [])
        self.assertEqual(sum(counts.values()), 59)  # v0.4.21 reopened eight writers + intake chain; v0.4.28 restore; v0.4.29 offload; v0.4.30 claim finalize
        self.assertGreaterEqual(counts["session_integrated"], 5)
        self.assertEqual(counts["routed"], 1)
        self.assertGreater(counts["pending"], 0)  # all-writer scope is not complete yet
        self.assertEqual(subject.main(["--format", "text"]), 0)

    def test_unclassified_stale_and_misclassified_paths_block(self):
        manifest = json.loads(subject.MANIFEST.read_text(encoding="utf-8"))
        paths = manifest["paths"]
        del paths["create-draft"]
        paths["synthetic-retired-command"] = {"status": "pending", "target": "v0.4.21"}
        paths["work-session"] = {"status": "pending", "target": "v0.4.21"}
        paths["mint-zet"] = {"status": "session_integrated", "evidence": ["test_missing_module"]}
        # v0.4.23: create-draft exposes session refs itself; route through a
        # pending native writer that still has none.
        paths["zet-title-remap-revert"]["route"] = "promote"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            problems, _counts = subject.check(path)
            self.assertNotEqual(subject.main(["--manifest", str(path), "--format", "json"]), 0)
        joined = "\n".join(problems)
        self.assertIn("not classified: create-draft", joined)
        self.assertIn("no longer approval-available: synthetic-retired-command", joined)
        self.assertIn("work-session: marked pending but already exposes session refs", joined)
        self.assertIn("mint-zet: session_integrated but mint-zet exposes no session refs", joined)
        self.assertIn("evidence test module missing: test_missing_module", joined)
        self.assertIn("zet-title-remap-revert: session_integrated but promote exposes no session refs", joined)
        self.assertIn("route promote is not itself session_integrated", joined)
        self.assertNotEqual(subject.main(["--manifest", str(path.with_name("absent.json")), "--format", "json"]), 0)


if __name__ == "__main__":
    unittest.main()
