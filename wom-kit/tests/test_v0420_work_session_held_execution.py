"""One archive lock composes actor discovery and original approval/resume."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_registry as registry
import test_v0420_work_session_execution as fixture


class HeldSessionExecutionTests(unittest.TestCase):
    def setUp(self):
        fixture.SessionExecutionTests.setUp(self)

    def execute_held(self, held):
        return execution._execute_session_decision_held(
            self.root, held=held, action="create", client_app_ref=self.app,
            label="Synthetic held work", reviewer_claim="person:synthetic-session-reviewer",
            native=self.native, key_provider=self.key,
        )

    def test_real_decision_and_completed_resume_use_same_lock_without_reentry(self):
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            execution, "wait_for_archive_writer", side_effect=AssertionError("no nested lock"),
        ):
            result = self.execute_held(held)
            self.assertTrue(result["ok"])
            self.assertTrue(result["independent_post_verification"])
            plans = list(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
            self.assertEqual(len(plans), 1)
            generation = self.store.read().sha256
            resumed = execution._resume_session_decision_held(
                self.root, held=held, manifest_sha256="sha256:" + plans[0].stem,
                key_provider=self.key,
            )
            self.assertTrue(resumed["ok"])
            self.assertEqual(resumed["execution_sha256"], result["execution_sha256"])
            self.assertEqual(resumed["receipt_sha256"], result["receipt_sha256"])
            self.assertEqual(self.store.read().sha256, generation)
            held.verify_held()
        self.assertEqual(self.native.calls, 1)

    def test_unheld_and_foreign_lock_fail_before_plan_native_or_claim(self):
        with tempfile.TemporaryDirectory(prefix="wom-held-foreign-") as temporary:
            foreign = Path(temporary)
            with exact.ExactOperationWriterLock(foreign) as foreign_held:
                candidates = (None, object(), exact.ExactOperationWriterLock(self.root), foreign_held)
                original = self.store.read().sha256
                for candidate in candidates:
                    with self.subTest(lock_type=type(candidate).__name__), patch.object(
                        registry, "plan_transition", side_effect=AssertionError("must reject before plan"),
                    ), patch.object(
                        bundle, "load_context_bound_session_decision",
                        side_effect=AssertionError("must reject before resume payload"),
                    ):
                        with self.assertRaises(registry.WorkSessionRegistryError):
                            self.execute_held(candidate)
                        with self.assertRaises(registry.WorkSessionRegistryError):
                            execution._resume_session_decision_held(
                                self.root, held=candidate, manifest_sha256="sha256:" + "0" * 64,
                                key_provider=self.key,
                            )
                self.assertEqual(self.store.read().sha256, original)
        self.assertEqual(self.native.calls, 0)
        self.assertFalse(self.root.joinpath(*bundle.PRIVATE_ROOT).exists())

    def test_released_lock_cannot_open_native_or_resume(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()
        with self.assertRaises(registry.WorkSessionRegistryError):
            self.execute_held(held)
        with self.assertRaises(registry.WorkSessionRegistryError):
            execution._resume_session_decision_held(
                self.root, held=held, manifest_sha256="sha256:" + "0" * 64, key_provider=self.key,
            )
        self.assertEqual(self.native.calls, 0)


if __name__ == "__main__":
    unittest.main()
