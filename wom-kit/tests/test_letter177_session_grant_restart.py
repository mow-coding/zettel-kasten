"""Beta letter 177 (2026-09-30): a session grant survives the calling process, like the desktop apps.

The owner's 2026-09-25 decision: a grant lasts until it is released in that
session. Codex and Claude desktop keep such approvals as a durable record in
the user's account, keyed to the project or conversation; restarting the app
or starting a new process never resets them. The beta tester approved
allow_all, the calling process ended, and the same conversation's next process
got the native dialog again (work_session_presenter_missing). These tests
reproduce that: a new process that presents only this conversation's three
session refs uses the recorded grant without a dialog; another conversation's
route still gets the dialog; the claims still say which process used the grant.

Synthetic archives and the injected dialog and key of the v0.4.20 fixture only.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from wom_kit import presenter_fingerprint
from wom_kit import work_session_permission as permission

import test_v0424_session_permission_modes as _permission_fixture


def _basis(tag: str) -> dict:
    return {"schema": presenter_fingerprint.FINGERPRINT_SCHEMA, "image_basename": "synthetic.exe",
            "pid": 5000 + len(tag), "creation_time": 200 + len(tag)}


class SessionGrantSurvivesProcessTests(unittest.TestCase):
    # Helpers only; inheriting the fixture class would rerun its own tests.
    _Base = _permission_fixture.SessionPermissionModeTests
    setUp = _Base.setUp
    call = _Base.call
    session_call = _Base.session_call
    establish = _Base.establish
    routing = _Base.routing
    draft_call = _Base.draft_call
    manifested_source = _Base.manifested_source
    draft_flags = _Base.draft_flags
    approve_flags = _Base.approve_flags
    set_mode = _Base.set_mode
    presenter_env = _Base.presenter_env
    index = _Base.index
    env = _Base.env

    def restarted_env(self, task):
        """A new process of the same conversation: the three refs, no presenter secret."""

        permission.release_presenter(task["session"])
        return {"WOM_CLIENT_APP_REF": task["app"], "WOM_TASK_ROUTE_REF": task["route"],
                "WOM_WORK_SESSION_REF": task["session"]}

    def test_new_process_of_the_same_conversation_uses_the_grant_without_a_dialog(self) -> None:
        task = self.establish("restart")
        self.set_mode(task, "allow_all")
        env = self.restarted_env(task)
        refs = dict(client_app_ref=task["app"], task_route_ref=task["route"], work_session_ref=task["session"])
        # the process that approved is gone: nothing presents the old secret
        grant, reason = permission.resolve_grant_outcome(self.root, presenter=None, **refs)
        self.assertIsNotNone(grant, reason)
        self.assertIsNone(reason)
        self.assertEqual(grant.mode, "allow_all")
        self.assertIsNone(grant.expires_at)
        # a write from the new process: no dialog, the claim records the mechanism
        object_id = self.manifested_source(b"letter 177 restarted process source\n")
        self.index()
        flags = self.draft_flags(object_id, "Draft after the approving process ended")
        preview = self.draft_call(*flags, "--dry-run")
        dialogs = self.native.calls
        clean = {name: value for name, value in os.environ.items() if name != permission.PRESENTER_ENV}
        with patch.dict(os.environ, {**clean, **env}, clear=True), \
                patch.object(presenter_fingerprint, "observe", return_value=_basis("restarted")):
            written = self.draft_call(*flags, *self.approve_flags(preview))
        self.assertEqual(self.native.calls, dialogs, written)
        self.assertNotIn("session_permission_refused", written)
        self.assertFalse(written["exact_human_approval"]["live_dialog_shown"])

    def test_caller_status_in_a_new_process_reports_the_grant_usable(self) -> None:
        task = self.establish("caller")
        self.set_mode(task, "allow_all")
        env = self.restarted_env(task)
        clean = {name: value for name, value in os.environ.items() if name != permission.PRESENTER_ENV}
        with patch.dict(os.environ, {**clean, **env}, clear=True):
            status = self.call("work-session", "--action", "inspect", "--caller-status")
        caller = status["caller_status"]["caller"] if "caller_status" in status else status["caller"]
        self.assertTrue(caller["can_use_recorded_grant"], caller)
        self.assertIsNone(caller["reason_code"])
        self.assertEqual(caller["recovery_steps"], [])

    def test_another_conversation_route_and_a_released_grant_still_get_the_dialog(self) -> None:
        task = self.establish("boundary")
        self.set_mode(task, "allow_all")
        self.restarted_env(task)
        other = self.establish("other-conversation")
        # another conversation's route cannot name this session's grant
        grant, reason = permission.resolve_grant_outcome(
            self.root, client_app_ref=other["app"], task_route_ref=other["route"],
            work_session_ref=task["session"], presenter=None)
        self.assertIsNone(grant)
        self.assertEqual(reason, "work_session_grant_unavailable")
        # releasing the grant (manual) is the only thing that ends it
        self.set_mode(task, "manual")
        grant, reason = permission.resolve_grant_outcome(
            self.root, client_app_ref=task["app"], task_route_ref=task["route"],
            work_session_ref=task["session"], presenter=None)
        self.assertIsNone(grant)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
