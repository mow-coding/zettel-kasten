from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from wom_kit import archive_services as services, objet_capture_batch_exact as capture
from wom_kit import exact_human_approval_workflow as broker
from . import test_v0410_objet_capture_batch_exact as fixture


class CaptureConcurrencyTests(unittest.TestCase):
    setUp = fixture.ObjetCaptureBatchExactTests.setUp
    tearDown = fixture.ObjetCaptureBatchExactTests.tearDown
    _request = fixture.ObjetCaptureBatchExactTests._request
    _plan = fixture.ObjetCaptureBatchExactTests._plan
    _workflow = staticmethod(fixture.ObjetCaptureBatchExactTests._workflow)

    def test_second_capture_commits_before_first_source_processing_returns(self):
        request_a, execution_a = self._request(1, batch_id="parallel-a")
        with patch.object(fixture, "PRIVATE_BODY", b"synthetic distinct second source\n"):
            request_b, execution_b = self._request(1, batch_id="parallel-b")
        plan_a, plan_b = self._plan(request_a, execution_a), self._plan(request_b, execution_b)
        original = services._objet_capture_process_item
        second = []
        def process(root, item, **kwargs):
            if kwargs["approve"] and item["item_id"].startswith("parallel-a"):
                with ThreadPoolExecutor(max_workers=1) as worker:
                    result = worker.submit(capture.execute_objet_capture_batch, plan_b,
                        reviewer_claim=fixture.REVIEWER).result(timeout=15)
                self.assertTrue(result["ok"], result)
                second.append(result)
            return original(root, item, **kwargs)
        with patch.object(capture, "_execute_exact_human_approved_write",
                side_effect=self._workflow(fixture._Native(approved=True), fixture._KeyProvider())), \
                patch.object(broker, "_production_key_provider", return_value=fixture._KeyProvider()), \
                patch.object(services, "_objet_capture_process_item", side_effect=process):
            first = capture.execute_objet_capture_batch(plan_a, reviewer_claim=fixture.REVIEWER)
        self.assertTrue(first["ok"], first)
        self.assertEqual(len(second), 1)
        self.assertTrue(services.require_current_zettel_index(self.root)["ok"])
