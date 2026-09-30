"""Beta letter 177: object-storage keys go into the Windows Credential Manager through WOM's masked window.

Like the desktop apps' keychain: the human enters each key in the native
masked popup inside an isolated child; WOM writes exact, slash-free generic
targets and returns only the two credential-manager: refs, which survive
restarts and updates. A test double stands in for the native facade and the
child; no real window, credential or key is used.
"""

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import archive_services as services
from wom_kit import object_storage_credential_store as store
from wom_kit.credential_popup_windows import (
    CredentialPopupContext, CredentialPopupInputIntent, popup_instruction_text,
)
from wom_kit.credential_secure_intake import HumanSecretInputResult

KIT_ROOT = Path(__file__).resolve().parents[1]
ACCESS = b"SYNTHETICACCESSKEY0123456789ABCD"
SECRET = b"synthetic-secret-access-key-value-0123456789abcdef0123456789abcd"


class FakeFacade:
    def __init__(self, inputs, *, existing=(), fail_write_on=None):
        self.inputs = list(inputs)
        self.store = {name: b"old" for name in existing}
        self.fail_write_on = fail_write_on
        self.prompts, self.buffers = [], []

    def prompt_masked_secret(self, *, request_id, context):
        self.prompts.append((request_id, context.purpose))
        value = self.inputs.pop(0)
        if value is None:
            return HumanSecretInputResult(secret=None, credential_input_received=False,
                                          complete_line_received=False, cancelled=True)
        buffer = bytearray(value)
        self.buffers.append(buffer)
        return HumanSecretInputResult(secret=buffer, credential_input_received=True,
                                      complete_line_received=True, cancelled=False)

    def generic_exists(self, target):
        return target in self.store

    def write_generic(self, target, view):
        if self.fail_write_on and target.endswith(self.fail_write_on):
            raise OSError("synthetic write failure")
        self.store[target] = bytes(view)

    def delete_generic(self, target):
        self.store.pop(target, None)


class ObjectStorageCredentialStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)

    def test_refs_are_exact_slash_free_and_accepted_by_the_storage_writers(self):
        refs = store.refs("r2-main")
        self.assertEqual(refs, {"access_key_id_ref": "credential-manager:wom-object-storage.r2-main.access-key-id",
                                "secret_access_key_ref": "credential-manager:wom-object-storage.r2-main.secret-access-key"})
        blockers = []
        services._object_storage_validate_credential_refs(blockers=blockers, **refs)
        self.assertEqual(blockers, [])
        for bad in ("R2", "r2/main", "-r2", "a" * 60, ""):
            with self.assertRaises(store.ObjectStorageCredentialStoreError):
                store.targets(bad)

    def test_enroll_writes_both_keys_and_wipes_the_buffers(self):
        facade = FakeFacade([ACCESS, SECRET])
        status = store.enroll(facade, slug="r2-main", store_label="R2 main", replace_existing=False)
        self.assertTrue(status["ok"], status)
        names = store.targets("r2-main")
        self.assertEqual(facade.store[names["access_key_id"]], ACCESS)
        self.assertEqual(facade.store[names["secret_access_key"]], SECRET)
        self.assertEqual([purpose for _id, purpose in facade.prompts],
                         ["object_storage_access_key_id", "object_storage_secret_access_key"])
        self.assertTrue(all(not any(buffer) for buffer in facade.buffers))
        self.assertNotIn(ACCESS.decode(), json.dumps(status))

    def test_existing_cancelled_invalid_and_failed_writes_leave_no_half_pair(self):
        names = store.targets("r2-main")
        existing = FakeFacade([ACCESS, SECRET], existing=[names["access_key_id"]])
        self.assertEqual(store.enroll(existing, slug="r2-main", store_label="R2", replace_existing=False)["code"],
                         "object_storage_credential_exists")
        self.assertEqual(existing.prompts, [])
        self.assertTrue(store.enroll(FakeFacade([ACCESS, SECRET], existing=[names["access_key_id"]]),
                                     slug="r2-main", store_label="R2", replace_existing=True)["replaced_existing"])
        cancelled = FakeFacade([ACCESS, None])
        self.assertEqual(store.enroll(cancelled, slug="r2-main", store_label="R2", replace_existing=False)["code"],
                         "object_storage_credential_cancelled")
        self.assertEqual(cancelled.store, {})
        invalid = FakeFacade([b"short", SECRET])
        self.assertEqual(store.enroll(invalid, slug="r2-main", store_label="R2", replace_existing=False)["code"],
                         "object_storage_credential_input_invalid")
        self.assertEqual(invalid.store, {})
        broken = FakeFacade([ACCESS, SECRET], fail_write_on="secret-access-key")
        status = store.enroll(broken, slug="r2-main", store_label="R2", replace_existing=False)
        self.assertEqual(status["code"], "object_storage_credential_write_failed")
        self.assertTrue(status["partial_writes_rolled_back"])
        self.assertEqual(broken.store, {})

    def test_popup_text_names_object_storage_and_refuses_other_purposes(self):
        context = CredentialPopupContext(provider="object_storage", purpose="object_storage_access_key_id",
                                         account_label="R2 main", workspace_label="Access Key ID",
                                         task_summary="synthetic task", connection_reason="synthetic reason")
        text = popup_instruction_text(context, input_intent=CredentialPopupInputIntent.live_registration)
        self.assertIn("오브젝트 스토리지 / R2 main / Access Key ID", text)
        with self.assertRaises(Exception):
            popup_instruction_text(CredentialPopupContext(
                provider="object_storage", purpose="notion_page_recovery", account_label="x",
                workspace_label="y", task_summary="t", connection_reason="r"),
                input_intent=CredentialPopupInputIntent.live_registration)

    def call(self, *flags):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = cli.main(["object-storage-credential-store", str(self.root), "--store-slug", "r2-main", *flags])
        return code, json.loads(out.getvalue())

    def test_cli_previews_then_stores_through_the_isolated_worker_and_lists_the_refs(self):
        code, preview = self.call("--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["credential_refs"], store.refs("r2-main"))
        code, refused = self.call("--approve", "--expected-request-sha256", "sha256:" + "0" * 64)
        self.assertEqual(refused["reason_code"], "object_storage_credential_request_changed")
        with patch.object(store, "run_isolated", return_value={"ok": True, "code": None, "writes_performed": True,
                                                                 "replaced_existing": False}) as worker, \
                patch.object(store, "windows_available", return_value=True):
            code, stored = self.call("--approve", "--expected-request-sha256", preview["request_sha256"])
        self.assertEqual(code, 0, stored)
        self.assertTrue(stored["stored"])
        self.assertEqual(worker.call_args.kwargs["slug"], "r2-main")
        record = self.root / stored["record_path"]
        self.assertFalse(json.loads(record.read_text(encoding="utf-8"))["key_values_recorded"])
        self.assertEqual(store.list_records(self.root)[0]["credential_refs"], store.refs("r2-main"))
        with patch.object(store, "run_isolated", return_value={"ok": False, "code": "object_storage_credential_cancelled"}), \
                patch.object(store, "windows_available", return_value=True):
            code, cancelled = self.call("--approve", "--expected-request-sha256", preview["request_sha256"])
        self.assertEqual(code, 1)
        self.assertEqual(cancelled["reason_code"], "object_storage_credential_cancelled")
        self.assertEqual(cancelled["effects_state"], "none")
        with patch.object(store, "windows_available", return_value=False):
            code, elsewhere = self.call("--approve", "--expected-request-sha256", preview["request_sha256"])
        self.assertEqual(elsewhere["reason_code"], "object_storage_credential_windows_required")


if __name__ == "__main__":
    unittest.main()
