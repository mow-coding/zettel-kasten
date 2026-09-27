"""Remote A stays paused until disjoint B has committed: never a sequential proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest

from wom_kit import object_storage_upload_exact as upload
from . import test_v0433_object_storage_upload as fixture


class ConcurrentUploadTests(unittest.TestCase):
    def setUp(self):
        self.archive = fixture._Archive()
        self.addCleanup(self.archive.close)

    def test_disjoint_upload_commits_while_first_remote_request_is_still_active(self):
        first, second = b"remote transfer A", b"remote transfer B"
        self.archive.write([self.archive.local(first), self.archive.local(second)])
        a = self.archive.plan(only=fixture._oid(first))
        b = self.archive.plan(only=fixture._oid(second))
        entered, release = threading.Event(), threading.Event()

        class SlowTransport(fixture._MemoryTransport):
            def put_object(self, **kwargs):
                if kwargs["key"] == fixture._key(first):
                    entered.set()
                    if not release.wait(15):
                        raise TimeoutError("synthetic test budget")
                return super().put_object(**kwargs)

        transport = SlowTransport()
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(fixture._run, a, transport)
            try:
                self.assertTrue(entered.wait(10))
                # Revalidation after A has started must remain about B's target.
                b = upload._fresh_revalidated(b, progress_hook=None)
                second_result = pool.submit(fixture._run, b, transport).result(timeout=10)
                self.assertTrue(second_result["ok"], second_result)
                self.assertFalse(pending.done())
            finally:
                release.set()
            result = pending.result(timeout=10)
        self.assertTrue(result["ok"], result)
        self.assertEqual(transport.put_calls, 2)
        for row in self.archive.rows().values():
            self.assertTrue(any(location.get("availability") == "wom_uploaded" for location in row["locations"]))

    def test_unrelated_new_object_does_not_change_approved_selection_but_same_target_does(self):
        raw = b"selected"
        original = self.archive.local(raw)
        self.archive.write([original])
        plan = self.archive.plan()
        self.archive.write([original, self.archive.local(b"other session new intake")])
        self.assertIs(upload._fresh_revalidated(plan, progress_hook=None), plan)
        changed = {**original, "synthetic_metadata": "changed target"}
        self.archive.write([changed])
        with self.assertRaisesRegex(upload.ObjectStorageUploadError, "object_storage_upload_plan_changed"):
            upload._fresh_revalidated(plan, progress_hook=None)

    def test_legacy_control_manifest_is_preserved_and_loadable(self):
        self.archive.write([self.archive.local(b"legacy")])
        current = self.archive.plan()
        legacy = replace(current, target_preimages=None, manifest=upload._manifest_for_specs(
            archive_id=current.archive_id, specs=current.specs, scope=current.scope))
        result = fixture._run(legacy, fixture._MemoryTransport())
        self.assertTrue(result["ok"])
        loaded = upload.load_object_storage_upload_plan(self.archive.root, manifest_sha256=legacy.manifest.manifest_sha256)
        self.assertIsNone(loaded.target_preimages)
        self.assertEqual(loaded.manifest.document(), legacy.manifest.document())
