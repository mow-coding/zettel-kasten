"""Restore downloads hold only selected object leases, preserving legacy controls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from wom_kit import object_storage_restore as restore
from . import test_v0428_object_storage_restore as fixture


class ConcurrentRestoreTests(unittest.TestCase):
    def test_other_restore_commits_during_first_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture._build_root(Path(tmp))
            raws = (b"synthetic restore A", b"synthetic restore B")
            fixture._write_rows(root, [fixture._row(raw, locations=[fixture._remote(raw)]) for raw in raws])
            plans = [restore.plan_object_storage_restore(root, provider_kind=fixture.PROVIDER,
                store_ref=fixture.STORE, only="sha256:" + hashlib.sha256(raw).hexdigest()) for raw in raws]
            entered, release = threading.Event(), threading.Event()
            class SlowGet(fixture._MemoryTransport):
                def get_object(self, **kwargs):
                    if kwargs["key"] == plans[0].specs[0].remote_key:
                        entered.set()
                        if not release.wait(20):
                            raise TimeoutError("synthetic timeout")
                    return super().get_object(**kwargs)
            transport = SlowGet({plan.specs[0].remote_key: raw for plan, raw in zip(plans, raws)})
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(fixture._run, plans[0], transport)
                try:
                    self.assertTrue(entered.wait(8))
                    b = pool.submit(fixture._run, plans[1], transport).result(timeout=12)
                    self.assertTrue(b["ok"], b)
                    self.assertFalse(a.done())
                finally:
                    release.set()
                self.assertTrue(a.result(timeout=10)["ok"])
            self.assertEqual(transport.get_calls, 2)
            for raw in raws:
                self.assertEqual(fixture._dest(root, raw).read_bytes(), raw)

    def test_legacy_control_keeps_its_original_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture._build_root(Path(tmp))
            raw = b"synthetic legacy restore"
            fixture._write_rows(root, [fixture._row(raw, locations=[fixture._remote(raw)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=fixture.PROVIDER,
                store_ref=fixture.STORE, only="sha256:" + hashlib.sha256(raw).hexdigest())
            legacy = replace(plan, concurrent=False, manifest=restore._manifest_for_specs(
                plan.archive_id, plan.specs, mode=plan.mode, scope=plan.scope))
            self.assertTrue(fixture._run(legacy, fixture._MemoryTransport({legacy.specs[0].remote_key: raw}))["ok"])
            loaded = restore.load_object_storage_restore_plan(root, manifest_sha256=legacy.manifest.manifest_sha256)
            self.assertFalse(loaded.concurrent)
            self.assertEqual(loaded.manifest.document(), legacy.manifest.document())

    def test_selected_remote_source_change_is_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture._build_root(Path(tmp))
            raw = b"synthetic selected drift"
            fixture._write_rows(root, [fixture._row(raw, locations=[fixture._remote(raw)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=fixture.PROVIDER,
                store_ref=fixture.STORE, only="sha256:" + hashlib.sha256(raw).hexdigest())
            rows = list(fixture._rows_after(root).values())
            rows[0]["locations"][0]["remote_key"] = "synthetic/changed"
            fixture._write_rows(root, rows)
            transport = fixture._MemoryTransport({plan.specs[0].remote_key: raw})
            with self.assertRaises(restore.ObjectStorageRestoreError):
                fixture._run(plan, transport)
            self.assertEqual(transport.get_calls, 0)
