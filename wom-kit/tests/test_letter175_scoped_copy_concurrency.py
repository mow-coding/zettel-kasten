"""A separate official CLI process can write during scoped intake approval/copy."""
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from wom_kit import source_intake_external as external, source_intake_batch_exact as intake
from . import test_v0420_source_intake_session_public_workflow as fixture

CHILD = '''
import io,json,sys
from contextlib import redirect_stdout
from wom_kit import archive_cli
root,label=sys.argv[1:]
def call(mode,request):
    output=io.StringIO()
    sys.stdin=io.StringIO(json.dumps(request))
    with redirect_stdout(output):
        code=archive_cli.main(["work-session",root,"--action","register-app",mode,"--request-stdin","--format","json","--no-progress"])
    result=json.loads(output.getvalue())
    if code: raise RuntimeError(result)
    return result["result"]
preview=call("--dry-run",{"label":label})
call("--apply",{"label":label,"selection":preview})
print("official unrelated registration completed")
'''


class ScopedCopyConcurrencyTests(unittest.TestCase):
    setUp = fixture.PublicSessionSourceIntakeJourneyTests.setUp
    call = fixture.PublicSessionSourceIntakeJourneyTests.call
    session_command = fixture.PublicSessionSourceIntakeJourneyTests.session_command

    def test_separate_writer_finishes_before_approval_and_copy_return(self):
        source = self.fixture.workspace / "synthetic-concurrent-external.bin"
        source.write_bytes(b"synthetic source" * 8192)
        self.request.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA, "batch_id": "parallel-copy",
            "items": [{"item_id": "one", "local_path": str(source), "source_role": "primary_source"}]}), encoding="utf-8")
        observed = []
        def child(stage):
            result = subprocess.run([sys.executable, "-c", CHILD, str(self.root), "synthetic-" + stage],
                capture_output=True, text=True, timeout=12)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("official unrelated registration completed", result.stdout)
            observed.append(stage)
        show = self.native.show
        def approved(**kwargs):
            child("approval")
            return show(**kwargs)
        self.native.show = approved
        original = external.copy_approved
        def copy(plan, item, *, heartbeat):
            child("copy")
            return original(plan, item, heartbeat=heartbeat)
        with patch.object(external, "copy_approved", side_effect=copy):
            result = self.call("source-intake-batch", *self.refs, "--work-session-ref", self.session,
                "--manifest", str(self.request), "--stage-external", "--approve", "--reviewed-by", "person:synthetic")
        self.assertTrue(result["ok"], result)
        self.assertEqual(observed, ["approval", "copy"])
        self.assertEqual(source.read_bytes(), b"synthetic source" * 8192)
