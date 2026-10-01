"""v0.4.57 (owner idea 2026-10-01): archived mail as thread text records per mailbox account.

A synthetic archive holds .eml objets: a three-message reply chain with a
duplicate fetch, a two-message conversation without threading headers, an
HTML-only reply, a second account known only from Delivered-To, an offloaded
mail and a non-mail objet. Threads are a derived snapshot rebuilt from the
objets; the objets never change and command output never echoes addresses,
subjects or bodies.
"""

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wom_kit import archive_cli
from wom_kit import mail_threads


def _eml(headers: dict[str, str], body: str, *, html: bool = False) -> bytes:
    lines = [f"{key}: {value}" for key, value in headers.items()]
    lines.append("MIME-Version: 1.0")
    lines.append(f"Content-Type: {'text/html' if html else 'text/plain'}; charset=utf-8")
    lines.append("Content-Transfer-Encoding: 8bit")
    return ("\r\n".join(lines) + "\r\n\r\n" + body + "\r\n").encode("utf-8")


class MailThreadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: archive:test:mail\n", encoding="utf-8")
        self.rows = []
        mail_threads.record_mail_account(self.root, source_id="gmail-main", account_address="Me@Example.com",
                                         mailbox="INBOX")

    def add(self, raw: bytes, *, name: str = "mail.eml", mime: str = "message/rfc822", local: bool = True) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        if local:
            path = self.root / "objects" / "sha256" / digest[:2] / digest
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.rows.append({"object_id": "sha256:" + digest, "sha256": digest, "mime": mime,
                          "logical_key": f"objects/sha256/{digest[:2]}/{digest}", "size_bytes": len(raw),
                          "provenance": {"source": "b4_local_objet_capture", "original_filename": name}})
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("".join(json.dumps(row) + "\n" for row in self.rows), encoding="utf-8")
        return "sha256:" + digest

    def build_mailbox(self):
        self.first = self.add(_eml({"From": "Partner <partner@other.org>", "To": "me@example.com",
                                    "Delivered-To": "me@example.com", "Subject": "회의 일정",
                                    "Date": "Mon, 01 Sep 2026 09:00:00 +0900", "Message-ID": "<1@other.org>"},
                                   "다음 주 회의 가능하세요?"))
        self.add(_eml({"From": "me@example.com", "To": "partner@other.org", "Subject": "Re: 회의 일정",
                       "Date": "Mon, 01 Sep 2026 10:00:00 +0900", "Message-ID": "<2@example.com>",
                       "In-Reply-To": "<1@other.org>", "References": "<1@other.org>"},
                      "화요일 좋습니다.\n> 다음 주 회의 가능하세요?"))
        # the same reply fetched a second time (different bytes, same Message-ID)
        self.add(_eml({"From": "me@example.com", "To": "partner@other.org", "Subject": "Re: 회의 일정",
                       "Date": "Mon, 01 Sep 2026 10:00:00 +0900", "Message-ID": "<2@example.com>",
                       "In-Reply-To": "<1@other.org>", "References": "<1@other.org>", "X-Fetch": "again"},
                      "화요일 좋습니다.\n> 다음 주 회의 가능하세요?"))
        self.add(_eml({"From": "partner@other.org", "To": "me@example.com", "Subject": "RE: 회의 일정",
                       "Date": "Mon, 01 Sep 2026 11:00:00 +0900", "Message-ID": "<3@other.org>",
                       "In-Reply-To": "<2@example.com>", "References": "<1@other.org> <2@example.com>"},
                      "<p>확정했습니다.</p><br><b>장소</b>는 본관", html=True))
        # a conversation without threading headers
        self.add(_eml({"From": "colleague@team.net", "To": "me@example.com", "Subject": "보고서",
                       "Date": "Tue, 02 Sep 2026 09:00:00 +0900"}, "초안 보냅니다."))
        self.add(_eml({"From": "me@example.com", "To": "colleague@team.net", "Subject": "답장: 보고서",
                       "Date": "Tue, 02 Sep 2026 12:00:00 +0900"}, "확인했습니다."))
        # another mailbox account, known only from Delivered-To
        self.add(_eml({"From": "news@shop.com", "To": "second@mail.com", "Delivered-To": "second@mail.com",
                       "Subject": "주문 확인", "Date": "Wed, 03 Sep 2026 09:00:00 +0900",
                       "Message-ID": "<9@shop.com>"}, "주문이 접수되었습니다."))
        # an offloaded mail and a non-mail objet
        self.add(_eml({"From": "x@y.com", "To": "me@example.com", "Subject": "offloaded",
                       "Message-ID": "<o@y.com>"}, "remote only"), local=False)
        self.add(b"%PDF-1.4 not mail", name="doc.pdf", mime="application/pdf")

    def test_threads_group_replies_per_account_and_change_no_objet(self):
        self.build_mailbox()
        before = {path: path.read_bytes() for path in (self.root / "objects").rglob("*") if path.is_file()}
        result = mail_threads.build_mail_threads(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["account_count"], 2)
        self.assertEqual(result["thread_count"], 3)
        self.assertEqual(result["multi_message_thread_count"], 2)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["local_bytes_absent_count"], 1)
        self.assertEqual(result["mail_objet_count"], 8)
        after = {path: path.read_bytes() for path in (self.root / "objects").rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        generation = self.root / result["location"]
        files = sorted(path.relative_to(generation).as_posix() for path in generation.rglob("*.md"))
        self.assertEqual(len(files), 3)
        self.assertTrue(all(name.startswith(("me_at_example.com/", "second_at_mail.com/")) for name in files))
        meeting = next(path for path in generation.rglob("*.md") if "회의 일정" in path.read_text(encoding="utf-8"))
        text = meeting.read_text(encoding="utf-8")
        self.assertIn("메일 수: 3", text)
        self.assertIn("- 메일함 계정: me@example.com", text)
        self.assertLess(text.index("다음 주 회의"), text.index("화요일 좋습니다"))
        self.assertLess(text.index("화요일 좋습니다"), text.index("확정했습니다"))
        self.assertIn("인용 1줄은 접었습니다", text)
        self.assertIn("본관", text)
        self.assertNotIn("<p>", text)
        self.assertIn(f"- 원본 오브제: {self.first}", text)
        report = next(path for path in generation.rglob("*.md") if "초안 보냅니다" in path.read_text(encoding="utf-8"))
        self.assertIn("메일 수: 2", report.read_text(encoding="utf-8"))
        self.assertTrue((self.root / "db" / "mail-threads" / ".gitignore").is_file())
        latest = json.loads((self.root / "db" / "mail-threads" / "latest.json").read_text(encoding="utf-8"))
        self.assertEqual(latest["generation"], result["generation"])

    def test_a_rebuild_is_the_same_snapshot_and_new_mail_makes_a_new_one(self):
        self.build_mailbox()
        first = mail_threads.build_mail_threads(self.root)
        again = mail_threads.build_mail_threads(self.root)
        self.assertEqual(again["generation"], first["generation"])
        self.assertTrue(again["reused"])
        self.add(_eml({"From": "me@example.com", "To": "partner@other.org", "Subject": "Re: 회의 일정",
                       "Date": "Mon, 01 Sep 2026 12:00:00 +0900", "Message-ID": "<4@example.com>",
                       "In-Reply-To": "<3@other.org>", "References": "<1@other.org> <3@other.org>"}, "감사합니다."))
        third = mail_threads.build_mail_threads(self.root)
        self.assertNotEqual(third["generation"], first["generation"])
        self.assertEqual(third["thread_count"], 3)
        meeting = next(path for path in (self.root / third["location"]).rglob("*.md")
                       if "회의 일정" in path.read_text(encoding="utf-8"))
        self.assertIn("메일 수: 4", meeting.read_text(encoding="utf-8"))

    def test_the_command_prints_counts_only(self):
        self.build_mailbox()
        for action in ("--dry-run", "--build"):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = archive_cli.main(["mail-threads", str(self.root), action, "--format", "json"])
            self.assertEqual(code, 0, out.getvalue())
            rendered = out.getvalue()
            for private in ("me@example.com", "partner@other.org", "회의 일정", "화요일", str(self.root)):
                self.assertNotIn(private, rendered)
            self.assertEqual(json.loads(rendered)["thread_count"], 3)
        self.assertFalse((self.root / "db" / "mail-threads" / "latest.json").read_text(encoding="utf-8") == "")

    def test_the_account_record_is_private_and_validated(self):
        record = json.loads((self.root / "profiles" / "local" / "mail-accounts" / "gmail-main.json").read_text(encoding="utf-8"))
        self.assertEqual(record["account_address"], "me@example.com")
        mail_threads.record_mail_account(self.root, source_id="bad id!", account_address="me@example.com", mailbox="INBOX")
        mail_threads.record_mail_account(self.root, source_id="other", account_address="not-an-address", mailbox="INBOX")
        self.assertEqual(sorted(p.name for p in (self.root / "profiles" / "local" / "mail-accounts").glob("*.json")),
                         ["gmail-main.json"])


if __name__ == "__main__":
    unittest.main()
