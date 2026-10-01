"""Beta letter 179: an R2 connection made earlier is reused, not typed in again.

The operator had connected R2 before through a key file that an earlier
script read. WOM asked for the two keys again in masked windows. Now the
human names that file and the two field names; an isolated child reads it and
stores the keys in the Windows Credential Manager; the parent, the chat, argv
and stdout never see a value. A test double stands in for the native facade
and the child; no real window, credential or key is used.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval_windows as windows
from wom_kit import object_storage_credential_store as store
from wom_kit import work_session_permission as permission
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation

import test_letter177_object_storage_credential_store as fixture
import test_v0433_object_storage_upload as _upload_fixture

ACCESS = fixture.ACCESS
SECRET = fixture.SECRET
FIELDS = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


class KeyFileImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()

    def write(self, name, text):
        path = self.folder / name
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path

    def run_import(self, path, fields=FIELDS, *, existing=(), replace=False):
        facade = fixture.FakeFacade([], existing=existing)
        status = store.import_from_file(facade, slug="r2-main", source_path=str(path), fields=fields,
                                        replace_existing=replace)
        return status, facade

    def test_dotenv_ini_and_json_files_are_read(self):
        cases = {
            "keys.env": b"# old connection\nexport R2_ACCESS_KEY_ID=" + ACCESS + b"\nR2_SECRET_ACCESS_KEY=\"" + SECRET + b"\"\n",
            "rclone.conf": b"[r2]\ntype = s3\naccess_key_id = " + ACCESS + b"\nsecret_access_key = " + SECRET + b"\n",
            "keys.json": json.dumps({"r2": {"access": ACCESS.decode(), "secret": SECRET.decode()}}).encode(),
        }
        fields = {"keys.env": FIELDS, "rclone.conf": ("r2.access_key_id", "r2.secret_access_key"),
                  "keys.json": ("r2.access", "r2.secret")}
        for name, raw in cases.items():
            with self.subTest(name=name):
                status, facade = self.run_import(self.write(name, raw), fields[name])
                self.assertTrue(status["ok"], status)
                self.assertEqual(facade.store["wom-object-storage.r2-main.access-key-id"], ACCESS)
                self.assertEqual(facade.store["wom-object-storage.r2-main.secret-access-key"], SECRET)
                self.assertNotIn(ACCESS.decode(), json.dumps(status))

    def test_missing_ambiguous_and_invalid_values_are_refused_without_writes(self):
        path = self.write("missing.env", b"R2_ACCESS_KEY_ID=" + ACCESS + b"\n")
        status, facade = self.run_import(path)
        self.assertEqual(status["code"], "object_storage_credential_source_field_missing")
        self.assertEqual(facade.store, {})
        path = self.write("twice.conf", b"[a]\nkey = " + ACCESS + b"\n[b]\nkey = " + SECRET + b"\nsecret = " + SECRET + b"\n")
        status, _facade = self.run_import(path, ("key", "secret"))
        self.assertEqual(status["code"], "object_storage_credential_source_field_ambiguous")
        path = self.write("short.env", b"R2_ACCESS_KEY_ID=short\nR2_SECRET_ACCESS_KEY=" + SECRET + b"\n")
        status, facade = self.run_import(path)
        self.assertEqual(status["code"], "object_storage_credential_input_invalid")
        self.assertEqual(facade.store, {})

    def test_existing_keys_need_replace(self):
        path = self.write("keys.env", b"R2_ACCESS_KEY_ID=" + ACCESS + b"\nR2_SECRET_ACCESS_KEY=" + SECRET + b"\n")
        status, _facade = self.run_import(path, existing=("wom-object-storage.r2-main.access-key-id",))
        self.assertEqual(status["code"], "object_storage_credential_exists")
        status, facade = self.run_import(path, existing=("wom-object-storage.r2-main.access-key-id",), replace=True)
        self.assertTrue(status["ok"])
        self.assertTrue(status["replaced_existing"])

    def test_the_plan_binds_the_file_without_reading_or_echoing_it(self):
        path = self.write("keys.env", b"R2_ACCESS_KEY_ID=" + ACCESS + b"\nR2_SECRET_ACCESS_KEY=" + SECRET + b"\n")
        first = store.import_plan(archive_id="archive:test", slug="r2-main", replace_existing=False, source_path=path,
                                  access_field=FIELDS[0], secret_field=FIELDS[1])
        rendered = json.dumps(first)
        self.assertNotIn(str(self.folder), rendered)
        self.assertNotIn(ACCESS.decode(), rendered)
        self.assertEqual(first["popup_count"], 0)
        os.utime(path, ns=(1, 1))
        second = store.import_plan(archive_id="archive:test", slug="r2-main", replace_existing=False, source_path=path,
                                   access_field=FIELDS[0], secret_field=FIELDS[1])
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])
        with self.assertRaises(store.ObjectStorageCredentialStoreError):
            store.import_plan(archive_id="archive:test", slug="r2-main", replace_existing=False,
                              source_path="relative.env", access_field=FIELDS[0], secret_field=FIELDS[1])


class KeyFileImportCliTests(unittest.TestCase):
    """Borrows the v0.4.33 CLI fixture (fake dialog) without its tests."""

    for _name, _value in vars(_upload_fixture.UploadCliTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def test_one_dialog_imports_the_file_and_returns_only_refs(self):
        with tempfile.TemporaryDirectory() as temporary:
            key_file = Path(temporary) / "old-r2.env"
            key_file.write_bytes(b"R2_ACCESS_KEY_ID=" + ACCESS + b"\nR2_SECRET_ACCESS_KEY=" + SECRET + b"\n")
            facade = fixture.FakeFacade([])

            def in_process(*, slug, source_path, fields, replace_existing):
                return store.import_from_file(facade, slug=slug, source_path=source_path, fields=fields,
                                              replace_existing=replace_existing)

            base = ["object-storage-credential-store", str(self.archive.root), "--store-slug", "r2-main",
                    "--from-file", str(key_file), "--access-key-field", FIELDS[0],
                    "--secret-access-key-field", FIELDS[1]]
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = cli.main([*base, "--dry-run"])
            plan = json.loads(out.getvalue())
            self.assertEqual(code, 0, plan)
            self.assertEqual(self.native.calls, 0)
            out = io.StringIO()
            with patch.object(store, "run_isolated_import", side_effect=in_process), \
                    patch.object(store, "windows_available", return_value=True), \
                    redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = cli.main([*base, "--approve", "--expected-request-sha256", plan["request_sha256"],
                                 "--reviewed-by", _upload_fixture.REVIEWER])
            result = json.loads(out.getvalue())
            self.assertEqual(code, 0, result)
            self.assertTrue(result["stored"])
            self.assertEqual(self.native.calls, 1)
            self.assertEqual(result["credential_refs"]["access_key_id_ref"],
                             "credential-manager:wom-object-storage.r2-main.access-key-id")
            rendered = out.getvalue()
            self.assertNotIn(ACCESS.decode(), rendered)
            self.assertNotIn(str(key_file), rendered)
            self.assertEqual(facade.store["wom-object-storage.r2-main.secret-access-key"], SECRET)

    def test_the_import_kind_is_grantable_and_its_copy_is_korean(self):
        kind = ExactHumanApprovalOperation.object_storage_credential_import
        self.assertIn(kind, permission.GRANTABLE_OPERATIONS)
        for table in (windows._OPERATION_LABELS, windows._OPERATION_QUESTIONS, windows._OPERATION_SUMMARIES,
                      windows._OPERATION_APPROVE_BUTTONS):
            self.assertIn(kind, table)
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))


if __name__ == "__main__":
    unittest.main()
