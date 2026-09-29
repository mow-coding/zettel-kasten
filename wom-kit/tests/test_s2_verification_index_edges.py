"""S2 verification: index, edges, inbox attention and runtime entrypoints.

Every test drives the official command surface through
``archive_cli.build_parser()`` on a temporary copy of the example archive and
stays content-free: no private path or body text is asserted on or echoed.

S2-U08 stays unconfirmed: no fixture exists for it in this batch.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from wom_kit import archive_cli, archive_services as services

KIT_ROOT = Path(__file__).resolve().parents[1]
FAKE_ARCHIVE = KIT_ROOT / "examples" / "fake-life-archive"
ARCHIVE_ID = "archive:personal:fake-life"
LUNCH = "zet_20240504_fake_lunch_thought"
ONBOARDING = "zet_20240505_fake_company_onboarding_insight"
FAMILY = "zet_20260519_fake_family_memory"
SCHOOL = "zet_20110228_fake_school_record"


def _frontmatter(zettel_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": zettel_id,
        "title": f"S2 fixture {zettel_id}",
        "created_at": "2026-07-29T01:02:03+09:00",
        "updated_at": "2026-07-29T01:02:03+09:00",
        "archive_id": ARCHIVE_ID,
        "status": "canonical",
        "kind": "record_note",
        "facets": {"record_type": "memory"},
        "assets": [],
        "edges": [],
        "provenance": {
            "created_by": "person:test",
            "created_in": ARCHIVE_ID,
            "source": "test_fixture",
            "derived_from": [],
        },
        "visibility": {
            "scope": "private",
            "allowed_archives": [],
            "source_visibility": "private",
        },
    }
    base.update(overrides)
    return base


class S2VerificationIndexEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "archive"
        shutil.copytree(FAKE_ARCHIVE, self.root)
        self.parser = archive_cli.build_parser()

    def invoke(self, argv: list[str]) -> tuple[int, Any, str]:
        args = self.parser.parse_args(argv)
        with redirect_stdout(out := io.StringIO()), redirect_stderr(io.StringIO()):
            code = args.func(args)
        text = out.getvalue()
        self.assertNotIn(str(self.tmp), text)
        return code, json.loads(text), text

    def snapshot(self, root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def write_zet(self, frontmatter: dict[str, Any], *, folder: str = "zettels", body: str = "Body.") -> Path:
        path = self.root / folder / f"{frontmatter['id']}.md"
        path.write_text(
            "---\n" + services.dump_yaml(frontmatter) + "---\n\n" + body + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def strip_link_type(self, edge_id: str) -> None:
        types_path = self.root / "zettel-kasten" / "types.yml"
        data = services.load_yaml(types_path.read_text(encoding="utf-8"))
        data["link_types"] = [item for item in data["link_types"] if item.get("id") != edge_id]
        types_path.write_text(services.dump_yaml(data), encoding="utf-8")

    def test_s2_u01_base_link_types_selective_revert_keeps_the_used_type(self) -> None:
        """S2-U01: reverting A+B removes only B when a zet edge still uses A."""
        types_path = self.root / "zettel-kasten" / "types.yml"
        for edge_id in ("continues", "sequence"):
            self.strip_link_type(edge_id)
        before_text = types_path.read_text(encoding="utf-8")
        common = ["migrate", str(self.root), "--target", "base-link-types",
                  "--link-type", "continues", "--link-type", "sequence", "--format", "json"]
        code, sync, _ = self.invoke([*common, "--dry-run"])
        self.assertEqual(code, 0, sync)
        self.assertEqual(sorted(sync["appended_link_type_ids"]), ["continues", "sequence"])
        # S2-U01 gap: `migrate --approve` for base-link-types is routed through
        # exact human approval (native dialog) and fails closed headlessly, so
        # adoption is installed from the dry-run text plus the receipt shape the
        # planner reads, mirroring test_completion_workflows.
        code, blocked, _ = self.invoke([*common, "--approve", "--reviewed-by", "person:test"])
        self.assertEqual(code, 1, blocked)
        self.assertEqual(blocked["reason_codes"], ["compound_exact_human_approval_binding_required"])
        after_text = sync["new_text"]
        types_path.write_text(after_text, encoding="utf-8")
        seed = {"archive_id": ARCHIVE_ID, "target": "base-link-types",
                "appended_link_type_ids": ["continues", "sequence"],
                "before_sha256": services.sha256_text(before_text),
                "after_sha256": services.sha256_text(after_text)}
        receipt_path = services.archive_internal_path(
            self.root, services.migration_receipt_relative_path("base-link-types", seed))
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps({
            **seed, "schema_version": "wom-kit/base-link-types-sync-receipt/v0.1",
            "lifecycle_action": "base_link_types_sync", "receipt_kind": "base_link_types_sync",
            "created_at": "2026-08-20T00:00:00Z", "reviewed_by": "person:historical-fixture",
            "adoption_generation": 0, "selected_link_type_ids": ["continues", "sequence"],
            "files_changed": ["zettel-kasten/types.yml"],
            "result": {"types_file_written": True, "receipt_written": True},
            "closed_actions": {"provider_api_called": False, "real_source_export_files_read": False,
                               "zettel_files_written": False, "edge_receipts_deleted": False},
        }, sort_keys=True) + "\n", encoding="utf-8")
        # One zet edge of type A ("continues"); the zettel-edge writer is dialog-gated too.
        self.write_zet(_frontmatter("zet_20260929_s2u01_uses_continues", edges=[
            {"type": "continues", "target": LUNCH, "visibility": "private"}]))

        before = self.snapshot(self.root)
        code, revert, _ = self.invoke([*common, "--revert", "--dry-run"])
        self.assertEqual(code, 1, revert)
        self.assertFalse(revert["ok"])
        self.assertEqual(revert["removable_link_type_ids"], ["sequence"])
        self.assertEqual(revert["used_link_type_ids"], ["continues"])
        in_use = [item for item in revert["blockers"] if item["code"] == "link_type_in_use"]
        self.assertEqual([item["id"] for item in in_use], ["continues"])
        self.assertEqual(revert["files_written"], [])
        self.assertEqual(self.snapshot(self.root), before)

    def test_s2_u02_event_anchor_membership_plan_requires_event_start(self) -> None:
        """S2-U02: an event anchor plans a member as ready_to_add; no event_start blocks."""
        anchor_id = "zet_20260929_s2u02_event_anchor"
        member_id = "zet_20260929_s2u02_member"
        code, preview, _ = self.invoke([
            "create-draft", str(self.root), "--title", "S2 event anchor", "--body", "Anchor body.",
            "--facet", "record_type=event", "--facet", "event_start=2022-08-26",
            "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["frontmatter_preview"]["facets"],
                         {"record_type": "event", "event_start": "2022-08-26"})
        # S2-U02 gap: create-draft only proposes an inbox draft (status draft,
        # kind fleeting_capture) behind exact human approval; the plan needs a
        # canonical record_note in zettels/, and no headless promotion route
        # exists, so the anchor and member are installed as canonical fixtures.
        self.assertEqual(preview["frontmatter_preview"]["status"], "draft")
        anchor = _frontmatter(anchor_id, facets={"record_type": "event", "event_start": "2022-08-26"})
        self.write_zet(anchor)
        self.write_zet(_frontmatter(member_id))
        request_relative = ".wom-scratch/private/activity-groups/s2u02.json"
        request_path = self.root / request_relative
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(json.dumps({
            "schema": "wom-kit/activity-group-membership-request/v0.1",
            "archive_id": ARCHIVE_ID, "anchor_zettel_id": anchor_id,
            "member_zettel_ids": [member_id]}), encoding="utf-8")
        argv = ["activity-group-membership-plan", str(self.root), "--request", request_relative,
                "--dry-run", "--format", "json"]
        before = self.snapshot(self.root)
        code, plan, _ = self.invoke(argv)
        self.assertEqual(code, 0, plan)
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["anchor"]["status"], "ready_for_review")
        self.assertEqual(plan["summary"]["ready_to_add_count"], 1)
        self.assertEqual([item["status"] for item in plan["items"]], ["ready_to_add"])
        self.assertEqual(self.snapshot(self.root), before)

        anchor["facets"] = {"record_type": "event"}
        self.write_zet(anchor)
        code, blocked, _ = self.invoke(argv)
        self.assertEqual(code, 1, blocked)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["anchor"]["status"], "blocked")
        self.assertIn("anchor_event_start_invalid_or_missing", blocked["anchor"]["blocker_codes"])
        self.assertIn("anchor_validation_blocked", blocked["blockers"])
        self.assertEqual(blocked["items"], [])

    def test_s2_u03_fresh_entrypoint_flags_one_hand_placed_inbox_draft(self) -> None:
        """S2-U03: ai-start-here counts the out-of-pipeline draft; reads still work; doctor warns."""
        draft = _frontmatter(
            "zet_20260929_s2u03_hand_placed", status="draft", kind="fleeting_capture",
            provenance={"created_by": "ai:test", "created_in": ARCHIVE_ID,
                        "source": "user_conversation", "creation_mode": "ai_generated",
                        "assisted_by": ["ai_runtime:test"], "derived_from": []})
        self.write_zet(draft, folder="inbox")  # AI-declared, but no promotion block

        code, start, _ = self.invoke(["ai-start-here", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, start)
        attention = start["inbox_attention"]
        self.assertTrue(attention["complete"])
        self.assertEqual(attention["unpublished_draft_count"], 2)
        self.assertEqual(attention["possible_out_of_pipeline_draft_count"], 1)
        self.assertFalse(attention["paths_titles_or_body_echoed"])
        routing = start["action_routing"]
        self.assertFalse(routing["raw_filesystem_search_is_authoritative"])
        self.assertFalse(routing["direct_ai_file_writes_to_inbox_allowed"])
        self.assertFalse(routing["direct_ai_file_writes_to_canonical_zets_allowed"])
        self.assertTrue(all(
            route["direct_file_write_allowed"] is False
            for route in routing.get("write_action_routes", [])
            if "direct_file_write_allowed" in route))

        self.assertTrue(services.index_archive(self.root)["ok"])
        code, found, _ = self.invoke(["search", str(self.root), "lunch", "--format", "json"])
        self.assertEqual(code, 0, found)
        self.assertTrue(found["ok"])
        self.assertGreater(found["count"], 0)
        code, preview, _ = self.invoke([
            "create-draft", str(self.root), "--title", "S2 follow-up", "--body", "Follow-up body.",
            "--facet", "domain=test", "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, preview)
        self.assertTrue(preview["ok"])
        code, edge, _ = self.invoke([
            "zettel-edge", str(self.root), "--from-zettel", LUNCH, "--target", ONBOARDING,
            "--edge-type", "references", "--visibility", "private", "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, edge)
        self.assertTrue(edge["ok"])

        code, findings, _ = self.invoke(["doctor", str(self.root), "--format", "json"])
        self.assertIn("possible_out_of_pipeline_inbox_draft", {item["code"] for item in findings})
        self.assertTrue((self.root / "inbox" / f"{draft['id']}.md").is_file())

    def test_s2_u04_archive_without_ai_runtime_entrypoint_reports_absent_codes(self) -> None:
        """S2-U04: no AGENTS routing block and no skill -> absent codes, install route, no writes."""
        repo = self.tmp / "repo"
        repo.mkdir()
        shutil.move(str(self.root), str(repo / "archive"))
        self.root = repo / "archive"
        self.assertFalse((repo / "AGENTS.md").exists())
        self.assertFalse((repo / ".agents").exists())
        before = self.snapshot(repo)

        code, ready, text = self.invoke([
            "runtime-guidance-readiness", str(self.root), "--host", "codex", "--scope", "repo",
            "--repo-root", str(repo), "--format", "json"])
        self.assertEqual(code, 0, ready)
        self.assertTrue(ready["ok"])
        self.assertFalse(ready["ready"])
        self.assertEqual(ready["status"], "attention_required")
        self.assertEqual(ready["diagnostic_codes"], ["runtime_skill_absent", "agents_routing_contract_absent"])
        self.assertEqual(ready["runtime_skill"]["status"], "absent")
        self.assertEqual(ready["agents_routing"]["status"], "absent")
        self.assertFalse(ready["agents_routing"]["body_echoed"])
        self.assertTrue(any(
            "runtime-skill-install" in command and "--dry-run" in command
            for command in ready["next_safe_commands"]))
        self.assertFalse(ready["closed_actions"]["files_written"])
        self.assertFalse(ready["closed_actions"]["agents_file_modified"])
        self.assertNotIn(str(repo), text)

        code, start, _ = self.invoke(["ai-start-here", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, start)
        # S2-U04 gap: ai-start-here does not surface the absent codes itself; it
        # only points at the explicit host-specific readiness check (pinned).
        self.assertEqual(start["runtime_guidance_readiness"]["status"], "not_checked")
        self.assertEqual(start["runtime_guidance_readiness"]["reason_code"],
                         "explicit_host_specific_check_required")
        self.assertIn("runtime-guidance-readiness", start["runtime_guidance_readiness"]["check_command"])
        self.assertEqual(self.snapshot(repo), before)

    def test_s2_u05_source_coverage_and_storage_integrity_are_separate_axes(self) -> None:
        """S2-U05: 3 recovered + 1 unrecovered occurrences never imply storage integrity."""
        for index in range(3):
            self.write_zet(_frontmatter(
                f"zet_20260801_00000{index}_s2u05_ref",
                source_refs=[{"type": "object_id", "value": "sha256:" + chr(97 + index) * 64}]))
        self.write_zet(
            _frontmatter("zet_20260801_000009_s2u05_marker",
                         facets={"domain": "test", "source_system": "notion_db3",
                                 "source_locator_omitted_count": 1},
                         provenance={"created_by": "ai_runtime:test", "created_in": ARCHIVE_ID,
                                     "source": "notion_db3", "creation_mode": "imported",
                                     "derived_from": []}),
            body="Body.\n" + services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER)
        before = self.snapshot(self.root)
        # The audit requires an explicit interpreter -B flag, so it runs as the
        # official module command in a subprocess (same as its own test module).
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(KIT_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "wom_kit.archive_cli", "source-reference-coverage-audit",
             str(self.root), "--dry-run", "--format", "json"],
            cwd=KIT_ROOT, env=environment, check=False, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(str(self.tmp), completed.stdout)
        result = json.loads(completed.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(self.snapshot(self.root), before)

        coverage = result["source_reference_coverage"]
        storage = result["recorded_storage_evidence"]
        self.assertEqual(coverage["population_count"], 4)
        self.assertEqual(coverage["recovered_count"], 3)
        self.assertEqual(coverage["unrecovered_count"], 1)
        self.assertEqual(coverage["state"], "partial")
        self.assertEqual(storage["state"], "no_evidence")
        self.assertEqual(storage["no_evidence_count"], 4)
        self.assertEqual(storage["recorded_time_evidence_count"], 0)
        self.assertFalse(storage["live_storage_integrity_claim_supported"])
        separation = result["claim_separation"]
        self.assertIs(separation["source_coverage_implies_storage_integrity"], False)
        self.assertIs(separation["storage_integrity_implies_source_coverage"], False)
        self.assertEqual(
            set(coverage) & set(storage),
            {"state", "not_applicable_count"},
            "the storage axis carries no coverage counts of its own",
        )
        self.assertNotIn("recovered_count", storage)
        self.assertNotIn("unrecovered_count", storage)
        self.assertNotIn("no_evidence_count", coverage)

    def test_s2_u07_tie_summary_equals_edge_count_across_index_rebuild(self) -> None:
        """S2-U07: 4 edges show as 4 in overview, catalog and SQLite, before and after rebuild."""
        # S2-U07 gap: `zettel-edge --approve` is dialog-gated, so the four
        # edges are a hand-written fixture on an existing canonical zet.
        edges = [
            {"type": "references", "target": ONBOARDING, "visibility": "private"},
            {"type": "material", "target": FAMILY, "visibility": "private"},
            {"type": "derived_from", "target": SCHOOL, "visibility": "private"},
            {"type": "semantic", "target": ONBOARDING, "visibility": "private"},
        ]
        path = self.root / "zettels" / f"{LUNCH}.md"
        frontmatter, body = services.split_zettel_text(path.read_text(encoding="utf-8"))
        frontmatter["edges"] = edges
        self.write_zet(frontmatter, body=body.rstrip())

        def assert_four_everywhere() -> None:
            code, read, _ = self.invoke([
                "read-zettel", str(self.root), "--zettel-id", LUNCH,
                "--section", "overview", "--format", "json"])
            self.assertEqual(code, 0, read)
            tie = read["overview"]["tie_summary"]
            self.assertEqual(tie["edge_count"], 4)
            self.assertEqual(tie["edge_types"], ["derived_from", "material", "references", "semantic"])
            code, catalog, _ = self.invoke(["zet-catalog", str(self.root), "--dry-run", "--format", "json"])
            self.assertEqual(code, 0, catalog)
            item = next(item for item in catalog["items"] if item["id"] == LUNCH)
            self.assertEqual(len(item["edges"]), 4)
            self.assertEqual(item["tie_summary"]["edge_count"], 4)
            self.assertTrue(item["edges_complete"])
            connection = sqlite3.connect(self.root / "db" / "archive-index.sqlite")
            try:
                (count,) = connection.execute(
                    "SELECT COUNT(*) FROM edges WHERE from_id = ?", (LUNCH,)).fetchone()
            finally:
                connection.close()
            self.assertEqual(count, 4)

        self.assertTrue(services.index_archive(self.root)["ok"])
        assert_four_everywhere()
        code, rebuilt, _ = self.invoke(["index", str(self.root), "--format", "json"])
        self.assertEqual(code, 0, rebuilt)
        self.assertTrue(rebuilt["ok"])
        assert_four_everywhere()


if __name__ == "__main__":
    unittest.main()
