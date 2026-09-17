"""v0.4.24: per-work-session permission modes (manual / limited / allow_all).

The grant is one human decision on the claimed session; a permitted write
skips the native dialog but still publishes its own one-use claim, which
records the permission mechanism; always-dialog operations can never be
granted; pause/handoff/complete/recover clear the grant; a grant revoked
between the decision and the claim fails closed. Synthetic archive, injected
dialog and key only."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import mcp_server
from wom_kit import work_session_permission as permission
from wom_kit import work_session_registry as registry
from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID, ExactHumanApprovalContext, ExactHumanApprovalOperation,
    PERMISSION_INTERACTIVE_INTENT_MECHANISM,
)
from wom_kit.work_session_command_modes import resolve_work_session_mode
import test_v0420_session_intake_git_public_workflow as _session_fixture

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-session-reviewer"


class _CountingNative:
    def __init__(self):
        self.calls = 0

    def show(self, **_kwargs):
        self.calls += 1
        return APPROVE_BUTTON_ID, False


class SessionPermissionModeTests(unittest.TestCase):
    _Fixture = _session_fixture.SessionIntakeGitPublicWorkflowTests
    setUp = _Fixture.setUp
    call = _Fixture.call
    session_call = _Fixture.session_call
    establish = _Fixture.establish
    routing = _Fixture.routing

    def draft_call(self, *flags, ok=True):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(["create-draft", str(self.root), "--format", "json", *flags])
        result = json.loads(output.getvalue())
        if ok is not None:
            self.assertEqual(code == 0, ok, result)
        return result

    def manifested_source(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        path = self.root.joinpath(*logical_key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({
                "object_id": f"sha256:{digest}", "sha256": digest, "logical_key": logical_key,
                "mime": "text/plain", "size_bytes": len(raw),
                "locations": [{"provider": "local", "path": logical_key, "availability": "available"}],
                "provenance": {"source": "test"}, "captured_at": "2026-09-18T00:00:00Z",
            }, ensure_ascii=False) + "\n")
        return f"sha256:{digest}"

    def draft_flags(self, object_id: str, title: str):
        return ("--title", title, "--abstract", "A reviewed summary for the permission test.",
                "--body", "A reviewed summary of the manifested source.", "--kind", "record_note",
                "--created-by", "ai_runtime:test", "--creation-mode", "ai_assisted",
                "--assisted-by", "ai_runtime:test", "--facet", "record_type=source_fidelity",
                "--source-fidelity", "faithful_summary", "--fidelity-audience", "private_self",
                "--fidelity-source-object-id", object_id)

    def approve_flags(self, preview):
        replay = preview["approval_replay"]
        return ("--draft-id", replay["draft_id"], "--created-at", replay["created_at"],
                "--expected-body-sha256", replay["expected_body_sha256"],
                "--expected-source-fidelity-plan-sha256", replay["expected_source_fidelity_plan_sha256"],
                "--approve", "--draft-approved-by", REVIEWER)

    def set_mode(self, task, mode, operations=None, ok=True):
        return self.call("work-session", "--action", "set-permission-mode", "--approve", "--request-stdin",
                         *task["refs"], "--work-session-ref", task["session"],
                         request={"reviewer_claim": REVIEWER, "permission_mode": mode, "operations": operations or []},
                         ok=ok)

    def inspect(self, task):
        return self.call("work-session", "--action", "inspect", "--kind", "session", "--ref", task["session"])["item"]

    def claim_document(self, approval_id):
        path = self.root / "profiles" / "local" / "exact-human-approvals" / "claims" / f"{approval_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def index(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["index", str(self.root), "--format", "json"]), 0)

    def env(self, task):
        return {"WOM_CLIENT_APP_REF": task["app"], "WOM_TASK_ROUTE_REF": task["route"], "WOM_WORK_SESSION_REF": task["session"]}

    # ------------------------------------------------------------ grant lifecycle
    def test_set_permission_mode_is_one_human_decision_on_the_claimed_session(self) -> None:
        task = self.establish("grant")
        dialogs = self.native.calls
        self.assertEqual(self.inspect(task)["permission_mode"], "manual")
        result = self.set_mode(task, "limited", ["create_draft", "mint_zet"])
        self.assertEqual(self.native.calls, dialogs + 1)  # exactly one dialog for the grant
        self.assertEqual(result["result"]["permission_mode"], "limited")
        self.assertEqual(result["result"]["permitted_operations"], ["create_draft", "mint_zet"])
        self.assertTrue(result["result"]["current_claim_ownership_verified"])
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))
        row = self.inspect(task)
        self.assertEqual(row["permission_mode"], "limited")
        self.assertEqual(row["permitted_operations"], ["create_draft", "mint_zet"])
        self.assertEqual(row["state"], "claimed")
        # the actor's observed binding follows the new session revision
        actor = self.routing(task).read().document()
        self.assertEqual(actor["last_completed_operation"]["kind"], "human_session_decision")
        self.assertIsNone(actor.get("pending_manifest_sha256"))
        # back to manual is the same human action and clears the key
        self.set_mode(task, "manual")
        self.assertEqual(self.native.calls, dialogs + 2)
        self.assertEqual(self.inspect(task)["permission_mode"], "manual")
        self.assertNotIn("permission", registry.RegistrySnapshot.__dict__)  # no accidental class-level field

    def test_always_dialog_operations_are_never_grantable(self) -> None:
        task = self.establish("refuse")
        refused = self.set_mode(task, "limited", ["project_version_update"], ok=False)
        self.assertEqual(refused["reason_code"], "work_session_permission_operation_not_grantable")
        self.assertEqual(self.inspect(task)["permission_mode"], "manual")
        with self.assertRaises(permission.WorkSessionPermissionError):
            permission.normalize_grant("allow_all", ["create_draft"])
        grant = permission.SessionPermissionGrant(
            client_app_ref=task["app"], task_route_ref=task["route"], work_session_ref=task["session"],
            claim_ref="claim_" + "a" * 32, binding_sha256="sha256:" + "b" * 64, mode="allow_all", operations=())
        for member in permission.ALWAYS_DIALOG_OPERATIONS:
            self.assertFalse(grant.permits(member), member)
        self.assertTrue(grant.permits(ExactHumanApprovalOperation.create_draft))
        self.assertEqual(len(permission.ALWAYS_DIALOG_OPERATIONS) + len(permission.GRANTABLE_OPERATIONS),
                         len(ExactHumanApprovalOperation))

    # ------------------------------------------------------------ writes under a grant
    def test_permitted_write_skips_the_dialog_and_its_claim_records_the_mechanism(self) -> None:
        task = self.establish("write")
        object_id = self.manifested_source(b"permission mode source\n")
        self.index()
        self.set_mode(task, "limited", ["create_draft"])
        refs = (*task["refs"], "--work-session-ref", task["session"])
        flags = self.draft_flags(object_id, "Draft under a limited grant")
        preview = self.draft_call(*refs, *flags, "--dry-run")
        dialogs = self.native.calls
        created = self.draft_call(*refs, *flags, *self.approve_flags(preview))
        self.assertEqual(self.native.calls, dialogs)  # no dialog for the permitted write
        summary = created["exact_human_approval"]
        self.assertEqual(summary["approval_mechanism"], PERMISSION_INTERACTIVE_INTENT_MECHANISM)
        self.assertFalse(summary["live_dialog_shown"])
        self.assertEqual(summary["status"], "succeeded")
        claim = self.claim_document(summary["approval_id"])
        self.assertEqual(claim["interactive_intent"], {"mechanism": PERMISSION_INTERACTIVE_INTENT_MECHANISM, "confirmed": True})
        self.assertEqual(claim["status"], "succeeded")
        # the receipt names that claim; the claim states the mechanism
        receipt = json.loads((self.root / created["source_fidelity_draft_receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["work_session_binding"]["work_session_ref"], task["session"])
        self.assertEqual(created["exact_human_approval_reference"]["approval_id"], summary["approval_id"])

    def test_environment_context_grants_sessionless_commands_and_manual_still_asks(self) -> None:
        task = self.establish("env")
        object_id = self.manifested_source(b"environment context source\n")
        self.index()
        flags = self.draft_flags(object_id, "Draft under allow_all through the environment")
        preview = self.draft_call(*flags, "--dry-run")
        # manual: the dialog opens
        dialogs = self.native.calls
        with patch.dict(os.environ, self.env(task)):
            manual = self.draft_call(*flags, *self.approve_flags(preview))
        self.assertEqual(self.native.calls, dialogs + 1)
        self.assertNotEqual(manual["exact_human_approval"]["approval_mechanism"], PERMISSION_INTERACTIVE_INTENT_MECHANISM)
        self.assertTrue(manual["exact_human_approval"]["live_dialog_shown"])
        # allow_all through the retained refs in the environment: no dialog
        self.set_mode(task, "allow_all")
        second = self.draft_flags(self.manifested_source(b"second source\n"), "Second draft under allow_all")
        self.index()  # the first write changed the archive; approvals need a current index
        preview2 = self.draft_call(*second, "--dry-run")
        dialogs = self.native.calls
        with patch.dict(os.environ, self.env(task)):
            granted = self.draft_call(*second, *self.approve_flags(preview2))
        self.assertEqual(self.native.calls, dialogs)
        self.assertEqual(granted["exact_human_approval"]["approval_mechanism"], PERMISSION_INTERACTIVE_INTENT_MECHANISM)
        # a foreign or stale route in the environment resolves to the dialog
        third = self.draft_flags(self.manifested_source(b"third source\n"), "Third draft with a wrong route")
        self.index()
        preview3 = self.draft_call(*third, "--dry-run")
        with patch.dict(os.environ, {**self.env(task), "WOM_TASK_ROUTE_REF": "task_route_" + "0" * 32}):
            stale = self.draft_call(*third, *self.approve_flags(preview3))
        self.assertEqual(self.native.calls, dialogs + 1)
        self.assertTrue(stale["exact_human_approval"]["live_dialog_shown"])

    def test_pause_clears_the_grant(self) -> None:
        task = self.establish("pause")
        self.set_mode(task, "allow_all")
        self.assertEqual(self.inspect(task)["permission_mode"], "allow_all")
        self.assertIsNotNone(permission.resolve_grant(self.root, client_app_ref=task["app"],
                                                      task_route_ref=task["route"], work_session_ref=task["session"]))
        self.session_call("--action", "pause", "--apply", *task["refs"], "--work-session-ref", task["session"])
        self.assertEqual(self.inspect(task)["permission_mode"], "manual")
        self.assertEqual(self.inspect(task)["state"], "paused")
        self.assertIsNone(permission.resolve_grant(self.root, client_app_ref=task["app"],
                                                   task_route_ref=task["route"], work_session_ref=task["session"]))
        # resuming the session starts manual again; a new grant needs a new decision
        self.session_call("--action", "resume", "--apply", *task["refs"], "--work-session-ref", task["session"])
        self.assertEqual(self.inspect(task)["permission_mode"], "manual")

    def test_a_grant_revoked_between_decision_and_claim_fails_closed(self) -> None:
        task = self.establish("revoke")
        self.set_mode(task, "allow_all")
        grant = permission.resolve_grant(self.root, client_app_ref=task["app"],
                                         task_route_ref=task["route"], work_session_ref=task["session"])
        self.assertIsNotNone(grant)
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                cli.archive_services.read_archive_id(self.root)),
            plan_sha256="sha256:" + "1" * 64, target_binding_sha256="sha256:" + "2" * 64,
            reviewer_claim=REVIEWER, review_binding_codes=("body_digest_reviewed",), warning_codes=())
        native = _CountingNative()
        writes = []
        with patch.object(permission, "grant_still_permits", return_value=False):
            with self.assertRaises(broker.ExactHumanApprovalWorkflowError) as raised:
                broker._execute_exact_human_approved_write_core(
                    self.root, context, lambda claim: writes.append(claim) or {"ok": True},
                    native=native, key_provider=self.key, session_permission=grant)
        self.assertEqual(raised.exception.code, "exact_human_approval_permission_revoked")
        self.assertEqual(native.calls, 0)
        self.assertEqual(writes, [])
        claims = list((self.root / "profiles" / "local" / "exact-human-approvals" / "claims").glob("approval_*.json"))
        self.assertFalse(any(json.loads(p.read_text(encoding="utf-8"))["context_sha256"]
                             == approval.exact_human_approval_context_sha256(context) for p in claims))
        # with the grant intact and a permitted operation, no dialog and one claim
        outcome = broker._execute_exact_human_approved_write_core(
            self.root, context, lambda claim: {"ok": True, "files_written": []},
            native=native, key_provider=self.key, session_permission=grant)
        self.assertEqual(native.calls, 0)
        self.assertEqual(outcome["exact_human_approval"]["approval_mechanism"], PERMISSION_INTERACTIVE_INTENT_MECHANISM)
        # an always-dialog operation ignores the grant even in allow_all
        update_context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.project_version_update,
            archive_identity_sha256=context.archive_identity_sha256,
            plan_sha256="sha256:" + "3" * 64, target_binding_sha256="sha256:" + "4" * 64,
            reviewer_claim=REVIEWER, review_binding_codes=("body_digest_reviewed",), warning_codes=())
        broker._execute_exact_human_approved_write_core(
            self.root, update_context, lambda claim: {"ok": True, "files_written": []},
            native=native, key_provider=self.key, session_permission=grant)
        self.assertEqual(native.calls, 1)

    # ------------------------------------------------------------ surfaces
    def test_command_modes_and_mcp_enum_carry_the_action(self) -> None:
        fresh = resolve_work_session_mode(action="set-permission-mode", approve=True)
        self.assertEqual(fresh["mode"], "set-permission-mode")
        self.assertTrue(fresh["native_approval_required"])
        rereview = resolve_work_session_mode(action="set-permission-mode", approve=True, review_original=True)
        self.assertTrue(rereview["native_approval_required"])
        resume = resolve_work_session_mode(action="set-permission-mode", resume=True)
        self.assertTrue(resume["available"])
        self.assertFalse(resume["native_approval_required"])
        self.assertFalse(resolve_work_session_mode(action="set-permission-mode", apply=True)["available"])
        source = (KIT_ROOT / "src" / "wom_kit" / "mcp_server.py").read_text(encoding="utf-8")
        self.assertIn('"set-permission-mode"]', source)
        self.assertIsNotNone(mcp_server)

    def test_registry_transition_and_historical_rows(self) -> None:
        task = self.establish("registry")
        store = self.store
        snapshot = store.read()
        row = snapshot._document["sessions"][task["session"]]
        self.assertEqual(row["state"], "claimed")
        planned = registry.plan_transition(snapshot, action="set-permission-mode", client_app_ref=task["app"],
                                           work_session_ref=task["session"], claim_ref=row["claim_ref"],
                                           permission={"mode": "limited", "operations": ["create_draft"]})
        after = planned.after._document["sessions"][task["session"]]
        self.assertEqual(after["permission"], {"mode": "limited", "operations": ["create_draft"]})
        self.assertEqual(after["revision"], row["revision"] + 1)
        self.assertEqual(planned._request["permission"], {"mode": "limited", "operations": ["create_draft"]})
        self.assertNotIn("permission", registry.plan_transition(
            snapshot, action="pause", client_app_ref=task["app"], work_session_ref=task["session"],
            claim_ref=row["claim_ref"])._request)
        with self.assertRaises(registry.WorkSessionRegistryError):
            registry.plan_transition(snapshot, action="pause", client_app_ref=task["app"],
                                     work_session_ref=task["session"], claim_ref=row["claim_ref"],
                                     permission={"mode": "allow_all", "operations": []})
        with self.assertRaises(registry.WorkSessionRegistryError):
            registry.plan_transition(snapshot, action="set-permission-mode", client_app_ref=task["app"],
                                     work_session_ref=task["session"], claim_ref="claim_" + "f" * 32,
                                     permission={"mode": "allow_all", "operations": []})
        # a paused row cannot carry a permission; a claimed row without the key is the legacy shape
        broken = json.loads(json.dumps(planned.after._document))
        broken["sessions"][task["session"]].update(state="paused", claim_ref=None)
        with self.assertRaises(registry.WorkSessionRegistryError):
            registry.RegistrySnapshot(broken)
        legacy = json.loads(json.dumps(snapshot._document))
        self.assertNotIn("permission", legacy["sessions"][task["session"]])
        registry.RegistrySnapshot(legacy)


if __name__ == "__main__":
    unittest.main()
