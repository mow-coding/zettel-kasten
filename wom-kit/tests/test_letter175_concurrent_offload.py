"""Offload remote verification does not serialize unrelated objects."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest

from wom_kit import object_storage_offload as offload
from . import test_v0429_object_storage_offload as fixture


@unittest.skipUnless(os.name == "nt", "native bound offload")
class ConcurrentOffloadTests(unittest.TestCase):
    def test_other_offload_commits_while_first_remote_verification_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture.restore_tests._build_root(Path(tmp))
            raws = (b"synthetic selected A", b"synthetic selected B")
            fixture.restore_tests._write_rows(root, [fixture._aged_row(raw) for raw in raws])
            for raw in raws:
                fixture.restore_tests._write_local(root, raw)
            plans = [offload.plan_object_storage_offload(root, provider_kind=fixture.PROVIDER,
                store_ref=fixture.STORE, only="sha256:" + hashlib.sha256(raw).hexdigest()) for raw in raws]
            entered, release = threading.Event(), threading.Event()
            class SlowProof(fixture._ProofTransport):
                def head_object(self, **kwargs):
                    if kwargs["key"] == plans[0].specs[0].remote_key:
                        entered.set()
                        if not release.wait(20):
                            raise TimeoutError("synthetic timeout")
                    return super().head_object(**kwargs)
            transport = SlowProof({plan.specs[0].remote_key: raw for plan, raw in zip(plans, raws)})
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(fixture._run_offload, plans[0], transport)
                try:
                    self.assertTrue(entered.wait(8))
                    b = pool.submit(fixture._run_offload, plans[1], transport).result(timeout=12)
                    self.assertTrue(b["ok"], b)
                    self.assertFalse(a.done())
                finally:
                    release.set()
                self.assertTrue(a.result(timeout=10)["ok"])
            self.assertEqual(transport.head_calls, 2)
            self.assertEqual(transport.put_calls, 0)
            for raw in raws:
                self.assertFalse(fixture.restore_tests._dest(root, raw).exists())

    def test_legacy_control_remains_readable_without_changing_approval_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture.restore_tests._build_root(Path(tmp))
            raw = b"synthetic legacy offload"
            fixture.restore_tests._write_rows(root, [fixture._aged_row(raw)])
            fixture.restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=fixture.PROVIDER,
                store_ref=fixture.STORE, only="sha256:" + hashlib.sha256(raw).hexdigest())
            legacy = replace(plan, concurrent=False,
                manifest=offload._manifest_for_specs(plan.archive_id, plan.specs, scope=plan.scope))
            result = fixture._run_offload(legacy, fixture._ProofTransport({legacy.specs[0].remote_key: raw}))
            self.assertTrue(result["ok"], result)
            loaded = offload.load_object_storage_offload_plan(root, manifest_sha256=legacy.manifest.manifest_sha256)
            self.assertFalse(loaded.concurrent)
            self.assertEqual(loaded.manifest.document(), legacy.manifest.document())
