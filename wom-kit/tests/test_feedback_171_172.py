"""Synthetic regressions for the integrated activity-completion release."""
import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_v0428_object_storage_restore as rs
import test_v0429_object_storage_offload as ofs
from wom_kit import archive_cli, object_storage_offload as offload
from wom_kit.object_storage_scope import ObjectScope


class ImmediateOffloadTests(unittest.TestCase):
    def test_zero_age_includes_today_missing_and_future_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            bodies = [b"today synthetic", b"unknown synthetic", b"future synthetic"]
            dates = [datetime.now(timezone.utc).isoformat(), None, "2999-01-01T00:00:00Z"]
            rows = [ofs._aged_row(raw, captured_at=date) for raw, date in zip(bodies, dates)]
            rs._write_rows(root, rows)
            for raw in bodies:
                rs._write_local(root, raw)
            for options in ({}, {"min_age_days": 0}):
                plan = offload.plan_object_storage_offload(root, store_ref=rs.STORE,
                    min_size_bytes=0, scope=ObjectScope("all_sessions"), **options)
                self.assertEqual(len(plan.specs), 3)
                doc = plan.public_document()
                self.assertFalse(doc["age_filter_enabled"])
                self.assertEqual(doc["age_filter_excluded_count"], 0)
            filtered = offload.plan_object_storage_offload(root, store_ref=rs.STORE,
                min_age_days=30, min_size_bytes=0, scope=ObjectScope("all_sessions")).public_document()
            self.assertEqual(filtered["planned_object_count"], 0)
            self.assertEqual(filtered["age_filter_excluded_count"], 3)
            self.assertEqual(filtered["captured_at_unknown_count"], 1)
            self.assertIn("object_storage_offload_age_filter_excluded", filtered["warning_codes"])
            self.assertTrue(any("--min-age-days 0" in a for a in filtered["next_safe_actions"]))


class DiagnosticTests(unittest.TestCase):
    def test_rotated_progress_keeps_original_and_each_new_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "progress.jsonl"
            log.write_text("original\n", encoding="utf-8")
            for index in (1, 2):
                callback = archive_cli._make_stage_progress_callback(False,
                    label="object-storage-offload", progress_log_path=log)
                try:
                    callback("offload", "done", index, 2)
                finally:
                    callback.close()
                result = json.loads(log.with_name(log.name + f".{index}").read_text())
                self.assertEqual(result["current"], index)
            self.assertEqual(log.read_text(), "original\n")

    def test_credential_absence_and_unknown_provider_are_not_conflated(self):
        with patch.dict(os.environ, {"SYNTHETIC_KEY": "not-a-secret"}, clear=True):
            for refs, expected in [((None, None), False),
                (("env:SYNTHETIC_KEY", "env:NOT_DEFINED"), False),
                (("keyring:synthetic", None), False),
                (("env:SYNTHETIC_KEY", "env:SYNTHETIC_KEY"), True),
                (("keyring:synthetic", "env:SYNTHETIC_KEY"), None)]:
                args = argparse.Namespace(access_key_id_ref=refs[0], secret_access_key_ref=refs[1])
                self.assertIs(archive_cli._object_storage_upload_credential_refs_present(args), expected)

    def test_unknown_options_do_not_echo_values(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            code = archive_cli.main(["object-storage-offload", "synthetic-root", "--dry-run",
                "--private-option=C:/private-example/do-not-echo", "--wrong", "secret-example",
                "--format", "json"])
        self.assertEqual(code, 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result["unknown_arguments"], ["--private-option", "--wrong"])
        self.assertNotIn("do-not-echo", output.getvalue())
        self.assertNotIn("secret-example", output.getvalue())

    def test_storage_progress_log_options_are_registered(self):
        parser = archive_cli.build_parser()
        for command in ("object-storage-restore", "object-storage-offload"):
            args = parser.parse_args([command, "synthetic-root", "--dry-run", "--progress-log", "out.jsonl"])
            self.assertEqual(args.progress_log, "out.jsonl")




class RemotePreservationTests(unittest.TestCase):
    def _transport(self, data=b"synthetic object", etag='"v1"'):
        import hashlib
        from wom_kit import archive_services as services
        calls = []
        state = {"data": data, "etag": etag, "status": 200}
        def send(**kwargs):
            calls.append(kwargs)
            if state["status"] != 200:
                return {"status": state["status"], "headers": {}}
            if kwargs["method"] == "HEAD":
                supplied = kwargs["headers"].get("if-match")
                if supplied and supplied != state["etag"]:
                    return {"status": 412, "headers": {}}
                return {"status": 200, "headers": {"content-length": str(len(state["data"])), "etag": state["etag"]}}
            return {"status": 200, "headers": {"etag": state["etag"]}, "body": state["data"]}
        transport = services._S3CompatibleTransport(endpoint_host="synthetic.example", bucket="synthetic-bucket",
            access_key_id="synthetic", secret_access_key="synthetic", region="auto", send=send)
        return transport, state, calls, "sha256:" + hashlib.sha256(data).hexdigest()

    def test_get_response_validator_is_bound_to_full_content_proof(self):
        from wom_kit import remote_preservation_proof as proofs
        transport, state, calls, oid = self._transport()
        verifier = proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256="run1")
        first = verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))
        second = verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))
        self.assertEqual(first["state"], "verified_match")
        self.assertEqual(first["proof"]["etag"], '"v1"')
        self.assertEqual(second["method"], "conditional_head")
        self.assertEqual(sum(c["method"] == "GET" for c in calls), 1)
        self.assertEqual(calls[-1]["headers"]["if-match"], '"v1"')

    def test_changed_remote_content_and_network_failure_never_reuse_success(self):
        from wom_kit import remote_preservation_proof as proofs
        transport, state, calls, oid = self._transport()
        verifier = proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256="run1")
        self.assertEqual(verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))["state"], "verified_match")
        state["status"] = 403
        self.assertEqual(verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))["state"], "verification_unavailable")
        state.update(status=200, etag='"v2"', data=b"different object")
        result = verifier.verify(key="synthetic-object", object_id=oid, size=len(b"synthetic object"))
        self.assertEqual(result["state"], "checksum_mismatch")

    def test_signed_proof_survives_execution_without_a_second_download(self):
        from wom_kit import remote_preservation_proof as proofs
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            store = proofs.ProofStore(root, rs._KeyProvider())
            transport, state, calls, oid = self._transport()
            # Without the private boundary no proof is persisted (letter 173 privacy fix).
            proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256="unignored",
                                        proof_store=store).verify(key="synthetic-object", object_id=oid, size=len(state["data"]))
            self.assertFalse((root / proofs.ROOT).exists())
            calls.clear()
            (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
            for execution in ("first", "second"):
                verifier = proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256=execution, proof_store=store)
                result = verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))
                self.assertEqual(result["state"], "verified_match")
            self.assertEqual(result["method"], "conditional_head")
            self.assertEqual(sum(c["method"] == "GET" for c in calls), 1)
            proof_path = next((root / proofs.ROOT).rglob("*.json"))
            doc = json.loads(proof_path.read_text())
            doc["proof"]["etag"] = '"forged"'
            proof_path.write_text(json.dumps(doc))
            verifier = proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256="third", proof_store=store)
            self.assertEqual(verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))["method"], "whole_get")

    def test_weak_etag_is_not_reusable_in_another_execution(self):
        from wom_kit import remote_preservation_proof as proofs
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            store = proofs.ProofStore(root, rs._KeyProvider())
            transport, state, calls, oid = self._transport(etag='W/"weak"')
            for execution in ("first", "second"):
                verifier = proofs.PreservationVerifier(transport, store_ref="synthetic", execution_sha256=execution, proof_store=store)
                for _ in range(2):
                    result = verifier.verify(key="synthetic-object", object_id=oid, size=len(state["data"]))
                    self.assertEqual(result["state"], "verified_match")
            self.assertEqual(sum(c["method"] == "GET" for c in calls), 2)


class DraftRevisionTests(unittest.TestCase):
    def setUp(self):
        import shutil
        from contextlib import ExitStack
        from wom_kit import archive_services, exact_human_approval_workflow as broker, exact_human_approval_windows as windows
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples/fake-life-archive", self.root)
        original = next((self.root / "inbox").glob("*.md"))
        frontmatter, body = archive_services.require_readable_zettel_content(original)
        frontmatter["provenance"]["created_by"] = "person:synthetic"
        frontmatter["provenance"].pop("assisted_by", None)
        frontmatter.pop("local_ai_sessions", None)
        original.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        self.draft = original.relative_to(self.root).as_posix()
        self.before = original.read_bytes()
        proposal = self.root / ".wom-scratch/revision.md"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        frontmatter["title"] = "Synthetic revised title"
        frontmatter["abstract"] = "A revised synthetic summary, retaining the original identity."
        proposal.write_text("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body + "\nSynthetic additional analysis.\n", encoding="utf-8")
        self.proposal = proposal.relative_to(self.root).as_posix()
        self.native = rs._Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=rs._KeyProvider()))
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        archive_services.index_archive(self.root)

    def _run(self, command, *extra):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            code = archive_cli.main([command, str(self.root), "--draft", self.draft, "--proposal", self.proposal, *extra])
        return code, json.loads(output.getvalue())

    def test_plan_rejects_identity_or_connection_changes_without_writes(self):
        from wom_kit import draft_revision
        code, plan = self._run("draft-revision-plan")
        self.assertEqual(code, 0, plan)
        self.assertTrue(plan["source_fidelity_verified"])
        proposal = self.root / self.proposal
        text = proposal.read_text(encoding="utf-8").replace("edges: []", "edges:\n- predicate: relates_to\n  target: zet:synthetic-other")
        proposal.write_text(text, encoding="utf-8")
        candidate = draft_revision.plan(self.root, draft=self.draft, proposal=self.proposal)
        self.assertIn("draft_revision_identity_or_links_changed", candidate["public"]["blockers"])
        self.assertEqual((self.root / self.draft).read_bytes(), self.before)
        self.assertFalse((self.root / draft_revision.ROOT).exists())

    @unittest.skipUnless(os.name == "nt", "native compare-and-swap write")
    def test_write_preserves_previous_body_and_same_id_without_publication(self):
        from wom_kit import draft_revision, archive_services
        code, plan = self._run("draft-revision-plan")
        self.assertEqual(code, 0, plan)
        code, result = self._run("draft-revision-write", "--approve", "--reviewed-by", "person:synthetic",
            "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual((self.root / self.draft).read_bytes(), (self.root / self.proposal).read_bytes())
        snapshots = list((self.root / draft_revision.ROOT / "snapshots").glob("*.md"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.before)
        receipt = json.loads(next((self.root / draft_revision.ROOT).glob("*.revision.json")).read_bytes())
        self.assertEqual(receipt["exact_human_approval"]["operation"], "draft_revision_write")
        self.assertFalse(result["auto_publish"])
        before_frontmatter = archive_services.require_readable_zettel_content(snapshots[0])[0]
        after_frontmatter = archive_services.require_readable_zettel_content(self.root / self.draft)[0]
        for field in ("id", "created_at", "provenance", "edges", "assets", "status"):
            self.assertEqual(before_frontmatter.get(field), after_frontmatter.get(field))

    @unittest.skipUnless(os.name == "nt", "native revision recovery")
    def test_interruption_after_replacement_resumes_original_claim_and_retains_history(self):
        from wom_kit import object_storage_offload as module, exact_approval_claims as claims
        code, plan = self._run("draft-revision-plan")
        self.assertEqual(code, 0)
        args = ("--approve", "--reviewed-by", "person:synthetic", "--expected-plan-sha256", plan["plan_sha256"])
        original = module._create_or_match_document
        def fail_receipt(root, relative, raw, **kwargs):
            if relative.endswith(".revision.json"):
                raise OSError("synthetic stop after replacement")
            return original(root, relative, raw, **kwargs)
        with patch.object(module, "_create_or_match_document", side_effect=fail_receipt):
            code, result = self._run("draft-revision-write", *args)
        self.assertEqual(code, 1)
        self.assertEqual(result["effects_state"], "unknown")
        self.assertEqual((self.root / self.draft).read_bytes(), (self.root / self.proposal).read_bytes())
        code, result = self._run("draft-revision-write", *args, "--resume")
        self.assertEqual(code, 0, result)
        listing = claims.list_exact_human_approval_claims(self.root, status="all", key_provider=rs._KeyProvider())
        self.assertEqual(listing["status_counts"]["started"], 0)
        self.assertEqual(listing["status_counts"]["succeeded"], 1)
        code, result = self._run("draft-revision-write", *args, "--resume")
        self.assertEqual(code, 0, result)
        self.assertFalse(result["writes_performed"])


class AIDraftRevisionFlowTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "native approved revision and mint")
    def test_ai_revision_quality_and_mint_preserve_creation_evidence(self):
        from contextlib import ExitStack
        from test_letter136_source_fidelity_facets import Letter136SourceFidelityFacetTests
        from wom_kit import archive_services as services, exact_human_approval_workflow as broker
        from wom_kit import exact_human_approval_windows as windows, draft_revision
        fixture = Letter136SourceFidelityFacetTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.test_v02_session_authority_create_and_mint_verification()
        root = fixture.root
        draft = next((root / "inbox").glob("*.md"))
        original = draft.read_bytes()
        original_receipts = {p: p.read_bytes() for p in (root / "receipts/source-fidelity").rglob("*.json")}
        fm, body = services.require_readable_zettel_content(draft)
        fm["title"] = "Revised reviewed synthetic session"
        proposal = root / "workbench/revised-draft.md"
        proposal.write_bytes(("---\n" + archive_cli.dump_yaml(fm) + "---\n\n" + body + "\nAdditional synthetic interpretation.\n").encode("utf-8"))
        class KeyProvider:
            def use_key(self, archive_root, consumer, *, create_if_missing=False):
                return consumer(bytearray(b"c" * 32))
        def run(command, *args):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = archive_cli.main([command, str(root), *args, "--format", "json"])
            return code, json.loads(output.getvalue())
        with ExitStack() as stack:
            stack.enter_context(patch.object(broker, "_production_key_provider", return_value=KeyProvider()))
            stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=rs._Native()))
            revision_args = ("--draft", draft.relative_to(root).as_posix(), "--proposal", proposal.relative_to(root).as_posix())
            code, plan = run("draft-revision-plan", *revision_args)
            self.assertEqual(code, 0, plan)
            code, result = run("draft-revision-write", *revision_args, "--approve", "--reviewed-by", "person:letter136-test", "--expected-plan-sha256", plan["plan_sha256"])
            self.assertEqual(code, 0, result)
            self.assertEqual(draft.read_bytes(), proposal.read_bytes())
            self.assertEqual(next((root / draft_revision.ROOT / "snapshots").glob("*.md")).read_bytes(), original)
            self.assertEqual({p: p.read_bytes() for p in original_receipts}, original_receipts)
            args = ("--path", draft.relative_to(root).as_posix())
            code, quality = run("zet-quality-check", *args, "--dry-run")
            self.assertEqual(quality["blocker_count"], 0, quality)
            mint_args = (*args, "--reviewed-by", "person:letter136-test", "--affirm", "one_clear_purpose", "--affirm", "sensitive_content_reviewed")
            code, preview = run("mint-zet", *mint_args, "--dry-run")
            self.assertEqual(code, 0, preview)
            code, minted = run("mint-zet", *mint_args, "--approve", "--allow-warnings", "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"])
            self.assertEqual(code, 0, minted)
            canonical = services.resolve_zet_revision_canonical_candidate(root, fm["id"])
            self.assertTrue(canonical.is_file())
            self.assertEqual(services.require_readable_zettel_content(canonical)[0]["id"], fm["id"])
            self.assertEqual({p: p.read_bytes() for p in original_receipts}, original_receipts)


class TableQualityTests(unittest.TestCase):
    def test_authored_table_needs_real_structure_review_but_no_source_row_mapping(self):
        from wom_kit import archive_services as services
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            note = root / "inbox" / "synthetic-table.md"
            note.parent.mkdir(exist_ok=True)
            body = "| topic | summary |\n| --- | --- |\n| A | synthetic |\n"
            base = {"id": "synthetic-table", "title": "Synthetic authored table",
                "document_type": "private_working_note", "audience": "self"}
            authored = services.zettel_quality_assessment(root, note,
                {**base, "parse_review": {"table_origin": "authored"}}, body)
            authored_codes = {issue["code"] for issue in authored["issues"]}
            self.assertIn("table_structure_review_missing", authored_codes)
            self.assertNotIn("table_row_mapping_missing", authored_codes)
            transcribed = services.zettel_quality_assessment(root, note,
                {**base, "parse_review": {"table_origin": "transcribed", "structure_reviewed": True}}, body)
            transcribed_codes = {issue["code"] for issue in transcribed["issues"]}
            self.assertIn("table_row_mapping_missing", transcribed_codes)
            invalid = services.zettel_quality_assessment(root, note,
                {**base, "parse_review": {"table_origin": "wrong"}}, body)
            explanation = next(row for row in invalid["warning_explanations"] if row["code"] == "table_origin_invalid")
            self.assertEqual(explanation["field"], "parse_review.table_origin")
            self.assertTrue(explanation["table_count"])


class AuthenticatedUsageTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows claim store")
    def test_diagnostic_text_does_not_become_session_object_use(self):
        from wom_kit import session_object_usage as usage, archive_services as services
        from wom_kit import exact_approval_claims as claims, exact_human_approval_workflow as broker
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
        from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            oid = "sha256:" + "a" * 64
            context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.zettel_objet_link,
                archive_identity_sha256=exact_human_approval_archive_identity_sha256(services.read_archive_id(root)),
                plan_sha256="sha256:" + "b" * 64, target_binding_sha256="sha256:" + "c" * 64,
                reviewer_claim="person:synthetic", review_binding_codes=("synthetic_object_reviewed",), warning_codes=())
            broker._execute_exact_human_approved_write_core(root, context,
                lambda claim: {"ok": True, "diagnostic": "Mentioned objet:" + oid + " without use"},
                native=rs._Native(), key_provider=rs._KeyProvider())
            listing = claims.list_exact_human_approval_claims(root, status="all", max_claims=100, key_provider=rs._KeyProvider())
            by_id = {row["approval_id"]: row for row in listing["claims"]}
            for row in by_id.values():
                row["session_presenter"] = {"work_session_ref": "work_session_" + "d" * 32}
            owners = {}
            usage.add_owners(root, by_id, owners, key_provider=rs._KeyProvider())
            self.assertEqual(owners, {})

    @unittest.skipUnless(os.name == "nt", "Windows claim store")
    def test_missing_middle_part_does_not_silently_shrink_session_scope(self):
        from wom_kit import session_object_usage as usage, archive_services as services
        from wom_kit import exact_approval_claims as claims, exact_human_approval_workflow as broker
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
        from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            object_ids = ["sha256:" + f"{number:064x}" for number in range(1001)]
            context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.zettel_objet_link,
                archive_identity_sha256=exact_human_approval_archive_identity_sha256(services.read_archive_id(root)),
                plan_sha256="sha256:" + "b" * 64, target_binding_sha256="sha256:" + "c" * 64,
                reviewer_claim="person:synthetic", review_binding_codes=("synthetic_object_reviewed",), warning_codes=())
            result = broker._execute_exact_human_approved_write_core(root, context,
                lambda claim: {"ok": True, "object_ids": object_ids},
                native=rs._Native(), key_provider=rs._KeyProvider())
            self.assertTrue(result["ok"])
            listing = claims.list_exact_human_approval_claims(root, status="all", max_claims=100, key_provider=rs._KeyProvider())
            by_id = {row["approval_id"]: row for row in listing["claims"]}
            owner = "work_session_" + "d" * 32
            for row in by_id.values():
                row["session_presenter"] = {"work_session_ref": owner}
            owners = {}
            usage.add_owners(root, by_id, owners, key_provider=rs._KeyProvider())
            self.assertEqual(len(owners), 1001)
            middle = next(path for path in (root / usage.ROOT).glob("*-1.json"))
            middle.unlink()
            owners = {}
            usage.add_owners(root, by_id, owners, key_provider=rs._KeyProvider())
            self.assertEqual(owners, {})

    @unittest.skipUnless(os.name == "nt", "Windows claim store")
    def test_signed_usage_rejects_modified_object_and_copied_approval(self):
        from wom_kit import session_object_usage as usage, object_storage_scope as scope
        from wom_kit import archive_services as services, exact_approval_claims as claims
        from wom_kit import exact_human_approval_workflow as broker
        from wom_kit.exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
        from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
        with tempfile.TemporaryDirectory() as tmp:
            root = rs._build_root(Path(tmp))
            oid = "sha256:" + "a" * 64
            context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.zettel_objet_link,
                archive_identity_sha256=exact_human_approval_archive_identity_sha256(services.read_archive_id(root)),
                plan_sha256="sha256:" + "b" * 64, target_binding_sha256="sha256:" + "c" * 64,
                reviewer_claim="person:synthetic", review_binding_codes=("synthetic_object_reviewed",), warning_codes=())
            result = broker._execute_exact_human_approved_write_core(root, context, lambda claim: {"ok": True, "object_id": oid},
                native=rs._Native(), key_provider=rs._KeyProvider())
            self.assertTrue(result["ok"])
            listing = claims.list_exact_human_approval_claims(root, status="all", max_claims=100, key_provider=rs._KeyProvider())
            by_id = {row["approval_id"]: row for row in listing["claims"]}
            owner = "work_session_" + "d" * 32
            for row in by_id.values():
                row["session_presenter"] = {"work_session_ref": owner}
            owners = {}
            usage.add_owners(root, by_id, owners, key_provider=rs._KeyProvider())
            self.assertEqual(owners, {oid: {owner}})
            target = next((root / usage.ROOT).glob("*.json"))
            doc = json.loads(target.read_bytes())
            doc["payload"]["object_ids"] = ["sha256:" + "f" * 64]
            target.write_text(json.dumps(doc), encoding="utf-8")
            owners = {}
            usage.add_owners(root, by_id, owners, key_provider=rs._KeyProvider())
            self.assertEqual(owners, {})


if __name__ == "__main__":
    unittest.main()
