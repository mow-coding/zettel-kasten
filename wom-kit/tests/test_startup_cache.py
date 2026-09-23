import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from wom_kit import startup_cache as cache


class StartupCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in cache.MODULES:
            (self.root / (name + ".py")).write_bytes(b"answer = 42\n")
        cache.build(self.root)

    def test_checked_hash_bytes_are_deterministic_and_do_not_contain_machine_paths(self):
        retained = cache.verify(self.root, verify_compiled=True)
        for name in cache.MODULES:
            payload = retained["wom_kit." + name][1]
            self.assertEqual(payload[4:8], b"\x03\x00\x00\x00")
            self.assertNotIn(str(self.root).encode(), payload)
            self.assertEqual(payload, cache.compiled_bytes(b"answer = 42\n", name))

    def test_source_change_with_same_size_and_mtime_is_detected(self):
        source = self.root / "archive_cli.py"
        before = source.stat()
        source.write_bytes(b"answer = 43\n")
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root)

    def test_cache_mutation_and_forged_cache_manifest_fail_independent_verification(self):
        target = self.root / cache._filename("archive_cli")
        raw = bytearray(target.read_bytes())
        raw[-1] ^= 1
        target.write_bytes(raw)
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root)
        manifest = self.root / cache.MANIFEST
        doc = json.loads(manifest.read_bytes())
        doc["modules"]["archive_cli"]["cache_sha256"] = hashlib.sha256(raw).hexdigest()
        manifest.write_text(json.dumps(doc))
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root, verify_compiled=True)

    def test_replacement_after_read_does_not_change_retained_execution(self):
        import types
        filename, payload = cache.verify(self.root)["wom_kit.archive_cli"]
        target = self.root / cache._filename("archive_cli")
        target.write_bytes(b"invalid replacement")
        module = types.ModuleType("synthetic")
        cache._RetainedLoader(filename, payload).exec_module(module)
        self.assertEqual(module.answer, 42)


if __name__ == "__main__":
    unittest.main()
