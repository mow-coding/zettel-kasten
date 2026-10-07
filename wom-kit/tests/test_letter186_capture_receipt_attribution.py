"""Beta letter 186: a real objet-capture receipt names its approval one level deeper.

The v0.4.67 route `object-storage-scope-list --approval-id` found the
customer's succeeded capture approval but attributed none of its 21 objects:
"approvals_with_no_valid_capture_receipt_count: 1". Cause: a real capture
receipt carries the operation approval receipt, whose reference is nested
(`exact_human_approval.exact_human_approval.approval_id`), while the selector
read `exact_human_approval.approval_id` and found nothing. The same reader
served the session selector since v0.4.5x, so no real capture receipt was ever
attributed by session either; the earlier tests used a flat synthetic shape.

Since v0.4.68 the nested reference is read, every rejection is counted by a
fixed reason, and this module proves it with receipts and claims produced by
the real objet-capture-batch writer (window approval, no session mark).
"""
import json
import os
import unittest
from unittest import mock
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import objet_capture_batch_exact
from wom_kit import object_storage_scope as scope

import test_v0410_objet_capture_batch_exact as capture_fixture


class _ListingKeyProvider(capture_fixture._KeyProvider):
    """The writer's key, also usable by read-only listings (create_if_missing=False)."""

    @staticmethod
    def assert_create(value: bool) -> None:
        pass


class RealCaptureReceiptTests(capture_fixture.ObjetCaptureBatchExactTests):
    def capture(self, count, batch_id):
        request, execution = self._request(count, batch_id=batch_id)
        native, keys = capture_fixture._Native(approved=True), _ListingKeyProvider()
        with mock.patch.object(objet_capture_batch_exact, "_execute_exact_human_approved_write",
                               side_effect=self._workflow(native, keys)):
            plan = self._plan(request, execution)
            result = objet_capture_batch_exact.execute_objet_capture_batch(
                plan, expected_plan_sha256=plan.batch_plan_sha256, reviewer_claim=capture_fixture.REVIEWER)
        self.assertTrue(result["ok"], result)
        receipt = json.loads(self.root.joinpath(*result["summary"]["capture_receipt_path"].split("/"))
                             .read_text(encoding="utf-8"))
        return result, receipt, keys

    def test_real_receipt_reference_is_nested_and_now_read(self):
        result, receipt, keys = self.capture(3, "letter186")
        outer = receipt["exact_human_approval"]
        self.assertEqual(outer["operation"], "objet_capture_batch")
        self.assertNotIn("approval_id", outer)                      # the shape the old reader expected
        reference = scope._approval_reference(receipt)
        self.assertEqual(reference["approval_id"], outer["exact_human_approval"]["approval_id"])
        self.assertEqual(receipt["summary"]["captured"], 3)
        approval_id = reference["approval_id"]
        output = self.workspace / "letter186-list.txt"
        listed = scope.export_scope_list(self.root, output=output, approval_ids=[approval_id], key_provider=keys)
        self.assertTrue(listed["ok"], listed)
        self.assertEqual(listed["selected_object_count"], 3)
        self.assertEqual(listed["approvals"]["object_count"], 3)
        self.assertEqual(listed["approvals"]["without_session_mark_count"], 1)   # approved through a window
        self.assertEqual(listed["approvals"]["approvals_with_no_valid_capture_receipt_count"], 0)
        self.assertEqual(listed["approvals"]["receipt_count_naming_named_approvals"], 1)
        self.assertEqual(listed["approvals"]["rejections"], {})
        ids = output.read_text(encoding="utf-8").split()
        self.assertEqual(sorted(ids), sorted(item["object_id"] for item in receipt["items"]))
        self.assertNotIn(approval_id, json.dumps(listed))
        for oid in ids:
            self.assertNotIn(oid, json.dumps(listed))
        # the diagnosis of a session that owns nothing counts these as unmarked
        diagnosis = scope.session_scope_diagnosis(self.root, "work_session_" + "a" * 32, key_provider=keys)
        self.assertEqual(diagnosis["captured_without_session_mark_count"], 3)
        self.assertEqual(diagnosis["capture_approvals_without_session_mark_count"], 1)
        self.assertEqual(diagnosis["capture_receipt_rejections"], {})

    def test_cli_route_with_the_real_receipt(self):
        result, receipt, keys = self.capture(2, "letter186cli")
        approval_id = receipt["exact_human_approval"]["exact_human_approval"]["approval_id"]
        output = self.workspace / "letter186-cli-list.txt"
        out = __import__("io").StringIO()
        with patch.object(broker, "_production_key_provider", return_value=keys), \
                __import__("contextlib").redirect_stdout(out), \
                __import__("contextlib").redirect_stderr(__import__("io").StringIO()):
            code = archive_cli.main(["object-storage-scope-list", str(self.root), "--approval-id", approval_id,
                                     "--output", str(output), "--format", "json"])
        listed = json.loads(out.getvalue())
        self.assertEqual(code, 0, listed)
        self.assertEqual(listed["selected_object_count"], 2)
        self.assertEqual(len(output.read_text(encoding="utf-8").split()), 2)

    def test_rejections_are_counted_by_reason(self):
        result, receipt, keys = self.capture(2, "letter186reject")
        approval_id = receipt["exact_human_approval"]["exact_human_approval"]["approval_id"]
        path = self.root.joinpath(*result["summary"]["capture_receipt_path"].split("/"))
        # a receipt whose reference points at a context the claim does not have
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["exact_human_approval"]["exact_human_approval"]["context_sha256"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(tampered), encoding="utf-8")
        output = self.workspace / "letter186-rejected.txt"
        listed = scope.export_scope_list(self.root, output=output, approval_ids=[approval_id], key_provider=keys)
        self.assertFalse(listed["ok"])
        self.assertEqual(listed["approvals"]["object_count"], 0)
        self.assertEqual(listed["approvals"]["receipt_count_naming_named_approvals"], 1)
        self.assertEqual(listed["approvals"]["rejections"], {"claim_context_mismatch": 1})
        self.assertFalse(output.exists())
        # an unknown approval id: nothing names it
        listed = scope.export_scope_list(self.root, output=output, approval_ids=["approval_" + "9" * 32],
                                         key_provider=keys)
        self.assertEqual(listed["approvals"]["found_count"], 0)
        self.assertEqual(listed["approvals"]["receipt_count_naming_named_approvals"], 0)


# The inherited capture scenarios run in their own module.
for _name in [name for name in dir(capture_fixture.ObjetCaptureBatchExactTests) if name.startswith("test_")]:
    setattr(RealCaptureReceiptTests, _name, None)


if __name__ == "__main__":
    unittest.main()
