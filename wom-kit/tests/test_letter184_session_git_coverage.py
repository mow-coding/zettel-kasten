"""Beta letter 184: what a session-scoped Git preview covers, and how far it got.

After one conversation completed 21 objet registrations and 43 zettel-objet
links, `git-backup-reconcile-plan --dry-run` for that session answered
ok=true with selected_output_count=2 and nothing else: not what the two
were, not that the registrations and links are outside what a session-scoped
backup can prove, and a repeated preview sat in git_receipt_provenance for
more than ten minutes with no count. Since v0.4.65 the preview carries a
content-free coverage block and progress counts, and the discovery and
selection stages authenticate each original once.

Real temporary Git, registry and claims; synthetic files only.
"""
import json
import unittest
from unittest.mock import patch

from wom_kit import exact_approval_claims as claims
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_git_coverage as coverage
from wom_kit import work_session_git_workflow as workflow
from wom_kit import work_session_source_intake_inventory as inventory_module

import test_v0420_work_session_git_workflow as workflow_fixtures


class RoleLabelTests(unittest.TestCase):
    def test_roles_are_fixed_labels(self):
        cases = {
            "zettels/2026/PRIVATE-note.md": "zettel_documents",
            "objects/manifests/files.jsonl": "objet_ledger",
            "objects/sha256/ab/abcdef": "objet_files_under_objects",
            "receipts/objects/zettel-links/PRIVATE.json": "zettel_objet_link_receipts",
            "receipts/objects/captures/PRIVATE.json": "objet_receipts",
            "receipts/ops/exact-operations/" + "a" * 64 + ".json": "exact_operation_receipts",
            "receipts/session-object-usage/x.json": "session_object_usage_records",
            "receipts/PRIVATE-family/x.json": "receipts_other",
            "PRIVATE.txt": "archive_root_file",
            "PRIVATE-dir/x": "other",
        }
        for path, label in cases.items():
            with self.subTest(label=label):
                self.assertEqual(coverage.changed_path_role(path), label)
                self.assertNotIn("PRIVATE", label)
        self.assertEqual(coverage.changed_path_role(None), "other")


class CoverageBlockTests(unittest.TestCase):
    def operations(self, **counts):
        return {"state": "counted", "counts": counts, "succeeded_approvals_without_session_mark": 3}

    def test_customer_shape_says_what_the_two_are_and_what_is_left_out(self):
        proofs = [
            {"change_ref": "change:000001", "producer": "authenticated_source_intake_batch_output",
             "output_kind": "source_intake_receipt"},
            {"change_ref": "change:000002", "producer": "authenticated_source_intake_batch_output",
             "output_kind": "prepared_capture_request"},
            {"change_ref": "change:000003", "producer": "authenticated_work_session_completion_receipt"},
        ]
        changed = (["zettels/PRIVATE-%d.md" % n for n in range(42)]
                   + ["receipts/objects/zettel-links/PRIVATE-%d.json" % n for n in range(43)]
                   + ["objects/manifests/files.jsonl", "receipts/ops/source-intake-batches/PRIVATE.json"])
        block = coverage.build(
            proofs=proofs, selected_refs={"change:000001", "change:000002"}, changed_paths=changed,
            inspected_path_count=2,
            operations=self.operations(objet_capture_batch=21, zettel_objet_link=43,
                                       source_intake_batch=1, git_backup=1))
        self.assertEqual(block["selected_by_kind"], {"prepared_capture_request": 1, "source_intake_receipt": 1})
        self.assertEqual(block["selected_total"], 2)
        self.assertEqual(block["changed_paths_by_role"]["zettel_documents"], 42)
        self.assertEqual(block["changed_paths_by_role"]["zettel_objet_link_receipts"], 43)
        self.assertEqual(block["changed_paths_by_role"]["objet_ledger"], 1)
        self.assertEqual(block["changed_path_total"], 87)
        rows = {row["operation"]: row for row in block["session_operations"]["operations"]}
        # v0.4.66: zettel-objet links are provable; objet registration is not yet.
        self.assertEqual(rows["zettel_objet_link"],
                         {"operation": "zettel_objet_link", "succeeded_approval_count": 43,
                          "git_changes": "session_ownership_provable"})
        self.assertEqual(rows["objet_capture_batch"]["git_changes"], "not_provable_as_session_owned_yet")
        self.assertEqual(rows["source_intake_batch"]["git_changes"], "session_ownership_provable")
        self.assertEqual(rows["git_backup"]["git_changes"], "no_git_managed_output")
        self.assertEqual(block["session_operations"]["approval_count_whose_git_changes_are_not_selected"], 21)
        self.assertEqual(block["session_operations"]["reason_code"],
                         "no_session_bound_whole_file_proof_for_this_operation")
        text = " ".join(block["plain_summary"])
        self.assertIn("21 objet_capture_batch", text)
        self.assertNotIn("43 zettel_objet_link", text)
        self.assertIn("NOT in this selection", text)
        self.assertIn("Objet bytes are never part of a Git backup", text)
        self.assertFalse(block["object_bytes"]["included_in_git_backup"])
        self.assertEqual(block["shared_by_design_changed_path_count"], 1)
        self.assertIn("shared by every conversation", text)
        self.assertIn("git-backup-plan", block["official_route_for_unselected_changes"])
        self.assertNotIn("PRIVATE", json.dumps(block))

    def test_everything_provable_has_no_left_out_sentence(self):
        block = coverage.build(proofs=[], selected_refs=set(), changed_paths=[], inspected_path_count=0,
                               operations=self.operations(source_intake_batch=2))
        self.assertEqual(block["session_operations"]["approval_count_whose_git_changes_are_not_selected"], 0)
        self.assertIsNone(block["session_operations"]["reason_code"])
        self.assertNotIn("NOT in this selection", " ".join(block["plain_summary"]))
        self.assertIn("Nothing was selected", block["plain_summary"][0])

    def test_unavailable_claims_are_not_read_as_no_operations(self):
        block = coverage.build(proofs=[], selected_refs=set(), changed_paths=None, inspected_path_count=0,
                               operations={"state": "unavailable",
                                           "reason_code": "approval_claim_listing_unavailable"})
        self.assertEqual(block["session_operations"],
                         {"state": "unavailable", "reason_code": "approval_claim_listing_unavailable"})
        self.assertIsNone(block["changed_paths_by_role"])
        self.assertIn("could not be counted", " ".join(block["plain_summary"]))


class SessionOperationCountTests(unittest.TestCase):
    def listing(self, rows, blockers=()):
        return {"claims": rows, "blocker_codes": list(blockers)}

    def claim(self, operation, session=None, status="succeeded"):
        row = {"operation": operation, "status": status}
        if session:
            row["session_presenter"] = {"work_session_ref": session}
        return row

    def test_counts_only_this_sessions_succeeded_marked_approvals(self):
        mine, other = "work_session_" + "a" * 32, "work_session_" + "b" * 32
        rows = ([self.claim("zettel_objet_link", mine)] * 43 + [self.claim("objet_capture_batch", mine)] * 21
                + [self.claim("zettel_objet_link", other)] * 5 + [self.claim("zettel_objet_link", mine, "failed")]
                + [self.claim("objet_capture_batch")] * 2)
        with patch.object(claims, "list_exact_human_approval_claims", return_value=self.listing(rows)):
            result = coverage.session_operation_counts("unused", mine)
        self.assertEqual(result, {"state": "counted",
                                  "counts": {"objet_capture_batch": 21, "zettel_objet_link": 43},
                                  "succeeded_approvals_without_session_mark": 2})

    def test_incomplete_or_failing_listing_is_unavailable(self):
        with patch.object(claims, "list_exact_human_approval_claims",
                          return_value=self.listing([], blockers=["x"])):
            self.assertEqual(coverage.session_operation_counts("unused", "s")["state"], "unavailable")
        with patch.object(claims, "list_exact_human_approval_claims", side_effect=OSError("PRIVATE")):
            result = coverage.session_operation_counts("unused", "s")
        self.assertEqual(result, {"state": "unavailable", "reason_code": "approval_claim_listing_unavailable"})


class ObservationTests(unittest.TestCase):
    def test_counts_are_emitted_and_end_at_total(self):
        events = []
        with coverage.observing(lambda phase, current, total: events.append((phase, current, total))):
            coverage.stage("git_receipt_provenance")
            coverage.add_total(3)
            for _ in range(3):
                coverage.tick()
        self.assertEqual(events[0], ("git_receipt_provenance", 0, 3))
        self.assertEqual(events[-1], ("git_receipt_provenance", 3, 3))

    def test_outside_a_scope_everything_is_a_no_op(self):
        coverage.stage("git_receipt_provenance")
        coverage.add_total(5)
        coverage.tick()
        coverage.record_changed_paths(["a"])
        self.assertIsNone(coverage.memo())
        self.assertIsNone(coverage.active())

    def test_a_failing_display_never_fails_the_work(self):
        def broken(*_args):
            raise RuntimeError("PRIVATE")
        with coverage.observing(broken):
            coverage.stage("git_receipt_provenance")
            coverage.add_total(1)
            coverage.tick()


class PreviewIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = workflow_fixtures.SessionGitWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        root = self.fixture.root
        # changes of other conversations and of operations a session backup cannot prove
        (root / "zettels").mkdir(exist_ok=True)
        (root / "zettels" / "PRIVATE-note.md").write_bytes(b"synthetic zettel\n")
        links = root / "receipts" / "objects" / "zettel-links"
        links.mkdir(parents=True, exist_ok=True)
        (links / "PRIVATE-link.json").write_bytes(b"{}\n")

    def preview(self, events=None):
        fixture = self.fixture
        with exact.ExactOperationWriterLock(fixture.root) as held:
            return workflow._preview_session_git_backup_held(
                fixture.root, held=held, client_app_ref=fixture.app, task_route_ref=fixture.route,
                work_session_ref=fixture.session, key_provider=fixture.key,
                progress_hook=None if events is None else events.append)

    def test_preview_explains_selection_roles_and_progress(self):
        events = []
        preview = self.preview(events)
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["selected_receipt_count"], 1)
        block = preview["session_backup_coverage"]
        self.assertEqual(block["selected_by_kind"], {"work_session_decision_receipt": 1})
        roles = block["changed_paths_by_role"]
        self.assertEqual(roles["zettel_documents"], 1)
        self.assertEqual(roles["zettel_objet_link_receipts"], 1)
        self.assertGreaterEqual(roles["exact_operation_receipts"], 1)
        self.assertEqual(block["changed_path_total"], sum(roles.values()))
        self.assertEqual(block["session_owned_candidate_path_count"], 1)
        self.assertIn(block["session_operations"]["state"], {"counted", "unavailable"})
        self.assertTrue(preview["long_run_guidance"]["preview_is_read_only"])
        self.assertFalse(preview["long_run_guidance"]["resume_supported"])
        self.assertNotIn("PRIVATE", json.dumps(preview))
        counted = [event for event in events if "total" in event]
        self.assertTrue(counted)
        self.assertEqual({event["phase"] for event in counted},
                         {"git_output_scope_discovery", "git_receipt_provenance"})
        for event in counted:
            self.assertLessEqual(event["current"], event["total"])
        # the untouched files of other work are still there and uncommitted
        self.assertIn("PRIVATE-note.md", self.fixture.git("status", "--porcelain", "-uall").stdout)

    def test_originals_are_authenticated_once_per_preview(self):
        calls = {"batch": 0, "record": 0}
        batch = inventory_module._capture_source_intake_context_inventory_held
        record = inventory_module._capture_source_intake_record_context_inventory_held

        def count(name, original):
            def wrapper(*args, **kwargs):
                calls[name] += 1
                return original(*args, **kwargs)
            return wrapper
        with patch.object(inventory_module, "_capture_source_intake_context_inventory_held",
                          side_effect=count("batch", batch)), \
             patch.object(inventory_module, "_capture_source_intake_record_context_inventory_held",
                          side_effect=count("record", record)):
            self.preview()
        self.assertEqual(calls, {"batch": 1, "record": 1})

    def test_write_path_result_is_unchanged_and_skips_the_explanation(self):
        fixture = self.fixture
        with patch.object(coverage, "session_operation_counts",
                          side_effect=AssertionError("explained on the write path")):
            with exact.ExactOperationWriterLock(fixture.root) as held:
                result = fixture.execute(held)
        self.assertTrue(result["original_commit_verified"])
        self.assertNotIn("session_backup_coverage", result)


if __name__ == "__main__":
    unittest.main()
