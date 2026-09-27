import hashlib
import unittest

from wom_kit import archive_services as services


class TransferObservationTests(unittest.TestCase):
    def test_malformed_response_is_returned_unchanged(self):
        from wom_kit.transfer_observation import TransferObservation
        observer = TransferObservation()
        for response in (None, {}, {"status": "invalid"}, {"status": True}):
            self.assertIs(observer.call("GET", lambda: response), response)
        self.assertEqual(observer.snapshot()["failed_or_unmeasured_responses"], 4)

    def test_real_provider_dispatch_counts_whole_get_and_failed_retry_separately(self):
        content = b"synthetic bytes"
        responses = [
            {"status": 503},
            {"status": 200, "headers": {"content-length": str(len(content))}},
            {"status": 200, "body": content, "headers": {"etag": '"synthetic"'}},
            {"status": 200, "headers": {"content-length": str(len(content)), "etag": '"synthetic"'}},
        ]
        transport = services._S3CompatibleTransport(endpoint_host="example.invalid", bucket="synthetic",
            access_key_id="synthetic", secret_access_key="synthetic", region="auto",
            send=lambda **kwargs: responses.pop(0))
        first = transport.head_object(key="private-synthetic-key")
        self.assertEqual(first["presence_state"], "unavailable")
        second = transport.head_object(key="private-synthetic-key")
        self.assertEqual(second["checksum_sha256"], hashlib.sha256(content).hexdigest())
        transport.head_object_if_match(key="private-synthetic-key", etag='"synthetic"')
        observed = transport.transfer_observation()
        self.assertEqual(observed["request_counts"], {"HEAD": 3, "GET": 1})
        self.assertEqual(observed["observed_complete_download_body_bytes"], len(content))
        self.assertEqual(observed["failed_or_unmeasured_responses"], 1)
        self.assertIsNone(observed["wire_bytes_including_headers_tls_and_failed_partial_transfers"])
        self.assertNotIn("private-synthetic-key", repr(observed))

    def test_sender_exception_is_preserved_and_counted_without_claiming_bytes(self):
        def failed(**kwargs):
            raise OSError("synthetic private endpoint failure")
        transport = services._S3CompatibleTransport(endpoint_host="example.invalid", bucket="synthetic",
            access_key_id="synthetic", secret_access_key="synthetic", region="auto", send=failed)
        with self.assertRaises(OSError):
            transport.head_object(key="private-synthetic-key")
        self.assertEqual(transport.transfer_observation()["request_count"], 1)
        self.assertEqual(transport.transfer_observation()["failed_or_unmeasured_responses"], 1)
