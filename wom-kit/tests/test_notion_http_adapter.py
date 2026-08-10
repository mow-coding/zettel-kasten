from __future__ import annotations

from email.message import Message
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib import request as urllib_request
import uuid

from wom_kit.credential_secure_intake import _validate_identity, create_secure_intake_plan
from wom_kit.notion_http_adapter import (
    NOTION_API_VERSION,
    NotionBearerSecret,
    NotionHttpAdapter,
    NotionHttpAdapterError,
)
from wom_kit.notion_page_recovery import REQUEST_SCHEMA, execute_recovery, plan_recovery


SECRET = "secret_N0t10n_PAT_must_never_leak"
PAGE_ID = str(uuid.UUID(int=101))
USER_ID = str(uuid.UUID(int=202))
UNKNOWN_ID = str(uuid.UUID(int=303))
PRIVATE_TITLE = "PRIVATE PAGE TITLE"
PRIVATE_EMAIL = "person@example.com"
PRIVATE_URL = "https://provider.example/private"
PRIVATE_ERROR = "PRIVATE TRANSPORT ERROR DETAIL"


class FakeResponse:
    def __init__(self, status=200, payload=None, *, raw=None, headers=None, read_error=None):
        self.status = status
        if raw is None:
            raw = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        self.raw = raw
        self.headers = dict(headers or {})
        self.read_error = read_error
        self.read_sizes = []
        self.closed = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.read_error is not None:
            raise self.read_error
        return self.raw

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if not self.outcomes:
            raise AssertionError("unexpected transport call")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class CountingPacer:
    def __init__(self) -> None:
        self.calls = 0

    def before_request(self) -> None:
        self.calls += 1


def page_payload(page_id=PAGE_ID, **overrides):
    payload = {
        "object": "page",
        "id": page_id,
        "last_edited_time": "2026-08-10T00:00:00.000Z",
        "in_trash": False,
        "properties": {"title": PRIVATE_TITLE, "email": PRIVATE_EMAIL},
        "url": PRIVATE_URL,
    }
    payload.update(overrides)
    return payload


def user_payload(**overrides):
    payload = {
        "object": "user",
        "id": USER_ID,
        "type": "bot",
        "name": "PRIVATE USER NAME",
        "person": {"email": PRIVATE_EMAIL},
        "bot": {"workspace_name": "PRIVATE WORKSPACE NAME"},
        "avatar_url": PRIVATE_URL,
    }
    payload.update(overrides)
    return payload


class NotionHttpAdapterRequestTests(unittest.TestCase):
    def test_default_transport_refuses_redirect_before_bearer_forwarding(self) -> None:
        adapter = NotionHttpAdapter()
        redirect_handlers = [
            handler
            for handler in adapter._transport.handlers
            if isinstance(handler, urllib_request.HTTPRedirectHandler)
        ]
        self.assertEqual(len(redirect_handlers), 1)
        original = urllib_request.Request(
            f"https://api.notion.com/v1/pages/{PAGE_ID}",
            headers={"Authorization": f"Bearer {SECRET}"},
            method="GET",
        )

        redirected = redirect_handlers[0].redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "https://attacker.example/collect",
        )

        self.assertIsNone(redirected)

    def test_secret_wrapper_and_adapter_repr_are_redacted(self) -> None:
        wrapped = NotionBearerSecret(SECRET)
        adapter = NotionHttpAdapter(transport=FakeTransport())
        rendered = repr(wrapped) + str(wrapped) + repr(adapter)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn(PRIVATE_URL, rendered)
        self.assertEqual(str(wrapped), "[redacted]")
        self.assertIn("transport=redacted", repr(adapter))

        wrapped.close()
        with self.assertRaisesRegex(NotionHttpAdapterError, "notion_secret_closed"):
            wrapped._authorization_value()

        with self.assertRaises(NotionHttpAdapterError) as context:
            NotionBearerSecret("bad\r\nAuthorization: leaked")
        self.assertEqual(str(context.exception), "notion_secret_invalid")
        self.assertNotIn("Authorization", str(context.exception))

    def test_secret_authority_revalidator_is_content_free_and_cleared_on_close(self) -> None:
        unbound = NotionBearerSecret(SECRET)
        with self.assertRaisesRegex(
            NotionHttpAdapterError,
            "notion_authority_revalidator_missing",
        ):
            unbound.revalidate_authority()
        unbound.close()

        wrapped = NotionBearerSecret(SECRET)
        calls: list[str] = []
        wrapped._bind_authority_revalidator(lambda: calls.append("checked"))

        wrapped.revalidate_authority()
        wrapped.revalidate_authority()
        self.assertEqual(calls, ["checked", "checked"])
        self.assertNotIn(SECRET, repr(wrapped))

        wrapped.close()
        with self.assertRaisesRegex(NotionHttpAdapterError, "notion_secret_closed"):
            wrapped.revalidate_authority()
        self.assertEqual(calls, ["checked", "checked"])

    def test_retrieve_page_uses_fixed_uuid_get_and_minimal_response_projection(self) -> None:
        response = FakeResponse(
            payload=page_payload(),
            headers={
                "Retry-After": "7",
                "X-Request-Id": "request-abc-123",
                "Authorization": "Bearer RESPONSE-SECRET",
                "Set-Cookie": "private-cookie",
                "X-Private": PRIVATE_EMAIL,
            },
        )
        transport = FakeTransport(response)
        adapter = NotionHttpAdapter(
            transport=transport,
            timeout_seconds=12.5,
            max_response_bytes=2048,
        )

        result = adapter.retrieve_page(PAGE_ID.replace("-", ""), SECRET, api_version=NOTION_API_VERSION)

        self.assertEqual(result.status, 200)
        self.assertEqual(
            result.payload,
            {
                "object": "page",
                "id": PAGE_ID,
                "last_edited_time": "2026-08-10T00:00:00.000Z",
                "in_trash": False,
            },
        )
        self.assertEqual(result.headers, {"Retry-After": "7", "request-id": "request-abc-123"})
        self.assertEqual(len(transport.calls), 1)
        request, timeout = transport.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, f"https://api.notion.com/v1/pages/{PAGE_ID}")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {SECRET}")
        self.assertEqual(request.get_header("Notion-version"), NOTION_API_VERSION)
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(timeout, 12.5)
        self.assertEqual(response.read_sizes, [2049])
        self.assertTrue(response.closed)

        rendered = json.dumps(
            {"status": result.status, "payload": result.payload, "headers": result.headers},
            ensure_ascii=False,
        )
        for private in (SECRET, PRIVATE_TITLE, PRIVATE_EMAIL, PRIVATE_URL, "private-cookie"):
            self.assertNotIn(private, rendered)

    def test_retrieve_markdown_uses_official_path_and_filters_unrelated_fields(self) -> None:
        markdown = "# Exact markdown\r\n\r\nbody\n"
        response = FakeResponse(
            payload={
                "object": "page_markdown",
                "id": PAGE_ID,
                "markdown": markdown,
                "truncated": True,
                "unknown_block_ids": [UNKNOWN_ID.replace("-", ""), UNKNOWN_ID],
                "next_cursor": "RAW-CURSOR-MUST-NOT-LEAK",
                "url": PRIVATE_URL,
            }
        )
        transport = FakeTransport(response)
        adapter = NotionHttpAdapter(transport=transport)

        result = adapter.retrieve_page_as_markdown(
            PAGE_ID,
            NotionBearerSecret(SECRET),
            api_version=NOTION_API_VERSION,
        )

        self.assertEqual(result.status, 200)
        self.assertEqual(
            result.payload,
            {
                "object": "page_markdown",
                "id": PAGE_ID,
                "markdown": markdown,
                "truncated": True,
                "unknown_block_ids": [UNKNOWN_ID],
            },
        )
        request, _ = transport.calls[0]
        self.assertEqual(
            request.full_url,
            f"https://api.notion.com/v1/pages/{PAGE_ID}/markdown",
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn("RAW-CURSOR-MUST-NOT-LEAK", json.dumps(result.headers))
        self.assertNotIn(PRIVATE_URL, json.dumps(result.headers))

    def test_invalid_uuid_version_and_secret_never_reach_transport(self) -> None:
        transport = FakeTransport()
        adapter = NotionHttpAdapter(transport=transport)

        invalid_id = adapter.retrieve_page(
            "../../users/me?token=" + SECRET,
            SECRET,
            api_version=NOTION_API_VERSION,
        )
        invalid_version = adapter.retrieve_page(
            PAGE_ID,
            SECRET,
            api_version="2025-09-03",
        )
        invalid_secret = adapter.retrieve_page(
            PAGE_ID,
            "bad secret value",
            api_version=NOTION_API_VERSION,
        )

        self.assertEqual(invalid_id.payload, {"reason_code": "notion_page_id_invalid"})
        self.assertEqual(invalid_version.payload, {"reason_code": "notion_api_version_invalid"})
        self.assertEqual(invalid_secret.payload, {"reason_code": "notion_secret_invalid"})
        self.assertEqual(transport.calls, [])
        rendered = json.dumps([invalid_id.payload, invalid_version.payload, invalid_secret.payload])
        self.assertNotIn(SECRET, rendered)

    def test_only_exact_200_and_valid_timestamp_are_accepted(self) -> None:
        created = NotionHttpAdapter(
            transport=FakeTransport(FakeResponse(status=201, payload=page_payload()))
        ).retrieve_page(PAGE_ID, SECRET, api_version=NOTION_API_VERSION)
        malformed_time = NotionHttpAdapter(
            transport=FakeTransport(
                FakeResponse(payload=page_payload(last_edited_time="not-a-timestamp"))
            )
        ).retrieve_page(PAGE_ID, SECRET, api_version=NOTION_API_VERSION)

        self.assertEqual(created.status, 201)
        self.assertEqual(created.payload, {"reason_code": "notion_http_error"})
        self.assertEqual(malformed_time.status, 502)
        self.assertEqual(
            malformed_time.payload,
            {"reason_code": "notion_response_malformed"},
        )

    def test_http_401_403_404_are_content_free_and_error_body_is_not_read(self) -> None:
        expected = {
            401: "notion_unauthorized",
            403: "notion_forbidden",
            404: "notion_not_found_or_not_shared",
        }
        for status, reason in expected.items():
            with self.subTest(status=status):
                response = FakeResponse(
                    status=status,
                    raw=(PRIVATE_ERROR + PRIVATE_EMAIL + PRIVATE_URL + SECRET).encode("utf-8"),
                    headers={"X-Request-Id": f"request-{status}", "X-Private": PRIVATE_ERROR},
                )
                transport = FakeTransport(response)
                result = NotionHttpAdapter(transport=transport).retrieve_page(
                    PAGE_ID,
                    SECRET,
                    api_version=NOTION_API_VERSION,
                )
                self.assertEqual(result.status, status)
                self.assertEqual(result.payload, {"reason_code": reason})
                self.assertEqual(result.headers, {"request-id": f"request-{status}"})
                self.assertEqual(response.read_sizes, [])
                self.assertTrue(response.closed)
                rendered = repr(result)
                for private in (PRIVATE_ERROR, PRIVATE_EMAIL, PRIVATE_URL, SECRET):
                    self.assertNotIn(private, rendered)

    def test_stdlib_http_error_is_sanitized_without_exposing_url_or_body(self) -> None:
        headers = Message()
        headers["X-Request-Id"] = "request-http-error"
        http_error = HTTPError(
            PRIVATE_URL + "?token=" + SECRET,
            401,
            PRIVATE_ERROR,
            headers,
            io.BytesIO((PRIVATE_ERROR + SECRET).encode("utf-8")),
        )
        result = NotionHttpAdapter(transport=FakeTransport(http_error)).retrieve_page(
            PAGE_ID,
            SECRET,
            api_version=NOTION_API_VERSION,
        )
        self.assertEqual(result.status, 401)
        self.assertEqual(result.payload, {"reason_code": "notion_unauthorized"})
        rendered = repr(result)
        for private in (PRIVATE_URL, PRIVATE_ERROR, SECRET):
            self.assertNotIn(private, rendered)

    def test_adapter_plugs_into_completed_recovery_protocol_without_network(self) -> None:
        markdown = "# recovered through injected transport\n"
        transport = FakeTransport(
            FakeResponse(payload=page_payload()),
            FakeResponse(
                payload={
                    "object": "page_markdown",
                    "id": PAGE_ID,
                    "markdown": markdown,
                    "truncated": False,
                    "unknown_block_ids": [],
                }
            ),
            FakeResponse(payload=page_payload()),
        )
        adapter = NotionHttpAdapter(transport=transport)
        manifest = {
            "schema": REQUEST_SCHEMA,
            "batch_id": "adapter-contract",
            "archive_id": "private-archive",
            "expected_item_count": 1,
            "groups": [
                {
                    "group_id": "group-1",
                    "expected_count": 1,
                    "scope_binding": {
                        "credential_id": "cred_notion_adapter_00000001",
                        "workspace_fingerprint": "sha256:" + ("1" * 64),
                        "scope_receipt_sha256": "sha256:" + ("2" * 64),
                        "revision": "r1",
                        "persisted": True,
                        "workspace_evidence_verified": True,
                    },
                }
            ],
            "items": [{"item_id": "item-1", "group_id": "group-1", "page_id": PAGE_ID}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "archive.yml").write_text(
                "archive_id: private-archive\n", encoding="utf-8"
            )
            plan = plan_recovery(root, manifest, max_items=1)
            result = execute_recovery(
                root,
                manifest,
                expected_plan_sha256=plan["plan_sha256"],
                reviewed_by="reviewer-1",
                max_items=1,
                provider=adapter,
                credential_broker=lambda _scope: SECRET,
                request_pacer=lambda: None,
                sleep=lambda _delay: None,
                jitter=lambda: 0.0,
                clock=lambda: datetime(2026, 8, 10, tzinfo=timezone.utc),
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["counts"]["outcomes"]["recovered"], 1)
        self.assertEqual(
            [call[0].full_url for call in transport.calls],
            [
                f"https://api.notion.com/v1/pages/{PAGE_ID}",
                f"https://api.notion.com/v1/pages/{PAGE_ID}/markdown",
                f"https://api.notion.com/v1/pages/{PAGE_ID}",
            ],
        )
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(markdown, json.dumps(result))

    def test_markdown_object_id_and_official_unknown_limit_fail_closed(self) -> None:
        malformed_payloads = [
            {
                "object": "page",
                "id": PAGE_ID,
                "markdown": "body",
                "truncated": False,
                "unknown_block_ids": [],
            },
            {
                "object": "page_markdown",
                "id": UNKNOWN_ID,
                "markdown": "body",
                "truncated": False,
                "unknown_block_ids": [],
            },
            {
                "object": "page_markdown",
                "id": PAGE_ID,
                "markdown": "body",
                "truncated": True,
                "unknown_block_ids": [UNKNOWN_ID] * 101,
            },
        ]
        for payload in malformed_payloads:
            with self.subTest(payload_kind=payload["object"]):
                adapter = NotionHttpAdapter(
                    transport=FakeTransport(FakeResponse(payload=payload))
                )
                result = adapter.retrieve_page_as_markdown(
                    PAGE_ID,
                    NotionBearerSecret(SECRET),
                    api_version=NOTION_API_VERSION,
                )
                self.assertEqual(result.status, 502)
                self.assertEqual(
                    result.payload,
                    {"reason_code": "notion_response_malformed"},
                )

    def test_page_projection_requires_official_object_identity(self) -> None:
        adapter = NotionHttpAdapter(
            transport=FakeTransport(
                FakeResponse(payload=page_payload(object="database"))
            )
        )
        result = adapter.retrieve_page(
            PAGE_ID,
            NotionBearerSecret(SECRET),
            api_version=NOTION_API_VERSION,
        )
        self.assertEqual(result.status, 502)
        self.assertEqual(
            result.payload,
            {"reason_code": "notion_response_malformed"},
        )


class NotionHttpAdapterBoundaryTests(unittest.TestCase):
    def test_malformed_duplicate_and_non_object_json_have_fixed_reason(self) -> None:
        raw_cases = [
            b"not json " + PRIVATE_ERROR.encode("utf-8"),
            b'{"id":"one","id":"two"}',
            b"[]",
            b"\xff\xfe",
        ]
        for raw in raw_cases:
            with self.subTest(raw=raw[:8]):
                response = FakeResponse(raw=raw)
                result = NotionHttpAdapter(transport=FakeTransport(response)).retrieve_page(
                    PAGE_ID,
                    SECRET,
                    api_version=NOTION_API_VERSION,
                )
                self.assertEqual(result.status, 502)
                self.assertEqual(result.payload, {"reason_code": "notion_response_malformed"})
                self.assertNotIn(PRIVATE_ERROR, repr(result))

        structurally_bad = FakeResponse(payload=page_payload(id="not-a-uuid"))
        result = NotionHttpAdapter(transport=FakeTransport(structurally_bad)).retrieve_page(
            PAGE_ID,
            SECRET,
            api_version=NOTION_API_VERSION,
        )
        self.assertEqual(result.status, 502)
        self.assertEqual(result.payload, {"reason_code": "notion_response_malformed"})

    def test_declared_and_actual_oversize_responses_are_bounded(self) -> None:
        declared = FakeResponse(
            payload=page_payload(),
            headers={"Content-Length": "2049"},
        )
        actual = FakeResponse(raw=b"{" + (b"x" * 2048) + b"}")
        for response in (declared, actual):
            with self.subTest(declared=response is declared):
                result = NotionHttpAdapter(
                    transport=FakeTransport(response),
                    max_response_bytes=2048,
                ).retrieve_page(PAGE_ID, SECRET, api_version=NOTION_API_VERSION)
                self.assertEqual(result.status, 413)
                self.assertEqual(result.payload, {"reason_code": "notion_response_oversize"})
                self.assertTrue(response.closed)
        self.assertEqual(declared.read_sizes, [])
        self.assertEqual(actual.read_sizes, [2049])

    def test_transport_and_read_failures_return_fixed_codes_without_error_text(self) -> None:
        transport_failure = NotionHttpAdapter(
            transport=FakeTransport(RuntimeError(PRIVATE_ERROR + SECRET + PRIVATE_URL))
        ).retrieve_page(PAGE_ID, SECRET, api_version=NOTION_API_VERSION)
        read_response = FakeResponse(read_error=RuntimeError(PRIVATE_ERROR + SECRET))
        read_failure = NotionHttpAdapter(
            transport=FakeTransport(read_response)
        ).retrieve_page(PAGE_ID, SECRET, api_version=NOTION_API_VERSION)

        for result in (transport_failure, read_failure):
            self.assertEqual(result.status, 599)
            self.assertEqual(result.payload, {"reason_code": "notion_transport_error"})
            rendered = repr(result)
            for private in (PRIVATE_ERROR, SECRET, PRIVATE_URL):
                self.assertNotIn(private, rendered)
        self.assertTrue(read_response.closed)

    def test_timeout_and_limit_configuration_errors_are_fixed_and_content_free(self) -> None:
        cases = [
            ({"timeout_seconds": 0}, "notion_timeout_invalid"),
            ({"timeout_seconds": 61}, "notion_timeout_invalid"),
            ({"max_response_bytes": 100}, "notion_response_limit_invalid"),
            ({"max_response_bytes": 17 * 1024 * 1024}, "notion_response_limit_invalid"),
            ({"max_attempts": 0}, "notion_retry_attempts_invalid"),
            ({"max_attempts": 6}, "notion_retry_attempts_invalid"),
            ({"max_retry_delay_seconds": 61}, "notion_retry_delay_invalid"),
            ({"request_pacer": object()}, "notion_request_pacer_invalid"),
        ]
        for kwargs, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(NotionHttpAdapterError) as context:
                    NotionHttpAdapter(transport=FakeTransport(), **kwargs)
                self.assertEqual(str(context.exception), reason)
                self.assertNotIn(repr(kwargs), str(context.exception))

    def test_only_safe_retry_after_and_request_id_headers_are_returned(self) -> None:
        response = FakeResponse(
            payload=page_payload(),
            headers={
                "Retry-After": "7\r\nAuthorization: " + SECRET,
                "Request-Id": PRIVATE_EMAIL,
                "X-Request-Id": "safe-request-1",
                "Authorization": "Bearer " + SECRET,
            },
        )
        result = NotionHttpAdapter(transport=FakeTransport(response)).retrieve_page(
            PAGE_ID,
            SECRET,
            api_version=NOTION_API_VERSION,
        )
        self.assertEqual(result.headers, {"request-id": "safe-request-1"})
        self.assertNotIn(SECRET, repr(result))


class NotionHttpAdapterIdentityTests(unittest.TestCase):
    def test_verify_identity_requires_users_me_and_reviewed_anchor_success(self) -> None:
        user_response = FakeResponse(payload=user_payload())
        anchor_response = FakeResponse(payload=page_payload())
        transport = FakeTransport(user_response, anchor_response)
        adapter = NotionHttpAdapter(transport=transport)

        evidence = adapter.verify_identity(SECRET, PAGE_ID)

        self.assertEqual(evidence["provider"], "notion")
        self.assertEqual(
            evidence["reason_code"], "notion_identity_and_workspace_anchor_verified"
        )
        self.assertTrue(evidence["identity_verified"])
        self.assertTrue(evidence["workspace_anchor_verified"])
        self.assertRegex(evidence["account_fingerprint"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(evidence["workspace_fingerprint"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(
            evidence["account_fingerprint"], evidence["workspace_fingerprint"]
        )
        self.assertTrue(evidence["capabilities"]["retrieve_page_as_markdown"])
        self.assertEqual(evidence["api_version"], NOTION_API_VERSION)
        self.assertEqual(
            [call[0].full_url for call in transport.calls],
            [
                "https://api.notion.com/v1/users/me",
                f"https://api.notion.com/v1/pages/{PAGE_ID}",
            ],
        )
        for request, _ in transport.calls:
            self.assertEqual(request.get_header("Authorization"), f"Bearer {SECRET}")

    def test_identity_requests_share_pacer_and_retry_after_policy(self) -> None:
        pacer = CountingPacer()
        sleeps: list[float] = []
        transport = FakeTransport(
            FakeResponse(status=429, payload={}, headers={"Retry-After": "2"}),
            FakeResponse(payload=user_payload()),
            FakeResponse(payload=page_payload()),
        )
        adapter = NotionHttpAdapter(
            transport=transport,
            request_pacer=pacer,
            max_attempts=3,
            max_retry_delay_seconds=10,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
        )

        evidence = adapter.verify_identity(SECRET, PAGE_ID)

        self.assertTrue(evidence["identity_verified"])
        self.assertTrue(evidence["workspace_anchor_verified"])
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(pacer.calls, 3)
        self.assertEqual(sleeps, [2.0])
        rendered = json.dumps(evidence, ensure_ascii=False)
        self.assertNotIn(SECRET, rendered)
        self.assertNotIn(PAGE_ID, rendered)

    def test_retry_after_above_approved_ceiling_fails_without_short_sleep(self) -> None:
        pacer = CountingPacer()
        sleeps: list[float] = []
        transport = FakeTransport(
            FakeResponse(status=429, payload={}, headers={"Retry-After": "60"}),
        )
        adapter = NotionHttpAdapter(
            transport=transport,
            request_pacer=pacer,
            max_attempts=3,
            max_retry_delay_seconds=5,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
        )

        evidence = adapter.verify_identity(SECRET, PAGE_ID)

        self.assertFalse(evidence["identity_verified"])
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(pacer.calls, 1)
        self.assertEqual(sleeps, [])

        rendered = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        for private in (
            SECRET,
            USER_ID,
            PAGE_ID,
            "PRIVATE USER NAME",
            "PRIVATE WORKSPACE NAME",
            PRIVATE_EMAIL,
            PRIVATE_TITLE,
            PRIVATE_URL,
        ):
            self.assertNotIn(private, rendered)

    def test_same_reviewed_anchor_groups_different_accounts_into_one_workspace_scope(self) -> None:
        other_user = str(uuid.UUID(int=777))
        first = NotionHttpAdapter(
            transport=FakeTransport(
                FakeResponse(payload=user_payload(id=USER_ID)),
                FakeResponse(payload=page_payload()),
            )
        ).verify_identity(NotionBearerSecret(SECRET), PAGE_ID)
        second = NotionHttpAdapter(
            transport=FakeTransport(
                FakeResponse(payload=user_payload(id=other_user)),
                FakeResponse(payload=page_payload()),
            )
        ).verify_identity(NotionBearerSecret(SECRET + "-second"), PAGE_ID)

        self.assertNotEqual(
            first["account_fingerprint"], second["account_fingerprint"]
        )
        self.assertEqual(
            first["workspace_fingerprint"], second["workspace_fingerprint"]
        )

    def test_users_me_success_alone_never_claims_workspace_identity(self) -> None:
        anchor_error = FakeResponse(
            status=404,
            raw=(PRIVATE_ERROR + PRIVATE_TITLE + SECRET).encode("utf-8"),
        )
        transport = FakeTransport(FakeResponse(payload=user_payload()), anchor_error)
        evidence = NotionHttpAdapter(transport=transport).verify_identity(SECRET, PAGE_ID)

        self.assertTrue(evidence["identity_verified"])
        self.assertFalse(evidence["workspace_anchor_verified"])
        self.assertIsNotNone(evidence["account_fingerprint"])
        self.assertIsNone(evidence["workspace_fingerprint"])
        self.assertEqual(
            evidence["reason_code"], "notion_workspace_anchor_not_found_or_not_shared"
        )
        self.assertEqual(anchor_error.read_sizes, [])
        rendered = json.dumps(evidence)
        for private in (PRIVATE_ERROR, PRIVATE_TITLE, SECRET, PAGE_ID, USER_ID):
            self.assertNotIn(private, rendered)

    def test_identity_401_403_404_have_context_specific_fixed_reasons(self) -> None:
        expected = {
            401: "notion_identity_unauthorized",
            403: "notion_identity_forbidden",
            404: "notion_identity_not_found",
        }
        for status, reason in expected.items():
            with self.subTest(status=status):
                response = FakeResponse(
                    status=status,
                    raw=(PRIVATE_ERROR + SECRET + PRIVATE_EMAIL).encode("utf-8"),
                )
                transport = FakeTransport(response)
                evidence = NotionHttpAdapter(transport=transport).verify_identity(
                    SECRET, PAGE_ID
                )
                self.assertFalse(evidence["identity_verified"])
                self.assertFalse(evidence["workspace_anchor_verified"])
                self.assertEqual(evidence["reason_code"], reason)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(response.read_sizes, [])
                self.assertNotIn(PRIVATE_ERROR, json.dumps(evidence))

    def test_malformed_identity_or_anchor_never_produces_verified_workspace(self) -> None:
        malformed_user = FakeTransport(FakeResponse(payload=user_payload(id="not-a-uuid")))
        user_evidence = NotionHttpAdapter(transport=malformed_user).verify_identity(
            SECRET, PAGE_ID
        )
        self.assertEqual(user_evidence["reason_code"], "notion_identity_response_malformed")
        self.assertFalse(user_evidence["identity_verified"])

        wrong_anchor = str(uuid.UUID(int=999))
        transport = FakeTransport(
            FakeResponse(payload=user_payload()),
            FakeResponse(payload=page_payload(page_id=wrong_anchor)),
        )
        anchor_evidence = NotionHttpAdapter(transport=transport).verify_identity(
            SECRET, PAGE_ID
        )
        self.assertTrue(anchor_evidence["identity_verified"])
        self.assertFalse(anchor_evidence["workspace_anchor_verified"])
        self.assertEqual(
            anchor_evidence["reason_code"], "notion_workspace_anchor_response_malformed"
        )

    def test_identity_verifier_callback_is_redacted_and_secure_intake_friendly(self) -> None:
        transport = FakeTransport(
            FakeResponse(payload=user_payload()),
            FakeResponse(payload=page_payload()),
        )
        verifier = NotionHttpAdapter(transport=transport).identity_verifier(PAGE_ID)
        self.assertNotIn(PAGE_ID, repr(verifier))
        evidence = verifier(NotionBearerSecret(SECRET))
        self.assertTrue(evidence["workspace_anchor_verified"])

        invalid = NotionHttpAdapter(transport=FakeTransport()).identity_verifier(
            PRIVATE_URL + "/" + SECRET
        )
        invalid_evidence = invalid(SECRET)
        self.assertEqual(
            invalid_evidence["reason_code"], "notion_workspace_anchor_id_invalid"
        )
        self.assertNotIn(PRIVATE_URL, repr(invalid) + json.dumps(invalid_evidence))
        self.assertNotIn(SECRET, repr(invalid) + json.dumps(invalid_evidence))

    def test_secure_intake_protocol_bridge_uses_safe_fingerprints_not_raw_ids(self) -> None:
        transport = FakeTransport(
            FakeResponse(payload=user_payload()),
            FakeResponse(payload=page_payload()),
        )
        verifier = NotionHttpAdapter(transport=transport).secure_intake_verifier()
        secret_buffer = bytearray(SECRET.encode("utf-8"))
        identity = verifier.verify_identity(
            memoryview(secret_buffer),
            provider="notion",
            reviewed_anchor_uuid=PAGE_ID,
        )
        self.assertRegex(identity.account_subject, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(identity.workspace_identity, r"^sha256:[0-9a-f]{64}$")
        self.assertIn("read_content", identity.capabilities)
        self.assertIn("retrieve_user_identity", identity.capabilities)
        rendered = repr(verifier) + repr(identity)
        for private in (SECRET, USER_ID, PAGE_ID, PRIVATE_EMAIL, PRIVATE_URL):
            self.assertNotIn(private, rendered)

        plan = create_secure_intake_plan(
            provider="notion",
            account_label="personal",
            workspace_label="reviewed",
            purpose="source_recovery",
            reviewed_anchor_uuid=PAGE_ID,
            owner_binding="windows-user:test",
            requested_capabilities=("read_content", "retrieve_user_identity"),
            request_id_factory=lambda: "intake_1234567890abcdef",
        )
        failure, capabilities = _validate_identity(identity, plan)
        self.assertIsNone(failure)
        self.assertIn("read_content", capabilities)

        no_calls = FakeTransport()
        wrong_provider = NotionHttpAdapter(transport=no_calls).secure_intake_verifier()
        with self.assertRaises(NotionHttpAdapterError) as context:
            wrong_provider.verify_identity(
                memoryview(secret_buffer),
                provider="other",
                reviewed_anchor_uuid=PAGE_ID,
            )
        self.assertEqual(str(context.exception), "notion_provider_mismatch")
        self.assertEqual(no_calls.calls, [])


if __name__ == "__main__":
    unittest.main()
