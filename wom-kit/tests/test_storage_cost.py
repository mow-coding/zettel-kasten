import tempfile
import unittest
from pathlib import Path
from wom_kit import storage_cost as cost
import test_v0428_object_storage_restore as fixture


class StorageCostTests(unittest.TestCase):
    def test_no_unknown_account_free_allowance_is_assumed_and_requests_separate(self):
        result = cost.estimate(remote_bytes=1_100_000_000, class_a=1_000_001, class_b=0)
        self.assertEqual(result["monthly_storage_usd_before_free_allowance"], .03)
        self.assertEqual(result["request_usd_if_billed_as_separate_usage"], 9)
        self.assertFalse(result["free_allowance_subtracted"])
        self.assertFalse(result["actual_account_invoice_estimated"])
        self.assertFalse(cost.estimate(remote_bytes=10, provider_kind="generic-s3")["available"])

    def test_duplicate_manifest_rows_and_uploads_do_not_double_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture._build_root(Path(tmp))
            row = fixture._row(b"test", locations=[fixture._local(b"test")])
            groups = {row["object_id"]: [row, dict(row)]}
            summary = cost.capacity(root, groups, planned_uploads=[(row["object_id"],4), (row["object_id"],4)])
            self.assertEqual(summary["unique_object_bytes"], 4)
            self.assertEqual(summary["local_only_bytes"], 4)
            self.assertEqual(summary["projected_remote_bytes"], 4)
            self.assertIsNone(summary["offloadable_bytes_pending_live_verification"])
            groups[row["object_id"]].append({**row, "size_bytes":8})
            incomplete = cost.capacity(root, groups)
            self.assertEqual(incomplete["unknown_or_conflicting_object_count"],1)
            self.assertEqual(incomplete["estimate_coverage"], "incomplete")
            self.assertFalse(cost.estimate_capacity(incomplete)["available"])

    def test_conflicting_planned_size_or_truncated_scan_has_no_total_cost_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture._build_root(Path(tmp))
            oid = "sha256:" + "a" * 64
            summary = cost.capacity(root, {}, planned_uploads=[(oid, 4), (oid, 8)])
            self.assertEqual(summary["projected_remote_bytes"], 0)
            self.assertEqual(summary["estimate_coverage"], "incomplete")
            self.assertFalse(cost.estimate_capacity(summary)["available"])
            complete = cost.capacity(root, {}, planned_uploads=[(oid, 4)])
            complete["scan_complete"] = False
            self.assertFalse(cost.estimate_capacity(complete)["available"])


if __name__ == "__main__":
    unittest.main()
