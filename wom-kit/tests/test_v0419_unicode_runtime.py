from __future__ import annotations

from contextlib import contextmanager, nullcontext
import hashlib
import importlib
from importlib import machinery, util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import ModuleType
import unittest
from unittest import mock


KIT = Path(__file__).resolve().parents[1]
SRC = KIT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wom_kit import _unicode_runtime as adapter


NAME = "unicodedata2"
HOST_WINDOWS = os.name == "nt"
LONG_ORIGIN = "C:\\" + "a" * 250 + "\\unicodedata2.pyd"
HISTORICAL_HELPER_SHA = "79081fd211d06705b06fe2123271c135bc6e9c4af2de5dc3331eddd51fb592c2"
HISTORICAL_MANIFEST_SHA = "a521cf945384ea8cb653fb39fdfec38821e6e0c549f4a2d57af4acb1dc89ef0a"


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


@contextmanager
def controlled_finders(spec=None, *, platform="nt"):
    # Preserve host finders. Never return a native spec for another import.
    entries = [entry for entry in sys.meta_path if entry is not adapter._FINDER]
    original_find = adapter._PATH_FINDER.find_spec

    def find(fullname, path=None, target=None):
        return spec if fullname == NAME else original_find(fullname, path, target)

    # CPython's frozen POSIX spec factory normalizes a Windows spelling into
    # a POSIX absolute path even if os.name is patched. Simulate only that
    # platform spelling in pure tests; the real Windows native test below
    # always runs the actual standard factory and loader without mocks.
    def windows_spec(fullname, origin, *, loader):
        value = machinery.ModuleSpec(fullname, loader, origin=origin)
        value.has_location = True
        return value

    spelling = (
        nullcontext() if HOST_WINDOWS else
        mock.patch.object(adapter.util, "spec_from_file_location", side_effect=windows_spec)
    )
    with spelling, mock.patch.object(sys, "meta_path", entries), \
         mock.patch.object(adapter.os, "name", platform), \
         mock.patch.object(adapter._PATH_FINDER, "find_spec", side_effect=find) as selected:
        adapter.register_unicode_finder()
        yield selected


def extension_spec(origin=LONG_ORIGIN):
    spec = machinery.ModuleSpec(NAME, machinery.ExtensionFileLoader(NAME, origin), origin=origin)
    spec.has_location = True
    return spec


class UnicodeRuntimeAdapterTests(unittest.TestCase):
    def test_existing_engine_is_shared_by_both_consumers_without_rediscovery(self):
        from wom_kit import credential_continuity, private_objet_metadata

        engine = importlib.import_module(NAME)
        with mock.patch.object(adapter._PATH_FINDER, "find_spec", side_effect=AssertionError):
            self.assertIs(adapter.load_unicode(), engine)
        self.assertIs(private_objet_metadata.unicodedata2, engine)
        self.assertIs(credential_continuity.unicodedata, engine)
        self.assertEqual(engine.unidata_version, "17.0.0")

    def test_none_sentinel_and_missing_dependency_fail_closed_without_fallback(self):
        for blocked in (False, True):
            with self.subTest(blocked=blocked), absent_engine(), controlled_finders():
                if blocked:
                    sys.modules[NAME] = None
                with self.assertRaises(ImportError) as raised:
                    adapter.load_unicode()
                self.assertEqual(str(raised.exception), "unicode_runtime_dependency_unavailable")
                self.assertIsNone(raised.exception.__context__)
                self.assertEqual(NAME in sys.modules, blocked)

    def test_short_noncanonical_custom_state_and_non_windows_keep_standard_import(self):
        for platform, origin, state in (
            ("nt", "C:\\native\\unicodedata2.pyd", None),
            ("nt", "C:\\native\\..\\native\\unicodedata2.pyd", None),
            ("nt", "C:\\native\\.\\unicodedata2.pyd", None),
            ("nt", "C:/native/unicodedata2.pyd", None),
            ("nt", "C:\\native\\unicodedata2.pyd", {"custom": True}),
            ("posix", LONG_ORIGIN, None),
        ):
            spec = extension_spec(origin)
            spec.loader_state = state
            with self.subTest(platform=platform, spelling=origin.count(".")), \
                 controlled_finders(spec, platform=platform) as selected, \
                 mock.patch.object(adapter.os.path, "samefile", side_effect=AssertionError):
                observed = adapter._FINDER.find_spec(NAME)
                self.assertIs(observed, spec if platform == "nt" else None)
                self.assertEqual(selected.call_count, int(platform == "nt"))
                if platform == "posix":
                    self.assertNotIn(adapter._FINDER, sys.meta_path)

    def test_length_is_utf16_and_unc_keeps_the_same_selected_file(self):
        for origin, extended in (
            ("C:\\" + "a" * 242 + "unicodedata2.pyd", "\\\\?\\C:\\" + "a" * 242 + "unicodedata2.pyd"),
            ("C:\\" + "\U0001f600" * 130 + "\\unicodedata2.pyd", "\\\\?\\C:\\" + "\U0001f600" * 130 + "\\unicodedata2.pyd"),
            ("\\\\server\\share\\" + "b" * 245 + "\\unicodedata2.pyd", "\\\\?\\UNC\\server\\share\\" + "b" * 245 + "\\unicodedata2.pyd"),
        ):
            with self.subTest(kind="unc" if origin.startswith("\\\\") else "drive"), \
                 controlled_finders(extension_spec(origin)), \
                 mock.patch.object(adapter.os.path, "samefile", return_value=True) as same:
                selected = adapter._FINDER.find_spec(NAME)
                self.assertEqual(selected.origin, extended)
                self.assertEqual(selected.loader.path, extended)
                self.assertIs(type(selected.loader), adapter._UnicodeExtensionLoader)
                same.assert_called_once_with(origin, extended)

    def test_exact_long_spec_boundary_and_no_path_normalization_or_substitution(self):
        cases = [extension_spec(origin) for origin in (
            "relative\\" + "a" * 260 + "\\unicodedata2.pyd",
            "C:\\a\\..\\" + "a" * 260 + "\\unicodedata2.pyd",
            "C:/" + "a" * 260 + "/unicodedata2.pyd",
            "\\\\.\\C:\\" + "a" * 260 + "\\unicodedata2.pyd",
        )]
        for attribute, value in (
            ("name", "other"), ("submodule_search_locations", []),
            ("loader_state", {"custom": True}), ("has_location", False),
        ):
            spec = extension_spec()
            setattr(spec, attribute, value)
            cases.append(spec)
        for attribute, value in (("name", "other"), ("path", "C:\\different\\unicodedata2.pyd")):
            spec = extension_spec()
            setattr(spec.loader, attribute, value)
            cases.append(spec)
        for index, spec in enumerate(cases):
            with self.subTest(case=index), controlled_finders(spec):
                with self.assertRaises(ImportError) as raised:
                    adapter._FINDER.find_spec(NAME)
                self.assertEqual(str(raised.exception), "unicode_runtime_dependency_unavailable")
                self.assertIsNone(raised.exception.__context__)
        with controlled_finders(extension_spec()), \
             mock.patch.object(adapter.os.path, "samefile", return_value=False):
            with self.assertRaisesRegex(ImportError, "^unicode_runtime_dependency_unavailable$"):
                adapter._FINDER.find_spec(NAME)

    def test_nonstandard_loader_and_already_extended_origin_are_not_replaced(self):
        class CustomExtension(machinery.ExtensionFileLoader):
            pass

        custom = util.spec_from_file_location(NAME, LONG_ORIGIN, loader=CustomExtension(NAME, LONG_ORIGIN))
        for spec in (custom, extension_spec("\\\\?\\" + LONG_ORIGIN)):
            with controlled_finders(spec), \
                 mock.patch.object(adapter.os.path, "samefile", side_effect=AssertionError):
                self.assertIs(adapter._FINDER.find_spec(NAME), spec)

    def test_registration_is_lazy_non_target_is_zero_io_and_reload_is_idempotent(self):
        with controlled_finders(extension_spec()) as selected, \
             mock.patch.object(adapter.os.path, "samefile", side_effect=AssertionError):
            hook = adapter._FINDER
            self.assertIsNone(hook.find_spec("another_module"))
            self.assertIsNone(hook.find_spec(NAME, ["explicit-subpackage"]))
            selected.assert_not_called()
            before = tuple(sys.meta_path)
            adapter.register_unicode_finder()
            importlib.reload(adapter)
            adapter.register_unicode_finder()
            self.assertIs(adapter._FINDER, hook)
            self.assertEqual(tuple(sys.meta_path), before)
            self.assertNotIn("_bootstrap", vars(adapter))

    def test_early_and_late_custom_finder_precedence_is_preserved(self):
        class SelectedLoader:
            def create_module(self, _spec):
                return None

            def exec_module(self, module):
                module.selected_by_host = True

        class HostFinder:
            def find_spec(self, fullname, path=None, target=None):
                return machinery.ModuleSpec(NAME, SelectedLoader()) if fullname == NAME else None

        for late in (False, True):
            with self.subTest(late=late), absent_engine(), controlled_finders(extension_spec()) as selected:
                hook_index = next(i for i, entry in enumerate(sys.meta_path) if entry is adapter._FINDER)
                sys.meta_path.insert(hook_index + int(late), HostFinder())
                self.assertTrue(importlib.import_module(NAME).selected_by_host)
                selected.assert_not_called()
                before = tuple(sys.meta_path)
                adapter.register_unicode_finder()
                self.assertEqual(tuple(sys.meta_path), before)

    def test_real_stateful_path_entry_finder_is_consulted_once(self):
        class Loader:
            def create_module(self, spec):
                return None

            def exec_module(self, module):
                module.complete = True

        class StatefulEntry:
            calls = 0

            def find_spec(self, fullname, target=None):
                if fullname != NAME:
                    return None
                self.calls += 1
                return machinery.ModuleSpec(NAME, Loader()) if self.calls == 1 else None

        for hooked in (False, True):
            entry = StatefulEntry()
            entries = [adapter._PATH_FINDER]
            with self.subTest(hooked=hooked), absent_engine(), \
                 mock.patch.object(sys, "meta_path", entries), \
                 mock.patch.object(sys, "path", ["synthetic-unicode-entry"]), \
                 mock.patch.dict(sys.path_importer_cache, {"synthetic-unicode-entry": entry}), \
                 mock.patch.object(adapter.os, "name", "nt"):
                if hooked:
                    adapter.register_unicode_finder()
                self.assertTrue(importlib.import_module(NAME).complete)
                self.assertEqual(entry.calls, 1)

    def test_missing_replaced_duplicate_or_moved_pathfinder_is_never_guessed(self):
        for entries in ([], [object()], [adapter._PATH_FINDER, adapter._PATH_FINDER]):
            with mock.patch.object(sys, "meta_path", list(entries)), mock.patch.object(adapter.os, "name", "nt"):
                adapter.register_unicode_finder()
                self.assertEqual(sys.meta_path, entries)
        with controlled_finders(extension_spec()) as selected:
            sys.meta_path.remove(adapter._PATH_FINDER)
            self.assertIsNone(adapter._FINDER.find_spec(NAME))
            selected.assert_not_called()
        with controlled_finders(extension_spec()) as selected, \
             mock.patch.object(adapter.machinery, "PathFinder", object()):
            self.assertIsNone(adapter._FINDER.find_spec(NAME))
            selected.assert_not_called()

    def test_stable_pathfinder_miss_still_reaches_later_meta_finder(self):
        class LaterLoader:
            def create_module(self, spec):
                return None

            def exec_module(self, module):
                module.selected_later = True

        class LaterFinder:
            def find_spec(self, fullname, path=None, target=None):
                return machinery.ModuleSpec(NAME, LaterLoader()) if fullname == NAME else None

        with absent_engine(), controlled_finders() as selected:
            position = next(i for i, entry in enumerate(sys.meta_path) if entry is adapter._PATH_FINDER)
            sys.meta_path.insert(position + 1, LaterFinder())
            self.assertTrue(importlib.import_module(NAME).selected_later)
            # A miss intentionally yields to the untouched PathFinder and
            # later meta finders; it is not promoted to an import failure.
            self.assertEqual(selected.call_count, 2)

    def test_create_and_exec_failure_keep_standard_cleanup_and_private_errors_hidden(self):
        for boundary in ("create", "exec"):
            for use_facade in (False, True):
                with self.subTest(boundary=boundary, facade=use_facade), absent_engine(), \
                     controlled_finders(extension_spec()), \
                     mock.patch.object(adapter.os.path, "samefile", return_value=True), \
                     mock.patch.object(machinery.ExtensionFileLoader, "create_module", side_effect=ImportError("private-value") if boundary == "create" else None, return_value=ModuleType(NAME)) as create, \
                     mock.patch.object(machinery.ExtensionFileLoader, "exec_module", side_effect=OSError("private-value")) as execute:
                    with self.assertRaises(ImportError) as raised:
                        adapter.load_unicode() if use_facade else importlib.import_module(NAME)
                    self.assertEqual(str(raised.exception), "unicode_runtime_dependency_unavailable")
                    self.assertIsNone(raised.exception.__context__)
                    self.assertNotIn(NAME, sys.modules)
                    create.assert_called_once()
                    self.assertEqual(execute.call_count, int(boundary == "exec"))

    def test_forwarders_keep_success_results_and_do_not_swallow_base_exceptions(self):
        loader = adapter._UnicodeExtensionLoader(NAME, "\\\\?\\" + LONG_ORIGIN)
        marker = object()
        for name in ("create_module", "exec_module"):
            with mock.patch.object(machinery.ExtensionFileLoader, name, return_value=marker) as forward:
                self.assertIs(getattr(loader, name)(marker), marker)
                forward.assert_called_once_with(marker)
            for kind in (KeyboardInterrupt, SystemExit):
                with mock.patch.object(machinery.ExtensionFileLoader, name, side_effect=kind):
                    with self.assertRaises(kind):
                        getattr(loader, name)(marker)

    def test_raw_import_waits_for_standard_initialization_and_gets_same_module(self):
        entered, release, raw_started, raw_done = (threading.Event() for _ in range(4))
        results, failures, initial = [], [], []

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

        path_before, meta_before = list(sys.path), list(sys.meta_path)
        with absent_engine(), controlled_finders(extension_spec()), \
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

    def test_package_and_checkout_version_stay_lazy_when_native_engine_is_unavailable(self):
        script = r'''
import contextlib, io, json, sys
sys.path.insert(0, sys.argv[1])
class BlockNative:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "unicodedata2":
            raise ImportError("native-unavailable")
sys.meta_path.insert(0, BlockNative())
import wom_kit
from wom_kit import cli_entry
capture = io.StringIO()
with contextlib.redirect_stdout(capture):
    code = cli_entry.main(["--version"])
print(json.dumps({"ok": code == 0, "version": capture.getvalue() == "archive " + wom_kit.__version__ + "\n",
                  "lazy": not any(name in sys.modules for name in ("unicodedata2", "argparse", "wom_kit.archive_services", "wom_kit.archive_cli"))}))
'''
        for source in (SRC, KIT.parent):
            with self.subTest(checkout=source == KIT.parent):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", script, str(source)],
                    capture_output=True, text=True, timeout=30, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self.assertEqual(result.returncode, 0, "lazy_version_nonzero")
                self.assertFalse(bool(result.stderr), "lazy_version_stderr_present")
                self.assertEqual(json.loads(result.stdout), {"ok": True, "version": True, "lazy": True})

    def test_exact_historical_helper_schema_and_fingerprint_survive_actual_index_reopen(self):
        from wom_kit import archive_services, private_objet_metadata
        from wom_kit import private_objet_metadata_index as index
        from wom_kit import private_objet_metadata_index_authority as authority
        from wom_kit import private_objet_metadata_index_health as health
        from wom_kit import private_objet_metadata_index_session as session

        self.assertEqual(hashlib.sha256(Path(private_objet_metadata.__file__).read_bytes()).hexdigest(), HISTORICAL_HELPER_SHA)
        self.assertEqual(index.NORMALIZATION_HELPER_SHA256, "sha256:" + HISTORICAL_HELPER_SHA)
        self.assertEqual(authority.NORMALIZATION_HELPER_SHA256, "sha256:" + HISTORICAL_HELPER_SHA)
        self.assertEqual(index.GENERATED_SCHEMA_MANIFEST_SHA256, "sha256:" + HISTORICAL_MANIFEST_SHA)
        authority._verify_package_pins()
        manifest = KIT / "schemas" / "private-objet-generated-schema-manifest-v0.1.json"
        self.assertEqual(manifest.read_bytes(), index.GENERATED_SCHEMA_MANIFEST_BYTES)
        self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(), HISTORICAL_MANIFEST_SHA)

        with tempfile.TemporaryDirectory(prefix="wom-unicode-index-") as temporary:
            root = Path(temporary) / "archive"
            shutil.copytree(KIT / "examples" / "fake-life-archive", root)
            preserve = {
                path.relative_to(root): path.read_bytes()
                for directory in (root / "zettels", root / "receipts") if directory.is_dir()
                for path in directory.rglob("*") if path.is_file()
            }
            # These exact schema and fingerprint literals predate the adapter.
            # Reopen that projection, then use the actual public index writer.
            db = root / session.PRIVATE_INDEX_RELATIVE_PATH
            db.parent.mkdir(exist_ok=True)
            capture = authority._capture_private_objet_index_authority(root, "unicode-index-compatibility")
            projection = index._compile_private_objet_index_projection(capture.compiler_input)
            with sqlite3.connect(db) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("BEGIN IMMEDIATE")
                index.install_private_objet_index_projection(connection, projection)
            connection.close()
            self.assertIn(health.evaluate_private_objet_metadata_index_health(root, "unicode-index-compatibility").case_id, {"C10", "C11"})
            result = archive_services.index_archive(root)
            self.assertTrue(result.get("ok", True))
            with sqlite3.connect(db) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                index.verify_private_objet_index_schema(connection)
                self.assertEqual(connection.execute("SELECT count(*) FROM private_objet_index_metadata").fetchone()[0], 1)
            connection.close()
            self.assertEqual(preserve, {relative: (root / relative).read_bytes() for relative in preserve})

    @unittest.skipUnless(os.name == "nt", "Windows native-extension path contract")
    def test_actual_long_native_raw_import_and_bad_binary_fail_without_fallback(self):
        original = Path(importlib.import_module(NAME).__file__)
        self.assertEqual(original.suffix, ".pyd")
        original_bytes = original.read_bytes()
        with tempfile.TemporaryDirectory(prefix="wom-unicode-native-") as temporary:
            native = Path(temporary)
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
before_path = list(sys.path)
adapter.register_unicode_finder()
before_meta = list(sys.meta_path)
try:
    import unicodedata2 as module
except ImportError as error:
    print(json.dumps({"state": "blocked", "fixed_error": str(error) == "unicode_runtime_dependency_unavailable",
                      "no_context": error.__context__ is None, "no_cached_module": "unicodedata2" not in sys.modules}))
else:
    print(json.dumps({"state": "loaded", "pinned": module.unidata_version == "17.0.0",
                      "normalized": module.normalize("NFC", "e\u0301") == "\u00e9",
                      "same_alias": module is adapter.load_unicode(),
                      "extended_origin": module.__file__.startswith("\\\\?\\"),
                      "search_paths_unchanged": sys.path == before_path and sys.meta_path == before_meta}))
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
                    expected = (
                        {"state": "blocked", "fixed_error": True, "no_context": True, "no_cached_module": True}
                        if corrupted else
                        {"state": "loaded", "pinned": True, "normalized": True, "same_alias": True,
                         "extended_origin": True, "search_paths_unchanged": True}
                    )
                    self.assertEqual(json.loads(result.stdout), expected)


if __name__ == "__main__":
    unittest.main()
