"""Pure mode matrix only; no registry, lock, native UI, or provider calls."""

from itertools import product
import json
import unittest

from wom_kit.work_session_command_modes import resolve_work_session_mode


FLAGS = ("dry_run", "approve", "apply", "resume", "review_original")
UNAVAILABLE = {
    "available": False,
    "mode": None,
    "read_only": None,
    "native_approval_required": False,
    "potential_write": False,
    "reason_code": "work_session_mode_unavailable",
}


class WorkSessionCommandModeTests(unittest.TestCase):
    def test_complete_boolean_matrix_has_only_the_twenty_nine_explicit_inputs(self):
        # This declarative oracle specifies every accepted input independently
        # of the classifier's branches, including query --dry-run equivalence.
        expected = {
            ("list", False, False, False, False, False): ("read_only_query", True, False),
            ("list", True, False, False, False, False): ("read_only_query", True, False),
            ("inspect", False, False, False, False, False): ("read_only_query", True, False),
            ("inspect", True, False, False, False, False): ("read_only_query", True, False),
            ("request-init", False, False, False, False, False): ("task_request_init", True, False),
            ("request-init", True, False, False, False, False): ("task_request_init", True, False),
            ("register-app", True, False, False, False, False): ("registration_preview", True, False),
            ("register-app", False, False, True, False, False): ("registration_apply", False, False),
            ("register-app", False, False, False, True, False): ("registration_resume", False, False),
            ("create", False, True, False, False, False): ("create", False, True),
            ("create", False, True, False, False, True): ("original_rereview", False, True),
            ("create", False, False, False, True, False): ("original_create_resume", False, False),
            ("claim", False, False, True, False, False): ("claim_apply", False, False),
            ("claim", False, False, False, True, False): ("claim_resume", False, False),
            ("pause", False, False, True, False, False): ("state_transition_apply", False, False),
            ("pause", False, False, False, True, False): ("original_state_transition_resume", False, False),
            ("resume", False, False, True, False, False): ("state_transition_apply", False, False),
            ("resume", False, False, False, True, False): ("original_state_transition_resume", False, False),
            ("complete", False, False, True, False, False): ("state_transition_apply", False, False),
            ("complete", False, False, False, True, False): ("original_state_transition_resume", False, False),
            ("accept", False, True, False, False, False): ("accept", False, True),
            ("accept", False, True, False, False, True): ("original_accept_rereview", False, True),
            ("accept", False, False, False, True, False): ("original_accept_resume", False, False),
            ("handoff", False, True, False, False, False): ("handoff", False, True),
            ("handoff", False, True, False, False, True): ("original_handoff_rereview", False, True),
            ("handoff", False, False, False, True, False): ("original_handoff_resume", False, False),
            ("recover", False, True, False, False, False): ("recover", False, True),
            ("recover", False, True, False, False, True): ("original_recover_rereview", False, True),
            ("recover", False, False, False, True, False): ("original_recover_resume", False, False),
        }
        observed_available = set()
        for action in ("list", "inspect", "request-init", "register-app", "create", "claim", "pause", "resume", "complete", "handoff", "accept", "recover"):
            for values in product((False, True), repeat=len(FLAGS)):
                key = (action, *values)
                with self.subTest(action=action, flags=values):
                    result = resolve_work_session_mode(action=action, **dict(zip(FLAGS, values)))
                    if key not in expected:
                        self.assertEqual(result, UNAVAILABLE)
                        continue
                    observed_available.add(key)
                    mode, read_only, native = expected[key]
                    self.assertEqual(result, {
                        "available": True,
                        "mode": mode,
                        "read_only": read_only,
                        "native_approval_required": native,
                        "potential_write": not read_only,
                        "reason_code": None,
                    })
        self.assertEqual(observed_available, set(expected))

    def test_defaults_are_queries_only_and_create_dry_run_is_not_invented(self):
        self.assertTrue(resolve_work_session_mode(action="list")["read_only"])
        self.assertTrue(resolve_work_session_mode(action="inspect")["read_only"])
        self.assertEqual(resolve_work_session_mode(action="request-init"), {
            "available": True, "mode": "task_request_init", "read_only": True,
            "native_approval_required": False, "potential_write": False, "reason_code": None,
        })
        for action in ("register-app", "create", "claim", "pause", "resume", "complete", "handoff", "accept", "recover"):
            self.assertEqual(resolve_work_session_mode(action=action), UNAVAILABLE)
        self.assertEqual(resolve_work_session_mode(action="create", dry_run=True), UNAVAILABLE)

    def test_future_unknown_alias_and_private_actions_are_fixed_unavailable(self):
        for action in ("register_app", "LIST", " create ", "", "PRIVATE_ACTION_DO_NOT_ECHO"):
            for values in product((False, True), repeat=len(FLAGS)):
                result = resolve_work_session_mode(action=action, **dict(zip(FLAGS, values)))
                self.assertEqual(result, UNAVAILABLE)
                self.assertNotIn("PRIVATE_ACTION", json.dumps(result))

    def test_flags_are_exact_bools_and_do_not_evaluate_private_objects(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("must_not_evaluate")

            def __eq__(self, other):
                raise AssertionError("must_not_compare")

            def __repr__(self):
                raise AssertionError("must_not_render")

        for flag in FLAGS:
            for value in (0, 1, None, "true", [], {}, Hostile()):
                result = resolve_work_session_mode(action="create", **{flag: value})
                self.assertEqual(result, UNAVAILABLE)
        for action in (None, True, 1, [], {}, Hostile()):
            self.assertEqual(resolve_work_session_mode(action=action), UNAVAILABLE)

    def test_str_subclasses_are_not_used_as_action_authority(self):
        class CustomAction(str):
            def __eq__(self, other):
                raise AssertionError("must_not_compare")

            def __hash__(self):
                raise AssertionError("must_not_hash")

        self.assertEqual(resolve_work_session_mode(action=CustomAction("create"), approve=True), UNAVAILABLE)

    def test_resume_never_requests_new_native_approval(self):
        for action in ("register-app", "create", "claim", "pause", "resume", "complete", "handoff", "accept", "recover"):
            result = resolve_work_session_mode(action=action, resume=True)
            self.assertTrue(result["available"])
            self.assertFalse(result["native_approval_required"])
            self.assertFalse(result["read_only"])
            self.assertTrue(result["potential_write"])
            self.assertEqual(resolve_work_session_mode(action=action, resume=True, approve=True), UNAVAILABLE)

    def test_every_result_is_detached_and_unavailable_is_not_read_only(self):
        first = resolve_work_session_mode(action="create", approve=True)
        first["mode"] = "PRIVATE_VALUE"
        self.assertEqual(resolve_work_session_mode(action="create", approve=True)["mode"], "create")
        first = resolve_work_session_mode(action="unsupported")
        first["available"] = True
        self.assertEqual(resolve_work_session_mode(action="unsupported"), UNAVAILABLE)
        self.assertIsNone(resolve_work_session_mode(action="unsupported")["read_only"])


if __name__ == "__main__":
    unittest.main()
