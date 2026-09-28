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

    def _retain_legacy_manifest(self):
        manifest = self.root / cache.MANIFEST
        document = json.loads(manifest.read_bytes())
        document["schema"] = cache.LEGACY_SCHEMA
        document["modules"] = {
            name: document["modules"][name] for name in cache.LEGACY_MODULES
        }
        manifest.write_text(json.dumps(document), encoding="ascii")
        for name in set(cache.MODULES) - set(cache.LEGACY_MODULES):
            (self.root / cache._filename(name)).unlink()

    def test_legacy_two_module_cache_is_still_verified_without_migration(self):
        self._retain_legacy_manifest()
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        retained = cache.verify(self.root, verify_compiled=True)
        self.assertEqual(set(retained), {"wom_kit." + n for n in cache.LEGACY_MODULES})
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_legacy_manifest_cannot_admit_unverified_extension_cache(self):
        self._retain_legacy_manifest()
        target = self.root / cache._filename("completion_workflows")
        target.write_bytes(cache.compiled_bytes(b"answer = 99\n", "completion_workflows"))
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root)

    def test_extended_source_same_size_mtime_mutation_is_detected(self):
        source = self.root / "completion_workflows.py"
        before = source.stat()
        source.write_bytes(b"answer = 43\n")
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root)

    def test_extension_payload_forgery_requires_independent_source_match(self):
        name = "completion_workflows"
        target = self.root / cache._filename(name)
        original = target.read_bytes()
        code = marshal.loads(original[16:])
        forged = original[:16] + marshal.dumps(code.replace(co_consts=(99, None)))
        target.write_bytes(forged)
        manifest = self.root / cache.MANIFEST
        document = json.loads(manifest.read_bytes())
        document["modules"][name]["cache_sha256"] = hashlib.sha256(forged).hexdigest()
        document["modules"][name]["cache_size"] = len(forged)
        manifest.write_text(json.dumps(document), encoding="ascii")
        with self.assertRaises(cache.StartupCacheError):
            cache.verify(self.root, verify_compiled=True)

    def test_manifest_module_set_is_fixed_and_cannot_select_paths(self):
        manifest = self.root / cache.MANIFEST
        original = json.loads(manifest.read_bytes())
        for mutation in ("missing", "extra", "relative_path", "non_mapping"):
            with self.subTest(mutation=mutation):
                document = json.loads(json.dumps(original))
                if mutation == "missing":
                    document["modules"].pop("completion_workflows")
                elif mutation == "extra":
                    document["modules"]["unexpected"] = {}
                elif mutation == "relative_path":
                    document["modules"]["../unexpected"] = document["modules"].pop("completion_workflows")
                else:
                    document = []
                manifest.write_text(json.dumps(document), encoding="ascii")
                with self.assertRaises(cache.StartupCacheError):
                    cache.verify(self.root)

    def test_ordinary_verification_and_retained_execution_create_no_files(self):
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob("*") if p.is_file()}
        retained = cache.verify(self.root)
        filename, payload = retained["wom_kit.completion_workflows"]
        module = types.ModuleType("synthetic")
        cache._RetainedLoader(filename, payload).exec_module(module)
        self.assertEqual(module.answer, 42)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                 for p in self.root.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
