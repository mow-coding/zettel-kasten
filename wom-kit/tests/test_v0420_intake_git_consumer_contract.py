"""Pure consumer projection and closed-dispatch tests, not proof authentication.

Actual original MACs, intake writes, Git transport and resume are exercised by
the separately named joined public workflow. These tests deliberately use
detached synthetic data and must not be reported as authority acceptance.
"""

from types import SimpleNamespace
import unittest

from wom_kit import work_session_git_provenance as provenance
from wom_kit import work_session_git_workflow as workflow


class IntakeGitConsumerContractTests(unittest.TestCase):
    def selection(self, *, intake=False, unverified=False):
        proofs = [{"change_ref": "change:000001", "producer": "authenticated_work_session_completion_receipt"}]
        selected = ["change:000001"]
        excluded = [{"change_ref": "change:000005", "scope": "unknown"}]
        if intake:
            for number, kind in ((2, "source_intake_receipt"), (3, "prepared_capture_request"),
                                 (4, "prepared_capture_request")):
                proofs.append({"change_ref": "change:" + str(number).zfill(6),
                    "producer": "authenticated_source_intake_batch_output", "output_kind": kind})
            selected.extend(["change:000002", "change:000003"])
            excluded.append({"change_ref": "change:000004", "scope": "other_session"})
        value = {"selection": {"selected_groups": [{"change_refs": selected}],
                               "excluded_changes": excluded},
                 "proofs": proofs, "unverified_receipt_candidates": 0}
        if unverified:
            value["intake_provenance_summary"] = {"context_hint_count": 2,
                "authenticated_original_count": 0, "unverified_context_hint_count": 2}
        return provenance._ReceiptSelection(provenance._canonical(value))

    def test_historical_receipt_only_projection_remains_unchanged(self):
        result = self.selection().public_summary()
        self.assertEqual(result["status"], "receipt_selection_classified")
        self.assertEqual(result["selected_receipt_count"], 1)
        self.assertTrue(result["receipt_only"])
        self.assertNotIn("selected_output_count", result)
        self.assertNotIn("unverified_intake_context_count", result)
        self.assertFalse(result["backup_performed"])

    def test_capture_request_is_an_output_not_a_receipt_or_preserved_source(self):
        result = self.selection(intake=True).public_summary()
        self.assertEqual(result["selected_output_count"], 3)
        self.assertEqual(result["selected_receipt_count"], 2)
        self.assertEqual(result["selected_intake_output_count"], 2)
        self.assertEqual(result["other_session_output_count"], 1)
        self.assertEqual(result["other_session_receipt_count"], 0)
        self.assertFalse(result["receipt_only"])
        for name in ("source_bytes_backed_up", "artifact_capture_performed", "artifact_backup_complete",
                     "backup_performed", "ready_for_write", "current_claim_authority_evaluated"):
            self.assertFalse(result[name])

    def test_unverified_hints_are_reported_not_claimed_absent_or_owned(self):
        result = self.selection(unverified=True).public_summary()
        self.assertEqual(result["unverified_intake_context_count"], 2)
        self.assertEqual(result["authenticated_intake_original_count"], 0)
        self.assertEqual(result["selected_intake_output_count"], 0)
        self.assertEqual(result["selected_output_count"], 1)

    def test_closed_dispatch_preserves_producer_order_and_rejects_unknown(self):
        rows = self.selection(intake=True)._private_document()["proofs"]
        prepared = SimpleNamespace(session_scope=SimpleNamespace(document=lambda: {"producer_proofs": rows}))
        human, intake, documents = workflow._partition_producer_proofs(prepared)
        self.assertEqual(documents, [])
        self.assertEqual(human, rows[:1])
        self.assertEqual(intake, rows[1:])
        rows.append({"producer": "unrecognized_synthetic_producer"})
        with self.assertRaises(workflow.WorkSessionGitWorkflowError) as caught:
            workflow._partition_producer_proofs(prepared)
        self.assertEqual(caught.exception.code, "work_session_git_original_evidence_invalid")

    def test_stored_proof_rows_include_exclusions_without_new_discovery(self):
        selected, excluded = {"synthetic": "selected"}, {"synthetic": "excluded"}
        prepared = SimpleNamespace(groups=[SimpleNamespace(private_changes=[selected])],
                                   excluded_changes=[{"private_change": excluded}])
        self.assertEqual(workflow._private_proof_changes(prepared), [selected, excluded])


if __name__ == "__main__":
    unittest.main()
