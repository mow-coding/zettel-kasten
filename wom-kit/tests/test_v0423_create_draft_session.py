"""v0.4.23 LR-06a: create-draft bound to a claimed work session.

The session refs are verified under the held archive lane, the scope digest is
frozen into the reviewed fidelity plan, the actor records the operation as
pending then completed, and the receipt carries the binding. Sessionless
create-draft is unchanged. Synthetic archive, injected dialog and key only."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from wom_kit import archive_cli as cli
from wom_kit import archive_services
from wom_kit import work_session_native_write as native_write
import test_v0420_session_intake_git_public_workflow as _session_fixture

KIT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = KIT_ROOT / "tools"


class CreateDraftSessionTests(unittest.TestCase):
    _Fixture = _session_fixture.SessionIntakeGitPublicWorkflowTests
    setUp = _Fixture.setUp
    call = _Fixture.call
    session_call = _Fixture.session_call
    establish = _Fixture.establish
    routing = _Fixture.routing

    # the fixture's call() adds flags the git commands need; create-draft takes its own
    def draft_call(self, command, *flags, ok=True):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli.main([command, str(self.root), "--format", "json", *flags])
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
                "provenance": {"source": "test"}, "captured_at": "2026-09-17T08:00:00Z",
            }, ensure_ascii=False) + "\n")
        return f"sha256:{digest}"

    def draft_flags(self, object_id: str, title: str):
        return ("--title", title, "--abstract", "A reviewed summary for the session test.",
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
                "--approve", "--draft-approved-by", "person:synthetic-session-reviewer")

    def test_session_bound_preview_and_approve_attribute_the_draft(self) -> None:
        task = self.establish("draft")
        refs = (*task["refs"], "--work-session-ref", task["session"])
        object_id = self.manifested_source("세션 테스트 원본\n".encode("utf-8"))
        flags = self.draft_flags(object_id, "Session bound draft")
        self.draft_call("index")

        plain = self.draft_call("create-draft", *flags, "--dry-run")
        self.assertNotIn("work_session", plain)
        bound = self.draft_call("create-draft", *refs, *flags, "--dry-run")
        session = bound["work_session"]
        self.assertTrue(session["bound"])
        self.assertRegex(session["scope_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(session["work_session_binding_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(session["private_values_echoed"])
        self.assertNotEqual(bound["source_fidelity_plan_sha256"], plain["source_fidelity_plan_sha256"])
        self.assertNotIn(task["session"], json.dumps(bound))
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(bound))
        # the same session yields the same scope while nothing changed
        self.assertEqual(self.draft_call("create-draft", *refs, *flags, "--dry-run")["work_session"], session)

        before = self.routing(task).read().document()
        self.assertIsNone(before.get("pending_manifest_sha256"))
        created = self.draft_call("create-draft", *refs, *flags, *self.approve_flags(bound))
        self.assertTrue(created["ok"], created)
        self.assertEqual(created["work_session"]["scope_sha256"], session["scope_sha256"])

        receipt_path = self.root / created["source_fidelity_draft_receipt_path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["work_session_scope_sha256"], session["scope_sha256"])
        self.assertEqual(receipt["work_session_binding"]["work_session_ref"], task["session"])
        self.assertEqual(receipt["work_session_binding"]["binding_sha256"], session["work_session_binding_sha256"])
        self.assertEqual(receipt["source_fidelity_plan_sha256"], bound["source_fidelity_plan_sha256"])
        schema = json.loads((KIT_ROOT / "schemas" / "source-fidelity-draft-receipt.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        self.assertTrue(archive_services._source_fidelity_private_receipt_shape_valid_v1(receipt))
        broken = dict(receipt)
        del broken["work_session_scope_sha256"]
        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(broken))

        # the actor recorded the completed operation; nothing is left pending
        after = self.routing(task).read().document()
        self.assertIsNone(after.get("pending_manifest_sha256"))
        completed = after["last_completed_operation"]
        self.assertEqual(completed["kind"], "create_draft")
        self.assertEqual(completed["manifest_sha256"], "sha256:" + bound["source_fidelity_plan_sha256"])
        self.assertEqual(after["work_session_ref"], task["session"])

        # mint-time verification recomputes the plan with the stored scope
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root, self.root / created["path"], affirmations=None)
        self.assertTrue(verification["ok"], verification)
        # an exact replay is idempotent and publishes nothing new
        replay = self.draft_call("create-draft", *refs, *flags, *self.approve_flags(bound))
        self.assertTrue(replay.get("idempotent_replay"), replay)
        self.assertEqual(self.routing(task).read().document()["last_completed_operation"], completed)

    def test_missing_or_foreign_session_refs_are_refused_without_a_dialog(self) -> None:
        task_a, task_b = self.establish("a"), self.establish("b")
        object_id = self.manifested_source(b"another manifested source\n")
        flags = self.draft_flags(object_id, "Refused session draft")
        without_session = self.draft_call("create-draft", *task_a["refs"], *flags, "--dry-run", ok=False)
        self.assertEqual(without_session["reason_codes"], ["work_session_task_context_required"])
        foreign = self.draft_call("create-draft", *task_a["refs"], "--work-session-ref", task_b["session"],
                            *flags, "--dry-run", ok=False)
        self.assertEqual(foreign["reason_codes"], ["work_session_task_context_mismatch"])
        both_modes = self.draft_call("create-draft", *task_a["refs"], "--work-session-ref", task_a["session"],
                               *flags, "--dry-run", "--approve", ok=False)
        self.assertIn(both_modes["reason_codes"][0], {"capability_mode_conflicting", "work_session_native_write_mode_required"})
        human = self.draft_call("create-draft", *task_a["refs"], "--work-session-ref", task_a["session"],
                          "--title", "Human draft", "--body", "body", "--kind", "record_note",
                          "--created-by", "person:test", "--dry-run", ok=False)
        self.assertEqual(human["reason_codes"], ["work_session_native_write_mode_required"])
        for result in (without_session, foreign, both_modes, human):
            self.assertEqual(result["files_written"], [])
            self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_scope_helpers_refuse_a_changed_actor(self) -> None:
        task = self.establish("helper")
        from wom_kit import work_session_service as sessions

        def run(held):
            scope, store, routing, selected = native_write.native_write_scope_held(
                self.root, held=held, kind="create_draft", client_app_ref=task["app"],
                task_route_ref=task["route"], work_session_ref=task["session"])
            self.assertEqual(scope.binding.work_session_ref, task["session"])
            self.assertEqual(scope.public_projection()["kind"], "create_draft")
            pending = native_write.publish_pending_held(scope, routing, selected, held=held,
                plan_sha256="sha256:" + "1" * 64, context_sha256="sha256:" + "2" * 64)
            self.assertEqual(pending.pending_operation().document()["kind"], "create_draft")
            with self.assertRaises(native_write.WorkSessionNativeWriteError) as raised:
                native_write.native_write_scope_held(self.root, held=held, kind="create_draft",
                    client_app_ref=task["app"], task_route_ref=task["route"], work_session_ref=task["session"])
            self.assertEqual(raised.exception.code, "work_session_original_operation_pending")
            with self.assertRaises(native_write.WorkSessionNativeWriteError) as mismatch:
                native_write.publish_completed_held(scope, routing, pending, held=held,
                    plan_sha256="sha256:" + "3" * 64, context_sha256="sha256:" + "2" * 64)
            self.assertEqual(mismatch.exception.code, "work_session_native_write_changed")
            done = native_write.publish_completed_held(scope, routing, pending, held=held,
                plan_sha256="sha256:" + "1" * 64, context_sha256="sha256:" + "2" * 64)
            self.assertIsNone(done.pending_operation())
            return True

        self.assertTrue(sessions._write(self.root, cancel_requested=lambda: False,
                                        progress=lambda _event: None, run=run))
        with self.assertRaises(native_write.WorkSessionNativeWriteError):
            native_write.NativeWriteScope(kind="unknown", binding=None, task_route_ref="x",
                                          actor_sha256="y", registry_preimage_sha256="z", claim_ref="w")

    def test_coverage_manifest_records_the_integration(self) -> None:
        import sys
        sys.path.insert(0, str(TOOLS_ROOT))
        try:
            import check_writer_session_coverage as gate
        finally:
            sys.path.remove(str(TOOLS_ROOT))
        problems, counts = gate.check()
        self.assertEqual(problems, [])
        manifest = json.loads((KIT_ROOT / "docs" / "writer-session-coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["paths"]["create-draft"]["status"], "session_integrated")
        self.assertIn("test_v0423_create_draft_session", manifest["paths"]["create-draft"]["evidence"])
        self.assertEqual(counts["pending"], 33)  # v0.4.28 restore, v0.4.29 offload, v0.4.30 claim finalize and v0.4.33 upload are pending


if __name__ == "__main__":
    unittest.main()
