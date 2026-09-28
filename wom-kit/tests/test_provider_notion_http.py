"""Official Notion source endpoints and query-only POST/DELETE transport."""
import unittest
from wom_kit.notion_http_adapter import _NotionHttpAdapter
import test_notion_http_adapter as helpers


class ProviderNotionHttpTests(unittest.TestCase):
    def test_property_id_is_encoded_once_and_cursor_cannot_change_path(self):
        transport = helpers.FakeTransport(helpers.FakeResponse(payload={"results": [], "has_more": False}))
        result = _NotionHttpAdapter(transport=transport).retrieve_page_property(helpers.PAGE_ID, "rel%3A%2F", "synthetic", cursor="a&secret=synthetic")
        self.assertEqual(result.status, 200)
        request = transport.calls[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/properties/rel%3A%2F?", request.full_url)
        self.assertIn("start_cursor=a%26secret%3Dsynthetic", request.full_url)

    def test_view_query_create_paginate_delete_never_mutate_a_view(self):
        transport = helpers.FakeTransport(*[helpers.FakeResponse(payload={"id": "query", "results": []}) for _ in range(3)])
        adapter = _NotionHttpAdapter(transport=transport)
        adapter.query_view(helpers.PAGE_ID, "synthetic")
        adapter.query_view(helpers.PAGE_ID, "synthetic", query_id="query", cursor="cursor")
        adapter.query_view(helpers.PAGE_ID, "synthetic", query_id="query", delete=True)
        self.assertEqual([row[0].get_method() for row in transport.calls], ["POST", "GET", "DELETE"])
        self.assertTrue(all("/queries" in row[0].full_url for row in transport.calls))
        self.assertEqual(adapter.query_view(helpers.PAGE_ID, "synthetic", query_id="../../pages").status, 400)
        self.assertEqual(len(transport.calls), 3)

    def test_views_list_is_limited_to_one_normalized_database(self):
        transport = helpers.FakeTransport(helpers.FakeResponse(payload={"results": []}))
        result = _NotionHttpAdapter(transport=transport).retrieve_source_object("database_views", helpers.PAGE_ID, "synthetic")
        self.assertEqual(result.status, 200)
        self.assertIn("/v1/views?database_id=" + helpers.PAGE_ID, transport.calls[0][0].full_url)
