"""A separate official CLI process can write during scoped intake approval/copy."""
import json
import subprocess
import sys
import time
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


def run_child(root, label):
    # The archive lock itself refuses after 30 seconds. Allow interpreter and
    # CLI startup too; holding A's lock still makes B fail, never pass this test.
    started = time.monotonic()
    try:
        result = subprocess.run([sys.executable, "-c", CHILD, str(root), label],
            capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(json.dumps({"child_stage": label, "failure": "timeout", "seconds": time.monotonic()-started}), file=sys.__stderr__, flush=True)
        raise
    if result.returncode:
        # Synthetic fixture only; scrub its exact path from diagnostic stderr.
        stderr = result.stderr.replace(str(root.parent), "<synthetic-parent>")
        print(json.dumps({"child_stage": label, "returncode": result.returncode,
            "stderr": stderr[-2500:], "seconds": time.monotonic()-started}), file=sys.__stderr__, flush=True)
    print(json.dumps({"child_stage": label, "completed": result.returncode == 0,
        "seconds": time.monotonic()-started}), file=sys.__stderr__, flush=True)
    return result


class ScopedCopyConcurrencyTests(unittest.TestCase):
    setUp = fixture.PublicSessionSourceIntakeJourneyTests.setUp
    call = fixture.PublicSessionSourceIntakeJourneyTests.call
    session_command = fixture.PublicSessionSourceIntakeJourneyTests.session_command

    def test_separate_writer_finishes_during_approval_copy_and_completion_hashing(self):
        source = self.fixture.workspace / "synthetic-concurrent-external.bin"
        source.write_bytes(b"synthetic source" * 8192)
        self.request.write_text(json.dumps({"schema": intake.REQUEST_SCHEMA, "batch_id": "parallel-copy",
            "items": [{"item_id": "one", "local_path": str(source), "source_role": "primary_source"}]}), encoding="utf-8")
        observed = []
        def child(stage):
            result = run_child(self.root, "synthetic-" + stage)
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
        original_verify = intake.verify_exact_operation
        def verify(*args, **kwargs):
            if kwargs.get("state") == "post" and "completion" not in observed:
                child("completion")
            return original_verify(*args, **kwargs)
        with patch.object(external, "copy_approved", side_effect=copy), \
                patch.object(intake, "verify_exact_operation", side_effect=verify):
            result = self.call("source-intake-batch", *self.refs, "--work-session-ref", self.session,
                "--manifest", str(self.request), "--stage-external", "--approve", "--reviewed-by", "person:synthetic")
        self.assertTrue(result["ok"], result)
        self.assertEqual(observed, ["approval", "copy", "completion"])
        self.assertEqual(source.read_bytes(), b"synthetic source" * 8192)


class ScopedRecordConcurrencyTests(unittest.TestCase):
    def test_metadata_approval_wait_does_not_hold_archive_writer(self):
        from . import test_v0420_source_intake_record_public_workflow as record_fixture
        case = record_fixture.PublicSingleRecordJourneyTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        native = case.fixture.native
        original = native.show
        completed = []
        def show(**kwargs):
            child = run_child(case.root, "synthetic-record-wait")
            self.assertEqual(child.returncode, 0, child.stderr)
            completed.append(child.stdout)
            return original(**kwargs)
        native.show = show
        result = case.cli()
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(completed), 1)
