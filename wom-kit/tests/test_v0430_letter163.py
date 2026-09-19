"""v0.4.30: beta letter 163 core — the mint-zet gate.

A source-fidelity draft's approve needs the plan digest the dry-run computed.
The dry-run now says so (approval_handoff + next_safe_actions), approve
refuses with a fixed code before any claim exists when it is missing or
stale, a writer-level failure still names its fixed cause and stage in the
mint error envelope, a hand-edited draft body is a named warning, the
incomplete-objet-reference block carries body line numbers (never text),
and a fidelity draft inside a mint batch binds its plan digest itself.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli, archive_services
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL

import test_v03313_source_fidelity as fidelity_tests

REVIEWER = "person:fidelity-test"
CLAIMS = "profiles/local/exact-human-approvals/claims"


class _Native:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0

    def show(self, **kwargs):
        self.calls += 1
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class Letter163MintGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fidelity_tests.SourceFidelityV03313Tests("setUp")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.native = _Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=_KeyProvider()))
        self.outputs: list[str] = []

    # -- helpers -----------------------------------------------------------

    def fidelity_draft(self, *, draft_id: str = "zet_20260919_101_letter163", body: str | None = None) -> Path:
        object_id = self.fixture.manifested_source(b"Exact source bytes for the letter 163 mint gate test.")
        summary = body if body is not None else (
            "A faithful summary of the exact source: it records the mint gate case for letter 163 "
            "in enough words to stand alone as a first self-contained note."
        )
        result = self.fixture.create_approved(
            self.fixture.ai_kwargs(object_id, draft_id=draft_id, title="Letter 163 mint gate", body=summary, mode="faithful_summary")
        )
        return self.root / result["path"]

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        return code, json.loads(out.getvalue())

    def mint_args(self, path: Path) -> list[str]:
        return [
            "mint-zet", str(self.root), "--path", path.relative_to(self.root).as_posix(),
            "--affirm", "one_clear_purpose", "--affirm", "sensitive_content_reviewed",
            "--allow-warnings", "--reviewed-by", REVIEWER,
        ]

    def started_claims(self) -> list[Path]:
        directory = self.root / CLAIMS
        if not directory.is_dir():
            return []
        found = []
        for path in sorted(directory.glob("approval_*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("status") == "started":
                found.append(path)
        return found

    # -- tests -------------------------------------------------------------

    def test_dry_run_names_the_required_plan_digest_and_the_approve_shape(self):
        path = self.fidelity_draft()
        code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertTrue(preview["ok"], preview)
        plan = preview["current_source_fidelity_plan_sha256"]
        self.assertRegex(plan, r"^[0-9a-f]{64}$")
        handoff = preview["approval_handoff"]
        self.assertEqual(handoff["stage"], "approval_required")
        self.assertTrue(handoff["ready"])
        self.assertEqual(handoff["next_command"], "archive mint-zet")
        by_option = {item["option"]: item for item in handoff["arguments"]}
        fidelity_argument = by_option["--expected-source-fidelity-plan-sha256"]
        self.assertTrue(fidelity_argument["required"])
        self.assertEqual(fidelity_argument["json_pointer"], "/current_source_fidelity_plan_sha256")
        self.assertEqual(fidelity_argument["value"], plan)
        self.assertTrue(by_option["--reviewed-by"]["required"])
        self.assertTrue(by_option["--approve"]["required"])
        self.assertTrue(any("--expected-source-fidelity-plan-sha256" in line for line in preview["next_safe_actions"]))
        self.assertTrue(any("mint_source_fidelity_plan_sha256_required" in line for line in preview["next_safe_actions"]))
        # a plain human draft has no fidelity requirement in its handoff
        human = self.root / "inbox" / "zet_20260919_102_plain.md"
        human.write_text(
            "---\nid: zet_20260919_102_plain\nstatus: draft\ntitle: A plain human draft with a clear purpose\n"
            "kind: record_note\nabstract: A plain draft used to prove the handoff shape.\n"
            "facets:\n  record_type: note\nprovenance:\n  source: human_note\n  created_by: person:fidelity-test\n"
            "  creation_mode: human\n---\n\n" + ("Plain body written by a person. " * 4) + "\n",
            encoding="utf-8",
        )
        code, plain = self.run_cli(*self.mint_args(human), "--dry-run")
        plain_by_option = {item["option"]: item for item in plain["approval_handoff"]["arguments"]}
        self.assertFalse(plain_by_option["--expected-source-fidelity-plan-sha256"]["required"])
        self.assertIsNone(plain["current_source_fidelity_plan_sha256"])

    def test_approve_without_the_plan_digest_is_refused_before_any_claim(self):
        path = self.fidelity_draft()
        before = self.started_claims()
        code, result = self.run_cli(*self.mint_args(path), "--approve")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["reason_codes"], ["mint_source_fidelity_plan_sha256_required"])
        self.assertTrue(any("current_source_fidelity_plan_sha256" in line for line in result["next_safe_actions"]))
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self.started_claims(), before)
        self.assertTrue(path.exists())
        self.assertFalse((self.root / "zettels" / path.name).exists())
        # a stale digest is a mismatch, also before any claim
        code, result = self.run_cli(*self.mint_args(path), "--approve", "--expected-source-fidelity-plan-sha256", "0" * 64)
        self.assertEqual(result["reason_codes"], ["mint_source_fidelity_plan_sha256_mismatch"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self.started_claims(), before)
        # the right digest mints through one dialog
        _code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        code, result = self.run_cli(
            *self.mint_args(path), "--approve",
            "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"],
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.native.calls, 1)
        self.assertTrue(any("retire-draft" in line for line in result["next_safe_actions"]))
        self.assertEqual(self.started_claims(), before)
        # the two refusal envelopes never echo the reviewer id (the mint receipt records it by design)
        self.assertNotIn(REVIEWER, "".join(self.outputs[:4]))

    def test_writer_failure_names_its_fixed_cause_and_stage(self):
        path = self.fidelity_draft(draft_id="zet_20260919_103_writer")
        _code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        real_mint = archive_services.mint_zettel

        def failing_mint(*args, **kwargs):
            raise archive_services.ArchiveServiceError("mint_source_fidelity_plan_sha256_required")

        with patch.object(archive_services, "mint_zettel", failing_mint):
            code, result = self.run_cli(
                *self.mint_args(path), "--approve",
                "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"],
            )
        self.assertEqual(code, 1)
        self.assertEqual(result["reason_codes"], ["mint_service_failed"])
        self.assertEqual(result["cause_code"], "mint_source_fidelity_plan_sha256_required")
        self.assertEqual(result["cause_stage"], "domain_writer")
        self.assertTrue(any("exact-approval-claims" in line for line in result["next_safe_actions"]))
        self.assertEqual(len(self.started_claims()), 1)  # preserved for reconciliation, now named
        # free text never becomes a cause
        def private_failure(*args, **kwargs):
            raise archive_services.ArchiveServiceError("PRIVATE-FREE-TEXT-CANARY secret.md failed")

        with patch.object(archive_services, "mint_zettel", private_failure):
            code, result = self.run_cli(
                *self.mint_args(path), "--approve",
                "--expected-source-fidelity-plan-sha256", preview["current_source_fidelity_plan_sha256"],
            )
        self.assertEqual(result["reason_codes"], ["mint_service_failed"])
        self.assertNotIn("cause_code", result)
        self.assertNotIn("secret.md", "".join(self.outputs))
        self.assertIs(archive_services.mint_zettel, real_mint)

    def test_hand_edited_fidelity_body_is_a_named_warning(self):
        path = self.fidelity_draft(draft_id="zet_20260919_104_edit")
        _code, before = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertNotIn("draft_body_changed_since_approval", before["warnings"])
        raw = path.read_bytes()
        path.write_bytes(raw + b"\nAn extra paragraph typed by hand after approval.\n")
        code, after = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertIn("draft_body_changed_since_approval", after["warnings"])
        self.assertNotEqual(after["current_source_fidelity_plan_sha256"], before["current_source_fidelity_plan_sha256"])

    def test_truncated_objet_reference_block_names_body_lines_not_text(self):
        path = self.fidelity_draft(draft_id="zet_20260919_105_truncated")
        raw = path.read_bytes()
        marker = b"\n---\n\n"
        head, body = raw.split(marker, 1)
        body = body.rstrip(b"\n") + b"\n\nSee sha256:ebbf7a0e1234 for the ledger.\nAnd objects/sha256/ab/abcdef0123456789 again.\n"
        path.write_bytes(head + marker + body)
        code, preview = self.run_cli(*self.mint_args(path), "--dry-run")
        self.assertEqual(code, 1)
        item = next(entry for entry in preview["checklist"] if entry["id"] == "object_id_only")
        self.assertEqual(item["status"], "blocked")
        self.assertRegex(item["message"], r"body lines: \d+, \d+")
        numbers = [int(n) for n in re.findall(r"\d+", item["message"].split("body lines:")[1])]
        self.assertEqual(len(numbers), 2)
        self.assertEqual(numbers[1] - numbers[0], 1)
        self.assertNotIn("ebbf7a0e", json.dumps(preview))
        self.assertNotIn("abcdef0123456789", json.dumps(preview))
        lines = archive_services.zettel_truncated_objet_reference_body_lines("a\nsha256:ebbf7a0e1234\n\nobjets/x objects/sha256/ab/abcdef0123456789\n")
        self.assertEqual(lines, [2, 4])

    def test_batch_binds_the_plan_digest_for_a_fidelity_draft(self):
        path = self.fidelity_draft(draft_id="zet_20260919_106_batch")
        # a batch carries no --affirm; the human decisions live in the draft's frontmatter
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)
        self.assertTrue(snapshot["ok"], snapshot)
        frontmatter = snapshot["frontmatter"]
        frontmatter["promotion"] = {
            "stage": "promotion_candidate",
            "ready_for_promotion": True,
            "checklist": {"one_clear_purpose": True, "sensitive_content_reviewed": True},
        }
        path.write_bytes(("---\n" + archive_services.dump_yaml(frontmatter) + "---\n\n").encode("utf-8") + snapshot["body_bytes"])
        archive_services.index_archive(self.root)
        plan_dir = self.root / "workbench"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "letter163-batch.plan.json").write_text(json.dumps({
            "schema": "wom-kit/mint-zet-batch/v0.1",
            "policy": {"policy_id": "policy:letter163-batch", "allow_warnings": True},
            "items": [{"item_id": "item:fidelity", "path": path.relative_to(self.root).as_posix()}],
        }), encoding="utf-8")
        code, preview = self.run_cli(
            "mint-zet-batch", str(self.root), "--plan", "workbench/letter163-batch.plan.json", "--dry-run", "--allow-warnings"
        )
        self.assertEqual(code, 0, preview)
        code, result = self.run_cli(
            "mint-zet-batch", str(self.root), "--plan", "workbench/letter163-batch.plan.json",
            "--approve", "--allow-warnings", "--reviewed-by", REVIEWER,
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["summary"]["written_item_count"], 1)
        self.assertEqual(result.get("failed_items", []), [])
        self.assertTrue((self.root / "zettels" / path.name).exists())
        self.assertEqual(self.native.calls, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
