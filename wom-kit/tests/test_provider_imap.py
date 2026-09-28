"""Synthetic provider tests: no real accounts, credential store or network."""
from email.message import EmailMessage
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_services, imap_message_fetch, provider_imap


class Client:
    def __init__(self, messages, epoch=b"10", failed=()):
        self.messages, self.epoch, self.failed = messages, epoch, failed
        self.calls = []
        self.selected_mailboxes = []

    def login(self, *_):
        return "OK", []

    def select(self, mailbox, readonly=False):
        assert readonly is True
        self.selected_mailboxes.append(mailbox)
        return "OK", []

    def response(self, _):
        return "UIDVALIDITY", [self.epoch]

    def uid(self, operation, *args):
        if operation == "search":
            return "OK", [b" ".join(self.messages)]
        assert args[1] == "(BODY.PEEK[])"
        self.calls.append(args[0])
        return ("NO", []) if args[0] in self.failed else ("OK", [(b"literal", self.messages[args[0]])])

    def logout(self):
        pass


def message(body="hello"):
    msg = EmailMessage()
    msg["Message-ID"] = "<same@example.invalid>"
    msg.set_content(body)
    msg.add_attachment(b"\x00\x01\xfe", maintype="application", subtype="octet-stream", filename="../unsafe.bin")
    return msg.as_bytes()


class ImapIncrementalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)
        bindings = archive_services.load_source_bindings(self.root)
        bindings["sources"] = [*archive_services.source_bindings_list(bindings), {"source_id": "mail-synthetic", "source_type": "imap_mailbox"}]
        archive_services.archive_internal_path(self.root, "source-bindings.yml").write_text(json.dumps(bindings), encoding="utf-8")
        self.args = dict(source_id="mail-synthetic", batch_id="first", imap_host="mail.example.invalid",
            username_ref="env:SYNTHETIC_USER", app_password_ref="env:SYNTHETIC_PASSWORD", sync=True, extract_mime=True)

    def fetch(self, client, **kwargs):
        args = {**self.args, **kwargs}
        plan = imap_message_fetch.plan_fetch(self.root, **args)
        self.assertTrue(plan["ok"], plan)
        with patch.object(imap_message_fetch, "_client_factory", return_value=client):
            return imap_message_fetch.execute_fetch(self.root, **args, expected_plan_sha256=plan["plan_sha256"], environment=lambda _: "synthetic")

    def test_two_runs_fetch_only_new_uid_and_stage_body_attachment(self):
        first = self.fetch(Client({b"4": message()}))
        self.assertTrue(first["ok"], first)
        run = json.loads((self.root / first["receipt_path"]).read_text())
        attachment = run["occurrences"][0]["parts"][0]
        self.assertEqual((self.root / attachment["path"]).read_bytes(), b"\x00\x01\xfe")
        self.assertEqual(attachment["filename"], "../unsafe.bin")
        self.assertNotIn("unsafe", attachment["path"])
        client = Client({b"4": message(), b"8": message("new")})
        second = self.fetch(client, batch_id="second")
        self.assertTrue(second["ok"], second)
        self.assertEqual(client.calls, [b"8"])
        self.assertEqual(second["message_count"], 1)

    def test_same_uid_in_two_accounts_and_mailboxes_keeps_separate_progress(self):
        bindings = archive_services.load_source_bindings(self.root)
        bindings["sources"] = [*archive_services.source_bindings_list(bindings),
            {"source_id": "mail-synthetic-other", "source_type": "imap_mailbox"}]
        archive_services.archive_internal_path(self.root, "source-bindings.yml").write_text(
            json.dumps(bindings), encoding="utf-8")
        first_client = Client({b"4": message("account-one-body")})
        first = self.fetch(first_client, mailbox="INBOX")
        second_client = Client({b"4": message("account-two-body")})
        second = self.fetch(second_client, source_id="mail-synthetic-other", batch_id="other",
            username_ref="env:SYNTHETIC_OTHER_USER", mailbox="Archive")
        third_client = Client({b"4": message("account-one-other-folder")})
        third = self.fetch(third_client, batch_id="folder", mailbox="Archive")
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        self.assertTrue(third["ok"], third)
        self.assertEqual(first_client.calls, [b"4"])
        self.assertEqual(second_client.calls, [b"4"])
        self.assertEqual(third_client.calls, [b"4"])
        self.assertEqual(first_client.selected_mailboxes, ['"INBOX"'])
        self.assertEqual(second_client.selected_mailboxes, ['"Archive"'])
        self.assertEqual(third_client.selected_mailboxes, ['"Archive"'])
        self.assertNotEqual(first["receipt_path"], second["receipt_path"])
        self.assertNotEqual(first["receipt_path"], third["receipt_path"])
        first_receipt = json.loads((self.root / first["receipt_path"]).read_text())
        second_receipt = json.loads((self.root / second["receipt_path"]).read_text())
        third_receipt = json.loads((self.root / third["receipt_path"]).read_text())
        self.assertNotEqual(first_receipt["occurrences"][0]["raw"]["sha256"],
            second_receipt["occurrences"][0]["raw"]["sha256"])
        self.assertNotEqual(first_receipt["occurrences"][0]["raw"]["sha256"],
            third_receipt["occurrences"][0]["raw"]["sha256"])

    def test_partial_run_resumes_missing_lower_uid(self):
        first = self.fetch(Client({b"4": message(), b"8": message("new")}, failed={b"4"}))
        self.assertFalse(first["ok"])
        client = Client({b"4": message(), b"8": message("new")})
        second = self.fetch(client, resume=True)
        self.assertTrue(second["ok"], second)
        self.assertEqual(client.calls, [b"4"])
        run = json.loads((self.root / second["receipt_path"]).read_text())
        self.assertEqual(len(run["occurrences"]), 2)
        self.assertEqual(len(run["items"]), 6)

    def test_new_epoch_refetches_but_deduplicates_identical_bytes(self):
        raw = message()
        first = self.fetch(Client({b"4": raw}))
        before = set((self.root / "workbench/provider-blobs").iterdir())
        client = Client({b"4": raw}, epoch=b"11")
        second = self.fetch(client, batch_id="second")
        self.assertTrue(second["ok"], second)
        self.assertEqual(client.calls, [b"4"])
        self.assertEqual(before, set((self.root / "workbench/provider-blobs").iterdir()))

    def test_same_message_id_never_collapses_different_bytes(self):
        result = self.fetch(Client({b"4": message("a"), b"8": message("b")}))
        run = json.loads((self.root / result["receipt_path"]).read_text())
        self.assertNotEqual(run["occurrences"][0]["raw"]["sha256"], run["occurrences"][1]["raw"]["sha256"])

    def test_changed_completed_source_is_not_silently_skipped(self):
        first = self.fetch(Client({b"4": message()}))
        run = json.loads((self.root / first["receipt_path"]).read_text())
        (self.root / run["occurrences"][0]["raw"]["path"]).write_bytes(b"changed")
        second = self.fetch(Client({b"4": message()}), batch_id="second")
        self.assertFalse(second["ok"])
        self.assertEqual(second["reason_code"], "imap_completed_source_missing_or_changed")

    def test_no_uidvalidity_means_no_false_incremental_success(self):
        second = self.fetch(Client({b"4": message()}, epoch=b""))
        self.assertFalse(second["ok"])
        self.assertEqual(second["message_count"], 0)

    def test_resume_raw_only_run_can_add_mime_bindings_without_losing_occurrence(self):
        raw = message()
        first = self.fetch(Client({b"4": raw}), extract_mime=False)
        self.assertTrue(first["ok"])
        second = self.fetch(Client({b"4": raw}), resume=True)
        self.assertTrue(second["ok"], second)
        run = json.loads((self.root / second["receipt_path"]).read_text())
        self.assertEqual(len(run["occurrences"]), 1)
        self.assertTrue(run["occurrences"][0]["mime_extracted"])
        self.assertEqual(len(run["occurrences"][0]["parts"]), 1)
        self.assertEqual(len(run["items"]), 3)


class MimeTests(unittest.TestCase):
    def test_html_fallback_does_not_extract_active_content(self):
        msg = EmailMessage()
        msg.set_content("<p>hello &amp; world</p><script>secret</script>", subtype="html")
        text, parts, warnings = provider_imap.extract_mime(msg.as_bytes())
        self.assertIn(b"hello & world", text)
        self.assertNotIn(b"secret", text)
        self.assertEqual(parts, ())

    def test_plain_alternative_is_preferred_and_inline_image_preserved(self):
        msg = EmailMessage()
        msg.set_content("plain")
        msg.add_alternative("<p>html</p>", subtype="html")
        msg.get_payload()[1].add_related(b"image", maintype="image", subtype="png", cid="<synthetic-cid>")
        text, parts, warnings = provider_imap.extract_mime(msg.as_bytes())
        self.assertIn(b"plain", text)
        self.assertNotIn(b"html", text)
        self.assertEqual(parts[0].content, b"image")
        self.assertEqual(parts[0].content_id, "<synthetic-cid>")
