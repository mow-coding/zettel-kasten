"""Stored synthetic PAT -> private worker -> canonical attachment bindings."""
from io import BytesIO, StringIO
from contextlib import redirect_stdout, redirect_stderr
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from urllib.parse import urlsplit
import unittest
from unittest import mock
import uuid

from wom_kit import archive_services as services, credential_workflows as credentials
from wom_kit import provider_workflows as workflows, provider_artifacts as artifacts
from wom_kit import provider_notion_connections as connections
from wom_kit import exact_human_approval_windows as windows, exact_human_approval_workflow as broker
from wom_kit import source_intake_batch_exact, objet_capture_batch_exact
from wom_kit import archive_cli as cli
from wom_kit.notion_http_adapter import _NotionHttpAdapter
from wom_kit.credential_capability import _CredentialCapability, CREDENTIAL_CAPABILITY_CONTENT_OPERATION, CredentialCapabilityError
import test_credential_workflows as credential_helpers
import test_notion_http_adapter as http_helpers
import test_v0410_objet_capture_batch_exact as approval_helpers
import test_v0421_lifecycle_batches_exact_approval as lifecycle_helpers

PAGE = credential_helpers.PAGE_ID
TARGET, IMAGE, DATABASE, VIEW = [str(uuid.UUID(int=i)) for i in range(600, 604)]


class Stream(BytesIO):
    status = 200


class SourceTransport:
    def __init__(self):
        self.calls = []

    def open(self, request, **_):
        path = urlsplit(request.full_url).path
        method = request.get_method()
        self.calls.append((method, path))
        if path == "/v1/pages/" + PAGE:
            payload = {"object": "page", "id": PAGE, "properties": {
                "Related": {"id": "rel", "type": "relation", "relation": [], "has_more": True}}}
        elif path.endswith("/properties/rel"):
            payload = {"results": [{"type": "relation", "relation": {"id": TARGET}}], "has_more": False}
        elif path.endswith("/children"):
            payload = {"results": [{"id": IMAGE, "type": "image", "image": {"type": "file", "file": {"url": "https://example.invalid/private-media"}}},
                {"id": DATABASE, "type": "child_database", "has_children": False},
                {"id": str(uuid.UUID(int=610)), "type": "synced_block", "synced_block": {"synced_from": {"block_id": TARGET}}},
                {"id": str(uuid.UUID(int=611)), "type": "paragraph", "paragraph": {"rich_text": [
                    {"type": "mention", "mention": {"page": {"id": TARGET}}},
                    {"type": "text", "text": {"link": {"url": "https://notion.so/" + TARGET}}}]}}], "has_more": False}
        elif path == "/v1/comments":
            payload = {"results": [{"object": "comment", "id": "synthetic-comment", "parent": {"page_id": TARGET}}], "has_more": False}
        elif path == "/v1/views":
            payload = {"results": [{"object": "view", "id": VIEW}], "has_more": False}
        elif path == "/v1/views/" + VIEW:
            payload = {"object": "view", "id": VIEW, "filter": {"property": "synthetic"}}
        elif path.endswith("/queries") and method == "POST":
            payload = {"object": "view_query", "id": "synthetic-query", "results": [{"id": TARGET}], "has_more": False}
        elif path.endswith("/queries/synthetic-query") and method == "DELETE":
            payload = {"object": "view_query", "id": "synthetic-query", "deleted": True}
        else:
            raise AssertionError("unexpected source endpoint")
        return http_helpers.FakeResponse(payload=payload)


class NotionProviderWorkflowTests(unittest.TestCase):
    def call(self, *arguments):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = cli.main(list(arguments))
        result = json.loads(output.getvalue())
        self.assertEqual(status, 0, result)
        return result

    def setUp(self):
        fixture = credential_helpers.CredentialWorkflowEndToEndTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original_adopt = fixture._adopt
        fixture._adopt = lambda: original_adopt(transport=credential_helpers.intake_transport(person=True))
        self.manifest, _ = fixture._prepare_pending_recovery()
        self.fixture, self.root = fixture, fixture.root
        self.native = approval_helpers._Native(approved=True)
        workflow = approval_helpers.ObjetCaptureBatchExactTests._workflow(self.native, approval_helpers._KeyProvider())
        for module in (workflows, source_intake_batch_exact, objet_capture_batch_exact):
            patcher = mock.patch.object(module, "_execute_exact_human_approved_write", side_effect=workflow)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_saved_pat_new_worker_fetches_six_types_and_canonical_attachment_binding(self):
        # Recover the actual page body through the established credential
        # worker first; the content worker subsequently resolves the saved PAT.
        body_transport = credential_helpers.intake_transport(include_recovery=True)
        body_transport.outcomes = body_transport.outcomes[2:]
        body_spawner = credentials._InjectedNotionRecoveryWorkerSpawner(native=self.fixture.native,
            notion_adapter=_NotionHttpAdapter(transport=body_transport), key_provider=self.fixture.key_provider,
            request_pacer=credential_helpers.NoOpPacer())
        transport = SourceTransport()
        def run(invocation):
            return credentials._execute_authenticated_notion_content_core(invocation, native=self.fixture.native,
                notion_adapter=_NotionHttpAdapter(transport=transport), key_provider=self.fixture.key_provider,
                download=lambda _: Stream(b"exact synthetic image bytes"), pacer=credential_helpers.NoOpPacer())
        options = dict(max_items=1, include_media=True, include_connections=True)
        request = "profiles/local/notion-page-recovery/synthetic-content.json"
        artifacts.write_json(self.root, request, self.manifest)
        flags = (str(self.root), "--request", request, "--max-items", "1", "--include-media", "--include-connections", "--format", "json")
        plan = self.call("notion-page-recovery-plan", *flags, "--dry-run")
        original = workflows.execute_notion_recovery_with_content
        def inject_worker(*args, **kwargs):
            return original(*args, **kwargs, claim_key_provider=approval_helpers._ReadKeyProvider(),
                body_worker_spawner=body_spawner, content_worker_spawner=SimpleNamespace(run_worker=run))
        with mock.patch.object(workflows, "execute_notion_recovery_with_content", side_effect=inject_worker):
            result = self.call("notion-page-recovery", *flags, "--approve", "--reviewed-by", approval_helpers.REVIEWER,
                "--expected-plan-sha256", plan["plan_sha256"])
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["capture_completed"])
        self.assertTrue(result["body_recovery_completed"])
        receipt = artifacts.read_json(self.root, result["receipt_path"])
        audio_rows = [row for row in receipt["bindings"] if row["role"] == "attachment"]
        self.assertEqual(len(audio_rows), 1)
        self.assertEqual(audio_rows[0]["child_object_id"], artifacts.digest(b"exact synthetic image bytes"))
        self.assertEqual(audio_rows[0]["parent_object_id"], services.notion_recovered_page_objects(self.root)[PAGE][0])
        source = artifacts.read_json(self.root, result["connection_evidence_path"])
        self.assertEqual({row["connection_kind"] for row in source["candidates"]},
            {"relation_property", "synced_block_reference", "database_view_filter", "internal_url_hyperlink", "mention_page", "comment_context"})
        self.assertFalse(any(method == "PATCH" for method, _ in transport.calls))
        self.assertNotIn(credential_helpers.SECRET_TEXT, json.dumps(result))
        found = services.search_archive(self.root, "exact body")
        self.assertTrue(any(row.get("source_object_id") == audio_rows[0]["parent_object_id"] for row in found["results"]), found)
        connection_plan = workflows.plan_connection_import(self.root, source_path=result["connection_evidence_path"],
            source_page_id=PAGE, format="json", batch_id="collected")
        self.assertEqual(connection_plan["candidate_count"], len(source["candidates"]))
        self.assertEqual(connection_plan["pending_count"], len(source["candidates"]))
        fixture_zettels = Path(__file__).parents[1] / "examples/fake-life-archive/zettels"
        first, second = "zet_20240504_fake_lunch_thought", "zet_20260519_fake_family_memory"
        (self.root / "zettels").mkdir(exist_ok=True)
        for zettel_id in (first, second):
            shutil.copyfile(fixture_zettels / f"{zettel_id}.md", self.root / "zettels" / f"{zettel_id}.md")
        self.assertTrue(services.index_archive(self.root)["index_complete"])
        selected = [row for row in source["candidates"]
            if row["source_page_id"] == PAGE and row["target_page_id"] == TARGET]
        self.assertEqual({row["connection_kind"] for row in selected},
            {"relation_property", "synced_block_reference", "database_view_filter",
             "internal_url_hyperlink", "mention_page", "comment_context"})
        judgments = [{"candidate_id": row["candidate_id"], "source_sha256": row["source_sha256"],
            "review_status": "approved", "model_provenance": {"provider": "synthetic", "model": "fixture", "run_id": "collected"},
            "lenses": {name: {"edge_type": "semantic", "direction": "source_to_target", "evidence_ref": row["source_ref"]}
                for name in connections.LENSES}} for row in selected]
        judgments_path = "profiles/local/notion-connections/collected-judgments.json"
        bindings_path = "profiles/local/notion-connections/collected-bindings.json"
        artifacts.write_json(self.root, judgments_path, judgments)
        artifacts.write_json(self.root, bindings_path, {PAGE: first, TARGET: second})
        review_options = dict(source_path=result["connection_evidence_path"], source_page_id=PAGE, format="json",
            batch_id="collected-review", judgments_path=judgments_path, bindings_path=bindings_path)
        review_plan = workflows.plan_connection_import(self.root, **review_options)
        self.assertEqual(review_plan["reviewed_edge_count"], 1)
        written = workflows.execute_connection_import(self.root, **review_options,
            reviewed_by=approval_helpers.REVIEWER, expected_plan_sha256=review_plan["plan_sha256"],
            claim_key_provider=approval_helpers._ReadKeyProvider())
        self.assertTrue(written["ok"], written)
        self.assertEqual(written["summary"]["written_edge_count"], 1)
        edge_plan = artifacts.read_json(self.root, "workbench/notion-connections/collected-review/edges.json")
        self.assertEqual(len(edge_plan["edges"]), 1)
        reviewed_sources = set(next(iter(edge_plan["edge_candidate_provenance"].values())))
        self.assertTrue({row["candidate_id"] for row in selected}.issubset(reviewed_sources))
        self.assertIn(second, (self.root / "zettels" / f"{first}.md").read_text(encoding="utf-8"))
        native = lifecycle_helpers._PagedNative()
        with mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=native), \
                mock.patch.object(broker, "_production_key_provider", return_value=lifecycle_helpers._KeyProvider()):
            reverted = self.call("revert-batch", str(self.root), "--receipt", written["receipt_path"],
                "--approve", "--reviewed-by", approval_helpers.REVIEWER, "--format", "json")
        self.assertEqual(reverted["summary"]["edge_revert_count"], 1)
        self.assertNotIn(second, (self.root / "zettels" / f"{first}.md").read_text(encoding="utf-8"))
        # A separate media-only operation has a different plan/batch but the
        # same original attachment. Reuse must still prove the old full chain.
        next_options = dict(max_items=1, include_media=True, include_connections=False)
        next_plan = workflows.plan_notion_content(self.root, self.manifest, **next_options)
        again = workflows.execute_notion_content(self.root, self.manifest, **next_options,
            reviewed_by=approval_helpers.REVIEWER, expected_plan_sha256=next_plan["plan_sha256"],
            claim_key_provider=approval_helpers._ReadKeyProvider(), worker_spawner=SimpleNamespace(run_worker=run))
        self.assertTrue(again["ok"], again)
        self.assertGreater(again["reused_intake_item_count"], 0)
        again_receipt = artifacts.read_json(self.root, again["receipt_path"])
        self.assertEqual(again_receipt["bindings"][0]["parent_object_id"], audio_rows[0]["parent_object_id"])
        self.assertEqual(again_receipt["bindings"][0]["child_object_id"], audio_rows[0]["child_object_id"])
        # The connection selection changes the collected source envelope, so
        # that new evidence is captured normally while the image is reused.
        self.assertEqual(len(again_receipt["executions"]), 1)
        self.assertEqual(sum(row.get("object_id") == audio_rows[0]["child_object_id"]
            for row in services.load_manifest_records(self.root)), 1)

    def test_content_capability_rejects_body_write_and_worker_public_call_requires_approval(self):
        plan = workflows.plan_notion_content(self.root, self.manifest, max_items=1)
        cap = _CredentialCapability.issue(request_sha256=plan["request_sha256"], plan_sha256=plan["plan_sha256"],
            scopes=credentials._credential_capability_scopes(self.manifest, max_items=1, offset=0), reviewed_by="tester-1",
            max_provider_requests=3, operation=CREDENTIAL_CAPABILITY_CONTENT_OPERATION)
        from datetime import datetime, timezone
        lease = cap.new_lease(claimed_at=datetime.now(timezone.utc))
        with self.assertRaises(CredentialCapabilityError):
            lease.authorize_request("move_page_to_trash", scope=cap.scopes[0])
        result = credentials.execute_spawned_authenticated_notion_content("must-not-read", {},
            expected_plan_sha256="invalid", reviewed_by="tester-1")
        self.assertFalse(result["ok"])

    def test_worker_result_rejects_secret_carrying_strings_and_extra_fields(self):
        plan = workflows.plan_notion_content(self.root, self.manifest, max_items=1)
        valid = {"ok": True, "reason_code": "notion_content_staged", "provider_calls": 1, "item_count": 1, "candidate_count": 0}
        for poisoned in [{**valid, "reason_code": credential_helpers.SecretStr("notion_content_staged", "PRIVATE")},
                         {**valid, "private": "PRIVATE"}]:
            result = workflows.execute_notion_content(self.root, self.manifest, max_items=1,
                reviewed_by=approval_helpers.REVIEWER, expected_plan_sha256=plan["plan_sha256"],
                worker_spawner=SimpleNamespace(run_worker=lambda _: poisoned))
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason_code"], "notion_content_worker_outcome_unknown")
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_parent_body_failure_never_runs_content_worker(self):
        options = dict(max_items=1, include_media=True)
        plan = workflows.plan_notion_recovery_with_content(self.root, self.manifest, **options)
        body = mock.Mock()
        body.run_worker.side_effect = RuntimeError("synthetic worker launch failure")
        content = mock.Mock()
        result = workflows.execute_notion_recovery_with_content(self.root, self.manifest, **options,
            expected_plan_sha256=plan["plan_sha256"], reviewed_by=approval_helpers.REVIEWER,
            body_worker_spawner=body, content_worker_spawner=content)
        self.assertFalse(result["ok"])
        self.assertFalse(result["content_started"])
        content.run_worker.assert_not_called()
