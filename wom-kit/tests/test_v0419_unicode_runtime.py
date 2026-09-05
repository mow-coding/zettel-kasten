from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
from importlib import machinery, util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from types import ModuleType
import unittest
from unittest import mock


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wom_kit import _unicode_runtime as adapter


NAME = "unicodedata2"
LONG_ORIGIN = "C:\\" + "a" * 250 + "\\unicodedata2.pyd"


@contextmanager
def absent_engine():
    sentinel = object()
    existing = sys.modules.pop(NAME, sentinel)
    try:
        yield
    finally:
        sys.modules.pop(NAME, None)
        if existing is not sentinel:
            sys.modules[NAME] = existing


def extension_spec(origin=LONG_ORIGIN):
    return util.spec_from_file_location(
        NAME, origin, loader=machinery.ExtensionFileLoader(NAME, origin)
    )


class UnicodeRuntimeAdapterTests(unittest.TestCase):
    def test_existing_engine_is_shared_by_both_consumers_without_rediscovery(self):
        from wom_kit import credential_continuity, private_objet_metadata

        engine = importlib.import_module(NAME)
        with mock.patch.object(adapter.util, "find_spec", side_effect=AssertionError):
            self.assertIs(adapter.load_unicode(), engine)
        self.assertIs(private_objet_metadata.unicodedata2, engine)
        self.assertIs(credential_continuity.unicodedata, engine)
        self.assertEqual(engine.unidata_version, "17.0.0")

    def test_none_sentinel_missing_dependency_and_unavailable_protocol_fail_closed(self):
        for state in ("blocked", "absent", "protocol"):
            with self.subTest(state=state), absent_engine():
                if state == "blocked":
                    sys.modules[NAME] = None
                with mock.patch.object(adapter.util, "find_spec", return_value=None), \
                     mock.patch.object(adapter._bootstrap, "_load", None if state == "protocol" else adapter._bootstrap._load):
                    with self.assertRaises(ImportError) as raised:
                        adapter.load_unicode()
                self.assertEqual(str(raised.exception), "unicode_runtime_dependency_unavailable")
                self.assertIsNone(raised.exception.__context__)
                if state == "blocked":
                    self.assertIsNone(sys.modules[NAME])
                else:
                    self.assertNotIn(NAME, sys.modules)

    def test_short_and_non_windows_paths_keep_standard_import(self):
        engine = ModuleType(NAME)
        for platform, origin, loader_state in (
            ("nt", "C:\\native\\unicodedata2.pyd", None),
            ("nt", "C:\\native\\..\\native\\unicodedata2.pyd", None),
            ("nt", "C:/native/unicodedata2.pyd", None),
            ("nt", "C:\\native\\unicodedata2.pyd", {"custom": True}),
            ("posix", LONG_ORIGIN, None),
        ):
            spec = extension_spec(origin)
            spec.loader_state = loader_state
            with self.subTest(platform=platform, spelling=origin.count(".")), absent_engine(), \
                 mock.patch.object(adapter.os, "name", platform), \
                 mock.patch.object(adapter.util, "find_spec", return_value=spec), \
                 mock.patch.object(adapter.importlib, "import_module", return_value=engine) as normal, \
                 mock.patch.object(adapter._bootstrap, "_load", side_effect=AssertionError), \
                 mock.patch.object(adapter.os.path, "samefile", side_effect=AssertionError):
                self.assertIs(adapter.load_unicode(), engine)
                normal.assert_called_once_with(NAME)

    def test_length_is_utf16_and_unc_keeps_the_same_selected_file(self):
        for origin, extended in (
            ("C:\\" + "a" * 242 + "unicodedata2.pyd", "\\\\?\\C:\\" + "a" * 242 + "unicodedata2.pyd"),
            ("C:\\" + "\U0001f600" * 130 + "\\unicodedata2.pyd", "\\\\?\\C:\\" + "\U0001f600" * 130 + "\\unicodedata2.pyd"),
            ("\\\\server\\share\\" + "b" * 245 + "\\unicodedata2.pyd", "\\\\?\\UNC\\server\\share\\" + "b" * 245 + "\\unicodedata2.pyd"),
        ):
            with self.subTest(kind="unc" if origin.startswith("\\\\") else "drive"), \
                 mock.patch.object(adapter.os, "name", "nt"), \
                 mock.patch.object(adapter.os.path, "samefile", return_value=True) as same:
                self.assertEqual(adapter._extended_origin(extension_spec(origin)), extended)
                same.assert_called_once_with(origin, extended)

    def test_exact_spec_boundary_and_no_path_normalization_or_substitution(self):
        cases = []
        for origin in (
            "relative\\" + "a" * 260 + "\\unicodedata2.pyd",
            "C:\\a\\..\\" + "a" * 260 + "\\unicodedata2.pyd",
            "C:/" + "a" * 260 + "/unicodedata2.pyd",
            "\\\\.\\C:\\" + "a" * 260 + "\\unicodedata2.pyd",
        ):
            cases.append(extension_spec(origin))
        spec = extension_spec()
        spec.loader.path = "C:\\different\\unicodedata2.pyd"
        cases.append(spec)
        spec = extension_spec()
        spec.submodule_search_locations = []
        cases.append(spec)
        spec = extension_spec()
        spec.loader.name = "other"
        cases.append(spec)
        spec = extension_spec()
        spec.loader_state = {"custom": True}
        cases.append(spec)
        for spec in cases:
            with self.subTest(case=cases.index(spec)), mock.patch.object(adapter.os, "name", "nt"):
                with self.assertRaises(ImportError):
                    adapter._extended_origin(spec)
        with mock.patch.object(adapter.os, "name", "nt"), \
             mock.patch.object(adapter.os.path, "samefile", return_value=False):
            with self.assertRaises(ImportError):
                adapter._extended_origin(extension_spec())

    def test_nonstandard_loader_is_not_silently_replaced(self):
        class CustomExtension(machinery.ExtensionFileLoader):
            pass

        spec = util.spec_from_file_location(NAME, LONG_ORIGIN, loader=CustomExtension(NAME, LONG_ORIGIN))
        with mock.patch.object(adapter.os, "name", "nt"), \
             mock.patch.object(adapter.os.path, "samefile", side_effect=AssertionError):
            self.assertIsNone(adapter._extended_origin(spec))

    def test_create_and_exec_failure_leave_no_module_or_private_error_context(self):
        for boundary in ("create", "exec"):
            with self.subTest(boundary=boundary), absent_engine(), \
                 mock.patch.object(adapter.os, "name", "nt"), \
                 mock.patch.object(adapter.util, "find_spec", return_value=extension_spec()), \
                 mock.patch.object(adapter.os.path, "samefile", return_value=True), \
                 mock.patch.object(machinery.ExtensionFileLoader, "create_module", side_effect=ImportError("private-value") if boundary == "create" else None, return_value=ModuleType(NAME)), \
                 mock.patch.object(machinery.ExtensionFileLoader, "exec_module", side_effect=ImportError("private-value")):
                with self.assertRaises(ImportError) as raised:
                    adapter.load_unicode()
                self.assertEqual(str(raised.exception), "unicode_runtime_dependency_unavailable")
                self.assertIsNone(raised.exception.__context__)
                self.assertNotIn(NAME, sys.modules)

    def test_raw_import_waits_for_standard_initialization_and_gets_same_module(self):
        entered = threading.Event()
        release = threading.Event()
        raw_started = threading.Event()
        raw_done = threading.Event()
        results = []
        failures = []
        initial = []

        def execute(_loader, module):
            initial.append((sys.modules[NAME] is module, module.__spec__._initializing))
            entered.set()
            if not release.wait(5):
                raise AssertionError("test_release_timeout")
            module.complete = True

        def adapted():
            try:
                results.append(adapter.load_unicode())
            except BaseException as error:
                failures.append(type(error).__name__)

        def raw():
            raw_started.set()
            try:
                results.append(importlib.import_module(NAME))
            except BaseException as error:
                failures.append(type(error).__name__)
            finally:
                raw_done.set()

        path_before = list(sys.path)
        meta_before = list(sys.meta_path)
        with absent_engine(), mock.patch.object(adapter.os, "name", "nt"), \
             mock.patch.object(adapter.util, "find_spec", return_value=extension_spec()), \
             mock.patch.object(adapter.os.path, "samefile", return_value=True), \
             mock.patch.object(machinery.ExtensionFileLoader, "create_module", return_value=ModuleType(NAME)) as create, \
             mock.patch.object(machinery.ExtensionFileLoader, "exec_module", execute):
            a, b = threading.Thread(target=adapted), threading.Thread(target=raw)
            a.start()
            try:
                self.assertTrue(entered.wait(5))
                b.start()
                self.assertTrue(raw_started.wait(5))
                self.assertFalse(raw_done.wait(0.05))
            finally:
                release.set()
                a.join(5)
                if b.ident is not None:
                    b.join(5)
            self.assertFalse(a.is_alive())
            self.assertFalse(b.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(len(results), 2)
            self.assertIs(results[0], results[1])
            self.assertIs(results[0], sys.modules[NAME])
            self.assertTrue(results[0].complete)
            self.assertFalse(results[0].__spec__._initializing)
            self.assertEqual(initial, [(True, True)])
            create.assert_called_once()
            self.assertEqual(create.call_args.args[0].origin, "\\\\?\\" + LONG_ORIGIN)
        self.assertEqual(sys.path, path_before)
        self.assertEqual(sys.meta_path, meta_before)

    @unittest.skipUnless(os.name == "nt", "Windows native-extension path contract")
    def test_actual_long_native_file_load_and_bad_binary_fail_without_fallback(self):
        engine = importlib.import_module(NAME)
        original = Path(engine.__file__)
        self.assertEqual(original.suffix, ".pyd")
        original_bytes = original.read_bytes()
        with tempfile.TemporaryDirectory(prefix="wom-unicode-native-") as temporary:
            root = Path(temporary)
            native = root
            while len(str(native / original.name).encode("utf-16-le")) // 2 < 280:
                native /= "native-path-segment"
            native.mkdir(parents=True)
            target = native / original.name
            shutil.copyfile(original, target)
            self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), hashlib.sha256(original_bytes).digest())
            script = r'''
import importlib.util, json, sys
source, native = sys.argv[1:]
spec = importlib.util.spec_from_file_location("unicode_adapter_under_test", source)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
sys.path.insert(0, native)
before_path, before_meta = list(sys.path), list(sys.meta_path)
try:
    module = adapter.load_unicode()
except ImportError as error:
    print(json.dumps({"state": "blocked", "fixed_error": str(error) == "unicode_runtime_dependency_unavailable",
                      "no_context": error.__context__ is None, "no_cached_module": "unicodedata2" not in sys.modules}))
else:
    print(json.dumps({"state": "loaded", "pinned": module.unidata_version == "17.0.0",
                      "normalized": module.normalize("NFC", "e\u0301") == "\u00e9",
                      "same_alias": module is adapter.load_unicode(),
                      "extended_origin": module.__file__.startswith("\\\\?\\"),
                      "global_paths_unchanged": sys.path == before_path and sys.meta_path == before_meta}))
'''
            for corrupted in (False, True):
                if corrupted:
                    target.write_bytes(b"not-a-native-extension")
                with self.subTest(corrupted=corrupted):
                    result = subprocess.run(
                        [sys.executable, "-I", "-B", "-X", "utf8", "-c", script, str(Path(adapter.__file__)), str(native)],
                        capture_output=True, text=True, encoding="utf-8", timeout=30,
                        check=False, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    self.assertEqual(result.returncode, 0, "native_probe_nonzero")
                    self.assertFalse(bool(result.stderr), "native_probe_stderr_present")
                    observed = json.loads(result.stdout)
                    expected = (
                        {"state": "blocked", "fixed_error": True, "no_context": True, "no_cached_module": True}
                        if corrupted else
                        {"state": "loaded", "pinned": True, "normalized": True, "same_alias": True,
                         "extended_origin": True, "global_paths_unchanged": True}
                    )
                    self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
