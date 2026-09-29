"""Synthetic complete inventory and batch receipts use no artifact body reads."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import unittest
import time
import threading
import sysconfig
from unittest.mock import patch

from wom_kit import human_artifact_inventory as module, human_artifact_registry as registry
import test_human_artifact_registry as fixture


class HumanArtifactInventoryTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixture.HumanArtifactRegistryTests()
        self.helper.setUp()
        self.addCleanup(self.helper.tearDown)
        self.root = self.helper.archive
        self.folder = self.root / ".wom-scratch"
        self.folder.mkdir()

    def request(self, count=3):
        for n in range(count):
            (self.folder / f"work-{n}.txt").write_bytes(b"synthetic")
        snapshot = module.publish(self.root)["snapshot_ref"]
        rows = module.query(self.root, snapshot_ref=snapshot)["items"]
        self.assertEqual(len(rows), count)
        return {"schema": module.REQUEST_SCHEMA, "snapshot_ref": snapshot, "items": [
            {"artifact_id": row["artifact_id"], "target_state": "reviewed_current", "content_sha256": "sha256:" + hashlib.sha256(b"synthetic").hexdigest(),
             "size_bytes": 9, "related_refs": []} for row in rows]}

    def execute(self, request, *, hook=None):
        plan = module.plan(self.root, request)
        context = module.approval_context(self.root, request, reviewer_claim=fixture.REVIEWER_CLAIM)
        self.claim = self.helper._claim(context, seed=901)
        return module.apply(self.root, request, expected_plan_sha256=plan["plan_sha256"],
                            reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=self.claim, progress_hook=hook)

    def test_complete_inventory_exceeds_old_limit_and_pages_never_scan_again(self):
        started = time.perf_counter()
        for n in range(12345):
            (self.folder / f"synthetic-{n}.txt").touch()
        published = module.publish(self.root)
        published_at = time.perf_counter()
        self.assertTrue(published["coverage_complete"])
        self.assertEqual(published["artifact_count"], 12345)
        seen, rows, cursor = set(), [], None
        with patch.object(registry, "_scan_scope", side_effect=AssertionError("page rescanned live files")):
            while True:
                page = module.query(self.root, snapshot_ref=published["snapshot_ref"], page_size=2000, cursor=cursor)
                for row in page["items"]:
                    self.assertNotIn(row["artifact_id"], seen)
                    seen.add(row["artifact_id"])
                    rows.append(row)
                cursor = page["pagination"]["next_cursor"]
                if not cursor:
                    break
        self.assertEqual(len(seen), 12345)
        self.assertNotIn("synthetic-", str(page))
        paged_at = time.perf_counter()
        recorded, batches = set(), 0
        with patch.object(registry, "_scan_internal", side_effect=AssertionError("batch rescanned entire archive")):
            for offset in range(0, len(rows), module.MAX_BATCH):
                batches += 1
                request = {"schema": module.REQUEST_SCHEMA, "snapshot_ref": published["snapshot_ref"], "items": [
                    {"artifact_id": row["artifact_id"], "target_state": "reviewed_current",
                     "content_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(), "size_bytes": 0, "related_refs": []}
                    for row in rows[offset:offset + module.MAX_BATCH]]}
                preview = module.plan(self.root, request)
                context = module.approval_context(self.root, request, reviewer_claim=fixture.REVIEWER_CLAIM,
                                                   expected_plan_sha256=preview["plan_sha256"])
                claim = self.helper._claim(context, seed=1000 + batches)
                result = module.apply(self.root, request, expected_plan_sha256=preview["plan_sha256"],
                                      reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=claim)
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["conflict_count"], 0)
                for item in result["items"]:
                    self.assertNotIn(item["artifact_id"], recorded)
                    recorded.add(item["artifact_id"])
                claim.finalize_succeeded()
        self.assertEqual(recorded, seen)
        refreshed = module.publish(self.root)
        states = module._read(self.root, refreshed["snapshot_ref"])[1]["report"]["state_counts"]
        self.assertEqual(states, {"reviewed_current": 12345})
        receipts = list((self.root / registry.REGISTRY_RELATIVE_ROOT / registry.RECEIPTS_DIRECTORY).rglob("*.json"))
        self.assertEqual(len(receipts), 12345)
        print(json.dumps({"scale_evidence": "human_inventory_and_batch", "artifact_count": len(seen),
            "recorded_count": len(recorded), "receipt_count": len(receipts), "missing": 0, "duplicates": 0,
            "bounded_batches": batches, "batch_size_limit": module.MAX_BATCH,
            "fixture_and_inventory_seconds": round(published_at-started, 3),
            "all_pages_seconds": round(paged_at-published_at, 3),
            "batch_and_result_verification_seconds": round(time.perf_counter()-paged_at, 3),
            "per_item_archive_scans": 0,
            "installed_product": Path(module.__file__).resolve().is_relative_to(
                Path(sysconfig.get_paths()["purelib"]).resolve())}))

    def test_batch_uses_one_approval_and_no_per_item_archive_scan_and_keeps_legacy_receipts(self):
        request = self.request()
        with patch.object(registry, "_scan_internal", side_effect=AssertionError("batch rescanned archive")):
            result = self.execute(request)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["recorded_count"], 3)
        scan = registry.scan_human_artifacts(self.root)
        self.assertEqual(scan["state_counts"], {"reviewed_current": 3})
        self.assertEqual(len(list((self.root / registry.REGISTRY_RELATIVE_ROOT / registry.APPROVAL_USES_DIRECTORY).glob("*.json"))), 1)
        for path in self.folder.iterdir():
            self.assertEqual(path.read_bytes(), b"synthetic")
        for document in self.helper._registry_json_documents():
            self.helper.validator.validate(document)
        self.claim.finalize_succeeded()

    def test_single_item_receipt_race_does_not_stop_disjoint_items(self):
        request = self.request()
        first_id = request["items"][0]["artifact_id"]
        original = module._append
        def competing_receipt(context, key, state, item, approval, created_at):
            if item["artifact_id"] == first_id:
                raise registry._fail("human_artifact_transition_conflict")
            return original(context, key, state, item, approval, created_at)
        with patch.object(module, "_append", side_effect=competing_receipt):
            result = self.execute(request)
        self.assertFalse(result["ok"])
        self.assertEqual(result["conflict_count"], 1)
        self.assertEqual(result["recorded_count"], 2)
        scan = registry.scan_human_artifacts(self.root)
        self.assertEqual(scan["state_counts"], {"unclassified": 1, "reviewed_current": 2})

    def test_malformed_target_state_is_fixed_domain_error(self):
        request = self.request(count=1)
        request["items"][0]["target_state"] = ["synthetic-private-value"]
        with self.assertRaisesRegex(module.services.ArchiveServiceError, "^human_artifact_batch_request_invalid$"):
            module.plan(self.root, request)

    def test_completed_claim_resume_only_reconciles_receipts_and_cannot_recreate_missing_one(self):
        request = self.request()
        original = self.execute(request)
        self.claim.finalize_succeeded()
        with patch.object(module, "_append", side_effect=AssertionError("completed claim authorized a write")):
            replayed = module.apply(self.root, request, expected_plan_sha256=original["plan_sha256"],
                reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=self.claim, resume=True)
            self.assertTrue(replayed["ok"], replayed)
            self.assertTrue(replayed["completed_claim_reconciliation_only"])
            folder = self.root / registry.REGISTRY_RELATIVE_ROOT / registry.RECEIPTS_DIRECTORY
            missing = next(folder.rglob("*.json"))
            missing.unlink()
            missing_replay = module.apply(self.root, request, expected_plan_sha256=original["plan_sha256"],
                reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=self.claim, resume=True)
        self.assertFalse(missing_replay["ok"])
        self.assertEqual(missing_replay["conflict_count"], 1)
        self.assertFalse(missing.exists())

    def concurrent_batches(self, *, share_one_target):
        complete = self.request()
        request_a = {**complete, "items": complete["items"][:1]}
        request_b = {**complete, "items": complete["items"][:2] if share_one_target else complete["items"][1:]}
        prepared = []
        for seed, request in enumerate((request_a, request_b), 2001):
            preview = module.plan(self.root, request)
            context = module.approval_context(self.root, request, reviewer_claim=fixture.REVIEWER_CLAIM)
            prepared.append((request, preview["plan_sha256"], self.helper._claim(context, seed=seed)))
        target_a = request_a["items"][0]["artifact_id"]
        held, release = threading.Event(), threading.Event()
        original = module._append
        def hold_first_target(context, key, state, item, approval, created_at):
            if item["artifact_id"] == target_a:
                held.set()
                if not release.wait(20):
                    raise RuntimeError("synthetic lease holder timeout")
            return original(context, key, state, item, approval, created_at)
        def execute(item):
            request, digest, claim = item
            return module.apply(self.root, request, expected_plan_sha256=digest,
                                reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=claim)
        with ThreadPoolExecutor(max_workers=2) as workers, patch.object(module, "_append", side_effect=hold_first_target):
            first = workers.submit(execute, prepared[0])
            try:
                self.assertTrue(held.wait(10), "batch A did not reach its actual target lease")
                second = workers.submit(execute, prepared[1])
                second_result = second.result(timeout=10)
                self.assertFalse(first.done(), "batch B only finished after A stopped")
                if share_one_target:
                    self.assertFalse(second_result["ok"])
                    self.assertEqual(second_result["state"], "partial_retryable")
                    self.assertEqual(second_result["retryable_count"], 1)
                    self.assertEqual(second_result["recorded_count"], 1)
                else:
                    self.assertTrue(second_result["ok"], second_result)
                    self.assertEqual(second_result["recorded_count"], 2)
            finally:
                release.set()
            first_result = first.result(timeout=10)
        self.assertTrue(first_result["ok"], first_result)
        if share_one_target:
            request, digest, claim = prepared[1]
            resumed = module.apply(self.root, request, expected_plan_sha256=digest,
                                   reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=claim, resume=True)
            self.assertEqual(resumed["retryable_count"], 0)
            self.assertEqual(resumed["conflict_count"], 1)
            self.assertEqual(resumed["recorded_count"], 1)
            self.assertEqual({row["state"] for row in resumed["items"]}, {"conflict_requires_review", "already_recorded"})
        else:
            self.assertEqual(registry.scan_human_artifacts(self.root)["state_counts"], {"reviewed_current": 3})

    def test_disjoint_batch_finishes_while_first_batch_still_owns_its_target(self):
        self.concurrent_batches(share_one_target=False)

    def test_same_target_is_retryable_while_other_batch_items_finish(self):
        self.concurrent_batches(share_one_target=True)

    def test_interrupted_batch_resumes_original_receipts_without_duplicate_or_new_review(self):
        request = self.request()
        digest = module.plan(self.root, request)["plan_sha256"]
        def interrupt(progress):
            if progress["completed_count"] == 1:
                raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.execute(request, hook=interrupt)
        resumed = module.apply(self.root, request, expected_plan_sha256=digest, reviewer_claim=fixture.REVIEWER_CLAIM,
                               approval_claim=self.claim, resume=True)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual([row["state"] for row in resumed["items"]].count("already_recorded"), 1)
        self.assertEqual(len(list((self.root / registry.REGISTRY_RELATIVE_ROOT / registry.RECEIPTS_DIRECTORY).rglob("*.json"))), 3)
        self.claim.finalize_succeeded()

    def test_changed_selected_file_requires_fresh_review_and_does_not_write(self):
        request = self.request()
        digest = module.plan(self.root, request)["plan_sha256"]
        context = module.approval_context(self.root, request, reviewer_claim=fixture.REVIEWER_CLAIM)
        claim = self.helper._claim(context, seed=902)
        (self.folder / "work-0.txt").write_bytes(b"changed")
        with self.assertRaisesRegex(Exception, "human_artifact_batch_inventory_target_changed"):
            module.apply(self.root, request, expected_plan_sha256=digest, reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=claim)
        self.assertFalse((self.root / registry.REGISTRY_RELATIVE_ROOT / registry.RECEIPTS_DIRECTORY).exists())

    def test_resume_keeps_missing_target_conflict_local_and_finishes_other_items(self):
        request = self.request()
        digest = module.plan(self.root, request)["plan_sha256"]
        def interrupt(progress):
            if progress["completed_count"] == 1:
                raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.execute(request, hook=interrupt)
        control = module._load_control(self.root, digest)
        missing_id = request["items"][1]["artifact_id"]
        relative = control["private_locators"][missing_id]["relative_path"]
        (self.folder / relative).unlink()
        result = module.apply(self.root, request, expected_plan_sha256=digest,
                              reviewer_claim=fixture.REVIEWER_CLAIM, approval_claim=self.claim, resume=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["conflict_count"], 1)
        self.assertEqual(result["recorded_count"], 2)
        self.assertFalse(result["whole_archive_closeout_claimed"])
        self.assertEqual(len(list((self.root / registry.REGISTRY_RELATIVE_ROOT / registry.RECEIPTS_DIRECTORY).rglob("*.json"))), 2)

    def test_identical_refresh_reuses_verified_snapshot_and_cursors(self):
        request = self.request()
        first = module.query(self.root, snapshot_ref=request["snapshot_ref"], page_size=1)
        repeated = module.publish(self.root)
        self.assertEqual(repeated["snapshot_ref"], first["snapshot_ref"])
        second = module.query(self.root, snapshot_ref=first["snapshot_ref"], page_size=1,
                              cursor=first["pagination"]["next_cursor"])
        self.assertNotEqual(first["items"][0]["artifact_id"], second["items"][0]["artifact_id"])


if __name__ == "__main__":
    unittest.main()
