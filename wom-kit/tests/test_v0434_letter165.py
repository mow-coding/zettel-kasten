"""v0.4.34 (beta letter 165): presenter-bound session grants, legacy identifier warnings,
feedback compose under exact approval, the revise path and revision-plan warning hints.

Synthetic archives, the injected dialog and key of the v0.4.20 session fixture only.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import archive_services
from wom_kit import exact_approval_claims
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import legacy_identifier
from wom_kit import mcp_server
from wom_kit import operator_feedback_body as body_module
from wom_kit import presenter_fingerprint
from wom_kit import work_session_permission as permission
from wom_kit import work_session_registry as registry
from wom_kit import work_session_service
from wom_kit.command_status import EXACT_APPROVAL_REOPENED_WRITERS
from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext, ExactHumanApprovalOperation, PERMISSION_INTERACTIVE_INTENT_MECHANISM,
    _OPERATION_LABELS,
)
from wom_kit.work_session_permission import ALWAYS_DIALOG_OPERATIONS, GRANTABLE_OPERATIONS

import test_v0424_session_permission_modes as _permission_fixture

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-session-reviewer"


class _CountingNative:
    def __init__(self):
        self.calls = 0

    def show(self, **_kwargs):
        self.calls += 1
        return _permission_fixture.APPROVE_BUTTON_ID, False


def _basis(tag: str) -> dict:
    return {"schema": presenter_fingerprint.FINGERPRINT_SCHEMA, "image_basename": "synthetic.exe",
            "pid": 4000 + len(tag), "creation_time": 100 + len(tag)}


class PresenterBoundGrantTests(_permission_fixture.SessionPermissionModeTests):
    """[A] the grant is presenter-bound and time-boxed; claims say who used it."""

    # ------------------------------------------------------------ the row and the dialog
    def test_grant_row_is_v2_and_the_dialog_shows_the_box(self) -> None:
        task = self.establish("v2row")
        preview = self.call("work-session", "--action", "set-permission-mode", "--dry-run", "--request-stdin",
                            *task["refs"], "--work-session-ref", task["session"],
                            request={"permission_mode": "limited", "operations": ["create_draft"], "grant_hours": 2})
        self.assertEqual(preview["result"]["would_box"],
                         {"grant_hours": 2, "expires_at_relative": True, "presenter_token_returned_once": True})
        self.assertTrue(preview["result"]["presenter_bound"])
        refused = self.call("work-session", "--action", "set-permission-mode", "--dry-run", "--request-stdin",
                            *task["refs"], "--work-session-ref", task["session"],
                            request={"permission_mode": "limited", "operations": ["create_draft"], "grant_hours": 48}, ok=False)
        self.assertEqual(refused["result"]["reason_code"], "work_session_permission_grant_hours_invalid")
        dialogs = self.native.calls
        result = self.set_mode(task, "limited", ["create_draft"])
        self.assertEqual(self.native.calls, dialogs + 1)
        inner = result["result"]
        self.assertTrue(inner["presenter_token_returned_once"])
        self.assertTrue(inner["presenter_token_is_secret"])
        self.assertTrue(inner["presenter_bound"])
        self.assertEqual(result["presenter_token_field"], "result.presenter_token")
        token = inner["presenter_token"]
        self.assertRegex(token, r"^[A-Za-z0-9_-]{43}$")
        self.assertTrue(any("WOM_WORK_SESSION_PRESENTER" in line for line in inner["next_safe_actions"]))
        row = self.store.read()._document["sessions"][task["session"]]
        self.assertEqual(set(row["permission"]), permission.PERMISSION_V2_KEYS)
        self.assertEqual(row["permission"]["presenter_sha256"], permission.presenter_sha256(token))
        self.assertNotIn(token, json.dumps(row))
        granted = datetime.strptime(row["permission"]["granted_at"], "%Y-%m-%dT%H:%M:%SZ")
        expires = datetime.strptime(row["permission"]["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(expires - granted, timedelta(hours=permission.GRANT_HOURS_DEFAULT))
        # the dialog carried the grant box line, bound with the presenter hash
        items = permission.preview_items(archive_identity_sha256="sha256:" + "a" * 64, permission=row["permission"])
        self.assertEqual(items[-1].kind, "grant_box")
        self.assertIn("8시간", items[-1].title)
        # inspect / list show the box, never the hash
        item = self.inspect(task)
        self.assertTrue(item["presenter_bound"])
        self.assertEqual(item["permission_expires_at"], row["permission"]["expires_at"])
        self.assertFalse(item["grant_expired"])
        self.assertFalse(item["grant_legacy_shape"])
        self.assertNotIn("presenter_sha256", json.dumps(item))
        listing = self.call("work-session", "--action", "list", "--kind", "session")
        self.assertEqual(listing["counts"]["non_manual_session_count"], 1)
        self.assertEqual(listing["counts"]["expired_grant_count"], 0)
        # resuming the original decision never re-issues the secret
        resumed = self.call("work-session", "--action", "set-permission-mode", "--resume",
                            *task["refs"], "--work-session-ref", task["session"], request=None)
        self.assertFalse(resumed["result"]["presenter_token_available"])
        self.assertNotIn("presenter_token", resumed["result"])

    def test_registry_accepts_both_shapes_and_refuses_broken_boxes(self) -> None:
        legacy = {"mode": "limited", "operations": ["create_draft"]}
        registry._validate_permission(legacy)
        good = permission.bind_grant(legacy, presenter_sha256="sha256:" + "b" * 64, grant_hours=3)
        registry._validate_permission(good)
        self.assertEqual(permission.permission_shape(legacy), "legacy")
        self.assertEqual(permission.permission_shape(good), "v2")
        self.assertIsNone(permission.permission_expired(legacy))
        self.assertFalse(permission.permission_expired(good))
        for broken in (
            {**good, "expires_at": good["granted_at"]},
            {**good, "presenter_sha256": "b" * 64},
            {**good, "granted_at": "2026-09-20 00:00:00"},
            {**good, "extra": 1},
        ):
            with self.assertRaises(registry.WorkSessionRegistryError):
                registry._validate_permission(broken)
        with self.assertRaises(permission.WorkSessionPermissionError):
            permission.normalize_grant_hours(0)
        with self.assertRaises(permission.WorkSessionPermissionError):
            permission.normalize_grant_hours(True)

    # ------------------------------------------------------------ refusals
    def test_missing_wrong_expired_and_legacy_presenters_get_the_dialog_and_a_code(self) -> None:
        task = self.establish("refusals")
        self.set_mode(task, "allow_all")
        token = task["presenter"]
        refs = dict(client_app_ref=task["app"], task_route_ref=task["route"], work_session_ref=task["session"])
        self.assertIsNotNone(permission.resolve_grant(self.root, presenter=token, **refs))
        self.assertEqual(permission.resolve_grant_outcome(self.root, presenter=None, **refs),
                         (None, "work_session_presenter_missing"))
        self.assertEqual(permission.resolve_grant_outcome(self.root, presenter="x" * 43, **refs),
                         (None, "work_session_presenter_mismatch"))
        with patch.object(permission, "_clock", lambda: datetime.now(timezone.utc) + timedelta(hours=9)):
            self.assertEqual(permission.resolve_grant_outcome(self.root, presenter=token, **refs),
                             (None, "work_session_grant_expired"))
            self.assertTrue(self.inspect(task)["grant_expired"])
        with patch.object(permission, "permission_shape", return_value="legacy"):
            self.assertEqual(permission.resolve_grant_outcome(self.root, presenter=token, **refs),
                             (None, "work_session_grant_legacy_shape"))
        with patch.dict(os.environ, {**self.env(task), "WOM_TASK_ROUTE_REF": "task_route_" + "0" * 32}):
            self.assertEqual(permission.resolve_grant_outcome_from_environment(self.root)[1],
                             "work_session_grant_unavailable")
        # a write that presents the refs without the token opens the dialog and says why
        object_id = self.manifested_source(b"presenter refusal source\n")
        self.index()
        flags = self.draft_flags(object_id, "Draft without the presenter token")
        preview = self.draft_call(*flags, "--dry-run")
        dialogs = self.native.calls
        env = {name: value for name, value in self.env(task).items() if name != permission.PRESENTER_ENV}
        with patch.dict(os.environ, env):
            written = self.draft_call(*flags, *self.approve_flags(preview))
        self.assertEqual(self.native.calls, dialogs + 1)
        self.assertEqual(written["session_permission_refused"],
                         {"reason_code": "work_session_presenter_missing", "dialog_shown": True,
                          "private_values_echoed": False})
        self.assertTrue(written["exact_human_approval"]["live_dialog_shown"])
        self.assertNotIn("presenter", written["exact_human_approval"])
        # with the token: no dialog, and the claim names the presenter
        second = self.draft_flags(self.manifested_source(b"presenter ok source\n"), "Draft with the presenter token")
        self.index()
        preview2 = self.draft_call(*second, "--dry-run")
        dialogs = self.native.calls
        with patch.dict(os.environ, self.env(task)), patch.object(presenter_fingerprint, "observe", return_value=_basis("one")):
            granted = self.draft_call(*second, *self.approve_flags(preview2))
        self.assertEqual(self.native.calls, dialogs)
        self.assertNotIn("session_permission_refused", granted)
        summary = granted["exact_human_approval"]
        self.assertEqual(summary["approval_mechanism"], PERMISSION_INTERACTIVE_INTENT_MECHANISM)
        self.assertEqual(summary["presenter"], {"fingerprint_state": "observed", "presenters_observed_before_this_claim": 0,
                                                "second_presenter_observed": False, "presenter_values_echoed": False})
        claim = self.claim_document(summary["approval_id"])
        presenter = claim["session_presenter"]
        self.assertEqual(presenter["schema"], approval.SESSION_PRESENTER_SCHEMA)
        self.assertEqual(presenter["work_session_ref"], task["session"])
        self.assertEqual(presenter["presenter_sha256"], permission.presenter_sha256(token))
        self.assertRegex(presenter["process_fingerprint_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(claim["status"], "succeeded")
        self.assertNotIn("synthetic.exe", json.dumps(claim))
        self.assertNotIn(token, json.dumps(claim))

    def test_second_presenter_is_recorded_and_warned(self) -> None:
        task = self.establish("second")
        self.set_mode(task, "allow_all")
        results = []
        for ordinal, tag in enumerate(("alpha", "beta-second", "alpha")):
            flags = self.draft_flags(self.manifested_source(f"second presenter source {ordinal}\n".encode()),
                                     f"Second presenter draft {ordinal}")
            self.index()
            preview = self.draft_call(*flags, "--dry-run")
            with patch.dict(os.environ, self.env(task)), patch.object(presenter_fingerprint, "observe", return_value=_basis(tag)):
                results.append(self.draft_call(*flags, *self.approve_flags(preview)))
        first, second, third = (r["exact_human_approval"] for r in results)
        self.assertEqual(first["presenter"]["presenters_observed_before_this_claim"], 0)
        self.assertNotIn("warnings", first)
        self.assertEqual(second["presenter"]["presenters_observed_before_this_claim"], 1)
        self.assertTrue(second["presenter"]["second_presenter_observed"])
        self.assertEqual(second["warnings"], ["work_session_second_presenter_observed"])
        self.assertEqual(third["presenter"]["presenters_observed_before_this_claim"], 1)
        self.assertTrue(third["presenter"]["second_presenter_observed"])
        # the claims listing counts mechanisms and presenter-less grant claims
        listing = exact_approval_claims.list_exact_human_approval_claims(self.root, status="all", key_provider=self.key)
        self.assertEqual(listing["mechanism_counts"][PERMISSION_INTERACTIVE_INTENT_MECHANISM], 3)
        self.assertEqual(listing["presenter_unknown_count"], 0)
        rows = [row for row in listing["claims"] if row["approval_mechanism"] == PERMISSION_INTERACTIVE_INTENT_MECHANISM]
        self.assertTrue(all(row["presenter_recorded"] for row in rows))
        self.assertEqual({row["session_presenter"]["work_session_ref"] for row in rows}, {task["session"]})
        self.assertIn("immutable", listing["presenter_evidence_note"])
        # an unavailable fingerprint is recorded as such, never as a refusal
        flags = self.draft_flags(self.manifested_source(b"no fingerprint source\n"), "No fingerprint draft")
        self.index()
        preview = self.draft_call(*flags, "--dry-run")
        with patch.dict(os.environ, self.env(task)), patch.object(presenter_fingerprint, "observe", return_value=None):
            unavailable = self.draft_call(*flags, *self.approve_flags(preview))
        self.assertEqual(unavailable["exact_human_approval"]["presenter"]["fingerprint_state"], "unavailable")
        claim = self.claim_document(unavailable["exact_human_approval"]["approval_id"])
        self.assertIsNone(claim["session_presenter"]["process_fingerprint_sha256"])

    def test_legacy_claims_and_presenter_blocks_validate(self) -> None:
        archive_id = "sha256:" + "c" * 64
        good = {"schema": approval.SESSION_PRESENTER_SCHEMA, "work_session_ref": "work_session_" + "d" * 32,
                "presenter_sha256": "sha256:" + "e" * 64, "fingerprint_state": "observed",
                "process_fingerprint_sha256": "sha256:" + "f" * 64, "presenters_observed_before_this_claim": 2}
        self.assertEqual(approval.validate_session_presenter(good), good)
        for broken in ({**good, "fingerprint_state": "unavailable"}, {**good, "presenters_observed_before_this_claim": -1},
                       {**good, "extra": 1}, {**good, "process_fingerprint_sha256": None}):
            with self.assertRaises(approval.ExactHumanApprovalError):
                approval.validate_session_presenter(broken)
        approval.validate_session_presenter({**good, "fingerprint_state": "unavailable", "process_fingerprint_sha256": None})
        # a dialog claim may never carry the block
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(cli.archive_services.read_archive_id(self.root)),
            plan_sha256="sha256:" + "1" * 64, target_binding_sha256="sha256:" + "2" * 64,
            reviewer_claim=REVIEWER, review_binding_codes=("body_digest_reviewed",), warning_codes=())
        from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision

        decision = _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
                                               reason_code="exact_human_approval_approved",
                                               plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256)
        with self.assertRaises(approval.ExactHumanApprovalError):
            self.key.use_key(self.root, lambda key: approval._claim_exact_human_approval_core(
                self.root, context, decision, key, session_presenter=good), create_if_missing=True)
        del archive_id

    def test_grant_never_covers_a_flagged_legacy_identifier(self) -> None:
        self.assertEqual(permission.grant_blocking_warnings(("legacy_identifier_in_new_record", "other")),
                         ("legacy_identifier_in_new_record",))
        self.assertEqual(permission.grant_blocking_warnings(("warning_set_sha256:abc",)), ())
        task = self.establish("flagged")
        self.set_mode(task, "allow_all")
        object_id = self.manifested_source(b"legacy identifier source\n")
        self.index()
        flags = self.draft_flags(object_id, "Notes taken from ZET777 last week")
        preview = self.draft_call(*flags, "--dry-run")
        self.assertIn("legacy_identifier_in_new_record", preview["warnings"])
        explanation = preview["quality_check"]["warning_explanations"][0]
        self.assertEqual(explanation["code"], "legacy_identifier_in_new_record")
        self.assertEqual(explanation["zet_number_count"], 1)
        self.assertTrue(explanation["zet_number_in_title"])
        self.assertFalse(explanation["matched_text_echoed"])
        self.assertFalse(preview["quality_check"]["privacy_guards"]["matched_text_echoed"])
        dialogs = self.native.calls
        with patch.dict(os.environ, self.env(task)):
            refused = self.draft_call(*flags, *self.approve_flags(preview), ok=False)
        self.assertEqual(refused["reason_code"], "create_draft_warning_override_required")
        self.assertEqual(self.native.calls, dialogs)
        self.assertTrue(any("ZET0637" in line for line in refused["next_safe_actions"]))
        with patch.dict(os.environ, self.env(task)):
            written = self.draft_call(*flags, *self.approve_flags(preview), "--allow-warnings")
        self.assertEqual(self.native.calls, dialogs + 1)  # the grant did not cover it
        self.assertTrue(written["exact_human_approval"]["live_dialog_shown"])
        self.assertEqual(written["quality_check"]["warning_explanations"][0]["code"], "legacy_identifier_in_new_record")

    # ------------------------------------------------------------ surfaces
    def test_attention_block_mcp_holder_and_inventory(self) -> None:
        task = self.establish("surfaces")
        block = archive_services.write_result_session_permission_attention(self.root)
        self.assertEqual(block["state"], "observed")
        self.assertEqual(block["non_manual_session_count"], 0)
        self.assertFalse(block["review_recommended"])
        self.set_mode(task, "limited", ["create_draft"])
        block = archive_services.write_result_session_permission_attention(self.root)
        self.assertEqual(block["non_manual_session_count"], 1)
        self.assertEqual(block["presenter_bound_count"], 1)
        self.assertEqual(block["legacy_grant_count"], 0)
        self.assertTrue(block["review_recommended"])
        self.assertIn("handoff/accept", block["guidance"])
        self.assertNotIn(task["presenter"], json.dumps(block))
        missing = archive_services.write_result_session_permission_attention(Path(self.root) / "missing")
        self.assertEqual(missing["state"], "unavailable")
        # the MCP host keeps the secret in its process and strips it from the model's view
        route = mcp_server.tool_archive_work_session_manage({
            "archive_root": str(self.root), "action": "request-init", "client_app_ref": task["app"]})
        route_ref = route["structuredContent"]["result"]["task_route_ref"]
        created = mcp_server.tool_archive_work_session_manage({
            "archive_root": str(self.root), "action": "create", "approve": True,
            "client_app_ref": task["app"], "task_route_ref": route_ref,
            "request": {"label": "SYNTHETIC_PRIVATE_TASK_mcp", "reviewer_claim": REVIEWER}})
        session = created["structuredContent"]["result"]["work_session_binding"]["work_session_ref"]
        mcp_server.tool_archive_work_session_manage({
            "archive_root": str(self.root), "action": "claim", "apply": True,
            "client_app_ref": task["app"], "task_route_ref": route_ref, "work_session_ref": session})
        granted = mcp_server.tool_archive_work_session_manage({
            "archive_root": str(self.root), "action": "set-permission-mode", "approve": True,
            "client_app_ref": task["app"], "task_route_ref": route_ref, "work_session_ref": session,
            "request": {"reviewer_claim": REVIEWER, "permission_mode": "allow_all", "operations": [], "grant_hours": 1}})
        inner = granted["structuredContent"]["result"]
        self.assertNotIn("presenter_token", json.dumps(granted))
        self.assertTrue(inner["presenter_token_held_in_process"])
        self.assertFalse(inner["presenter_token_returned_once"])
        held = permission._process_presenter(session)
        self.assertIsNotNone(held)
        self.assertIsNotNone(permission.resolve_grant(self.root, client_app_ref=task["app"], task_route_ref=route_ref,
                                                      work_session_ref=session))
        permission.release_presenter(session)
        self.assertIsNone(permission.resolve_grant(self.root, client_app_ref=task["app"], task_route_ref=route_ref,
                                                   work_session_ref=session, presenter=None))
        # inventory: the feedback body write is grantable and the reopened writer set names compose
        self.assertIn(ExactHumanApprovalOperation.operator_feedback_body_write, GRANTABLE_OPERATIONS)
        self.assertNotIn(ExactHumanApprovalOperation.operator_feedback_body_write, ALWAYS_DIALOG_OPERATIONS)
        self.assertIn("operator-feedback-compose", EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertEqual(_OPERATION_LABELS[ExactHumanApprovalOperation.operator_feedback_body_write], "운영자 피드백 편지 본문 기록")
        self.assertEqual(len(ALWAYS_DIALOG_OPERATIONS) + len(GRANTABLE_OPERATIONS), len(ExactHumanApprovalOperation))
        help_output = io.StringIO()
        with redirect_stdout(help_output), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(["work-session", "--help"])
        self.assertIn("presenter_token", help_output.getvalue())
        self.assertIn("handoff/accept", help_output.getvalue())


class LegacyIdentifierTests(unittest.TestCase):
    """[B] the shared detector and its surfaces."""

    def test_detector_flags_bare_identifiers_and_skips_wom_ids(self) -> None:
        scan = legacy_identifier.legacy_identifier_scan("see ZET777\nand zet0637 here\nsha256:" + "a" * 64)
        self.assertEqual(scan["zet_number_count"], 2)
        self.assertEqual(scan["zet_number_body_lines"], [1, 2])
        self.assertEqual(scan["notion_page_id_count"], 0)
        self.assertFalse(scan["matched_text_echoed"])
        for clean in ("zet_notion_db3_ZET0637", "approval_" + "0" * 32, "sha256/01/" + "0" * 64, "ZET12345",
                      "objet:" + "f" * 64):
            self.assertFalse(legacy_identifier.legacy_identifier_present(clean), clean)
        for flagged in ("ZET0637", "zet:notion:ZET637", "page 0123456789abcdef0123456789abcdef",
                        "01234567-89ab-cdef-0123-456789abcdef", "ZET777_final.pdf"):
            self.assertTrue(legacy_identifier.legacy_identifier_present(flagged), flagged)
        self.assertTrue(legacy_identifier.label_legacy_identifier_present("ZET777 scan.pdf"))
        self.assertFalse(legacy_identifier.label_legacy_identifier_present("zet_notion_db3_ZET0637.pdf"))
        self.assertIsNone(legacy_identifier.legacy_identifier_explanation("clean body", title="clean"))
        migrated = legacy_identifier.legacy_identifier_explanation("ZET777", migrated_record=True, mapping_available=True)
        self.assertEqual(migrated["code"], "legacy_identifier_in_migrated_record")
        self.assertTrue(migrated["next_safe_actions"])
        self.assertIn("zet_notion_db3_ZET0637", migrated["guidance"])

    def test_objet_link_and_source_intake_labels_warn_only(self) -> None:
        from wom_kit import completion_workflows

        self.assertTrue(completion_workflows._label_legacy_identifier_review("ZET777 scan"))
        self.assertFalse(completion_workflows._label_legacy_identifier_review(None))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
            source = root / "staging" / "ZET777-scan.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("synthetic source bytes\n", encoding="utf-8")
            plan = archive_services.source_intake_plan(root, local_path=source)
            self.assertIn("legacy_identifier_in_source_label", plan["warnings"])
            self.assertIn("full WOM id", plan["legacy_identifier_guidance"])
            self.assertNotIn("legacy_identifier_in_source_label",
                             archive_services.source_intake_plan(root, local_path=source, title="Clean title")["warnings"])
            self.assertFalse(archive_services.legacy_identifier_mapping_available(root / "missing"))

    def test_revision_plan_explanations_name_fields_and_tables(self) -> None:
        body = "intro\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        issues = [{"code": "document_type_missing", "severity": "warning"},
                  {"code": "table_row_mapping_missing", "severity": "warning"},
                  {"code": "table_structure_review_missing", "severity": "warning"},
                  {"code": "something_else", "severity": "blocker"}]
        explanations = archive_services.zettel_quality_warning_explanations({}, body, issues)
        self.assertEqual([item["code"] for item in explanations],
                         ["document_type_missing", "table_row_mapping_missing", "table_structure_review_missing"])
        self.assertEqual(explanations[0]["field"], "document_type")
        self.assertIn("raw_note", explanations[0]["allowed_values"])
        self.assertEqual(explanations[1]["tables"], [{"ordinal": 1, "header_body_line": 2, "row_count": 1}])
        self.assertIn("row_mapping", explanations[1]["field"])
        self.assertFalse(explanations[2]["cell_text_echoed"])
        self.assertEqual(archive_services.zettel_quality_warning_explanations({}, "", []), [])


class FeedbackComposeExactApprovalTests(unittest.TestCase):
    """[C]/[D] compose --approve opens the dialog, receipts name the claim, the revise path is announced."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.native = _permission_fixture._session_fixture.SessionNative()
        self.key = _permission_fixture._session_fixture._ActiveSyntheticKey()
        for seam in (patch.object(_permission_fixture._session_fixture.windows, "_CtypesTaskDialogNative", return_value=self.native),
                     patch.object(broker, "_production_key_provider", return_value=self.key)):
            seam.start()
            self.addCleanup(seam.stop)
        self.request_relative = "profiles/local/operator-feedback/requests/letter165.json"
        request_path = self.root.joinpath(*self.request_relative.split("/"))
        request_path.parent.mkdir(parents=True, exist_ok=True)
        self.request = {
            "schema": body_module.REQUEST_SCHEMA, "feedback_id": "synthetic-letter-165",
            "title": "Synthetic compose under exact approval",
            "sections": {"environment": "synthetic", "task": "compose", "observed_failure": "none",
                         "suspected_cause": "none", "requested_resolution": "dialog", "reproduction": "run it"},
        }
        request_path.write_text(json.dumps(self.request, ensure_ascii=False) + "\n", encoding="utf-8")
        self.request_path = request_path

    def run_cli(self, *args, ok=True):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([*args, "--format", "json"])
        result = json.loads(out.getvalue())
        self.assertEqual(code == 0, ok, result)
        return result

    def compose(self, *flags, ok=True):
        return self.run_cli("operator-feedback-compose", str(self.root), "--request", self.request_relative, *flags, ok=ok)

    def test_create_opens_one_dialog_and_the_receipt_names_the_claim(self) -> None:
        preview = self.compose("--dry-run")
        self.assertEqual(self.native.calls, 0)
        refused = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"],
                               "--reviewed-by", "operator:not-a-person", ok=False)
        self.assertEqual(refused["reason_codes"], ["feedback_compose_reviewer_claim_invalid"])
        stale = self.compose("--approve", "--expected-plan-sha256", "0" * 64, "--reviewed-by", REVIEWER, ok=False)
        self.assertEqual(stale["reason_codes"], ["feedback_compose_plan_changed"])
        self.assertEqual(self.native.calls, 0)
        created = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"], "--reviewed-by", REVIEWER)
        self.assertEqual(self.native.calls, 1)
        context = self.native.contexts[0] if hasattr(self.native, "contexts") else None
        self.assertEqual(created["state"], "written")
        summary = created["exact_human_approval"]
        self.assertTrue(summary["live_dialog_shown"])
        self.assertTrue(created["exact_human_approval_reference_present"])
        self.assertEqual(created["draft_record"]["skipped_reason"], "not_requested")
        self.assertTrue(any("--intent revise" in line for line in created["next_safe_actions"]))
        receipt = json.loads((self.root / created["proposed_receipt_relative_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema"], body_module.RECEIPT_SCHEMA_V2)
        self.assertEqual(receipt["exact_human_approval"]["approval_id"], summary["approval_id"])
        self.assertEqual(receipt["exact_human_approval"]["operation"], "operator_feedback_body_write")
        self.assertEqual(set(receipt), body_module.RECEIPT_KEYS | {"exact_human_approval"})
        rendered = json.dumps(created) + (json.dumps(context, ensure_ascii=False) if context else "")
        self.assertNotIn(self.request["title"], rendered)
        # the check accepts the v0.2 receipt and reports the claim reference
        check = self.run_cli("operator-feedback-body-check", str(self.root), "--feedback-id", self.request["feedback_id"],
                             "--dry-run", ok=False)  # no record yet
        self.assertIn("feedback_record_binding_missing", check["blockers"])
        self.assertTrue(check["exact_human_approval_reference_present"])
        self.assertTrue(check["receipt_persisted"])
        self.assertEqual(len(check["next_safe_actions"]), 5)
        # an idempotent replay of the same approval matches the existing receipt without a second claim
        replay = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"], "--reviewed-by", REVIEWER)
        self.assertEqual(self.native.calls, 2)
        self.assertTrue(replay["ok"], replay)
        self.assertEqual(replay["exact_human_approval"]["status"], "succeeded")

    def test_create_with_draft_record_then_revise_under_a_second_dialog(self) -> None:
        preview = self.compose("--dry-run")
        created = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"], "--reviewed-by", REVIEWER,
                               "--create-draft-record")
        self.assertTrue(created["draft_record"]["record_created"], created["draft_record"])
        self.assertTrue((self.root / created["draft_record"]["record_path"]).is_file())
        body_sha = created["feedback_ref"].rsplit(":", 1)[-1]
        check = self.run_cli("operator-feedback-body-check", str(self.root), "--feedback-id", self.request["feedback_id"], "--dry-run")
        self.assertTrue(check["record_binding"]["record_present"])
        self.request["sections"]["observed_failure"] = "a corrected synthetic fact"
        self.request_path.write_text(json.dumps(self.request, ensure_ascii=False) + "\n", encoding="utf-8")
        revise_preview = self.compose("--dry-run", "--intent", "revise", "--expected-body-sha256", body_sha)
        self.assertTrue(revise_preview["ok"], revise_preview)
        dialogs = self.native.calls
        revised = self.compose("--approve", "--intent", "revise", "--expected-body-sha256", body_sha,
                               "--expected-plan-sha256", revise_preview["plan_sha256"], "--reviewed-by", REVIEWER)
        self.assertEqual(self.native.calls, dialogs + 1)
        self.assertTrue(revised["ok"], revised)
        self.assertNotIn("draft_record", revised)
        revision_receipts = list((self.root / "receipts" / "operator-feedback" / "body" / "revisions").rglob("*-to-*.json"))
        self.assertEqual(len(revision_receipts), 1)
        revision = json.loads(revision_receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(revision["schema"], body_module.REVISION_RECEIPT_SCHEMA_V2)
        self.assertEqual(revision["exact_human_approval"]["approval_id"], revised["exact_human_approval"]["approval_id"])
        # the revision claim bound the warning set (digested, as every CLI context does); the create claim had none
        claims = list((self.root / "profiles" / "local" / "exact-human-approvals" / "claims").glob("approval_*.json"))
        codes = sorted(json.loads(p.read_text(encoding="utf-8"))["context"]["warning_codes"] for p in claims)
        self.assertEqual(len(codes), 2)
        self.assertEqual(codes[0], [])
        self.assertTrue(codes[1] and codes[1][0].startswith("warning_set_"), codes)

    def test_cancelled_dialog_writes_nothing_and_legacy_receipts_stay_valid(self) -> None:
        preview = self.compose("--dry-run")
        self.native.approve = False
        before = sorted(p.as_posix() for p in self.root.rglob("*"))
        cancelled = self.compose("--approve", "--expected-plan-sha256", preview["plan_sha256"], "--reviewed-by", REVIEWER, ok=False)
        self.assertEqual(cancelled["reason_codes"], ["exact_human_approval_cancelled"])
        self.assertEqual(before, sorted(p.as_posix() for p in self.root.rglob("*")))
        # a v0.1 receipt written by the service (emergency lane / pre-v0.4.34) still checks
        plan = body_module.plan_operator_feedback_body(self.root, self.request_path)
        legacy = body_module.approve_operator_feedback_body(self.root, self.request_path,
                                                            expected_plan_sha256=plan["plan_sha256"], reviewed_by="operator:legacy")
        self.assertTrue(legacy["ok"], legacy)
        self.assertFalse(legacy["exact_human_approval_reference_present"])
        receipt = json.loads((self.root / legacy["proposed_receipt_relative_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema"], body_module.RECEIPT_SCHEMA)
        self.assertNotIn("exact_human_approval", receipt)
        check = body_module.check_operator_feedback_body(self.root, self.request["feedback_id"])
        self.assertTrue(check["receipt_persisted"])
        self.assertFalse(check["exact_human_approval_reference_present"])


if __name__ == "__main__":
    unittest.main()
