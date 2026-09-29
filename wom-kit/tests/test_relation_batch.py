"""Synthetic discovery, multi-edge CAS, decision provenance and recovery."""
import json
from pathlib import Path
import tempfile
import time
import sysconfig
import unittest
from unittest.mock import patch

from wom_kit import archive_services as services, relation_batch as module
from wom_kit import local_recovery_execution as recovery, search_snapshots
import test_local_recovery_execution as fixture


class RelationBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-relation-batch-")
        self.addCleanup(temporary.cleanup)
        self.helper = fixture.LocalRecoveryExecutionTests()
        self.root = self.helper.archive(Path(temporary.name))
        self.source_id = fixture.ZETTEL_ID
        self.source = self.root / "zettels" / (self.source_id + ".md")
        original = self.source.read_bytes()
        self.targets = []
        for n in range(3):
            zid = f"zet_20260928_relation_target_{n}"
            path = self.root / "zettels" / (zid + ".md")
            path.write_bytes(original.replace(self.source_id.encode(), zid.encode()))
            self.targets.append((zid, path))
        self.source.write_bytes(original + ("\n" + "\n".join(zid for zid, _ in self.targets)).encode("utf-8"))
        services.index_archive(self.root)
        refreshed = search_snapshots.publish(self.root)
        self.assertTrue(refreshed["ok"], refreshed)
        self.snapshot = module.publish(self.root)["snapshot_ref"]

    def request(self, *, count=2, decision="accept"):
        result = module.query(self.root, from_zettel=self.source_id, snapshot_ref=self.snapshot)
        rows = [row for row in result["items"] if row["target_zettel"] in {zid for zid, _ in self.targets}][:count]
        self.assertEqual(len(rows), count)
        return {"schema": module.REQUEST_SCHEMA, "snapshot_ref": self.snapshot,
                "reviewed_by": "person:synthetic-reviewer", "decisions": [
            {"from_zettel": self.source_id, "candidate_id": row["candidate_id"], "decision": decision,
             "edge_type": "references" if decision == "accept" else None, "visibility": "private",
             "reason": "Explicit source mention reviewed in synthetic fixture.", "confidence": "high"}
            for row in rows]}

    def test_paged_native_signals_use_original_generation_without_live_reads(self):
        first = module.query(self.root, from_zettel=self.source_id, snapshot_ref=self.snapshot, page_size=1)
        self.assertTrue(any(signal["kind"] == "explicit_body_zettel_reference" for signal in first["items"][0]["signals"]))
        self.source.write_bytes(self.source.read_bytes() + b"\nnew live generation\n")
        with patch.object(module, "_read_target", side_effect=AssertionError("query read live target")):
            next_page = module.query(self.root, from_zettel=self.source_id, snapshot_ref=self.snapshot,
                                     page_size=1, cursor=first["pagination"]["next_cursor"])
        self.assertNotEqual(first["items"][0]["candidate_id"], next_page["items"][0]["candidate_id"])
        self.assertEqual(first["snapshot_ref"], next_page["snapshot_ref"])

    def test_many_edges_one_source_write_preserves_body_and_judgment_backlinks_and_revert(self):
        before_fm, before_body = services.require_readable_zettel_content(self.source)
        plan = module.plan(self.root, self.request())
        self.assertEqual(plan.public_summary["edge_count"], 2)
        self.assertEqual(plan.public_summary["source_write_count"], 1)
        self.assertEqual(len(plan.manifest.items), 2)
        with patch.object(services, "_replace_regular_file_bytes_compare_and_swap", wraps=services._replace_regular_file_bytes_compare_and_swap) as cas:
            result = self.helper.execute(plan, mode="apply")
        self.assertTrue(result["ok"], result)
        self.assertEqual(cas.call_count, 1)
        after_fm, after_body = services.require_readable_zettel_content(self.source)
        self.assertEqual(after_body, before_body)
        self.assertEqual({k: v for k, v in before_fm.items() if k != "edges"},
                         {k: v for k, v in after_fm.items() if k != "edges"})
        for edge in after_fm["edges"][-2:]:
            detail = module.judgment(self.root, edge["provenance"]["judgment_ref"])
            self.assertTrue(any(row["candidate_id"] == edge["provenance"]["candidate_id"] and row["reason"]
                                for row in detail["judgments"]))
        self.source.write_bytes(self.source.read_bytes() + b"\nLater unrelated human body edit.\n")
        services.index_archive(self.root)
        reverted = self.helper.execute(plan, mode="revert")
        self.assertTrue(reverted["ok"], reverted)
        reverted_fm, reverted_body = services.require_readable_zettel_content(self.source)
        self.assertEqual(reverted_fm["edges"], before_fm["edges"])
        self.assertIn("Later unrelated human body edit.", reverted_body)

    def test_changed_target_basis_blocks_source_write_after_review(self):
        plan = module.plan(self.root, self.request(count=3))
        target = self.targets[0][1]
        target.write_bytes(target.read_bytes() + b"\nChanged reviewed target.\n")
        with self.assertRaisesRegex(services.ArchiveServiceError, "relation_judgment_basis_changed"):
            recovery.local_recovery_observe_target_binding(plan, mode="apply")()
        services.index_archive(self.root)
        result = self.helper.execute(plan, mode="apply")
        self.assertFalse(result["ok"], result)
        self.assertEqual(recovery._field_value(self.root, plan.specs[1]), plan.specs[1].pre_value)

    def test_reject_and_defer_only_record_decisions_and_do_not_create_edges(self):
        request = self.request(decision="reject")
        request["decisions"][1]["decision"] = "defer"
        before = self.source.read_bytes()
        plan = module.plan(self.root, request)
        self.assertEqual(len(plan.manifest.items), 1)
        result = self.helper.execute(plan, mode="apply")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.source.read_bytes(), before)
        detail = module.judgment(self.root, plan.public_summary["judgment_ref"])
        self.assertEqual({row["decision"] for row in detail["judgments"]}, {"reject", "defer"})

    def test_same_generation_refresh_and_complete_type_guide(self):
        repeated = module.publish(self.root)
        self.assertEqual(repeated["snapshot_ref"], self.snapshot)
        guide = module.semantics(self.root)
        types = {row["edge_type"] for row in guide["types"]}
        self.assertTrue({"derived_from", "references", "continues", "sequence", "format_variant"} <= types)
        self.assertEqual(guide["type_count"], len(types))
        self.assertGreaterEqual(guide["type_count"], 21)

    def test_native_derivation_rank_and_explicit_pair_batch_avoids_corpus_candidate_scan(self):
        source = module._projection({"id": "zet_20260928_a", "title": "Different concept", "edges": [],
            "provenance": {"derived_from": ["zet_20260928_b"]}}, "", "zettels/a.md", "sha256:" + "a" * 64)
        target = module._projection({"id": "zet_20260928_b", "title": "Original source", "edges": []},
                                    "", "zettels/b.md", "sha256:" + "b" * 64)
        candidate = module._candidate(source, target)
        self.assertEqual(candidate["signals"][0]["kind"], "native_provenance_derived_from")
        self.assertEqual(candidate["suggested_types"][0], "derived_from")
        request = self.request()
        candidates = {row["candidate_id"]: row for row in module.query(self.root, from_zettel=self.source_id)["items"]}
        for row in request["decisions"]:
            row["target_zettel"] = candidates[row["candidate_id"]]["target_zettel"]
        with patch.object(module, "_candidates", side_effect=AssertionError("batch rediscovered all candidates")):
            plan = module.plan(self.root, request)
        self.assertEqual(plan.public_summary["edge_count"], 2)

    def test_native_batch_interruption_resumes_same_claim_and_no_duplicate_edges(self):
        from wom_kit.exact_human_approval_workflow import _execute_exact_human_approved_write_core
        plan = module.plan(self.root, self.request())
        native, keys = fixture._ApproveNative(), fixture._StableKeyProvider()
        original = recovery._Writer.write_field
        def broker(root, context, writer, **preview):
            return _execute_exact_human_approved_write_core(root, context, writer,
                        native=native, key_provider=keys, **preview)
        def crash_after_edges(writer, **kwargs):
            original(writer, **kwargs)
            if kwargs["field_ref"] == "frontmatter.edges":
                raise RuntimeError("synthetic interruption after source CAS")
        with patch.object(recovery, "_execute_exact_human_approved_write", new=broker), \
             patch.object(recovery._Writer, "write_field", new=crash_after_edges):
            interrupted = recovery.execute_local_recovery(plan)
        self.assertFalse(interrupted["ok"], interrupted)
        self.assertEqual(native.calls, 1)
        loaded = recovery.load_local_recovery_plan(self.root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = recovery.resume_local_recovery(loaded, key_provider=keys)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(native.calls, 1)
        self.assertFalse(resumed["native_approval_redisplayed"])
        self.assertEqual(recovery._field_value(self.root, plan.specs[1]), plan.specs[1].post_value)

    def test_malformed_private_request_returns_fixed_error_without_echoing_values(self):
        for field in ("from_zettel", "target_zettel", "candidate_id", "decision", "visibility", "confidence", "edge_type"):
            request = self.request(count=1)
            request["decisions"][0][field] = ["synthetic-private-value"]
            with self.subTest(field=field), self.assertRaisesRegex(services.ArchiveServiceError, "^relation_batch_decision_invalid$"):
                module.plan(self.root, request)
        with self.assertRaisesRegex(services.ArchiveServiceError, "^relation_source_invalid$"):
            module.query(self.root, from_zettel=["synthetic-private-value"])

    def test_five_thousand_zet_generation_pages_have_no_missing_or_duplicate_candidate(self):
        started = time.perf_counter()
        expected = set(module._read(self.root, self.snapshot)[2]["entries"])
        original = self.source.read_bytes()
        for number in range(5000 - len(expected)):
            zid = f"zet_20260928_scale_target_{number:05d}"
            (self.root / "zettels" / (zid + ".md")).write_bytes(original.replace(self.source_id.encode(), zid.encode()))
            expected.add(zid)
        expected.remove(self.source_id)
        self.source.write_bytes(original + ("\n" + "\n".join(sorted(expected))).encode("utf-8"))
        created = time.perf_counter()
        indexed = services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        snapshot = indexed["relation_snapshot"]["snapshot_ref"]
        self.assertEqual(indexed["relation_snapshot"]["zettel_count"], 5000)
        indexed_at = time.perf_counter()
        seen, cursor, pages = set(), None, 0
        with patch.object(module, "_read_target", side_effect=AssertionError("page reread canonical target")), \
             patch.object(services, "zet_catalog_entries", side_effect=AssertionError("page rescanned canonical corpus")):
            while True:
                result = module.query(self.root, from_zettel=self.source_id, snapshot_ref=snapshot,
                                      page_size=173, cursor=cursor)
                pages += 1
                for row in result["items"]:
                    self.assertNotIn(row["target_zettel"], seen)
                    seen.add(row["target_zettel"])
                cursor = result["pagination"]["next_cursor"]
                if cursor is None:
                    break
        self.assertEqual(seen, expected)
        print(json.dumps({"scale_evidence": "relation_pages", "source_zet_count": 5000,
            "candidate_count": len(seen), "missing": 0, "duplicates": 0, "pages": pages,
            "canonical_rereads_during_query": 0, "fixture_seconds": round(created-started, 3),
            "index_and_projection_seconds": round(indexed_at-created, 3),
            "all_pages_seconds": round(time.perf_counter()-indexed_at, 3),
            "installed_product": Path(module.__file__).resolve().is_relative_to(
                Path(sysconfig.get_paths()["purelib"]).resolve())}))


if __name__ == "__main__":
    unittest.main()
