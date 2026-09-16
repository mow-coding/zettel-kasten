"""Letter 159/160: WOM's own commands must not make a draft unmintable.

① zettel-edge rewrote a draft without the blank line after the closing
   ``---`` and mint-zet then rejected it; the rewrite now preserves the
   exact body suffix and mint-zet normalizes a missing separator.
② linking the declared fidelity source object as an asset made mint-zet
   report private authority exposure; that one asset row is now exempt while
   every other spelling of the object id and all digests stay blocked.
③ a blocked create-draft dry-run no longer hands out ready-looking replay
   values; a blocked --approve names the reason and blockers in text mode;
   a blocked zettel-edge names the condition.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import test_v03313_source_fidelity as fidelity_fixture
from wom_kit import archive_cli, archive_services
from wom_kit.exact_human_approval import _claim_exact_human_approval_core as claim_exact_human_approval
from wom_kit.exact_human_approval_windows import _ExactHumanApprovalDecision as ExactHumanApprovalDecision
from wom_kit.operation_approval_binding import zettel_edge_approval_binding


class Letter159DraftPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        # Compose the fidelity fixture instead of inheriting it so its own
        # test methods are not re-run here.
        self.f = fidelity_fixture.SourceFidelityV03313Tests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root

    def _draft(self, draft_id: str, title: str, body: str) -> tuple[str, str, Path]:
        object_id = self.f.manifested_source(
            ("Exact synthetic source for " + draft_id).encode("utf-8")
        )
        result = self.f.create_approved(
            self.f.ai_kwargs(object_id, draft_id=draft_id, title=title, body=body)
        )
        return object_id, result["path"], self.root / result["path"]

    def _separator_after_closing(self, raw: bytes) -> bytes:
        closing = raw.index(b"\n---\n", 4) + len(b"\n---\n")
        return raw[closing : closing + 1]

    def _write_exact_edge(self, **write_args: object) -> dict[str, object]:
        reviewed_by = str(write_args.get("reviewed_by") or "")
        if archive_services.require_current_zettel_index(self.root).get("ok") is not True:
            self.assertTrue(archive_services.index_archive(self.root)["ok"])
        preview = archive_services.zettel_edge_write(
            self.root, **write_args, dry_run=True, approve=False
        )
        self.assertTrue(preview["ok"], preview)
        binding = zettel_edge_approval_binding(preview)
        context = binding.context(
            archive_id=archive_services.read_archive_id(self.root),
            reviewer_claim=reviewed_by,
        )
        decision = ExactHumanApprovalDecision(
            approved=True, synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(self.root, context, decision, bytes(range(32)))
        try:
            result = archive_services.zettel_edge_write(
                self.root, **write_args, dry_run=False, approve=True,
                expected_exact_approval_plan_sha256=binding.plan_sha256,
                expected_exact_approval_target_binding_sha256=binding.target_binding_sha256,
                exact_human_approval_claim=claim,
            )
            if result.get("ok") is True:
                claim.finalize_succeeded()
            else:
                claim.finalize_failed("operation_blocked")
            return result
        finally:
            claim.close()

    def test_edge_rewrite_keeps_blank_separator_and_mint_still_verifies(self) -> None:
        _source, _relative, path = self._draft(
            "zet_20260914_159_edge_source", "Edge source draft",
            "Body line one.\n\n    indented code block\n\ttabbed line\n",
        )
        _target, _target_relative, _target_path = self._draft(
            "zet_20260914_159_edge_target", "Edge target draft", "Target body.\n"
        )
        before = path.read_bytes()
        self.assertEqual(self._separator_after_closing(before), b"\n")
        body_before = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)["body_bytes"]
        edge = self._write_exact_edge(
            from_zettel="zet_20260914_159_edge_source", target_ref="zet_20260914_159_edge_target",
            edge_type="references", visibility="private", reviewed_by="person:test",
        )
        self.assertTrue(edge["ok"], edge)
        after = path.read_bytes()
        self.assertNotEqual(after, before)
        # The blank separator and every body byte (leading blank line, tab,
        # four-space block) survive the edge rewrite exactly.
        self.assertEqual(self._separator_after_closing(after), b"\n")
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)
        self.assertTrue(snapshot["ok"], snapshot)
        self.assertFalse(snapshot["body_separator_normalized"])
        self.assertEqual(snapshot["body_bytes"], body_before)
        verification = archive_services._source_fidelity_verify_for_mint(self.root, path, affirmations=None)
        self.assertTrue(verification["ok"], verification)
        self.assertNotIn("source_fidelity_draft_body_separator_invalid", verification["blockers"])

    def test_missing_separator_from_an_older_rewrite_is_normalized_not_blocked(self) -> None:
        _source, _relative, path = self._draft(
            "zet_20260914_159_old_rewrite", "Older rewrite", "Body kept as is.\n"
        )
        raw = path.read_bytes()
        closing = raw.index(b"\n---\n", 4) + len(b"\n---\n")
        self.assertEqual(raw[closing : closing + 1], b"\n")
        expected_body = raw[closing + 1 :]
        path.write_bytes(raw[:closing] + raw[closing + 1 :])  # what v0.4.18 zettel-edge produced
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)
        self.assertTrue(snapshot["ok"], snapshot)
        self.assertTrue(snapshot["body_separator_normalized"])
        self.assertEqual(snapshot["body_bytes"], expected_body)
        verification = archive_services._source_fidelity_verify_for_mint(self.root, path, affirmations=None)
        self.assertTrue(verification["ok"], verification)
        # An actually damaged boundary is still blocked.
        path.write_bytes(raw.replace(b"\n---\n", b"\n--\n", 1))
        damaged = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)
        self.assertFalse(damaged["ok"])
        self.assertIn("source_fidelity_draft_frontmatter_boundary_invalid", damaged["blockers"])

    def test_fidelity_source_linked_as_asset_is_not_private_authority_exposure(self) -> None:
        object_id, _relative, path = self._draft(
            "zet_20260914_159_asset_link", "Asset linked draft", "Body about the source.\n"
        )
        snapshot = archive_services._source_fidelity_raw_draft_snapshot(self.root, path)
        frontmatter = snapshot["frontmatter"]

        def rewrite(updated: dict) -> None:
            path.write_bytes(
                ("---\n" + archive_services.dump_yaml(updated) + "---\n\n").encode("utf-8")
                + snapshot["body_bytes"]
            )

        linked = dict(frontmatter)
        linked["assets"] = [{"object_id": object_id, "role": "source_document", "label": "Evidence original"}]
        rewrite(linked)
        verification = archive_services._source_fidelity_verify_for_mint(self.root, path, affirmations=None)
        self.assertNotIn("source_fidelity_private_authority_exposed", verification["blockers"], verification)
        self.assertTrue(verification["ok"], verification)
        # Any other spelling of the id, or the id outside an asset row, is
        # still an exposure; the digests of the source stay private too.
        for exposed in (
            {**linked, "abstract": "See objet:" + object_id},
            {**linked, "assets": [{"object_id": "sha256:" + "0" * 64, "role": "source_document",
                                   "label": object_id.removeprefix("sha256:")}]},
            {**linked, "assets": [{"object_id": object_id, "role": "source_document",
                                   "label": "copy of " + object_id}]},
        ):
            rewrite(exposed)
            blocked = archive_services._source_fidelity_verify_for_mint(self.root, path, affirmations=None)
            self.assertIn("source_fidelity_private_authority_exposed", blocked["blockers"], exposed.get("assets"))

    def test_blocked_dry_run_has_no_ready_replay_and_blocked_approve_names_blockers(self) -> None:
        object_id = self.f.manifested_source(b"Exact synthetic source for a blocked draft.")
        kwargs = self.f.ai_kwargs(object_id, draft_id="zet_20260915_160_blocked", title="Blocked draft")
        kwargs["abstract"] = "x" * 361
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, **kwargs)
        self.assertFalse(preview["ok"])
        self.assertTrue(preview["blockers"])
        self.assertEqual(set(preview["approval_replay"]), {
            "draft_id", "created_at", "expected_body_sha256", "expected_source_fidelity_plan_sha256",
            "expected_archive_id", "expected_type", "profile_id"})
        self.assertTrue(all(value is None for value in preview["approval_replay"].values()))
        self.assertEqual(preview["approval_handoff"]["stage"], "blocked")
        # Text-mode --approve with a blocked preflight now says why.
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([
                "create-draft", str(self.root), "--title", "Blocked draft", "--abstract", "x" * 361,
                "--kind", "record_note", "--facet", "record_type=source_fidelity",
                "--created-by", "ai_runtime:test", "--source", "test_fixture",
                "--creation-mode", "ai_assisted", "--assisted-by", "ai_runtime:test",
                "--draft-id", "zet_20260915_160_blocked", "--created-at", "2026-08-10T12:10:00+09:00",
                "--source-fidelity", "verbatim", "--fidelity-audience", "private_self",
                "--fidelity-source-object-id", object_id, "--draft-approved-by", "person:test",
                "--expected-body-sha256", "0" * 64, "--expected-source-fidelity-plan-sha256", "0" * 64,
                "--approve",
            ])
        self.assertNotEqual(code, 0)
        self.assertIn("exact_human_approval_preflight_blocked", err.getvalue())
        self.assertIn("BLOCKED: abstract must be at most 360 characters.", err.getvalue())
        self.assertNotIn("x" * 50, err.getvalue() + out.getvalue())

    def test_blocked_zettel_edge_names_the_condition(self) -> None:
        self.assertEqual(
            archive_cli._zettel_edge_detail_reason_code(["edge already exists on the source zettel."]),
            "zettel_edge_already_exists",
        )
        self.assertEqual(
            archive_cli._zettel_edge_detail_reason_code(["Active link type contract is unavailable."]),
            "zettel_edge_type_contract_blocked",
        )
        self.assertEqual(archive_cli._zettel_edge_detail_reason_code(["zettel_edge_preflight_blocked"]),
                         "zettel_edge_preflight_blocked")


if __name__ == "__main__":
    unittest.main()
