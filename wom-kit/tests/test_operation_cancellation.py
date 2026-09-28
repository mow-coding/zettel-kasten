import json
import signal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import operation_control as control, operation_cancellation as cancel


class Keys:
    def use_key(self, root, consumer, **kwargs):
        return consumer(memoryview(b"s" * 32))


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = control.OperationRunJournal.prepare(self.root,
            command="object-storage-cleanup", run_id="c" * 32,
            output_relative=".wom-scratch/diagnostics/cleanup.json")
        self.addCleanup(self.journal.close)
        self.keys = Keys()

    def request(self):
        cancel._save(self.root, self.journal.journal_path.with_suffix(".cancel.json"),
                     cancel._binding(vars(self.journal)), self.keys)

    def test_request_is_not_acknowledgement_until_checkpoint(self):
        self.request()
        state = cancel.state(self.root, self.journal.journal_path, vars(self.journal), self.keys)
        self.assertTrue(state["cancel_requested"])
        self.assertFalse(state["cancel_acknowledged"])
        with cancel.observing(self.journal, provider=self.keys):
            with self.assertRaises(cancel.OperationCancelled):
                cancel.checkpoint()
        self.assertTrue(cancel.state(self.root, self.journal.journal_path, vars(self.journal), self.keys)["cancel_acknowledged"])

    def test_tampered_request_does_not_become_acknowledged(self):
        self.request()
        path = self.journal.journal_path.with_suffix(".cancel.json")
        value = json.loads(path.read_bytes())
        value["document"]["control_digest"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with cancel.observing(self.journal, provider=self.keys):
            with self.assertRaises(ValueError):
                cancel.checkpoint()
        self.assertFalse(self.journal.journal_path.with_suffix(".cancel-ack.json").exists())

    def test_different_execution_does_not_consume_request(self):
        self.request()
        second = control.OperationRunJournal.prepare(self.root,
            command="object-storage-cleanup", run_id="d" * 32,
            output_relative=".wom-scratch/diagnostics/second.json")
        try:
            with cancel.observing(second, provider=self.keys):
                cancel.checkpoint()
            self.assertFalse(second.journal_path.with_suffix(".cancel-ack.json").exists())
        finally:
            second.close()

    def test_ctrl_c_defers_stop_until_current_effect_is_recorded(self):
        previous = signal.getsignal(signal.SIGINT)
        effects = []
        with cancel.observing(self.journal, provider=self.keys):
            signal.raise_signal(signal.SIGINT)
            # Signal delivery itself must not interrupt an unknown write result.
            effects.append("current_effect_confirmed_and_recorded")
            self.assertFalse(self.journal.journal_path.with_suffix(".cancel-ack.json").exists())
            with self.assertRaises(cancel.OperationCancelled):
                cancel.checkpoint()
        self.assertEqual(effects, ["current_effect_confirmed_and_recorded"])
        self.assertIs(signal.getsignal(signal.SIGINT), previous)
        state = cancel.state(self.root, self.journal.journal_path, vars(self.journal), self.keys)
        self.assertEqual(state["cancellation_state"], "acknowledged_at_checkpoint")

    def test_status_does_not_confuse_acknowledgement_with_terminal(self):
        self.request()
        with cancel.observing(self.journal, provider=self.keys):
            with self.assertRaises(cancel.OperationCancelled):
                cancel.checkpoint()
        with patch("wom_kit.exact_human_approval_workflow._production_key_provider", return_value=self.keys):
            result = control.inspect_operation(self.root, self.journal.operation_ref)
        self.assertTrue(result["control"]["cancel_acknowledged"])
        self.assertFalse(result["control"]["cancellation_completed"])


if __name__ == "__main__":
    unittest.main()
