"""Beta letter 185: a blocked upload preview says why, and window-approved captures get an exact route.

After the v0.4.66 session Git backup succeeded, the conversation previewed the
remote preservation of its 21 objets with a store label seen in the ledger and
got `writer_unavailable` with no usable distinction. Its 21 captures had been
approved through a window, so they carry no session mark. Since v0.4.67:

- a writer_unavailable preview names its category (one of four), what it is
  not, that nothing after the store label was evaluated, and that the Git
  backup is a separate fact;
- `--this-session` with no attributed capture explains itself in counts;
- `object-storage-scope-list --approval-id` builds the exact list from the
  verified capture receipts of named approvals, session mark or not.

Synthetic archive, receipts and claims; the claim store boundary is substituted.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from wom_kit import archive_cli, exact_approval_claims
from wom_kit import object_storage_scope as scope
from wom_kit import object_storage_upload_exact as upload

import test_object_storage_scope as scope_fixture
import test_v0428_object_storage_restore as rs
import test_v0433_object_storage_upload as up

A = scope_fixture.A
APPROVAL_MARKED = "approval_" + "1" * 32
APPROVAL_WINDOW = "approval_" + "2" * 32
APPROVAL_OTHER = "approval_" + "3" * 32


class _Fixture(scope_fixture.ScopeTests):
    def receipt(self, raw, approval_id, number, owner=None):
        claim = self._capture_receipt(raw, owner or A, number)
        receipt_dir = self.root / "receipts" / "objet-capture"
        path = next(p for p in receipt_dir.glob("*.json") if json.loads(p.read_text(encoding="utf-8"))
                    ["exact_human_approval"]["approval_id"] == str(number))
        document = json.loads(path.read_text(encoding="utf-8"))
        document["exact_human_approval"]["approval_id"] = approval_id
        path.write_text(json.dumps(document), encoding="utf-8")
        claim["approval_id"] = approval_id
        claim["operation"] = "objet_capture_batch"
        if owner is None:
            claim.pop("session_presenter")       # approved through a window: no session mark
        return claim

    def cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())


class WriterUnavailableTests(_Fixture):
    def test_unregistered_label_is_explained_as_a_label_problem_only(self):
        plan = upload.plan_object_storage_upload(self.root, store_ref="label-from-the-ledger",
                                                 scope=scope.ObjectScope("all_sessions"))
        preview = plan.public_document()
        self.assertEqual(preview["state"], "writer_unavailable")
        explained = preview["writer_unavailable_explained"]
        self.assertEqual(explained["category"], "no_store_registration_under_this_label")
        self.assertEqual(explained["reason"], "store_setup_missing")
        self.assertIn("session_scope_problem", explained["is_not"])
        self.assertIn("writer_not_installed", explained["is_not"])
        self.assertFalse(explained["scope_evaluated"])
        self.assertFalse(explained["manifest_read"])
        self.assertIn("registered_store_refs", preview)
        self.assertIn(rs.STORE, preview["registered_store_refs"])
        text = " ".join(explained["plain_summary"])
        self.assertIn("stopped at the first check, the store label", text)
        self.assertIn("Git backup", text)
        relation = preview["preservation_relation"]
        self.assertFalse(relation["git_backup_covers_objet_bytes"])
        self.assertEqual(relation["remote_preservation_state"], "blocked_before_plan")
        self.assertNotIn("label-from-the-ledger", json.dumps(explained))

    def test_other_writer_causes_have_their_own_category(self):
        cases = {"provider_unsupported": ("backblaze-b2", rs.STORE, "provider_kind_has_no_live_transport"),
                 "store_ref_invalid": ("cloudflare-r2", "not a label!", "store_label_not_a_safe_label")}
        for reason, (provider, label, category) in cases.items():
            with self.subTest(reason=reason):
                plan = upload.plan_object_storage_upload(self.root, provider_kind=provider, store_ref=label,
                                                         scope=scope.ObjectScope("all_sessions"))
                explained = plan.public_document()["writer_unavailable_explained"]
                self.assertEqual((explained["reason"], explained["category"]), (reason, category))

    def test_an_available_writer_has_no_writer_block_and_a_planned_state(self):
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=scope.ObjectScope("all_sessions"))
        preview = plan.public_document()
        self.assertIsNone(preview["writer_unavailable_explained"])
        self.assertEqual(preview["preservation_relation"]["remote_preservation_state"], "planned_not_performed")


class SessionScopeDiagnosisTests(_Fixture):
    def claims(self):
        marked = self.receipt(self.a, APPROVAL_MARKED, 1, owner="work_session_" + "b" * 32)
        window = self.receipt(self.b, APPROVAL_WINDOW, 2)
        return [marked, window]

    def test_this_session_with_only_window_approved_captures_explains_itself(self):
        claims = self.claims()
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims",
                          return_value={"claims": claims, "blocker_codes": []}), \
                patch.dict(os.environ, {"WOM_WORK_SESSION_REF": A}):
            diagnosis = scope.session_scope_diagnosis(self.root, A)
            code, result = self.cli("object-storage-upload", str(self.root), "--store-ref", rs.STORE,
                                    "--this-session", "--dry-run")
        self.assertEqual(diagnosis["captured_by_this_session_count"], 0)
        self.assertEqual(diagnosis["captured_without_session_mark_count"], 1)
        self.assertEqual(diagnosis["capture_approvals_without_session_mark_count"], 1)
        self.assertEqual(diagnosis["captured_by_other_sessions_count"], 1)
        self.assertEqual(code, 1)
        self.assertIn("object_storage_session_scope_unavailable_use_object_list", result["reason_codes"])
        text = " ".join(result["next_safe_actions"])
        self.assertIn("1 object(s) under 1 capture approval(s) carry no session mark", text)
        self.assertIn("--approval-id", text)
        self.assertIn("Git backup", text)
        self.assertNotIn(APPROVAL_WINDOW, json.dumps(result))
        self.assertNotIn(up._oid(self.b), json.dumps(result))


class ApprovalScopeListTests(_Fixture):
    def test_named_approvals_select_their_captures_without_a_session_mark(self):
        claims = [self.receipt(self.a, APPROVAL_WINDOW, 1), self.receipt(self.b, APPROVAL_OTHER, 2, owner=A)]
        output = self.root.parent / "letter185-list.txt"
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims",
                          return_value={"claims": claims, "blocker_codes": []}):
            code, result = self.cli("object-storage-scope-list", str(self.root), "--approval-id", APPROVAL_WINDOW,
                                    "--output", str(output))
        self.assertEqual(code, 0, result)
        self.assertTrue(result["list_written"])
        self.assertEqual(result["selected_object_count"], 1)
        self.assertEqual(result["approvals"], {
            "named_count": 1, "found_count": 1, "succeeded_capture_count": 1, "without_session_mark_count": 1,
            "object_count": 1, "approvals_with_no_valid_capture_receipt_count": 0,
            "selection_basis": "verified_capture_receipt_naming_a_mac_verified_succeeded_capture_claim"})
        self.assertEqual(output.read_text(encoding="utf-8").split(), [up._oid(self.a)])
        self.assertNotIn(up._oid(self.a), json.dumps(result))
        # the list drives an upload plan that never widens
        selected = scope.resolve_scope(self.root, object_list=output)
        plan = upload.plan_object_storage_upload(self.root, store_ref=rs.STORE, scope=selected)
        self.assertEqual([spec.object_id for spec in plan.specs], [up._oid(self.a)])

    def test_unknown_failed_or_non_capture_approvals_select_nothing(self):
        failed = self.receipt(self.a, APPROVAL_WINDOW, 1)
        failed["status"] = "failed"
        link = {"approval_id": APPROVAL_OTHER, "context_sha256": "sha256:" + "c" * 64,
                "operation": "zettel_objet_link", "status": "succeeded"}
        output = self.root.parent / "letter185-empty.txt"
        with patch.object(exact_approval_claims, "list_exact_human_approval_claims",
                          return_value={"claims": [failed, link], "blocker_codes": []}):
            code, result = self.cli("object-storage-scope-list", str(self.root), "--approval-id", APPROVAL_WINDOW,
                                    "--approval-id", APPROVAL_OTHER, "--approval-id", "approval_" + "9" * 32,
                                    "--output", str(output))
        self.assertEqual(code, 1)
        self.assertFalse(result["list_written"])
        self.assertFalse(output.exists())
        self.assertEqual(result["approvals"]["named_count"], 3)
        self.assertEqual(result["approvals"]["found_count"], 2)
        self.assertEqual(result["approvals"]["succeeded_capture_count"], 0)
        self.assertEqual(result["selected_object_count"], 0)

    def test_malformed_approval_id_is_refused(self):
        code, result = self.cli("object-storage-scope-list", str(self.root), "--approval-id", "PRIVATE text",
                                "--output", str(self.root.parent / "never.txt"))
        self.assertEqual(code, 1)
        self.assertIn("object_storage_scope_approval_id_invalid", result["reason_codes"])
        self.assertNotIn("PRIVATE", json.dumps(result))


# The inherited scope scenarios run in their own module.
for _class in (_Fixture, WriterUnavailableTests, SessionScopeDiagnosisTests, ApprovalScopeListTests):
    for _name in [name for name in dir(scope_fixture.ScopeTests) if name.startswith("test_")]:
        setattr(_class, _name, None)


if __name__ == "__main__":
    unittest.main()
