import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from wom_kit import archive_services as services, draft_revision
from . import test_feedback_171_172 as fixture


CHILD = '''
import sys
from wom_kit.operation_target_leases import TargetLeases
from wom_kit.exact_operation_manifest import exact_operation_writer_lock, ExactOperationManifestError
root,identity=sys.argv[1:]
try:
    with TargetLeases(root,[("zet",identity)],timeout_seconds=.1):
        raise AssertionError("same zet did not contend")
except ExactOperationManifestError as error:
    assert error.code == "exact_operation_writer_busy"
with TargetLeases(root,[("zet","zet_synthetic_unrelated")]), exact_operation_writer_lock(root):
    print("unrelated publication completed while same zet was busy")
'''


@unittest.skipUnless(os.name == "nt", "native draft publication")
class ZetConcurrencyTests(unittest.TestCase):
    setUp = fixture.DraftRevisionTests.setUp
    _run = fixture.DraftRevisionTests._run

    def test_same_zet_wait_does_not_block_other_publication_during_fidelity(self):
        code, planned = self._run("draft-revision-plan")
        self.assertEqual(code, 0)
        identity = services.require_readable_zettel_content(self.root / self.draft)[0]["id"]
        original = draft_revision.plan
        observed = []
        # The write-only invocation of plan runs after acquiring its zet lease.
        original_write = draft_revision.write
        def write(*args, **kwargs):
            def planning(*args, **kwargs):
                result = subprocess.run([sys.executable, "-c", CHILD, str(self.root), identity],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed.append(result.stdout)
                return original(*args, **kwargs)
            with patch.object(draft_revision, "plan", side_effect=planning):
                return original_write(*args, **kwargs)
        with patch.object(draft_revision, "write", side_effect=write):
            code, result = self._run("draft-revision-write", "--approve", "--reviewed-by", "person:synthetic",
                "--expected-plan-sha256", planned["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(len(observed), 1)
