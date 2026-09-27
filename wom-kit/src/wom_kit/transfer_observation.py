"""Content-free measurements at the provider's actual HTTP dispatch boundary."""
import threading
import time


class TransferObservation:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = {}
        self.seconds = 0.0
        self.upload_bytes = 0
        self.download_bytes = 0
        self.incomplete = 0

    def call(self, method, invoke, *, payload_bytes=0):
        start = time.monotonic()
        result = None
        try:
            with self.lock:
                self.requests[method] = self.requests.get(method, 0) + 1
            result = invoke()
            return result
        finally:
            with self.lock:
                self.seconds += time.monotonic() - start
                status = result.get("status") if isinstance(result, dict) else None
                # Observation must not change or mask the provider's own
                # handling of a malformed response.
                successful = type(status) is int and 200 <= status < 300
                if not successful or result.get("transport_error"):
                    self.incomplete += 1
                elif method in {"PUT", "POST"}:
                    self.upload_bytes += payload_bytes
                elif method == "GET":
                    body = result.get("body")
                    size = result.get("body_size")
                    if result.get("body_complete") is True and type(size) is int and size >= 0:
                        self.download_bytes += size
                    elif isinstance(body, bytes) and result.get("body_complete") is not False:
                        self.download_bytes += len(body)
                    else:
                        self.incomplete += 1

    def snapshot(self):
        with self.lock:
            return {"request_counts": dict(self.requests), "request_count": sum(self.requests.values()),
                "provider_request_seconds": round(self.seconds, 6),
                "acknowledged_upload_payload_bytes": self.upload_bytes,
                "observed_complete_download_body_bytes": self.download_bytes,
                "failed_or_unmeasured_responses": self.incomplete,
                "wire_bytes_including_headers_tls_and_failed_partial_transfers": None,
                "scope": "current_transport_dispatches_including_retries", "private_values_echoed": False}
