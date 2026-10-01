"""Beta letter 179: offload was blocked by a valid draft and could not free bytes that came back.

A. A valid reviewed_session_evidence draft receipt (no object_id by contract)
   was counted as an unreadable fidelity receipt and blocked every offload and
   remote cleanup. It is now checked against its own contract; real corruption
   or a smuggled object_id still blocks.
B. A CAS file that reappeared under an ``offloaded`` manifest location (objet
   capture's ``re_materialize`` writes the bytes back without touching the row)
   was counted as already offloaded forever. Verified bytes are now offloaded
   again under the same remote proof; absent bytes stay already offloaded;
   different bytes are a conflict.

Synthetic archives and a provider double; no client data.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from wom_kit import archive_services
from wom_kit import object_storage_offload as offload
from wom_kit import object_storage_preservation as preservation
from wom_kit import object_storage_restore as restore
from wom_kit.object_storage_scope import ObjectScope
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)

import test_letter136_source_fidelity_facets as facets
import test_v0428_object_storage_restore as restore_tests
import test_v0429_object_storage_offload as offload_tests

STORE = restore_tests.STORE
PROVIDER = restore_tests.PROVIDER


class SessionEvidenceDraftTests(unittest.TestCase):
    setUp = facets.Letter136SourceFidelityFacetTests.setUp
    private_session_input = facets.Letter136SourceFidelityFacetTests.private_session_input
    approved_session_evidence = facets.Letter136SourceFidelityFacetTests.approved_session_evidence
    ai_session_kwargs = facets.Letter136SourceFidelityFacetTests.ai_session_kwargs

    def _create_session_draft(self) -> dict:
        approved, _ = self.approved_session_evidence()
        kwargs = self.ai_session_kwargs(str(approved["evidence_id"]))
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, **kwargs)
        self.assertTrue(preview["ok"], preview)
        archive_services.index_archive(self.root)
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256("archive:personal:letter136-test"),
            plan_sha256="sha256:" + str(preview["source_fidelity_plan_sha256"]),
            target_binding_sha256="sha256:" + str(preview["body_sha256"]),
            reviewer_claim="person:letter136-test",
            review_binding_codes=("body_digest_reviewed", "draft_identity_reviewed", "source_fidelity_reviewed"),
            warning_codes=(),
        )
        decision = ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False, reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(self.root, context, decision, bytearray(b"c" * 32))
        try:
            written = archive_services.create_draft_zettel(
                self.root, approved=True, draft_approved_by="person:letter136-test",
                expected_body_sha256=preview["body_sha256"],
                expected_source_fidelity_plan_sha256=preview["source_fidelity_plan_sha256"],
                exact_human_approval_claim=claim, **kwargs,
            )
            claim.finalize_succeeded()
        finally:
            claim.close()
        return written

    def test_a_valid_session_evidence_receipt_is_readable_and_retains_nothing(self):
        written = self._create_session_draft()
        receipt = json.loads((self.root / written["source_fidelity_draft_receipt_path"]).read_text(encoding="utf-8"))
        source = receipt["source_fidelity"]["source"]
        # the customer's observation, exactly
        self.assertEqual(receipt["schema"], archive_services.SOURCE_FIDELITY_DRAFT_RECEIPT_SCHEMA_V2)
        self.assertEqual(source["authority_kind"], "reviewed_session_evidence")
        self.assertIn("evidence_id", source)
        self.assertNotIn("object_id", source)
        # the official contract says it is valid ...
        self.assertTrue(archive_services._source_fidelity_private_receipt_shape_valid(receipt))
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root, self.root / written["path"], affirmations=None)
        self.assertTrue(verification["ok"], verification)
        # ... and offload agrees now (before v0.4.56 it counted it unreadable)
        fixed = offload._draft_retention_evidence(self.root)
        self.assertEqual(fixed.unreadable_fidelity_receipt_count, 0)
        self.assertEqual(fixed.fidelity_sources, frozenset())
        # real corruption of a session receipt still blocks
        receipt_path = self.root / written["source_fidelity_draft_receipt_path"]
        broken = json.loads(receipt_path.read_text(encoding="utf-8"))
        broken["source_fidelity"]["source"]["object_id"] = "sha256:" + "a" * 64  # smuggled key
        receipt_path.write_text(json.dumps(broken), encoding="utf-8")
        self.assertEqual(offload._draft_retention_evidence(self.root).unreadable_fidelity_receipt_count, 1)
        receipt_path.write_text("{not json", encoding="utf-8")
        self.assertEqual(offload._draft_retention_evidence(self.root).unreadable_fidelity_receipt_count, 1)

    def test_the_draft_no_longer_blocks_the_objects_next_to_it(self):
        written = self._create_session_draft()
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            eligible = b"eligible object next to a session-evidence draft"
            restore_tests._write_rows(root, [offload_tests._aged_row(eligible)])
            restore_tests._write_local(root, eligible)
            (root / "inbox").mkdir()
            shutil.copy2(self.root / written["path"], root / "inbox" / Path(written["path"]).name)
            target = root / written["source_fidelity_draft_receipt_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / written["source_fidelity_draft_receipt_path"], target)
            fixed = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                        min_age_days=0, scope=ObjectScope("all_sessions"))
            fixed_doc = fixed.public_document()
            self.assertNotIn("object_storage_offload_retention_evidence_unreadable", fixed_doc["reason_codes"])
            self.assertEqual(fixed_doc["offload_target_count"], 1)
            self.assertEqual(fixed_doc["unminted_draft_count"], 1)
            if os.name == "nt":
                self.assertTrue(fixed_doc["ok"], fixed_doc)


class ReappearedBytesTests(unittest.TestCase):
    def _offloaded_row(self, raw: bytes) -> dict:
        row = offload_tests._aged_row(raw)
        row["locations"] = [offload_tests._offloaded(raw), restore_tests._remote(raw)]
        return row

    def test_verified_bytes_under_an_offloaded_row_are_offloaded_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            back = b"bytes that came back under an offloaded location"
            restore_tests._write_rows(root, [self._offloaded_row(back)])
            restore_tests._write_local(root, back)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                       min_age_days=0, scope=ObjectScope("all_sessions"))
            document = plan.public_document()
            self.assertEqual(document["already_offloaded_count"], 0)
            self.assertEqual(document["offloaded_bytes_reappeared_count"], 1)
            self.assertEqual(document["offload_target_count"], 1)
            self.assertEqual(document["planned_local_bytes_freed"], len(back))
            if os.name != "nt":
                return  # the bound delete is Windows-only
            proof = offload_tests._ProofTransport(offload_tests._objects_for(plan, {"a": back}))
            result = offload_tests._run_offload(plan, proof)
            self.assertTrue(result["ok"], result)
            self.assertFalse(restore_tests._dest(root, back).exists())
            row = restore_tests._rows_after(root)["sha256:" + hashlib.sha256(back).hexdigest()]
            self.assertTrue(any(loc.get("availability") == "offloaded" for loc in row["locations"]))
            again = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                        min_age_days=0, scope=ObjectScope("all_sessions"))
            self.assertEqual(again.public_document()["already_offloaded_count"], 1)

    def test_changed_bytes_under_an_offloaded_row_are_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            back = b"bytes that came back under an offloaded location"
            restore_tests._write_rows(root, [self._offloaded_row(back)])
            destination = restore_tests._dest(root, back)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"something else entirely, same path")
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                       min_age_days=0, scope=ObjectScope("all_sessions"))
            document = plan.public_document()
            self.assertEqual(document["offload_target_count"], 0)
            self.assertEqual(document["local_bytes_conflict_count"], 1)
            self.assertTrue(destination.is_file())

    @unittest.skipUnless(os.name == "nt", "offload delete is Windows-only")
    def test_existing_two_step_workaround_restore_then_offload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            back = b"bytes that came back, two-step workaround"
            restore_tests._write_rows(root, [self._offloaded_row(back)])
            restore_tests._write_local(root, back)
            rplan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE,
                                                        scope=ObjectScope("all_sessions"))
            rdoc = rplan.public_document()
            self.assertEqual(rdoc["restore_target_count"], 1)
            self.assertEqual(rdoc["local_location_reactivate_count"], 1)
            transport = restore_tests._MemoryTransport({})
            result = restore_tests._run(rplan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(transport.get_calls, 0)  # already_present_verified: no download
            row = restore_tests._rows_after(root)["sha256:" + hashlib.sha256(back).hexdigest()]
            self.assertTrue(any(loc.get("availability") == "available" for loc in row["locations"]))
            oplan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                        min_age_days=0, scope=ObjectScope("all_sessions"))
            self.assertEqual(oplan.public_document()["offload_target_count"], 1)
            proof = offload_tests._ProofTransport(offload_tests._objects_for(oplan, {"a": back}))
            oresult = offload_tests._run_offload(oplan, proof)
            self.assertTrue(oresult["ok"], oresult)
            self.assertFalse(restore_tests._dest(root, back).exists())
            row = restore_tests._rows_after(root)["sha256:" + hashlib.sha256(back).hexdigest()]
            self.assertTrue(any(loc.get("availability") == "offloaded" for loc in row["locations"]))

    def test_bytes_a_capture_re_materialised_become_an_offload_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"original captured, offloaded, then re-intaken"
            restore_tests._write_rows(root, [self._offloaded_row(raw)])
            staged = root / "staging" / "incoming" / "same.bin"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(raw)
            object_id = "sha256:" + hashlib.sha256(raw).hexdigest()
            manifest_before = (root / "objects/manifests/files.jsonl").read_bytes()
            appended: list[dict] = []
            item = {"item_id": "i1", "approved": True, "input_kind": "local_path",
                    "staged_path": "staging/incoming/same.bin", "approved_object_id": object_id}
            canonical = archive_services.objet_capture_canonical_record_ids(archive_services.load_manifest_records(root))
            self.assertIn(object_id, canonical)
            with patch.object(archive_services, "objet_capture_intake_evidence_blockers", lambda *a, **k: []):
                result = archive_services._objet_capture_process_item(
                    root, item, approve=True, canonical_ids=canonical, appended_this_run=set(),
                    captured_at="2026-10-01T00:00:00Z", reviewed_by="person:test", selection={},
                    selection_sha256="", manifest_appender=appended.append, capture_enabled=True)
            self.assertEqual(result["blockers"], [], result)
            self.assertEqual(result["planned_action"], "re_materialize")
            self.assertEqual(result["action"], "re_materialized")
            self.assertTrue(restore_tests._dest(root, raw).is_file())          # CAS is back
            self.assertEqual(appended, [])                                     # no manifest row
            self.assertEqual((root / "objects/manifests/files.jsonl").read_bytes(), manifest_before)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE,
                                                       min_age_days=0, scope=ObjectScope("all_sessions"))
            self.assertEqual(plan.public_document()["offloaded_bytes_reappeared_count"], 1)
            self.assertEqual(plan.public_document()["offload_target_count"], 1)


if __name__ == "__main__":
    unittest.main()
