"""Same-key original absence admission, using the existing real claim codec."""

from contextlib import contextmanager
from dataclasses import replace
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import test_exact_human_approval_workflow as fixtures
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as subject
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, ExactHumanApprovalIntent


class OriginalReviewBrokerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExactHumanApprovalWorkflowTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root, self.context = self.fixture.root, self.fixture.context
        self.key = fixtures._KeyProvider()
        self.native = fixtures._Native((APPROVE_BUTTON_ID, True))

    @contextmanager
    def boundary(self):
        root = self.root.resolve()
        with archive_services._activity_group_bound_directory_chain(
                root, root / approval.CLAIMS_RELATIVE_ROOT, create=True) as parent:
            yield root, parent

    def claims(self):
        directory = self.root / approval.CLAIMS_RELATIVE_ROOT
        return {p.name: p.read_bytes() for p in directory.glob("*.json")}

    def create_claim(self, *, status="started", context=None, key=None):
        context = context or self.context
        decision = subject._request_exact_human_approval_core(context,
            intent=ExactHumanApprovalIntent.live_write,
            native=fixtures._Native((APPROVE_BUTTON_ID, True)))
        with self.boundary() as (root, parent):
            claim = subject._claim_exact_human_approval_core(root, context, decision,
                key if key is not None else memoryview(bytearray(range(32))),
                bound_archive_root=root, claim_parent_binding=parent)
            try:
                if status == "succeeded":
                    claim.finalize_succeeded()
                elif status == "failed":
                    claim.finalize_failed("synthetic_failure")
                return claim.public_reference()
            finally:
                claim.close()

    def test_fresh_default_signature_and_bytes_route_do_not_call_absence_scanner(self):
        parameters = inspect.signature(subject._execute_exact_human_approved_write_core).parameters
        self.assertEqual(set(parameters), {"archive_root", "context", "writer", "native", "key_provider",
            "post_decision_boundary", "claim_publication_boundary", "claim_succeeded_finalizer",
            "target_collection", "observe_target_binding", "session_permission"})
        with patch.object(subject, "_authenticated_resume_candidates_with_key_core",
                          side_effect=AssertionError("fresh must not scan")):
            result = subject._execute_exact_human_approved_write_core(self.root, self.context,
                lambda _claim: {"ok": True}, native=self.native, key_provider=self.key)
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(self.key.create_if_missing, [True])

    def test_shared_scanner_retains_both_statuses_and_unrelated_context_exclusion(self):
        first = self.create_claim()
        other = replace(self.context, reviewer_claim="person:other-original")
        self.create_claim(status="failed", context=other)
        with self.boundary() as boundary:
            found = subject._authenticated_resume_candidates_with_key_core(self.root, self.context,
                lambda _claim: True, lambda _claim: True,
                key=memoryview(bytearray(range(32))), filesystem_boundary=boundary)
        self.assertEqual(found, (first["approval_id"],))
        second = self.create_claim(status="succeeded")
        with self.boundary() as boundary:
            found = subject._authenticated_resume_candidates_with_key_core(self.root, self.context,
                lambda _claim: True, lambda _claim: True,
                key=memoryview(bytearray(range(32))), filesystem_boundary=boundary)
        self.assertEqual(set(found), {first["approval_id"], second["approval_id"]})

    def test_present_failed_corrupt_and_ambiguous_are_not_original_absence(self):
        for status in ("started", "succeeded", "failed", "corrupt", "ambiguous"):
            with self.subTest(status=status):
                # Distinct exact contexts keep unrelated valid claims in scope
                # for the shared scanner without making them candidates.
                other = replace(self.context, reviewer_claim="person:" + status)
                reference = self.create_claim(status=status if status in {"started", "succeeded", "failed"} else "started",
                                              context=other)
                if status == "corrupt":
                    path = self.root / approval.CLAIMS_RELATIVE_ROOT / (reference["approval_id"] + ".json")
                    authenticated_bytes = path.read_bytes()
                    path.write_bytes(b"{}")
                if status == "ambiguous":
                    self.create_claim(context=other)
                before = self.claims()
                with self.assertRaises(subject.ExactHumanApprovalWorkflowError), \
                     patch.object(subject, "_claim_exact_human_approval_core", side_effect=AssertionError("second claim")):
                    subject._execute_exact_human_approved_original_review_core(self.root, other,
                        lambda _claim: self.fail("writer entered"), native=self.native,
                        key_provider=self.key, post_decision_boundary=self.boundary)
                self.assertEqual(self.claims(), before)
                if status == "corrupt":
                    # Restore the test-owned authenticated bytes so later cases
                    # can distinguish ambiguous from unrelated corrupt state.
                    path.write_bytes(authenticated_bytes)

    def test_provider_entry_insertion_is_seen_by_same_key_before_second_claim(self):
        owner = self

        class InsertingKey(fixtures._KeyProvider):
            def use_key(self, root, consumer, *, create_if_missing=False):
                def entered(key):
                    owner.create_claim(key=key)
                    return consumer(key)
                return super().use_key(root, entered, create_if_missing=create_if_missing)

        key = InsertingKey()
        with self.assertRaises(subject.ExactHumanApprovalWorkflowError) as caught:
            subject._execute_exact_human_approved_original_review_core(self.root, self.context,
                lambda _claim: self.fail("writer entered"), native=self.native, key_provider=key,
                post_decision_boundary=self.boundary)
        self.assertEqual(caught.exception.code, "exact_human_approval_resume_claim_invalid")
        self.assertEqual(len(self.claims()), 1)
        self.assertEqual(key.calls, 1)
        self.assertEqual(key.create_if_missing, [False])
        self.assertEqual(self.native.calls, 1)

    def test_original_missing_key_does_not_generate_key_claim_or_enter_writer(self):
        generated, requested = [], []

        class MissingKey:
            def use_key(self, root, consumer, *, create_if_missing=False):
                requested.append(create_if_missing)
                if create_if_missing:
                    generated.append(True)
                raise RuntimeError("SYNTHETIC_PRIVATE_KEY_MISSING")

        with patch.object(subject, "_claim_exact_human_approval_core", side_effect=AssertionError("claim")):
            with self.assertRaises(subject.ExactHumanApprovalWorkflowError) as caught:
                subject._execute_exact_human_approved_original_review_core(self.root, self.context,
                    lambda _claim: self.fail("writer"), native=self.native, key_provider=MissingKey(),
                    post_decision_boundary=self.boundary)
        self.assertEqual(caught.exception.code, "exact_human_approval_key_unavailable")
        self.assertEqual(requested, [False])
        self.assertEqual(generated, [])
        self.assertEqual(self.claims(), {})

    def test_absent_original_publishes_after_guards_and_scans_once_without_nested_provider(self):
        order = []
        scanner = subject._authenticated_resume_candidates_with_key_core

        @contextmanager
        def publication():
            order.append("publication")
            yield

        def scan(*args, **kwargs):
            order.append("scan")
            return scanner(*args, **kwargs)

        def write(claim):
            order.append("writer")
            claim.assert_ready_for_context(self.context)
            return {"ok": True}

        with patch.object(subject, "_authenticated_resume_candidates_with_key_core", side_effect=scan):
            result = subject._execute_exact_human_approved_original_review_core(self.root, self.context,
                write, native=self.native, key_provider=self.key, post_decision_boundary=self.boundary,
                claim_publication_boundary=publication)
        self.assertEqual(order, ["publication", "scan", "writer"])
        self.assertEqual(self.key.calls, 1)
        self.assertEqual(self.key.create_if_missing, [False])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
