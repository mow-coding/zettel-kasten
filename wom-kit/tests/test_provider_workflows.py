"""End-to-end canonical provider capture with real approvals and synthetic UI."""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_services as services, provider_workflows as workflows
from wom_kit import provider_artifacts as artifacts, provider_tiro
from wom_kit import objet_capture_batch_exact, source_intake_batch_exact
from wom_kit import provider_notion_connections as connections
from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
import test_v0410_objet_capture_batch_exact as helpers
import test_v0421_lifecycle_batches_exact_approval as lifecycle_helpers
import test_provider_imap as imap_helpers


class ProviderWorkflowTests(unittest.TestCase):
    def call(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(list(arguments))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0, result)
        return result

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "archive"
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", self.root)
        services.index_archive(self.root)
        self.native = helpers._Native(approved=True)
        workflow = helpers.ObjetCaptureBatchExactTests._workflow(self.native, helpers._KeyProvider())
        for module in (workflows, objet_capture_batch_exact, source_intake_batch_exact):
            patcher = mock.patch.object(module, "_execute_exact_human_approved_write", side_effect=workflow)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_tiro_original_audio_transcript_and_ai_are_canonical_bound_and_searchable(self):
        raw = json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA, "notes": [{"guid": "note"}],
            "paragraphs_by_note": {"note": [{"content": "Synthetic transcript uniquequokka", "startAt": 13, "speaker": "Speaker 1"}]}}).encode()
        (self.root / "bundle.json").write_bytes(raw)
        (self.root / "audio.wav").write_bytes(b"original-audio")
        (self.root / "audio.json").write_text(json.dumps([{"note_guid": "note", "local_path": "audio.wav", "source_sha256": artifacts.digest(b"original-audio")}]))
        (self.root / "enrich.json").write_text(json.dumps([{"note_guid": "note", "source_sha256": artifacts.digest(raw),
            "content": "AI derivative uniquesloth", "model_provenance": {"provider": "synthetic", "model": "fixture", "run_id": "run"}}]))
        options = dict(bundle_path="bundle.json", batch_id="end-to-end", audio_manifest="audio.json", enrichment_manifest="enrich.json")
        preview = workflows.plan_tiro_content(self.root, **options)
        result = workflows.execute_tiro_content(self.root, **options, reviewed_by=helpers.REVIEWER,
            expected_plan_sha256=preview["plan_sha256"], claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["capture_completed"])
        self.assertTrue(result["search_verified"])
        receipt = artifacts.read_json(self.root, result["receipt_path"])
        self.assertEqual(receipt["items"]["tiro-original"], artifacts.digest(raw))
        self.assertEqual(receipt["bindings"][0]["note_guid"], "note")
        self.assertEqual(receipt["bindings"][0]["child_object_id"], artifacts.digest(b"original-audio"))
        for query in ("uniquequokka", "uniquesloth"):
            found = services.search_archive(self.root, query)
            self.assertTrue(any(row["type"] == "derived_text" for row in found["results"]), found)
        self.assertFalse(result["ai_model_called"])
        # A distinct provider occurrence of identical bytes uses authenticated
        # old intake members; it must not manufacture an empty new intake.
        other = {**options, "batch_id": "end-to-end-again"}
        preview = workflows.plan_tiro_content(self.root, **other)
        reused = workflows.execute_tiro_content(self.root, **other, reviewed_by=helpers.REVIEWER,
            expected_plan_sha256=preview["plan_sha256"], claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(reused["ok"], reused)
        self.assertGreater(reused["reused_intake_item_count"], 0)
        after = artifacts.read_json(self.root, reused["receipt_path"])
        self.assertEqual(after["items"], receipt["items"])
        self.assertEqual(after["bindings"], receipt["bindings"])
        self.assertEqual(after["executions"], [])

    def test_tiro_source_drift_is_rejected_before_approval(self):
        (self.root / "bundle.json").write_text(json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA, "notes": []}))
        options = dict(bundle_path="bundle.json", batch_id="drift")
        plan = workflows.plan_tiro_content(self.root, **options)
        (self.root / "bundle.json").write_text("changed")
        with self.assertRaisesRegex(artifacts.ProviderArtifactError, "plan_changed"):
            workflows.execute_tiro_content(self.root, **options, reviewed_by=helpers.REVIEWER, expected_plan_sha256=plan["plan_sha256"])
        self.assertEqual(self.native.calls, 0)

    def test_capture_failure_keeps_original_recovery_reference_and_partial_stage(self):
        (self.root / "bundle.json").write_text(json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA,
            "notes": [{"guid": "note"}], "paragraphs_by_note": {"note": [{"content": "synthetic"}]}}))
        options = dict(bundle_path="bundle.json", batch_id="capture-failure")
        plan = workflows.plan_tiro_content(self.root, **options)
        failure = {"ok": False, "cause_code": "capture_precommit_failed", "recovery": {"execution_ref": "synthetic-recovery"}}
        with mock.patch.object(objet_capture_batch_exact, "execute_objet_capture_batch", return_value=failure):
            result = workflows.execute_tiro_content(self.root, **options, reviewed_by=helpers.REVIEWER,
                expected_plan_sha256=plan["plan_sha256"], claim_key_provider=helpers._ReadKeyProvider())
        self.assertFalse(result["ok"])
        self.assertEqual(result["capture_result"], failure)
        self.assertEqual(result["recovery"], failure["recovery"])
        self.assertEqual(result["effects_state"], "partial_or_unknown")
        self.assertTrue((self.root / result["staging_receipt_path"]).is_file())
        resumed = workflows.execute_tiro_content(self.root, **options, reviewed_by=helpers.REVIEWER,
            expected_plan_sha256=plan["plan_sha256"], claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(resumed["ok"], resumed)
        self.assertTrue(resumed["search_verified"])

    def test_completion_exception_never_echoes_private_error_or_claims_no_effects(self):
        with mock.patch.object(workflows, "_capture_staged_content", side_effect=OSError("PRIVATE_PROVIDER_RESPONSE")):
            result = workflows.capture_staged_content(self.root, {"receipt_path": "workbench/synthetic.json"},
                reviewed_by=helpers.REVIEWER, receipt_name="synthetic")
        self.assertFalse(result["ok"])
        self.assertFalse(result["capture_completed"])
        self.assertEqual(result["effects_state"], "partial_or_unknown")
        self.assertNotIn("PRIVATE_PROVIDER_RESPONSE", json.dumps(result))

    def test_public_csv_relation_column_keeps_explicit_property_identity(self):
        page, target = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
        (self.root / "source.csv").write_text("Related\n" + target + "\n")
        result = self.call("connection-evidence-import", str(self.root), "--source", "source.csv",
            "--source-page-id", page, "--source-format", "csv", "--batch-id", "csv",
            "--relation-column", "Related=property-id", "--dry-run")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["pending_count"], 1)

    def test_imap_body_search_and_attachment_parent_are_finally_resolved(self):
        fixture = imap_helpers.ImapIncrementalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        services.index_archive(fixture.root)
        raw = imap_helpers.message("messagebody_uniqueotter")
        fetched = fixture.fetch(imap_helpers.Client({b"4": raw}))
        result = workflows.complete_imap_content(fixture.root, fetched, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(result["ok"], result)
        found = services.search_archive(fixture.root, "messagebody_uniqueotter")
        self.assertTrue(any(row.get("source_object_id") == artifacts.digest(raw) for row in found["results"]), found)
        receipt = artifacts.read_json(fixture.root, result["receipt_path"])
        part = next(row for row in receipt["bindings"] if row["role"] == "email_attachment")
        self.assertEqual(part["parent_object_id"], artifacts.digest(raw))
        self.assertEqual(part["child_object_id"], artifacts.digest(b"\x00\x01\xfe"))
        self.assertEqual(part["filename"], "../unsafe.bin")
        # A previously fetched batch may be completed again after an interrupted
        # caller. Existing canonical objects must converge without new copies.
        resumed = workflows.complete_imap_content(fixture.root, fetched, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["object_count"], result["object_count"])
        # Existing output bytes alone cannot authorize reuse after authenticated
        # completion evidence has changed.
        source_execution = receipt["executions"][0]["intake_execution_sha256"]
        final_path = fixture.root / "receipts/ops/exact-operations" / (source_execution[7:] + ".json")
        evidence = json.loads(final_path.read_text())
        evidence["receipt_sha256"] = "sha256:" + "0" * 64
        final_path.write_text(json.dumps(evidence) + "\n")
        rejected = workflows.complete_imap_content(fixture.root, fetched, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason_code"], "provider_intake_blocked")

    def test_imap_incremental_reuses_authenticated_attachment_in_new_batch(self):
        fixture = imap_helpers.ImapIncrementalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        services.index_archive(fixture.root)
        first_raw, second_raw = imap_helpers.message("first_uniqueotter"), imap_helpers.message("second_uniquesloth")
        first = fixture.fetch(imap_helpers.Client({b"4": first_raw}))
        complete = workflows.complete_imap_content(fixture.root, first, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(complete["ok"], complete)
        first_receipt = artifacts.read_json(fixture.root, complete["receipt_path"])
        second_client = imap_helpers.Client({b"4": first_raw, b"8": second_raw})
        second = fixture.fetch(second_client, batch_id="second")
        self.assertEqual(second_client.calls, [b"8"])
        result = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["reused_intake_item_count"], 1)
        receipt = artifacts.read_json(fixture.root, result["receipt_path"])
        old = next(row for row in first_receipt["bindings"] if row["role"] == "email_attachment")
        new = next(row for row in receipt["bindings"] if row["role"] == "email_attachment")
        self.assertEqual(old["child_object_id"], new["child_object_id"])
        self.assertNotEqual(old["parent_object_id"], new["parent_object_id"])
        self.assertTrue(receipt["reused_intakes"][0]["items"][0]["intake_final_receipt_sha256"])
        self.assertEqual(sum(row.get("object_id") == new["child_object_id"] for row in services.load_manifest_records(fixture.root)), 1)
        for query in ("first_uniqueotter", "second_uniquesloth"):
            self.assertTrue(services.search_archive(fixture.root, query)["results"])
        repeated = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(repeated["ok"], repeated)
        self.assertEqual(repeated["object_count"], result["object_count"])

    def test_two_mail_accounts_same_uids_complete_independent_incremental_captures(self):
        fixture = imap_helpers.ImapIncrementalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        bindings = services.load_source_bindings(fixture.root)
        bindings["sources"] = [*services.source_bindings_list(bindings),
            {"source_id": "mail-synthetic-other", "source_type": "imap_mailbox"}]
        services.archive_internal_path(fixture.root, "source-bindings.yml").write_text(
            json.dumps(bindings), encoding="utf-8")
        services.index_archive(fixture.root)
        scopes = [dict(source_id="mail-synthetic", username_ref="env:SYNTHETIC_USER", mailbox="INBOX"),
            dict(source_id="mail-synthetic-other", username_ref="env:SYNTHETIC_OTHER_USER", mailbox="Archive")]
        for index, scope in enumerate(scopes):
            first_raw = imap_helpers.message(f"firstscope{index}unique")
            next_raw = imap_helpers.message(f"nextscope{index}unique")
            first = fixture.fetch(imap_helpers.Client({b"4": first_raw}), batch_id=f"first-{index}", **scope)
            first_done = workflows.complete_imap_content(fixture.root, first,
                reviewed_by=helpers.REVIEWER, claim_key_provider=helpers._ReadKeyProvider())
            self.assertTrue(first_done["ok"], first_done)
            client = imap_helpers.Client({b"4": first_raw, b"8": next_raw})
            second = fixture.fetch(client, batch_id=f"second-{index}", **scope)
            self.assertEqual(client.calls, [b"8"])
            second_done = workflows.complete_imap_content(fixture.root, second,
                reviewed_by=helpers.REVIEWER, claim_key_provider=helpers._ReadKeyProvider())
            self.assertTrue(second_done["ok"], second_done)
            receipt = artifacts.read_json(fixture.root, second_done["receipt_path"])
            self.assertTrue(any(row["role"] == "email_attachment" and
                row["parent_object_id"] == artifacts.digest(next_raw) for row in receipt["bindings"]))
            for query in (f"firstscope{index}unique", f"nextscope{index}unique"):
                self.assertTrue(services.search_archive(fixture.root, query)["results"], query)
            interrupted_raw = imap_helpers.message(f"resumedscope{index}unique")
            all_messages = {b"4": first_raw, b"8": next_raw, b"12": interrupted_raw}
            interrupted = fixture.fetch(imap_helpers.Client(all_messages, failed={b"12"}),
                batch_id=f"interrupted-{index}", **scope)
            self.assertFalse(interrupted["ok"])
            resume_client = imap_helpers.Client(all_messages)
            resumed = fixture.fetch(resume_client, batch_id=f"interrupted-{index}", resume=True, **scope)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resume_client.calls, [b"12"])
            completed = workflows.complete_imap_content(fixture.root, resumed,
                reviewed_by=helpers.REVIEWER, claim_key_provider=helpers._ReadKeyProvider())
            self.assertTrue(completed["ok"], completed)
            self.assertTrue(services.search_archive(fixture.root, f"resumedscope{index}unique")["results"])

    def _completed_mail_and_next(self):
        fixture = imap_helpers.ImapIncrementalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        services.index_archive(fixture.root)
        first_raw, next_raw = imap_helpers.message("signedfirstbody"), imap_helpers.message("signednextbody")
        first = fixture.fetch(imap_helpers.Client({b"4": first_raw}))
        done = workflows.complete_imap_content(fixture.root, first, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(done["ok"], done)
        receipt = artifacts.read_json(fixture.root, done["receipt_path"])
        second = fixture.fetch(imap_helpers.Client({b"4": first_raw, b"8": next_raw}), batch_id="second")
        return fixture, receipt, second

    def test_cross_batch_reuse_rejects_changed_signed_evidence_and_canonical_bytes(self):
        fixture, receipt, second = self._completed_mail_and_next()
        from wom_kit import provider_intake_reuse as reuse
        plan = source_intake_batch_exact.plan_source_intake_batch(fixture.root, second["intake_requests"][0])
        strategy = reuse.discover(plan, key_provider=helpers._ReadKeyProvider())
        self.assertIsNotNone(strategy)
        proof = strategy["reused_items"][0]
        prior = objet_capture_batch_exact.plan_objet_capture_batch(fixture.root,
            intake_execution_sha256=proof["intake_execution_sha256"], claim_key_provider=helpers._ReadKeyProvider())
        row = next(row for row in prior.selection_document["items"] if row["item_id"] == proof["original_item_id"])
        final_path = fixture.root / "receipts/ops/exact-operations" / (proof["intake_execution_sha256"][7:] + ".json")
        source_receipt = fixture.root / row["source_intake_receipt_path"]
        canonical = fixture.root / workflows._object_verified(fixture.root, proof["object_id"])
        from dataclasses import replace
        incoming = next(item for item in plan.items if item.request_item_id == proof["item_id"])
        for changed_item in (replace(incoming, receipt_relative_path="receipts/other.json"),
                replace(incoming, capture_staged_path="staging/other.bin"),
                replace(incoming, source_bytes_sha256="sha256:" + "0" * 64),
                replace(incoming, source_size_bytes=incoming.source_size_bytes + 1),
                replace(incoming, source_intake_plan_sha256="sha256:" + "0" * 64)):
            self.assertIsNone(reuse._member(prior, changed_item))
        for path in (final_path, source_receipt, canonical):
            with self.subTest(path_kind=path.parent.name):
                original = path.read_bytes()
                path.write_bytes(b"{\"changed\":true}\n")
                try:
                    rejected = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
                        claim_key_provider=helpers._ReadKeyProvider())
                    self.assertFalse(rejected["ok"])
                    self.assertFalse(rejected["capture_completed"])
                finally:
                    path.write_bytes(original)
        # A newly hashed strategy still cannot alter its incoming request rows.
        changed = json.loads(json.dumps(strategy))
        changed["new_items"][0]["local_path"] = "bundle-other.json"
        basis = {key: value for key, value in changed.items() if key not in {"plan_sha256", "request_path"}}
        changed["plan_sha256"] = artifacts.digest(artifacts.canonical(basis))
        changed["request_path"] = "workbench/provider-intake/" + changed["plan_sha256"][7:] + ".json"
        with self.assertRaisesRegex(artifacts.ProviderArtifactError, "evidence_changed"):
            reuse.verify(plan, changed, key_provider=helpers._ReadKeyProvider())
        self.assertFalse((fixture.root / changed["request_path"]).exists())

    def test_cross_batch_prior_proof_drift_before_final_receipt_is_not_success(self):
        fixture, _, second = self._completed_mail_and_next()
        from wom_kit import provider_intake_reuse as reuse
        plan = source_intake_batch_exact.plan_source_intake_batch(fixture.root, second["intake_requests"][0])
        strategy = reuse.discover(plan, key_provider=helpers._ReadKeyProvider())
        execution = strategy["reused_items"][0]["intake_execution_sha256"]
        final_path = fixture.root / "receipts/ops/exact-operations" / (execution[7:] + ".json")
        original = final_path.read_bytes()
        approve = workflows._approve
        changed = []
        def before_final(root, operation, proposed, reviewer, write, **kwargs):
            if write.__name__ == "persist":
                final_path.write_bytes(b"{\"changed\":true}\n")
                changed.append(True)
            return approve(root, operation, proposed, reviewer, write, **kwargs)
        try:
            with mock.patch.object(workflows, "_approve", side_effect=before_final):
                rejected = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
                    claim_key_provider=helpers._ReadKeyProvider())
            self.assertEqual(changed, [True])
            self.assertFalse(rejected["ok"])
            self.assertFalse(rejected["capture_completed"])
            self.assertEqual(rejected["effects_state"], "partial_or_unknown")
            name = "imap-" + artifacts.digest(artifacts.canonical({"receipt": second["receipt_path"]}))[7:31]
            self.assertFalse((fixture.root / "receipts/provider-content" / (name + ".json")).exists())
        finally:
            final_path.write_bytes(original)

    def test_cross_batch_capture_failure_resumes_the_authenticated_new_subset(self):
        fixture, receipt, second = self._completed_mail_and_next()
        failure = {"ok": False, "cause_code": "synthetic_capture_interrupt", "recovery": {"execution_ref": "synthetic"}}
        with mock.patch.object(objet_capture_batch_exact, "execute_objet_capture_batch", return_value=failure):
            stopped = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
                claim_key_provider=helpers._ReadKeyProvider())
        self.assertEqual(stopped["reason_code"], "provider_capture_incomplete", stopped)
        self.assertEqual(stopped["recovery"], failure["recovery"])
        old_new_execution = stopped["intake_result"]["execution_sha256"]
        resumed = workflows.complete_imap_content(fixture.root, second, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(resumed["ok"], resumed)
        after = artifacts.read_json(fixture.root, resumed["receipt_path"])
        self.assertEqual(after["executions"][0]["intake_execution_sha256"], old_new_execution)
        self.assertEqual(resumed["reused_intake_item_count"], 1)
        self.assertTrue(services.search_archive(fixture.root, "signednextbody")["results"])

    def test_imap_no_new_uid_and_empty_mailbox_complete_without_false_skip(self):
        fixture = imap_helpers.ImapIncrementalTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        services.index_archive(fixture.root)
        raw = imap_helpers.message("cacheduncapturedbody")
        fixture.fetch(imap_helpers.Client({b"4": raw}))  # Download only, no canonical capture yet.
        client = imap_helpers.Client({b"4": raw})
        cached = fixture.fetch(client, batch_id="cached")
        self.assertEqual(client.calls, [])
        self.assertEqual(cached["message_count"], 0)
        self.assertEqual(cached["cached_message_count"], 1)
        completed = workflows.complete_imap_content(fixture.root, cached, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(completed["ok"], completed)
        self.assertGreater(completed["object_count"], 0)
        self.assertTrue(services.search_archive(fixture.root, "cacheduncapturedbody")["results"])
        empty = fixture.fetch(imap_helpers.Client({}), batch_id="empty")
        self.assertEqual(empty["intake_requests"], [])
        completed = workflows.complete_imap_content(fixture.root, empty, reviewed_by=helpers.REVIEWER,
            claim_key_provider=helpers._ReadKeyProvider())
        self.assertTrue(completed["ok"], completed)
        self.assertEqual(completed["object_count"], 0)

    def test_six_mechanisms_keep_provenance_and_write_one_reviewed_semantic_edge(self):
        first, second = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
        source = [{"type": "relation", "relation": [{"id": second}]},
            {"type": "synced_block", "synced_block": {"synced_from": {"block_id": second}}},
            {"object": "view_query", "id": "q", "view_id": first, "results": [{"id": second}]},
            {"href": "https://notion.so/" + second}, {"type": "mention", "mention": {"page": {"id": second}}},
            {"object": "comment", "parent": {"page_id": second}}]
        raw = json.dumps(source).encode()
        (self.root / "source.json").write_bytes(raw)
        parsed = connections.parse_source(raw, source_ref="source:" + artifacts.digest(raw), source_page_id=first, format="json")
        judgments = [{"candidate_id": row["candidate_id"], "source_sha256": row["source_sha256"], "review_status": "approved",
            "model_provenance": {"provider": "synthetic", "model": "fixture", "run_id": "run"},
            "lenses": {name: {"edge_type": "semantic", "direction": "source_to_target", "evidence_ref": row["source_ref"]} for name in connections.LENSES}}
            for row in parsed["candidates"]]
        (self.root / "judgments.json").write_text(json.dumps(judgments))
        (self.root / "bindings.json").write_text(json.dumps({first: "zet_20240504_fake_lunch_thought", second: "zet_20260519_fake_family_memory"}))
        options = dict(source_path="source.json", source_page_id=first, format="json", batch_id="reviewed", judgments_path="judgments.json", bindings_path="bindings.json")
        flags = ("connection-evidence-import", str(self.root), "--source", "source.json", "--source-page-id", first,
            "--source-format", "json", "--batch-id", "reviewed", "--judgments", "judgments.json", "--bindings", "bindings.json")
        preview = self.call(*flags, "--dry-run")
        self.assertEqual(preview["candidate_count"], 6)
        self.assertEqual(preview["reviewed_edge_count"], 1)
        original = workflows.execute_connection_import
        with mock.patch.object(workflows, "execute_connection_import", side_effect=lambda *args, **kwargs:
                original(*args, **kwargs, claim_key_provider=helpers._ReadKeyProvider())):
            result = self.call(*flags, "--approve", "--reviewed-by", helpers.REVIEWER,
                "--expected-plan-sha256", preview["plan_sha256"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["summary"]["written_edge_count"], 1)
        edge_plan = artifacts.read_json(self.root, "workbench/notion-connections/reviewed/edges.json")
        self.assertEqual(len(next(iter(edge_plan["edge_candidate_provenance"].values()))), 6)
        changed = (self.root / "zettels/zet_20240504_fake_lunch_thought.md").read_text()
        self.assertIn("zet_20260519_fake_family_memory", changed)
        native = lifecycle_helpers._PagedNative()
        with mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=native), \
                mock.patch.object(broker, "_production_key_provider", return_value=lifecycle_helpers._KeyProvider()):
            revert = self.call("revert-batch", str(self.root), "--receipt", result["receipt_path"],
                "--approve", "--reviewed-by", helpers.REVIEWER, "--format", "json")
        self.assertEqual(revert["write_status"], "reverted")
        self.assertEqual(revert["summary"]["edge_revert_count"], 1)
        self.assertNotIn("zet_20260519_fake_family_memory",
            (self.root / "zettels/zet_20240504_fake_lunch_thought.md").read_text())
        self.assertTrue((self.root / result["receipt_path"]).is_file())
