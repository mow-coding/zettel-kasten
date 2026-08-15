from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pickle
import threading
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from wom_kit.credential_capability import (
    CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES,
    CredentialCapability,
    CredentialCapabilityError,
    CredentialCapabilityScope,
)


NOW = datetime(2026, 8, 15, 3, 0, 0, tzinfo=timezone.utc)
REQUEST_SHA256 = "sha256:" + "1" * 64
PLAN_SHA256 = "sha256:" + "2" * 64


def scope(number: int) -> CredentialCapabilityScope:
    return CredentialCapabilityScope(
        credential_id=f"cred_capability_scope_{number:02d}",
        workspace_fingerprint="sha256:" + f"{number:064x}",
        scope_receipt_sha256="sha256:" + f"{number + 10:064x}",
        revision=f"rev-{number}",
    )


def issue_capability(
    *,
    scopes: tuple[CredentialCapabilityScope, ...] | None = None,
    max_provider_requests: int = 4,
    ttl_seconds: int = 900,
) -> CredentialCapability:
    with patch(
        "wom_kit.credential_capability.secrets.token_hex",
        return_value="ab" * 16,
    ):
        return CredentialCapability.issue(
            request_sha256=REQUEST_SHA256,
            plan_sha256=PLAN_SHA256,
            scopes=scopes or (scope(1),),
            reviewed_by="operator@example.test",
            max_provider_requests=max_provider_requests,
            issued_at=NOW,
            ttl_seconds=ttl_seconds,
        )


class CredentialCapabilityTests(unittest.TestCase):
    def test_issue_is_frozen_sorted_strict_and_redacted(self) -> None:
        capability = issue_capability(scopes=(scope(2), scope(1)))

        self.assertEqual(capability.capability_id, "cap_" + "ab" * 16)
        self.assertEqual(capability.ttl_seconds, 900)
        self.assertEqual(capability.max_uses, 1)
        self.assertEqual(capability.scopes, (scope(1), scope(2)))
        self.assertEqual(
            capability.endpoint_classes, CREDENTIAL_CAPABILITY_ENDPOINT_CLASSES
        )
        with self.assertRaises(FrozenInstanceError):
            capability.max_uses = 2  # type: ignore[misc]

        representation = repr(capability)
        self.assertIn("bindings=redacted", representation)
        self.assertNotIn(capability.capability_id, representation)
        self.assertNotIn(capability.request_sha256, representation)
        self.assertNotIn(capability.reviewed_by, representation)
        self.assertEqual(repr(capability.scopes[0]), "<CredentialCapabilityScope redacted>")

    def test_round_trip_canonical_document_and_digest(self) -> None:
        capability = issue_capability(scopes=(scope(2), scope(1)))
        document = capability.canonical_document()
        reparsed = CredentialCapability.from_document(copy.deepcopy(document))

        self.assertEqual(reparsed, capability)
        self.assertEqual(reparsed.canonical_document(), document)
        self.assertEqual(reparsed.digest(), capability.digest_sha256)
        self.assertRegex(capability.digest(), r"^sha256:[0-9a-f]{64}$")

        reordered = {key: document[key] for key in reversed(tuple(document))}
        self.assertEqual(
            CredentialCapability.from_document(reordered).digest(), capability.digest()
        )
        self.assertEqual(pickle.loads(pickle.dumps(capability)), capability)

    def test_schema_accepts_canonical_document(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "credential-capability-v0.1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(
            Draft202012Validator(schema).iter_errors(
                issue_capability().canonical_document()
            )
        )
        self.assertEqual(errors, [])

    def test_missing_and_extra_fields_are_rejected(self) -> None:
        document = issue_capability().canonical_document()
        missing = copy.deepcopy(document)
        missing.pop("plan_sha256")
        extra = copy.deepcopy(document)
        extra["provider_url"] = "https://example.invalid"

        for candidate in (missing, extra):
            with self.subTest(keys=sorted(candidate)):
                with self.assertRaisesRegex(
                    CredentialCapabilityError,
                    "^credential_capability_document_invalid$",
                ):
                    CredentialCapability.from_document(candidate)

    def test_nonexact_scalar_and_collection_types_are_rejected(self) -> None:
        document = issue_capability().canonical_document()
        mutations = {
            "ttl_bool": ("ttl_seconds", True),
            "uses_bool": ("max_uses", True),
            "budget_bool": ("max_provider_requests", True),
            "budget_float": ("max_provider_requests", 4.0),
            "methods_tuple": ("allowed_methods", ("GET",)),
            "scopes_tuple": ("scopes", tuple(document["scopes"])),
        }
        for name, (key, value) in mutations.items():
            candidate = copy.deepcopy(document)
            candidate[key] = value
            with self.subTest(name=name):
                with self.assertRaises(CredentialCapabilityError):
                    CredentialCapability.from_document(candidate)

        capability = issue_capability()
        direct = capability.canonical_document()
        with self.assertRaisesRegex(
            CredentialCapabilityError, "^credential_capability_scopes_invalid$"
        ):
            CredentialCapability(
                schema=direct["schema"],
                capability_id=direct["capability_id"],
                provider=direct["provider"],
                operation=direct["operation"],
                consumer=direct["consumer"],
                approval_decision=direct["approval_decision"],
                reviewed_by=direct["reviewed_by"],
                allowed_methods=tuple(direct["allowed_methods"]),
                endpoint_classes=tuple(direct["endpoint_classes"]),
                required_registered_capabilities=tuple(
                    direct["required_registered_capabilities"]
                ),
                request_sha256=direct["request_sha256"],
                plan_sha256=direct["plan_sha256"],
                scopes=list(capability.scopes),  # type: ignore[arg-type]
                issued_at=direct["issued_at"],
                expires_at=direct["expires_at"],
                ttl_seconds=direct["ttl_seconds"],
                max_uses=direct["max_uses"],
                max_provider_requests=direct["max_provider_requests"],
            )

    def test_fixed_authority_fields_are_exact(self) -> None:
        document = issue_capability().canonical_document()
        mutations = {
            "provider": "other",
            "operation": "notion_page_recovery_write",
            "consumer": "other-consumer",
            "approval_decision": "approve_forever",
            "allowed_methods": ["POST"],
            "endpoint_classes": ["retrieve_page"],
            "required_registered_capabilities": ["read_content"],
            "max_uses": 2,
        }
        for key, value in mutations.items():
            candidate = copy.deepcopy(document)
            candidate[key] = value
            with self.subTest(key=key):
                with self.assertRaises(CredentialCapabilityError):
                    CredentialCapability.from_document(candidate)

        for invalid_budget in (0, 5_000_001):
            with self.subTest(max_provider_requests=invalid_budget):
                with self.assertRaisesRegex(
                    CredentialCapabilityError,
                    "^credential_capability_request_budget_invalid$",
                ):
                    issue_capability(max_provider_requests=invalid_budget)

    def test_scope_documents_must_be_exact_unique_and_sorted(self) -> None:
        capability = issue_capability(scopes=(scope(1), scope(2)))
        document = capability.canonical_document()

        extra = copy.deepcopy(document)
        extra["scopes"][0]["group_id"] = "group-1"
        duplicate = copy.deepcopy(document)
        duplicate["scopes"] = [duplicate["scopes"][0], duplicate["scopes"][0]]
        unsorted = copy.deepcopy(document)
        unsorted["scopes"].reverse()
        for candidate in (extra, duplicate, unsorted):
            with self.assertRaises(CredentialCapabilityError):
                CredentialCapability.from_document(candidate)

    def test_ttl_and_exact_utc_window_are_enforced(self) -> None:
        for invalid_ttl in (29, 3601, True, 900.0):
            with self.subTest(ttl=invalid_ttl):
                with self.assertRaises(CredentialCapabilityError):
                    issue_capability(ttl_seconds=invalid_ttl)  # type: ignore[arg-type]

        document = issue_capability().canonical_document()
        invalid_documents = []
        offset = copy.deepcopy(document)
        offset["issued_at"] = "2026-08-15T12:00:00+09:00"
        invalid_documents.append(offset)
        fractional = copy.deepcopy(document)
        fractional["issued_at"] = "2026-08-15T03:00:00.000000Z"
        invalid_documents.append(fractional)
        wrong_window = copy.deepcopy(document)
        wrong_window["expires_at"] = "2026-08-15T03:14:59Z"
        invalid_documents.append(wrong_window)
        for candidate in invalid_documents:
            with self.assertRaises(CredentialCapabilityError):
                CredentialCapability.from_document(candidate)

        with self.assertRaisesRegex(
            CredentialCapabilityError, "^credential_capability_issued_at_invalid$"
        ):
            CredentialCapability.issue(
                request_sha256=REQUEST_SHA256,
                plan_sha256=PLAN_SHA256,
                scopes=(scope(1),),
                reviewed_by="operator",
                max_provider_requests=1,
                issued_at=datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=9))),
            )

    def test_recovery_binding_checks_time_request_plan_reviewer_and_scopes(self) -> None:
        capability = issue_capability(scopes=(scope(1), scope(2)))
        capability.validate_recovery_binding(
            request_sha256=REQUEST_SHA256,
            plan_sha256=PLAN_SHA256,
            scopes=(scope(2), scope(1)),
            reviewed_by="operator@example.test",
            now_utc=NOW,
        )

        cases = (
            {"request_sha256": "sha256:" + "8" * 64},
            {"plan_sha256": "sha256:" + "9" * 64},
            {"reviewed_by": "other-reviewer"},
            {"scopes": (scope(1), scope(3))},
            {"now_utc": NOW + timedelta(seconds=900)},
        )
        base = {
            "request_sha256": REQUEST_SHA256,
            "plan_sha256": PLAN_SHA256,
            "scopes": (scope(1), scope(2)),
            "reviewed_by": "operator@example.test",
            "now_utc": NOW,
        }
        for mutation in cases:
            arguments = {**base, **mutation}
            with self.subTest(mutation=mutation):
                with self.assertRaises(CredentialCapabilityError):
                    capability.validate_recovery_binding(**arguments)

    def test_lease_checks_scope_endpoint_expiry_and_request_budget(self) -> None:
        capability = issue_capability(max_provider_requests=2)
        lease = capability.new_lease(claimed_at=NOW)

        with self.assertRaisesRegex(
            CredentialCapabilityError,
            "^credential_capability_endpoint_not_allowed$",
        ):
            lease.authorize_request("create_page", scope=scope(1))
        with self.assertRaisesRegex(
            CredentialCapabilityError,
            "^credential_capability_scope_not_allowed$",
        ):
            lease.authorize_request("retrieve_page", scope=scope(2))
        self.assertEqual(lease.provider_requests_authorized, 0)

        self.assertEqual(
            lease.authorize_request("retrieve_page", scope=scope(1)),
            1,
        )
        self.assertEqual(
            lease.authorize_request("retrieve_page_as_markdown", scope=scope(1)),
            2,
        )
        self.assertEqual(lease.provider_requests_remaining, 0)
        with self.assertRaisesRegex(
            CredentialCapabilityError,
            "^credential_capability_request_budget_exhausted$",
        ):
            lease.authorize_request("retrieve_page", scope=scope(1))

        expiring = issue_capability(max_provider_requests=1, ttl_seconds=30)
        claimed_lease = expiring.new_lease(claimed_at=NOW)
        # Expiry is the claim deadline, not a mid-invocation kill switch.
        self.assertEqual(
            claimed_lease.authorize_request("retrieve_page", scope=scope(1)), 1
        )
        with self.assertRaisesRegex(
            CredentialCapabilityError, "^credential_capability_expired$"
        ):
            expiring.new_lease(claimed_at=NOW + timedelta(seconds=30))

    def test_request_budget_is_atomic_under_concurrency(self) -> None:
        capability = issue_capability(max_provider_requests=8)
        lease = capability.new_lease(claimed_at=NOW)
        barrier = threading.Barrier(32)
        successes: list[int] = []
        failures: list[str] = []
        result_lock = threading.Lock()

        def authorize() -> None:
            barrier.wait()
            try:
                sequence = lease.authorize_request(
                    "retrieve_page", scope=scope(1)
                )
            except CredentialCapabilityError as exc:
                with result_lock:
                    failures.append(exc.code)
            else:
                with result_lock:
                    successes.append(sequence)

        threads = [threading.Thread(target=authorize) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(successes), list(range(1, 9)))
        self.assertEqual(
            failures, ["credential_capability_request_budget_exhausted"] * 24
        )
        self.assertEqual(lease.provider_requests_authorized, 8)

    def test_serialization_and_errors_do_not_expose_secret_or_disallowed_fields(self) -> None:
        capability = issue_capability()
        serialized = json.dumps(
            capability.canonical_document(), ensure_ascii=False, sort_keys=True
        )
        for forbidden in (
            "Authorization",
            "Bearer ",
            "secret_value_only_for_test",
            "page_id",
            "provider_url",
            "credential_path",
            "C:\\\\Users\\\\",
            "https://api.notion.com",
        ):
            self.assertNotIn(forbidden, serialized)

        hostile = issue_capability().canonical_document()
        hostile["reviewed_by"] = "secret_value_only_for_test"
        with self.assertRaises(CredentialCapabilityError) as caught:
            CredentialCapability.from_document(hostile)
        self.assertEqual(caught.exception.code, "credential_capability_reviewer_invalid")
        self.assertNotIn("secret_value_only_for_test", str(caught.exception))
        self.assertNotIn("secret_value_only_for_test", repr(caught.exception))

        directly_hostile = CredentialCapabilityError(
            "secret_value_only_for_test/C:\\Users\\operator"
        )
        self.assertEqual(directly_hostile.code, "credential_capability_error")
        self.assertNotIn("secret_value_only_for_test", repr(directly_hostile))


if __name__ == "__main__":
    unittest.main()
