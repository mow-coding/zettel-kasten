"""Synthetic listing scope regression: MACs remain per claim, identity per read."""
from pathlib import Path
import os
from unittest.mock import patch

from wom_kit import exact_approval_claims as claims
from wom_kit import exact_human_approval as approval
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from test_v0430_exact_approval_claims import _ClaimStoreCase, AUTH_KEY


class ClaimListingInvocationScopeTests(_ClaimStoreCase):
    def test_bulk_listing_verifies_each_mac_with_constant_identity_reads(self):
        expected = {self.make_claim(ExactHumanApprovalOperation.mint_zet) for _ in range(24)}
        with patch.object(approval, "_archive_identity", wraps=approval._archive_identity) as identities, \
                patch.object(approval, "_authenticated_claim_document_for_identity",
                             wraps=approval._authenticated_claim_document_for_identity) as documents, \
                patch.object(approval, "_claim_windows_read_api", wraps=approval._claim_windows_read_api) as native_setup, \
                patch.object(claims, "_archive_identity", wraps=claims._archive_identity) as discovery:
            result = self.listing(status="all")
        self.assertTrue(result["complete"], result)
        self.assertEqual({row["approval_id"] for row in result["claims"]}, expected)
        self.assertEqual(documents.call_count, 24)
        self.assertEqual(identities.call_count, 2)
        self.assertEqual(discovery.call_count, 1)
        self.assertEqual(native_setup.call_count, 1 if os.name == "nt" else 0)

    def _change_during_listing(self, change):
        self.make_claim(ExactHumanApprovalOperation.mint_zet)
        project = claims._project_claim
        def project_and_change(parsed, *, clock):
            result = project(parsed, clock=clock)
            change()
            return result
        with patch.object(claims, "_project_claim", side_effect=project_and_change):
            with self.assertRaises(claims.ExactApprovalClaimsError) as caught:
                self.listing(status="all")
        self.assertEqual(caught.exception.code, "exact_approval_claim_store_unavailable")
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_archive_id_change_discards_whole_buffered_listing(self):
        marker = self.root / "archive.yml"
        self._change_during_listing(lambda: marker.write_bytes(marker.read_bytes().replace(
            b"archive:personal:fake-life", b"archive:personal:other-life")))

    def test_same_identity_marker_mutation_also_discards_listing(self):
        marker = self.root / "archive.yml"
        self._change_during_listing(lambda: marker.write_bytes(marker.read_bytes() + b"\n# changed\n"))

    def test_same_bytes_marker_replacement_discards_listing(self):
        marker = self.root / "archive.yml"
        original = marker.read_bytes()
        def replace():
            new = self.root / "replacement.yml"
            new.write_bytes(original)
            new.replace(marker)
        self._change_during_listing(replace)

    def test_marker_disappearance_has_fixed_error_and_no_partial_success(self):
        self._change_during_listing(lambda: (self.root / "archive.yml").unlink())

    def test_tampered_next_claim_is_still_invalid_not_accepted_from_scope(self):
        good = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        bad = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        bad_path = self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts) / (bad + ".json")
        original = bad_path.read_bytes()
        project = claims._project_claim
        def change_next(parsed, *, clock):
            if parsed["approval_id"] == good:
                bad_path.write_bytes(original.replace(b'"started"', b'"failed"'))
            return project(parsed, clock=clock)
        with patch.object(claims, "_project_claim", side_effect=change_next):
            result = self.listing(status="all")
        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["invalid_claim_count"], 1)
        self.assertEqual([row["approval_id"] for row in result["claims"]], [good])

    def test_wrong_key_still_rejects_every_document(self):
        self.make_claim(ExactHumanApprovalOperation.mint_zet)
        class WrongKey:
            def use_key(self, root, consumer, *, create_if_missing=False):
                return consumer(memoryview(bytes(reversed(AUTH_KEY))))
        result = claims.list_exact_human_approval_claims(
            self.root, status="all", key_provider=WrongKey(), claims_boundary=self.boundary)
        self.assertFalse(result["complete"])
        self.assertEqual(result["invalid_claim_count"], 1)
        self.assertEqual(result["claims"], [])

    def test_valid_mac_for_foreign_archive_is_not_projected(self):
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        path = self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts) / (approval_id + ".json")
        document = self.document(approval_id)
        document["archive_id"] = "archive:personal:other-life"
        document["authentication"]["mac"] = approval._claim_mac(document, AUTH_KEY)
        path.write_bytes(approval._canonical_bytes(document))
        result = self.listing(status="all")
        self.assertFalse(result["complete"])
        self.assertEqual(result["invalid_claim_count"], 1)
        self.assertEqual(result["claims"], [])

    def test_reader_cannot_outlive_held_directory_or_be_reused_as_permission(self):
        approval_id = self.make_claim(ExactHumanApprovalOperation.mint_zet)
        with self.boundary() as (root, binding):
            with approval._bound_claim_document_reader(
                self.root, bound_archive_root=root, claim_parent_binding=binding) as read:
                document, archive_id = read(approval_id, AUTH_KEY)
                self.assertEqual(document["approval_id"], approval_id)
                self.assertEqual(archive_id, "archive:personal:fake-life")
                self.assertIsInstance(document, dict)
        with self.assertRaises(approval.ExactHumanApprovalError) as caught:
            read(approval_id, AUTH_KEY)
        self.assertEqual(caught.exception.code, "exact_human_approval_claim_state_invalid")

    def test_foreign_directory_binding_is_not_reused(self):
        self.make_claim(ExactHumanApprovalOperation.mint_zet)
        with self.boundary() as (root, binding):
            altered = dict(binding)
            altered["path"] = self.root / "unrelated"
            with self.assertRaises(approval.ExactHumanApprovalError):
                with approval._bound_claim_document_reader(
                    self.root, bound_archive_root=root, claim_parent_binding=altered):
                    self.fail("foreign binding accepted")
