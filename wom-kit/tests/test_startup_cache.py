import hashlib
import json
import marshal
import os
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest import mock

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

    def test_installed_large_modules_verify_after_independent_compilation(self):
        source_root = Path(__file__).resolve().parents[1] / "src" / "wom_kit"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in cache.MODULES:
                shutil.copy2(source_root / (name + ".py"), root / (name + ".py"))
            cache.build(root)
            self.assertEqual(set(cache.verify(root, verify_compiled=True)),
                {"wom_kit." + name for name in cache.MODULES})

    def test_forged_code_origin_and_trailing_bytes_are_refused(self):
        target = self.root / cache._filename("archive_cli")
        original = target.read_bytes()
        code = marshal.loads(original[16:])
        self.assertIsInstance(code, types.CodeType)
        forged = original[:16] + marshal.dumps(code.replace(co_filename="private/other.py"))
        target.write_bytes(forged)
        manifest = self.root / cache.MANIFEST
        document = json.loads(manifest.read_bytes())
        document["modules"]["archive_cli"]["cache_sha256"] = hashlib.sha256(forged).hexdigest()
        document["modules"]["archive_cli"]["cache_size"] = len(forged)
        manifest.write_text(json.dumps(document), encoding="ascii")
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root, verify_compiled=True)
        with_trailing = original + b"ignored"
        target.write_bytes(with_trailing)
        document["modules"]["archive_cli"]["cache_sha256"] = hashlib.sha256(with_trailing).hexdigest()
        document["modules"]["archive_cli"]["cache_size"] = len(with_trailing)
        manifest.write_text(json.dumps(document), encoding="ascii")
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root, verify_compiled=True)

    def test_same_verified_bytes_skip_recompilation_but_changed_bytes_do_not(self):
        cache._COMPILED_PROOF_CACHE.clear()
        with mock.patch.object(cache, "_compiled_code_matches", wraps=cache._compiled_code_matches) as check:
            cache.verify(self.root, verify_compiled=True)
            cache.verify(self.root, verify_compiled=True)
            self.assertEqual(check.call_count, len(cache.MODULES))
            target = self.root / cache._filename("archive_cli")
            altered = target.read_bytes() + b"trailing"
            target.write_bytes(altered)
            manifest = self.root / cache.MANIFEST
            document = json.loads(manifest.read_bytes())
            document["modules"]["archive_cli"]["cache_sha256"] = hashlib.sha256(altered).hexdigest()
            document["modules"]["archive_cli"]["cache_size"] = len(altered)
            manifest.write_text(json.dumps(document), encoding="ascii")
            with self.assertRaises(cache.StartupCacheError):
                cache.verify(self.root, verify_compiled=True)
            self.assertEqual(check.call_count, len(cache.MODULES) + 1)


if __name__ == "__main__":
    unittest.main()
