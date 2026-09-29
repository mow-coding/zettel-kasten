import json
import unittest

from wom_kit.provider_notion_connections import KINDS, LENSES, materialize_view, parse_source, reviewed_edge_plan
from wom_kit.provider_artifacts import ProviderArtifactError

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


class ConnectionTests(unittest.TestCase):
    def parse(self, value):
        return parse_source(json.dumps(value).encode(), source_ref="synthetic.json", source_page_id=A, format="json")

    def test_six_mechanisms_are_read_from_actual_source_shapes(self):
        result = self.parse([
            {"type": "relation", "relation": [{"id": B}]},
            {"type": "synced_block", "synced_block": {"synced_from": {"block_id": B}}},
            {"object": "view_query", "id": "query", "view_id": A, "results": [{"id": B}]},
            {"type": "text", "text": {"link": {"url": "https://www.notion.so/" + B}}},
            {"type": "mention", "mention": {"type": "page", "page": {"id": B}}},
            {"object": "comment", "id": "comment", "parent": {"page_id": B}},
        ])
        self.assertEqual(set(result["observed_kinds"]), KINDS)
        self.assertEqual(result["edges_written"], 0)
        self.assertTrue(all(row["meaning"] is None for row in result["candidates"]))

    def test_real_html_and_markdown_links_keep_source_hash_and_do_not_guess_missing_types(self):
        for format, raw in [("html", f'<a href="https://notion.so/{B}">link</a>'), ("markdown", f'[link](https://notion.so/{B})')]:
            result = parse_source(raw.encode(), source_ref="source." + format, source_page_id=A, format=format)
            self.assertEqual(result["observed_kinds"], ["internal_url_hyperlink"])
            self.assertEqual(result["candidates"][0]["target_page_id"], B)
            self.assertIn("relation_property", result["unobserved_kinds"])

    def test_csv_requires_relation_schema_instead_of_guessing_column_meaning(self):
        raw = ("Related\n" + B + "\n").encode()
        result = parse_source(raw, source_ref="table.csv", source_page_id=A, format="csv")
        self.assertEqual(result["candidates"], [])
        self.assertIn("notion_csv_relation_schema_required", result["warnings"])
        result = parse_source(raw, source_ref="table.csv", source_page_id=A, format="csv", relation_columns={"Related": "property-id"})
        self.assertEqual(result["candidates"][0]["connection_kind"], "relation_property")

    def test_stable_query_pages_materialize_and_cleanup(self):
        calls = []
        result = materialize_view(A, retrieve=lambda _: {"filter": {"property": "Status"}},
            create_query=lambda _: {"id": "q", "results": [{"id": A}], "has_more": True, "next_cursor": "c"},
            query_page=lambda view, query, cursor: {"id": query, "results": [{"id": B}], "has_more": False},
            delete_query=lambda *args: calls.append(args), captured_at="2026-01-01T00:00:00Z")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(calls, [(A, "q")])
        self.assertFalse(result["has_more"])

    def test_changed_query_generation_is_refused_and_cleaned_up(self):
        calls = []
        with self.assertRaisesRegex(ProviderArtifactError, "generation_changed"):
            materialize_view(A, retrieve=lambda _: {}, create_query=lambda _: {"id": "q", "results": [], "has_more": True, "next_cursor": "c"},
                query_page=lambda *args: {"id": "other", "results": []}, delete_query=lambda *args: calls.append(args), captured_at="time")
        self.assertEqual(calls, [(A, "q")])

    def test_review_requires_three_lenses_provenance_and_exact_source(self):
        candidate = self.parse({"type": "relation", "relation": [{"id": B}]})["candidates"][0]
        bindings = {A: "zet:synthetic-a", B: "zet:synthetic-b"}
        self.assertEqual(reviewed_edge_plan([candidate], [], bindings)["edges"], [])
        judgment = {"candidate_id": candidate["candidate_id"], "source_sha256": candidate["source_sha256"],
            "review_status": "approved", "model_provenance": {"provider": "synthetic", "model": "fixture", "run_id": "run"},
            "lenses": {lens: {"edge_type": "semantic", "evidence_ref": "synthetic.json", "direction": "source_to_target"} for lens in LENSES}}
        plan = reviewed_edge_plan([candidate], [judgment], bindings)
        self.assertEqual(plan["edges"][0]["from_zettel"], "zet:synthetic-a")
        judgment["source_sha256"] = "changed"
        self.assertEqual(reviewed_edge_plan([candidate], [judgment], bindings)["edges"], [])
