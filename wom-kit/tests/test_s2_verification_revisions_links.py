"""S2 verification (U18-U25): revision reproducibility, objet-link role change
through receipts, a 40-edge batch with safe revert, compose request-path
refusal, facet vocabulary, reversible draft hold and the locator-loss audit
across ledger states.

Synthetic archive only (examples/fake-life-archive copied into a temp dir);
the native dialog and archive key are injected. Results never echo the temp
path. Where an official command cannot reach a scenario, the current
observable behaviour is pinned with an ``# S2-Uxx gap:`` comment.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, completion_workflows
from wom_kit import draft_disposition
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit.exact_human_approval import exact_human_approval_archive_identity_sha256
from wom_kit.local_locator_recovery import notion_locator_orphan_recovery_execution_plan

import test_v0421_lifecycle_batches_exact_approval as lifecycle
import test_v045_local_locator_title_recovery as locator

KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:synthetic-s2-reviewer"
LUNCH = "zet_20240504_fake_lunch_thought"
FAMILY = "zet_20260519_fake_family_memory"
INBOX_DRAFT = "zet_20260519_draft_ai_lunch_note"
OBJ_A = "sha256:acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
OBJ_B = "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
REVISED_TITLE = "PRIVATE_S2_REVISED_TITLE"


class _Claim:
    def assert_ready_for_context(self, context):
        return {"schema": "synthetic-approval", "context": context}


class S2VerificationRevisionsLinksTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-s2-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.assertTrue(archive_services.index_archive(self.root)["ok"])
        self.native = lifecycle._PagedNative()
        self.keys = locator._StableKeyProvider()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.keys))
        self.outputs: list[str] = []
        self.parser = archive_cli.build_parser()

    # ----- helpers -------------------------------------------------------
    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        self.assertNotIn(str(self.root), out.getvalue() + err.getvalue())
        return code, json.loads(out.getvalue())

    def files(self, *, skip: tuple[str, ...] = ("receipts/", "profiles/", "db/")) -> dict[str, bytes]:
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*")
                if p.is_file() and not p.relative_to(self.root).as_posix().startswith(skip)}

    def zet_text(self, zettel_id: str, folder: str = "zettels") -> tuple[dict, str]:
        return archive_services.split_zettel_text((self.root / folder / f"{zettel_id}.md").read_text(encoding="utf-8"))

    def write_zet(self, zettel_id: str, frontmatter: dict, body: str, relative: str | None = None) -> Path:
        path = self.root / (relative or f"zettels/{zettel_id}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        # LF on purpose: the edge writer normalizes line endings, so a CRLF
        # source would differ after a revert for a reason unrelated to edges.
        path.write_bytes(("---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body.rstrip() + "\n").encode("utf-8"))
        return path

    def revision_proposal(self, zettel_id: str, name: str) -> tuple[str, dict]:
        frontmatter, body = self.zet_text(zettel_id)
        frontmatter["abstract"] = "Current reviewed first read."
        self.write_zet(zettel_id, frontmatter, body)
        proposed = json.loads(json.dumps(frontmatter))
        proposed["title"] = REVISED_TITLE
        proposed["abstract"] = "PRIVATE_S2_REVISED_ABSTRACT"
        relative = f".wom-scratch/revisions/{name}.md"
        self.write_zet(zettel_id, proposed, body + "\n\nPRIVATE_S2_REVISED_BODY", relative)
        code, plan = self.run_cli("zet-revision-plan", str(self.root), "--zettel-id", zettel_id,
                                  "--proposal", relative, "--dry-run")
        self.assertEqual(code, 0, plan)
        return relative, plan

    def revision_write(self, zettel_id: str, relative: str, plan: dict) -> dict:
        args = ["zet-revision-write", str(self.root), "--zettel-id", zettel_id, "--proposal", relative,
                "--expected-canonical-sha256", plan["canonical"]["sha256"],
                "--expected-proposal-sha256", plan["proposal"]["sha256"],
                "--expected-proposal-semantic-sha256", plan["proposal"]["semantic_sha256"],
                "--expected-plan-digest", plan["plan_digest"], "--revision-at", "2026-09-29T12:00:00Z"]
        code, preview = self.run_cli(*args, "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["status"], "ready_to_apply")
        code, result = self.run_cli(*args, "--approve", "--reviewed-by", REVIEWER,
                                    "--affirm-revision-reviewed", "--affirm-abstract-body-pair-reviewed")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "applied")
        return result

    def link(self, object_id: str, role: str) -> tuple[int, dict]:
        common = ["zettel-objet-link", str(self.root), "--zettel-id", LUNCH, "--object-id", object_id, "--role", role]
        code, preview = self.run_cli(*common, "--dry-run")
        if code != 0:
            return code, preview
        return self.run_cli(*common, "--approve", "--reviewed-by", REVIEWER,
                            "--expected-plan-sha256", preview["summary"]["plan_sha256"])

    def edge_plan(self, sources: list[str], targets: list[str]) -> Path:
        edges = [{"candidate_id": f"candidate:{s}:{t}", "from_zettel": s, "target": t, "edge_type": "material",
                  "visibility": "private", "confidence": "high", "review_status": "policy_candidate",
                  "evidence_ref": "fixture:row"} for s in sources for t in targets]
        plan_path = self.tmp / "edges.plan.json"
        plan_path.write_text(json.dumps({"schema": "wom-kit/zettel-edge-batch/v0.1", "policy": {
            "policy_id": "policy:fixture-s2", "policy_label": "Fixture S2", "auto_write_edge_types": ["material"],
            "minimum_confidence": "high", "ambiguous_edges_to_review_queue": True}, "edges": edges}), encoding="utf-8")
        return plan_path

    @staticmethod
    def outside_edge_block(raw: bytes) -> bytes:
        """Drop the edges block and the updated_at line; keep every other byte."""
        kept, in_edges = [], False
        for line in raw.split(b"\n"):
            if line.startswith(b"edges:"):
                in_edges = True
                continue
            if in_edges and (line.startswith(b"- ") or line.startswith(b"  ")):
                continue
            in_edges = False
            if line.startswith(b"updated_at:"):
                continue
            kept.append(line)
        return b"\n".join(kept)

    def fidelity_object(self, text: str) -> str:
        raw = text.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        logical_key = f"objects/sha256/{digest[:2]}/{digest}"
        path = self.root.joinpath(*logical_key.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        rows = [line for line in manifest.read_bytes().split(b"\n") if line]
        rows.append(json.dumps({"object_id": f"sha256:{digest}", "sha256": digest, "logical_key": logical_key,
                                "mime": "text/plain", "size_bytes": len(raw),
                                "locations": [{"provider": "local", "path": logical_key, "availability": "available"}],
                                "provenance": {"created_in": archive_services.read_archive_id(self.root),
                                               "source": "s2_fixture"}}).encode("utf-8"))
        manifest.write_bytes(b"\n".join(rows) + b"\n")
        self.assertTrue(archive_services.index_archive(self.root)["ok"])
        return f"sha256:{digest}"

    def locator_audit(self) -> dict:
        code, doc = self.run_cli("notion-import-locator-loss-audit", str(self.root), "--dry-run")
        self.assertEqual(code, 0, doc)
        self.assertNotIn(locator.ZETTEL_ID, self.outputs[-2])
        return doc

    # ----- S2-U18 --------------------------------------------------------
    def test_s2_u18_revision_proposal_is_reproducible_and_contract_flags_exist(self) -> None:
        """S2-U18: same proposal -> same digests; contract flags exist; write applies."""
        relative, first = self.revision_proposal(LUNCH, "private-s2-u18")
        code, second = self.run_cli("zet-revision-plan", str(self.root), "--zettel-id", LUNCH,
                                    "--proposal", relative, "--dry-run")
        self.assertEqual(code, 0, second)
        self.assertEqual(first["status"], "ready_for_human_review")
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        self.assertEqual(first["proposal"]["sha256"], second["proposal"]["sha256"])
        self.assertEqual(first["proposal"]["semantic_sha256"], second["proposal"]["semantic_sha256"])
        self.assertEqual(first["canonical"]["sha256"], second["canonical"]["sha256"])
        self.assertFalse(first["proposal"]["path_echoed"])
        contract = first["approval_contract"]
        self.assertEqual(contract["writer_command"], "zet-revision-write")
        writer = self.parser._subparsers._group_actions[0].choices["zet-revision-write"]
        writer_flags = {o for a in writer._actions for o in a.option_strings if o.startswith("--expected-")}
        bound = [k for k, v in contract.items() if k.startswith("future_write_must_bind_") and v is True]
        self.assertEqual(sorted(bound), ["future_write_must_bind_canonical_sha256",
                                         "future_write_must_bind_plan_digest",
                                         "future_write_must_bind_proposal_sha256"])
        for key in bound:
            flag = "--expected-" + key.removeprefix("future_write_must_bind_").replace("_", "-")
            self.assertIn(flag, writer_flags, flag)
        # the semantic proposal digest is also required by the writer
        self.assertIn("--expected-proposal-semantic-sha256", writer_flags)
        result = self.revision_write(LUNCH, relative, first)
        self.assertEqual(self.native.calls, 1)
        self.assertIn(REVISED_TITLE, (self.root / "zettels" / f"{LUNCH}.md").read_text(encoding="utf-8"))
        receipt = json.loads((self.root / result["receipt"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["exact_human_approval"]["operation"], "zet_revision_write")
        self.assertNotIn(REVISED_TITLE, "".join(self.outputs))

    # ----- S2-U19 + S2-U22 ------------------------------------------------
    def test_s2_u19_u22_link_role_change_goes_through_receipt_revert(self) -> None:
        """S2-U19/S2-U22: role change = refuse, receipt lookup, exact revert, re-link."""
        zet = self.root / "zettels" / f"{LUNCH}.md"
        code, first = self.link(OBJ_A, "primary_source")  # unrelated link, created before
        self.assertEqual(code, 0, first)
        before = zet.read_bytes()
        code, linked = self.link(OBJ_B, "evidence")
        self.assertEqual(code, 0, linked)
        self.assertEqual(linked["state"], "written")
        code, refused = self.link(OBJ_B, "source_document")
        self.assertEqual(code, 1)
        self.assertEqual(refused["state"], "blocked")
        self.assertEqual(refused["blockers"], ["zettel_objet_link_already_present"])
        self.assertEqual(self.native.calls, 2)
        code, receipts = self.run_cli("zettel-objet-link-receipts", str(self.root), "--zettel-id", LUNCH,
                                      "--object-id", OBJ_B, "--dry-run")
        self.assertEqual(code, 0, receipts)
        self.assertEqual(receipts["state"], "revert_ready")
        self.assertEqual(receipts["summary"]["revert_ready_count"], 1)
        self.assertEqual(len(receipts["data"]["receipts"]), 1)
        selected = receipts["data"]["receipts"][0]
        self.assertEqual(selected["role"], "evidence")
        self.assertEqual(selected["receipt_path"], linked["summary"]["receipt_path"])
        self.assertFalse(receipts["privacy_guards"]["zettel_path_echoed"])
        code, reverted = self.run_cli("zettel-objet-link-revert", str(self.root), "--receipt",
                                      selected["receipt_path"], "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertTrue(reverted["summary"]["exact_byte_restore"])
        self.assertEqual(zet.read_bytes(), before)
        self.assertEqual(self.native.calls, 3)
        # S2-U22 observed: right after the revert the identity projection is
        # stale, so a re-link is refused until the archive is re-indexed.
        code, stale = self.link(OBJ_B, "source_document")
        self.assertEqual(code, 1)
        self.assertEqual(stale["reason_codes"], ["zettel_identity_projection_stale"])
        self.assertTrue(archive_services.index_archive(self.root)["ok"])
        code, relinked = self.link(OBJ_B, "source_document")
        self.assertEqual(code, 0, relinked)
        self.assertEqual(relinked["state"], "written")
        frontmatter, _body = self.zet_text(LUNCH)
        assets = frontmatter["assets"]
        self.assertEqual([a for a in assets if a["object_id"] == OBJ_B], [{"object_id": OBJ_B, "role": "source_document"}])
        self.assertEqual([a for a in assets if a["object_id"] == OBJ_A], [{"object_id": OBJ_A, "role": "primary_source"}])
        self.assertEqual(len(assets), 2)
        self.assertEqual(self.native.calls, 4)

    # ----- S2-U20 --------------------------------------------------------
    def test_s2_u20_batch_of_40_edges_reverts_exactly_and_revision_is_isolated(self) -> None:
        """S2-U20: 40 edges under one dialog, revert-batch removes exactly 40."""
        targets = sorted(p.stem for p in (self.root / "zettels").glob("*.md"))
        self.assertEqual(len(targets), 4)
        template, _body = self.zet_text(LUNCH)
        sources = []
        for index in range(10):
            zettel_id = f"zet_20260601_synthetic_edge_source_{index:02d}"
            frontmatter = json.loads(json.dumps(template))
            frontmatter.update(id=zettel_id, title=f"Synthetic edge source {index}", edges=[], assets=[])
            self.write_zet(zettel_id, frontmatter, f"Synthetic edge source body {index}.")
            sources.append(zettel_id)
        self.assertTrue(archive_services.index_archive(self.root)["ok"])
        plan_path = self.edge_plan(sources, targets)
        before = self.files()
        code, plan = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path), "--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["summary"]["policy_writable_edge_count"], 40)
        code, written = self.run_cli("zettel-edge-batch", str(self.root), "--plan", str(plan_path),
                                     "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, written)
        self.assertEqual(written["summary"]["written_edge_count"], 40)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.native.main, ["대상 10개"])
        for source in sources:
            self.assertEqual(len(self.zet_text(source)[0]["edges"]), 4)
        code, reverted = self.run_cli("revert-batch", str(self.root), "--receipt", written["receipt_path"],
                                      "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, reverted)
        self.assertEqual(reverted["write_status"], "reverted")
        self.assertEqual(reverted["summary"]["edge_revert_count"], 40)
        self.assertEqual(self.native.calls, 2)
        after = self.files()
        self.assertEqual(set(after), set(before))
        changed = sorted(k for k in after if after[k] != before[k])
        self.assertEqual(changed, sorted(f"zettels/{s}.md" for s in sources))
        for key in changed:
            self.assertEqual(self.zet_text(Path(key).stem)[0]["edges"], [])
            # S2-U20 observed: the revert rewrites updated_at; every other byte
            # outside the edges block is identical (no sources/source-bindings
            # frontmatter is touched by a material edge).
            self.assertEqual(self.outside_edge_block(after[key]), self.outside_edge_block(before[key]))
        self.assertEqual(after["source-bindings.yml"], before["source-bindings.yml"])
        # one safe revision on a different zet leaves an unrelated zet untouched
        lunch_before = (self.root / "zettels" / f"{LUNCH}.md").read_bytes()
        relative, plan = self.revision_proposal(FAMILY, "private-s2-u20")
        self.revision_write(FAMILY, relative, plan)
        self.assertEqual((self.root / "zettels" / f"{LUNCH}.md").read_bytes(), lunch_before)
        self.assertIn(REVISED_TITLE, (self.root / "zettels" / f"{FAMILY}.md").read_text(encoding="utf-8"))
        self.assertEqual(self.native.calls, 3)

    # ----- S2-U21 --------------------------------------------------------
    def test_s2_u21_compose_request_outside_the_request_root_is_refused_content_free(self) -> None:
        """S2-U21: a compose request under .wom-scratch/ names the pattern, echoes no path."""
        relative = ".wom-scratch/operator-feedback/requests/private-wrong-root.json"
        request = self.root / relative
        request.parent.mkdir(parents=True, exist_ok=True)
        request.write_text(json.dumps({"title": "PRIVATE_S2_TITLE", "sections": {}}), encoding="utf-8")
        code, result = self.run_cli("operator-feedback-compose", str(self.root), "--request", relative, "--dry-run")
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["blockers"], ["feedback_body_request_path_invalid"])
        self.assertEqual(result["requirements"]["request_path_pattern"],
                         "profiles/local/operator-feedback/requests/<name>.json")
        self.assertEqual(result["requirements"]["request_path_scope"], "archive_relative")
        self.assertFalse(result["privacy_guards"]["request_path_echoed"])
        self.assertFalse(result["privacy_guards"]["title_echoed"])
        rendered = "".join(self.outputs)
        self.assertNotIn(relative, rendered)
        self.assertNotIn("private-wrong-root", rendered)
        self.assertNotIn("PRIVATE_S2_TITLE", rendered)
        self.assertEqual(result["files_written"], [])
        self.assertEqual(self.native.calls, 0)

    # ----- S2-U23 --------------------------------------------------------
    def test_s2_u23_facet_vocabulary_and_unknown_facet_warning(self) -> None:
        """S2-U23: vocabulary lists keys with roles; an unknown facet warns, a known one does not."""
        code, vocabulary = self.run_cli("facet-vocabulary", str(self.root))
        self.assertEqual(code, 0, vocabulary)
        self.assertTrue(vocabulary["ok"])
        self.assertEqual(vocabulary["key_count"], len(vocabulary["keys"]))
        by_key = {item["key"]: item for item in vocabulary["keys"]}
        self.assertEqual(by_key["education_stage"]["role"], "navigation")
        self.assertEqual(by_key["page_id"]["role"], "internal")
        self.assertTrue(all(item["role"] in {"navigation", "internal", "unknown"} for item in vocabulary["keys"]))
        self.assertTrue(all(item["value_policy"] == vocabulary["value_policy"] for item in vocabulary["keys"]))
        self.assertEqual(vocabulary["unknown_key_policy"]["warning_code"], "unknown_facet_key_requires_human_review")
        self.assertFalse(vocabulary["facet_values_read"])
        self.assertNotIn("zzz_unknown_axis", by_key)
        object_id = self.fidelity_object("PRIVATE_S2_SOURCE_TEXT")
        common = ["create-draft", str(self.root), "--title", "Synthetic facet draft", "--abstract",
                  "Synthetic abstract for the facet check.", "--body", "Synthetic body.",
                  "--creation-mode", "ai_assisted", "--created-by", "ai_runtime:s2", "--assisted-by", "ai_runtime:s2",
                  "--source-fidelity", "faithful_summary", "--fidelity-audience", "private_self",
                  "--fidelity-source-object-id", object_id, "--facet", "education_stage=graduate"]
        code, known = self.run_cli(*common, "--dry-run")
        self.assertEqual(code, 0, known)
        self.assertTrue(known["ok"], known)
        self.assertNotIn("unknown_facet_key_requires_human_review", known["warnings"])
        code, mixed = self.run_cli(*common, "--facet", "zzz_unknown_axis=review", "--dry-run")
        self.assertEqual(code, 0, mixed)
        self.assertTrue(mixed["ok"], mixed)
        self.assertIn("unknown_facet_key_requires_human_review", mixed["warnings"])
        self.assertEqual(mixed["warnings"].count("unknown_facet_key_requires_human_review"), 1)
        self.assertEqual(mixed["frontmatter_preview"]["facets"],
                         {"education_stage": "graduate", "zzz_unknown_axis": "review"})
        # S2-U23 gap: the warning is a fixed code; the unknown key is not named
        # separately from the known one anywhere outside the facets preview.
        preview_free = json.loads(json.dumps(mixed))
        preview_free["frontmatter_preview"].pop("facets")
        self.assertNotIn("zzz_unknown_axis", json.dumps(preview_free))
        # S2-U23 gap: the create-draft --facet help names the KEY=VALUE form
        # but does not state the vocabulary's value_policy.
        facet_help = next(a.help for a in self.parser._subparsers._group_actions[0].choices["create-draft"]._actions
                          if a.dest == "facet")
        self.assertIn("KEY=VALUE", facet_help)
        self.assertEqual(vocabulary["value_policy"], "archive_defined_safe_scalar_or_list")
        self.assertNotIn(vocabulary["value_policy"], facet_help)
        self.assertEqual(self.native.calls, 0)

    # ----- S2-U24 --------------------------------------------------------
    def test_s2_u24_reversible_hold_keeps_id_and_reason_and_refuses_canonical(self) -> None:
        """S2-U24: hold -> review -> release keeps a stable id and reason; canonical ids are refused."""
        request = {"schema": draft_disposition.REQUEST_SCHEMA, "action": "hold", "zettel_id": INBOX_DRAFT,
                   "reason": "Wait for the source comparison.", "intended_next_action": "discard",
                   "conditions": [{"condition_id": "source_checked", "description": "Compare.", "state": "unmet"}]}
        request_path = self.tmp / "hold.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        code, plan = self.run_cli("draft-disposition", str(self.root), "--request", str(request_path), "--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["state"], "held_pending_review")
        # v0.4.56: the official --approve path reaches the dialog (its approval
        # context once carried unsorted review_binding_codes and raised first).
        draft_bytes = (self.root / "inbox" / f"{INBOX_DRAFT}.md").read_bytes()
        code, held_cli = self.run_cli("draft-disposition", str(self.root), "--request", str(request_path), "--approve",
                                      "--reviewed-by", REVIEWER, "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, held_cli)
        self.assertEqual(held_cli["state"], "held_pending_review")
        self.assertEqual(self.native.calls, 1)
        self.assertEqual((self.root / "inbox" / f"{INBOX_DRAFT}.md").read_bytes(), draft_bytes)
        # the domain writer itself, with the approval boundary injected
        with patch.object(draft_disposition, "_ClaimedExactHumanApproval", _Claim), \
                patch.object(draft_disposition, "_context",
                             side_effect=lambda value, reviewer: draft_disposition._sha(draft_disposition._canonical(value))):
            def apply(value: dict) -> dict:
                digest = draft_disposition.plan(self.root, value)["plan_sha256"]
                return draft_disposition.apply(self.root, value, expected_plan_sha256=digest,
                                               reviewer_claim=REVIEWER, approval_claim=_Claim())
            held = held_cli
            review = json.loads(json.dumps(request))
            review["action"] = "review"
            review["conditions"][0].update(state="met", evidence_ref="receipt:synthetic-source-comparison")
            review["expected_previous_event_sha256"] = held["event_sha256"]
            self.assertEqual(apply(review)["state"], "ready_for_review")
            release = {k: v for k, v in review.items() if k != "expected_previous_event_sha256"}
            release["action"] = "release"
            self.assertEqual(apply(release)["state"], "released")
        self.assertEqual((self.root / "inbox" / f"{INBOX_DRAFT}.md").read_bytes(), draft_bytes)
        code, history = self.run_cli("draft-disposition", str(self.root), "--zettel-id", INBOX_DRAFT, "--history")
        self.assertEqual(code, 0, history)
        self.assertEqual(history["event_count"], 3)
        events = history["events"]
        self.assertEqual([e["action"] for e in events], ["hold", "review", "release"])
        self.assertEqual({e["zettel_id"] for e in events}, {INBOX_DRAFT})
        self.assertEqual({e["reason"] for e in events}, {"Wait for the source comparison."})
        self.assertFalse(history["conditions_are_delete_authority"])
        # a canonical zet cannot be held: the CLI reports the fixed domain code
        canonical = {**request, "zettel_id": LUNCH}
        request_path.write_text(json.dumps(canonical), encoding="utf-8")
        code, refused = self.run_cli("draft-disposition", str(self.root), "--request", str(request_path), "--dry-run")
        self.assertEqual(code, 1)
        self.assertEqual(refused, {"ok": False, "blockers": ["draft_disposition_failed"], "private_values_echoed": False})
        with self.assertRaisesRegex(archive_services.ArchiveServiceError, "^draft_disposition_target_unavailable$"):
            draft_disposition.plan(self.root, canonical)
        # S2-U24 gap: no canonical hold/quarantine command exists; draft-disposition
        # only targets inbox drafts and the CLI collapses the code to draft_disposition_failed.

    # ----- S2-U25 --------------------------------------------------------
    def test_s2_u25_locator_loss_audit_across_ledger_states(self) -> None:
        """S2-U25: same fixture audited under a legacy v0.1 ledger and after a verified resolution."""
        helper = locator.V045LocalLocatorTitleRecoveryTests("test_legacy_v01_resolution_ledger_is_counted_but_never_trusted")
        marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
        fragment = f'<file src="{marker}"></file>'
        before = helper.write_notion_zettel(self.root, title="Current Human Title", body=fragment + "\n")
        legacy = {"schema": "wom-kit/notion-locator-orphan-recovery-ledger/v0.1",
                  "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
                      archive_services.read_archive_id(self.root)),
                  "classification_items": [], "private_values_echoed": False,
                  "operation_evidence": {"schema": "wom-kit/notion-locator-orphan-recovery-evidence/v1",
                                         "counts": {"orphan_row_count": 0},
                                         "digests": {"orphan_row_set_sha256": "sha256:" + "0" * 64},
                                         "private_values_echoed": False}}
        raw = json.dumps(legacy, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        ledger_dir = self.root / "profiles" / "local" / "local-recovery" / "ledgers" / "notion_locator_orphan"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        (ledger_dir / f"{hashlib.sha256(raw).hexdigest()}.json").write_bytes(raw)
        # (a) legacy v0.1 ledger: counted, never trusted
        legacy_audit = self.locator_audit()
        summary_a, item_a = legacy_audit["summary"], legacy_audit["items"][0]
        self.assertEqual((summary_a["body_marker_count"], summary_a["frontmatter_omitted_count"]), (1, 1))
        self.assertEqual((item_a["body_marker_count"], item_a["frontmatter_omitted_count"], item_a["count_state"]),
                         (1, 1, "exact"))
        self.assertEqual(summary_a["counts_by_state"], {"exact": 1})
        self.assertEqual(summary_a["skipped_legacy_resolution_ledger_count"], 1)
        self.assertEqual(summary_a["verified_reference_resolution_ledger_count"], 0)
        self.assertEqual(summary_a["verified_reference_resolution_count"], 0)
        self.assertEqual(item_a["verified_reference_resolution_state"], "not_present")
        self.assertEqual(summary_a["unresolved_occurrence_state"], "unknown")
        self.assertEqual(summary_a["unresolved_occurrence_reason_codes"], ["external_locator_sidecar_absent"])
        # (b) a current verified reference resolution receipt on the same zet
        object_id = OBJ_A
        after = helper.write_notion_zettel(self.root, title="Current Human Title",
                                           body=f"[Attached objet](wom-objet:{object_id})\n")
        binding = {"schema": completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA,
                   "archive_id": archive_services.read_archive_id(self.root),
                   "bindings": [{"zettel_id": locator.ZETTEL_ID, "binding_kind": "objet", "binding_id": object_id,
                                 "tag_sha256": completion_workflows._sha256_bytes(fragment.encode("utf-8"))}]}
        binding_raw = json.dumps(binding).encode("utf-8")
        binding_path = self.root / ".wom-scratch" / "markup-bindings" / "reviewed.json"
        binding_path.parent.mkdir(parents=True, exist_ok=True)
        binding_path.write_bytes(binding_raw)
        receipt = helper.write_markup_receipt(self.root, before=before, after=after, token="3",
                                              binding_manifest_sha256=hashlib.sha256(binding_raw).hexdigest())
        execution = notion_locator_orphan_recovery_execution_plan(self.root, markup_receipts=[receipt],
                                                                  expected_orphan_row_count=1)
        applied, _keys = helper.execute_authenticated(execution, key_provider=self.keys)
        self.assertTrue(applied["ok"], applied)
        verified_audit = self.locator_audit()
        summary_b, item_b = verified_audit["summary"], verified_audit["items"][0]
        # body_marker_count 1 -> 0: the verified resolution replaced the marker with an objet reference
        self.assertEqual(item_b["body_marker_count"], 0)
        self.assertEqual(summary_b["verified_reference_resolution_count"], 1)  # resolved_occurrence_count
        self.assertEqual(item_b["verified_reference_resolution_state"], "verified")
        # frontmatter_omitted_count stays 1 on the item: the resolution never edits the declared count;
        # the summary sum drops to 0 because no marker-bearing zet remains in `affected`
        self.assertEqual(item_b["frontmatter_omitted_count"], 1)
        self.assertEqual((summary_b["body_marker_count"], summary_b["frontmatter_omitted_count"]), (0, 0))
        # count_state exact -> frontmatter_count_exceeds_body for the same reason (declared 1, markers 0)
        self.assertEqual(item_b["count_state"], "frontmatter_count_exceeds_body")
        self.assertEqual(summary_b["counts_by_state"], {})
        # unresolved state unknown -> known: the receipt is a verified resolution ledger
        self.assertEqual((summary_b["unresolved_occurrence_state"], summary_b["unresolved_occurrence_count"]), ("known", 0))
        self.assertEqual(summary_b["verified_reference_resolution_ledger_count"], 1)
        self.assertEqual(summary_b["skipped_legacy_resolution_ledger_count"], 1)  # still counted, still untrusted
        # S2-U25 gap: the audit exposes the ledger's resolved_occurrence_count only as
        # verified_reference_resolution_count; no metric carries the raw name.
        self.assertNotIn('"resolved_occurrence_count"', json.dumps(verified_audit))


if __name__ == "__main__":
    unittest.main()
