"""v0.4.42: imap-mailbox-message-fetch keeps whole messages losslessly.

Beta letters asked to keep whole mail with attachments. The dry-run reads no
credential and opens no connection; `--approve` fetches after one exact
approval bound to the plan digest, opens the mailbox read-only, fetches with
BODY.PEEK[] so no flag changes, and writes raw `.eml` files plus a ready
source-intake-batch request and a receipt. The IMAP client, native dialog and
archive key are all fakes.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status, imap_message_fetch
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-mail-reviewer"
MESSAGES = {
    b"7": b"From: a@example.invalid\r\nSubject: first\r\n\r\nBody one\r\n",
    b"9": (
        b"From: b@example.invalid\r\nSubject: second\r\nMIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=x\r\n\r\n--x\r\nContent-Type: text/plain\r\n\r\nhi\r\n"
        b"--x\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename=a.bin\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\nAAEC\r\n--x--\r\n"
    ),
}


class _FakeImap:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def login(self, username, password):
        self.calls.append(("login", username, password))
        return ("OK", [b"logged in"])

    def select(self, mailbox, readonly=False):
        self.calls.append(("select", mailbox, readonly))
        return ("OK", [b"2"])

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "search":
            return ("OK", [b"7 9"])
        uid = args[0]
        return ("OK", [(b"1 (UID " + uid + b" BODY[] {n}", MESSAGES[uid]), b")"])

    def logout(self):
        self.calls.append(("logout",))
        return ("BYE", [])


class ImapMessageFetchTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-imap-fetch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        bindings = archive_services.load_source_bindings(self.root)
        bindings["sources"] = [*archive_services.source_bindings_list(bindings),
                               {"source_id": "mail-main", "source_type": "imap_mailbox"}]
        path = archive_services.archive_internal_path(self.root, "source-bindings.yml")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bindings), encoding="utf-8")
        self.native = lifecycle._PagedNative()
        self.client = _FakeImap()
        self.factory_calls: list[tuple] = []

        def factory(host, port, timeout):
            self.factory_calls.append((host, port, timeout))
            return self.client

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        stack.enter_context(patch.object(imap_message_fetch, "_client_factory", side_effect=factory))
        stack.enter_context(patch.dict("os.environ", {"WOM_TEST_IMAP_USER": "user@example.invalid",
                                                      "WOM_TEST_IMAP_PASS": "synthetic-app-password"}))

    def run_cli(self, *args: str) -> tuple[int, dict, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([
                "imap-mailbox-message-fetch", str(self.root), "--source-id", "mail-main", "--batch-id", "b1",
                "--imap-host", "imap.example.invalid", "--username-ref", "env:WOM_TEST_IMAP_USER",
                "--app-password-ref", "env:WOM_TEST_IMAP_PASS", *args, "--format", "json",
            ])
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_dry_run_reads_no_credential_and_opens_no_connection(self) -> None:
        code, plan, raw = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertRegex(plan["plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(self.factory_calls, [])
        self.assertEqual(plan["credential_reads"], 0)
        self.assertNotIn("imap.example.invalid", raw)
        self.assertNotIn("WOM_TEST_IMAP", raw)
        self.assertFalse((self.root / "workbench" / "imap-fetch" / "b1").exists())

    def test_approve_fetches_raw_messages_read_only_after_one_dialog(self) -> None:
        _code, plan, _raw = self.run_cli("--dry-run")
        code, result, raw = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                         "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["message_count"], 2)
        self.assertIn(("select", '"INBOX"', True), self.client.calls)
        fetches = [call for call in self.client.calls if call[:2] == ("uid", "fetch")]
        self.assertEqual([call[3] for call in fetches], ["(BODY.PEEK[])"] * 2)
        self.assertEqual([call[2] for call in fetches], [b"9", b"7"])  # newest first
        output = self.root / "workbench" / "imap-fetch" / "b1"
        self.assertEqual((output / "mail-0001.eml").read_bytes(), MESSAGES[b"9"])
        self.assertEqual((output / "mail-0002.eml").read_bytes(), MESSAGES[b"7"])
        request = json.loads((output / "source-intake-batch-request.json").read_text(encoding="utf-8"))
        self.assertEqual(request["schema"], "wom-kit/source-intake-batch-request/v0.1")
        self.assertEqual([item["mime"] for item in request["items"]], ["message/rfc822"] * 2)
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["files"][0]["sha256"], "sha256:" + hashlib.sha256(MESSAGES[b"9"]).hexdigest())
        self.assertFalse(receipt["server_flags_changed"])
        for secret in ("synthetic-app-password", "user@example.invalid", "Subject", "imap.example.invalid"):
            self.assertNotIn(secret, raw)
            self.assertNotIn(secret, json.dumps(receipt))

    def test_the_written_request_is_accepted_by_the_intake_batch_preview(self) -> None:
        _code, plan, _raw = self.run_cli("--dry-run")
        _code, result, _raw = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                           "--expected-plan-sha256", plan["plan_sha256"])
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = archive_cli.main(["source-intake-batch", str(self.root), "--manifest",
                                     str(self.root / result["intake_request"]), "--dry-run", "--format", "json"])
        preview = json.loads(out.getvalue())
        self.assertEqual(code, 0, preview)
        self.assertTrue(preview["ok"], preview)

    def test_a_changed_plan_is_refused_before_the_dialog(self) -> None:
        _code, plan, _raw = self.run_cli("--dry-run")
        code, error, _raw = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                         "--expected-plan-sha256", "sha256:" + "0" * 64)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["imap_mailbox_message_fetch_plan_changed"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self.factory_calls, [])

    def test_a_declined_dialog_reads_no_credential_and_writes_nothing(self) -> None:
        self.native.approve = False
        code, _error, _raw = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.factory_calls, [])
        self.assertFalse((self.root / "workbench" / "imap-fetch" / "b1").exists())

    def test_an_unregistered_source_is_blocked_before_the_dialog(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = archive_cli.main([
                "imap-mailbox-message-fetch", str(self.root), "--source-id", "not-there", "--batch-id", "b1",
                "--imap-host", "imap.example.invalid", "--username-ref", "env:WOM_TEST_IMAP_USER",
                "--app-password-ref", "env:WOM_TEST_IMAP_PASS", "--approve", "--reviewed-by", REVIEWER,
                "--format", "json",
            ])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["reason_codes"], ["imap_mailbox_message_fetch_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = imap_message_fetch.execute_fetch_approved(
            self.root, reviewed_by=REVIEWER, exact_human_approval_claim=None,
            expected_plan_sha256="sha256:" + "0" * 64, expected_exact_approval_plan_sha256=None,
            expected_exact_approval_target_binding_sha256=None, source_id="mail-main", batch_id="b1",
            imap_host="imap.example.invalid", username_ref="env:WOM_TEST_IMAP_USER",
            app_password_ref="env:WOM_TEST_IMAP_PASS",
        )
        self.assertEqual(result["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertEqual(self.factory_calls, [])


if __name__ == "__main__":
    unittest.main()
