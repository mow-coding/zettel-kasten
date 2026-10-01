"""Synthetic current-caller diagnostics through the real session CLI."""
import json
import os
import unittest
from unittest.mock import patch

from wom_kit import work_session_permission as permission
from . import test_v0424_session_permission_modes as fixture_module


class CallerStatusTests(unittest.TestCase):
    setUp = fixture_module.SessionPermissionModeTests.setUp
    call = fixture_module.SessionPermissionModeTests.call
    session_call = fixture_module.SessionPermissionModeTests.session_call
    establish = fixture_module.SessionPermissionModeTests.establish
    routing = fixture_module.SessionPermissionModeTests.routing
    set_mode = fixture_module.SessionPermissionModeTests.set_mode
    env = fixture_module.SessionPermissionModeTests.env
    presenter_env = fixture_module.SessionPermissionModeTests.presenter_env

    def diagnose(self, *, ref=None, ok=True):
        with patch("wom_kit.work_session_caller_status.runtime_status", return_value={"consistency_state": "test"}):
            return self.call("work-session", "--action", "inspect", "--caller-status",
                             *([] if ref is None else ["--ref", ref]), ok=ok)

    def test_live_caller_missing_presenter_and_other_conversation_are_distinct(self):
        first = self.establish("first")
        second = self.establish("second")
        self.set_mode(first, "allow_all")
        self.set_mode(second, "allow_all")
        dialogs = self.native.calls
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.dict(os.environ, self.env(first)):
            result = self.diagnose()["caller_status"]
            self.assertTrue(result["caller"]["can_use_recorded_grant"])
            self.assertEqual(result["recorded_permission"]["mode"], "allow_all")
            self.assertEqual(result["execution"]["state"], "not_observed")
            self.assertIsNone(first["presenter"])  # v0.4.55: no secret is returned
            other = self.diagnose(ref=second["session"])["caller_status"]
            self.assertFalse(other["caller"]["can_use_recorded_grant"])
            self.assertEqual(other["caller"]["reason_code"], "work_session_caller_session_mismatch")
        # v0.4.55 (letter 177): a new process of the same conversation without
        # any presenter secret still uses the recorded grant.
        with patch.dict(os.environ, {**self.env(first), permission.PRESENTER_ENV: ""}):
            restarted = self.diagnose()["caller_status"]
            self.assertTrue(restarted["caller"]["can_use_recorded_grant"])
            self.assertIsNone(restarted["caller"]["reason_code"])
            self.assertEqual(restarted["recorded_permission"]["mode"], "allow_all")
            self.assertFalse(restarted["caller"]["grant_expired"])
            self.assertEqual(restarted["caller"]["recovery_steps"], [])
        self.assertEqual(self.native.calls, dialogs)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_no_context_does_not_select_another_registered_grant(self):
        task = self.establish("context")
        self.set_mode(task, "allow_all")
        with patch.dict(os.environ, dict.fromkeys(permission.CONTEXT_ENV, "")):
            result = self.diagnose(ok=False)
            self.assertEqual(result["reason_code"], "work_session_caller_context_missing")
            self.assertEqual(result["context"]["state"], "missing")
            self.assertFalse(result["context"]["missing_context_proves_grant_expired"])
            self.assertIn("request-init", result["recovery_steps"][0]["if_original_context_unavailable"])
        with patch.dict(os.environ, {**dict.fromkeys(permission.CONTEXT_ENV, ""), permission.CONTEXT_ENV[0]: "private-invalid-value"}):
            result = self.diagnose(ok=False)
            self.assertEqual(result["context"]["state"], "incomplete")
            self.assertNotIn("private-invalid-value", json.dumps(result))

    def test_caller_flag_is_inspect_only(self):
        result = self.call("work-session", "--action", "list", "--caller-status", ok=False)
        self.assertEqual(result["reason_code"], "work_session_query_invalid")


if __name__ == "__main__":
    unittest.main()
