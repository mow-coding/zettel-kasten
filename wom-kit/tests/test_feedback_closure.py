import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from wom_kit import feedback_closure as closure


class FeedbackClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "ledger.json"

    def evidence(self, name, value):
        raw = json.dumps(value).encode()
        (self.root / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def request(self, identity, verified=False):
        value = {"request_id": identity, "original_requirement": "private original requirement",
                 "criteria": ["flow"], "reply_claim": "resolved", "customer_confirmation": "pending"}
        if verified:
            value["verification"] = [self.evidence(identity + ".json", {
                "schema": "wom-kit/feedback-flow-evidence/v1", "request_id": identity,
                "criterion_id": "flow", "ok": True, "execution_kind": "installed_product", "exit_code": 0,
                "actual_effect_verified": True, "commit": "a" * 40, "wheel_sha256": "b" * 64})]
            value["release"] = self.evidence(identity + "-release.json", {
                "schema": "wom-kit/feedback-release-evidence/v1", "public_download_verified": True,
                "fresh_install_verified": True, "tag_commit_verified": True, "version": "test-version",
                "commit": "a" * 40, "wheel_sha256": "b" * 64})
        return value

    def check(self, rows):
        self.path.write_text(json.dumps({"schema": closure.SCHEMA, "requests": rows}), encoding="utf-8")
        return closure.check(self.path)

    def test_one_of_three_released_keeps_two_open(self):
        result = self.check([self.request("one", True), self.request("two"), self.request("three")])
        self.assertFalse(result["ok"])
        self.assertEqual(result["summary"], {"total": 3, "product_complete": 1, "open": 2, "reply_overclaims": 2})
        self.assertEqual(result["requests"][0]["state"], "released_customer_pending")
        self.assertNotIn("private original", json.dumps(result))

    def test_recurring_complaint_reopens_existing_request(self):
        recurrence = self.request("again")
        recurrence["recurrence_of"] = "first"
        result = self.check([self.request("first", True), recurrence])
        self.assertEqual(result["requests"][0]["state"], "reopened")

    def test_changed_evidence_is_rejected(self):
        row = self.request("one", True)
        (self.root / "one.json").write_text("{}")
        with self.assertRaises(closure.FeedbackClosureError):
            self.check([row])

    def test_different_released_wheel_does_not_close_request(self):
        row = self.request("one", True)
        document = json.loads((self.root / "one-release.json").read_bytes())
        document["wheel_sha256"] = "d" * 64
        row["release"] = self.evidence("different.json", document)
        self.assertFalse(self.check([row])["requests"][0]["product_complete"])

    def test_unsubstantiated_customer_confirmation_remains_pending(self):
        row = self.request("one", True)
        row["customer_confirmation"] = "confirmed"
        result = self.check([row])["requests"][0]
        self.assertEqual(result["customer_confirmation"], "pending")
        self.assertFalse(result["customer_evidence_verified"])

    def test_completed_recurrence_does_not_permanently_block_ancestor(self):
        row = self.request("again", True)
        row["recurrence_of"] = "first"
        result = self.check([self.request("first", True), row])
        self.assertTrue(all(item["product_complete"] for item in result["requests"]))

    def test_cyclic_recurrence_is_invalid(self):
        one, two = self.request("one"), self.request("two")
        one["recurrence_of"], two["recurrence_of"] = "two", "one"
        with self.assertRaises(closure.FeedbackClosureError):
            self.check([one, two])

    def test_reply_claim_is_bound_to_actual_reply_file(self):
        row = self.request("one", True)
        body = b"The requested scenario is resolved in the verified release."
        (self.root / "reply.md").write_bytes(body)
        row["reply_evidence"] = self.evidence("reply-review.json", {
            "schema": "wom-kit/feedback-reply-evidence/v1", "claims": {"one": "resolved"},
            "claims_reviewed_against_body": True,
            "reply_file": {"path": "reply.md", "sha256": hashlib.sha256(body).hexdigest()}})
        self.assertTrue(self.check([row])["ok"])
        (self.root / "reply.md").write_bytes(b"A different unreviewed claim")
        with self.assertRaises(closure.FeedbackClosureError):
            self.check([row])


if __name__ == "__main__":
    unittest.main()
