from io import BytesIO
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

from wom_kit.provider_notion_media import discover, fetch_media, open_media
from wom_kit.provider_artifacts import ProviderArtifactError


class Stream(BytesIO):
    def __init__(self, content, status=200):
        super().__init__(content)
        self.status = status


class MediaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reads = []

    def read(self, kind, object_id, cursor):
        self.reads.append((kind, object_id, cursor))
        if kind == "page":
            return {"id": "page"}
        if kind == "block":
            return {"id": "image", "type": "image", "image": {"type": "file", "file": {"url": "https://example.invalid/fresh?secret=fresh"}}}
        if object_id == "page" and cursor is None:
            return {"results": [{"id": "nested", "has_children": True}], "has_more": True, "next_cursor": "next"}
        if object_id == "page":
            return {"results": [], "has_more": False}
        return {"results": [{"id": "image", "type": "image", "image": {"type": "file", "file": {"url": "https://example.invalid/old?secret=old"}}}], "has_more": False}

    def test_nested_pagination_expiry_refresh_bytes_and_private_receipt(self):
        downloads = []
        def download(url):
            downloads.append(url)
            return Stream(b"image-bytes", 403 if "/old?" in url else 200)
        result = fetch_media(self.root, page_ids=["page"], batch_id="synthetic", read=self.read, download=download)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["staged"], 1)
        self.assertIn(("children", "page", "next"), self.reads)
        receipt_raw = (self.root / result["receipt_path"]).read_text()
        self.assertNotIn("secret=", receipt_raw)
        row = json.loads(receipt_raw)["items"][0]
        self.assertEqual((self.root / row["path"]).read_bytes(), b"image-bytes")
        request = json.loads((self.root / result["intake_request"]).read_text())
        self.assertEqual(request["items"][0]["local_path"], row["path"])
        self.assertFalse(result["capture_completed"])

    def test_limit_does_not_leave_a_partial_as_success(self):
        result = fetch_media(self.root, page_ids=["page"], batch_id="limit", read=self.read, download=lambda _: Stream(b"12345"), max_bytes=3)
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed"], 1)
        self.assertEqual(list((self.root / "workbench/provider-blobs").glob("*.partial")), [])

    def test_cursor_cycle_is_not_silently_complete(self):
        def read(kind, object_id, cursor):
            return {} if kind == "page" else {"results": [], "has_more": True, "next_cursor": "same"}
        with self.assertRaisesRegex(ProviderArtifactError, "cursor_invalid"):
            discover(["page"], read)

    def test_private_address_and_redirect_target_are_not_requested(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(ProviderArtifactError, "transport_unavailable"):
                open_media("https://example.invalid/private")

    def test_repeated_capture_deduplicates_downloaded_bytes(self):
        args = dict(page_ids=["page"], batch_id="same", read=self.read, download=lambda _: Stream(b"same"))
        first = fetch_media(self.root, **args)
        second = fetch_media(self.root, **args)
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(len(list((self.root / "workbench/provider-blobs").glob("*.bin"))), 1)

    def test_many_leaf_blocks_are_bounded_even_without_child_pages(self):
        def read(kind, object_id, cursor):
            return {} if kind == "page" else {"results": [{"id": str(index)} for index in range(3)], "has_more": False}
        with self.assertRaisesRegex(ProviderArtifactError, "block_limit"):
            discover(["page"], read, max_blocks=2)

    def test_external_redirect_is_rechecked_without_authentication_headers(self):
        first, second = Mock(), Mock()
        first_response = first.getresponse.return_value
        first_response.status = 302
        first_response.getheader.return_value = "https://cdn.example.invalid/media"
        second.getresponse.return_value.status = 200
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]), patch(
                "wom_kit.provider_notion_media._PinnedHTTPS", side_effect=[first, second]):
            stream = open_media("https://example.invalid/media?private=initial")
            self.assertEqual(stream.status, 200)
            stream.close()
        self.assertEqual(second.request.call_args.args, ("GET", "/media"))
        self.assertEqual(second.request.call_args.kwargs["headers"], {"Accept": "*/*"})
        first.close.assert_called_once()

    def test_redirect_to_private_host_never_opens_second_connection(self):
        first = Mock()
        first.getresponse.return_value.status = 302
        first.getresponse.return_value.getheader.return_value = "https://internal.example.invalid/media"
        with patch("socket.getaddrinfo", side_effect=[[(2, 1, 6, "", ("8.8.8.8", 443))], [(2, 1, 6, "", ("127.0.0.1", 443))]]), patch(
                "wom_kit.provider_notion_media._PinnedHTTPS", return_value=first) as connections:
            with self.assertRaisesRegex(ProviderArtifactError, "transport_unavailable"):
                open_media("https://example.invalid/media")
        self.assertEqual(connections.call_count, 1)
