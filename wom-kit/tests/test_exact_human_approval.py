from __future__ import annotations

import json
import hashlib
import hmac
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wom_kit.exact_human_approval import (
    APPROVAL_INTEGRITY_MAC_DOMAIN,
    APPROVAL_INTEGRITY_MAC_MAX_PAYLOAD_BYTES,
    APPROVAL_LINK_MAC_DOMAIN,
    APPROVAL_LINK_MAC_MAX_PAYLOAD_BYTES,
    CLAIMS_RELATIVE_ROOT,
    ExactHumanApprovalError,
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)


AUTH_KEY = bytes(range(32))
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


class ExactHumanApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test\n", encoding="utf-8"
        )
        self.context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.mint_zet,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:test"
            ),
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
            reviewer_claim="person:local-operator",
            review_binding_codes=("body_digest", "frontmatter_digest"),
            warning_codes=(),
        )
        self.decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
        )
        self.clock = lambda: datetime(2026, 8, 20, 8, 30, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _claim(self):
        return claim_exact_human_approval(
            self.root,
            self.context,
            self.decision,
            AUTH_KEY,
            clock=self.clock,
            random_hex=lambda _size: "1" * 32,
        )

    def test_claim_is_create_once_authenticated_and_content_free(self) -> None:
        claim = self._claim()
        try:
            self.assertEqual(claim.status, "started")
            self.assertEqual(
                claim.public_reference(),
                {
                    "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
                    "approval_id": "approval_" + "1" * 32,
                    "context_sha256": claim.public_summary()["context_sha256"],
                    "approval_authority_sha256": claim.public_summary()[
                        "approval_authority_sha256"
                    ],
                    "one_use": True,
                },
            )
            path = (
                self.root
                / CLAIMS_RELATIVE_ROOT
                / ("approval_" + "1" * 32 + ".json")
            )
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "started")
            self.assertEqual(document["reviewer_identity_authenticated"], False)
            self.assertEqual(document["authentication"]["algorithm"], "hmac-sha256")
            self.assertEqual(
                claim.assert_ready_for_context(self.context),
                claim.public_reference(),
            )
            rendered = path.read_text(encoding="utf-8")
            self.assertNotIn("person:local-operator", rendered)
            self.assertNotIn(str(self.root), rendered)
        finally:
            claim.close()

    def test_same_identifier_is_permanently_spent(self) -> None:
        first = self._claim()
        first.close()
        with self.assertRaises(ExactHumanApprovalError) as captured:
            self._claim()
        self.assertEqual(captured.exception.code, "exact_human_approval_claim_replayed")

    def test_synthetic_cancelled_or_mismatched_decision_cannot_claim(self) -> None:
        decisions = (
            ExactHumanApprovalDecision(False, True, "exact_human_approval_synthetic_acknowledged", SHA_B, SHA_C),
            ExactHumanApprovalDecision(False, False, "exact_human_approval_cancelled", SHA_B, SHA_C),
            ExactHumanApprovalDecision(True, False, "exact_human_approval_approved", SHA_A, SHA_C),
        )
        for decision in decisions:
            with self.subTest(decision=decision):
                with self.assertRaises(ExactHumanApprovalError):
                    claim_exact_human_approval(
                        self.root,
                        self.context,
                        decision,
                        AUTH_KEY,
                    )
        self.assertFalse((self.root / "profiles").exists())

    def test_success_and_failure_are_terminal_and_key_is_wiped_on_close(self) -> None:
        success = self._claim()
        success.finalize_succeeded()
        self.assertEqual(success.status, "succeeded")
        with self.assertRaises(ExactHumanApprovalError) as terminal_mac:
            success.approval_integrity_mac(b'{"entry":"terminal"}\n')
        self.assertEqual(
            terminal_mac.exception.code,
            "exact_human_approval_claim_state_invalid",
        )
        with self.assertRaises(ExactHumanApprovalError):
            success.finalize_failed("late_failure")
        success.close()
        self.assertEqual(set(success._key), {0})

        failed = claim_exact_human_approval(
            self.root,
            self.context,
            self.decision,
            AUTH_KEY,
            clock=self.clock,
            random_hex=lambda _size: "2" * 32,
        )
        failed.finalize_failed("writer_failed")
        self.assertEqual(failed.status, "failed")
        failed.close()

    def test_tamper_blocks_finalization_and_does_not_echo_tampered_value(self) -> None:
        claim = self._claim()
        path = self.root / CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["context"]["plan_sha256"] = "sha256:" + "d" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(ExactHumanApprovalError) as captured:
            claim.finalize_succeeded()
        self.assertIn(
            captured.exception.code,
            {
                "exact_human_approval_claim_document_invalid",
                "exact_human_approval_claim_authentication_invalid",
            },
        )
        self.assertNotIn("d" * 64, str(captured.exception))
        claim.close()

    def test_finalize_replace_failure_leaves_started_claim_for_reconciliation(self) -> None:
        claim = self._claim()
        with mock.patch(
            "wom_kit.exact_human_approval.os.replace",
            side_effect=OSError("private failure text"),
        ):
            with self.assertRaises(ExactHumanApprovalError) as captured:
                claim.finalize_succeeded()
        self.assertEqual(
            captured.exception.code, "exact_human_approval_finalization_failed"
        )
        path = self.root / CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "started")
        claim.close()

    def test_integrity_mac_is_fixed_domain_bounded_and_keyless_to_callers(self) -> None:
        claim = self._claim()
        payload = b'{"entry":"content-free"}\n'
        try:
            mac = claim.approval_integrity_mac(payload)
            expected = "hmac-sha256:" + hmac.new(
                AUTH_KEY,
                APPROVAL_INTEGRITY_MAC_DOMAIN + payload,
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(hmac.compare_digest(mac, expected))
            self.assertNotEqual(
                mac,
                "hmac-sha256:"
                + hmac.new(AUTH_KEY, payload, hashlib.sha256).hexdigest(),
            )
            self.assertFalse(hasattr(claim, "receipt_authentication_key"))
            self.assertFalse(hasattr(claim, "approval_integrity_key"))
            self.assertNotIn(AUTH_KEY.hex(), repr(claim))
            for invalid in (
                b"",
                bytearray(payload),
                memoryview(payload),
                "private payload",
                b"x" * (APPROVAL_INTEGRITY_MAC_MAX_PAYLOAD_BYTES + 1),
            ):
                with self.subTest(invalid_type=type(invalid).__name__):
                    with self.assertRaises(ExactHumanApprovalError) as captured:
                        claim.approval_integrity_mac(invalid)  # type: ignore[arg-type]
                    self.assertEqual(
                        captured.exception.code,
                        "exact_human_approval_integrity_payload_invalid",
                    )
        finally:
            claim.close()

    def test_integrity_mac_verification_is_constant_time_and_tamper_sensitive(self) -> None:
        claim = self._claim()
        payload = b'{"entry":"bounded"}\n'
        try:
            mac = claim.approval_integrity_mac(payload)
            observed: list[tuple[object, object]] = []
            original = hmac.compare_digest

            def recording_compare(left, right):
                observed.append((left, right))
                return original(left, right)

            with mock.patch(
                "wom_kit.exact_human_approval.hmac.compare_digest",
                side_effect=recording_compare,
            ):
                self.assertTrue(
                    claim.approval_integrity_mac_matches(payload, mac)
                )
                tampered = mac[:-1] + ("0" if mac[-1] != "0" else "1")
                self.assertFalse(
                    claim.approval_integrity_mac_matches(payload, tampered)
                )
            self.assertIn((mac, mac), observed)
            self.assertIn((mac, tampered), observed)
            with self.assertRaises(ExactHumanApprovalError) as malformed:
                claim.approval_integrity_mac_matches(payload, "PRIVATE mac")
            self.assertEqual(
                malformed.exception.code,
                "exact_human_approval_integrity_mac_invalid",
            )
            self.assertNotIn("PRIVATE", str(malformed.exception))
        finally:
            claim.close()

    def test_approval_link_mac_is_a_second_fixed_domain_capability(self) -> None:
        claim = self._claim()
        payload = b'{"link":"content-free"}\n'
        try:
            link_mac = claim.exact_human_approval_link_mac(payload)
            expected = "hmac-sha256:" + hmac.new(
                AUTH_KEY,
                APPROVAL_LINK_MAC_DOMAIN + payload,
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(hmac.compare_digest(link_mac, expected))
            self.assertNotEqual(
                link_mac,
                claim.approval_integrity_mac(payload),
            )
            self.assertTrue(
                claim.exact_human_approval_link_mac_matches(payload, link_mac)
            )
            tampered = link_mac[:-1] + ("0" if link_mac[-1] != "0" else "1")
            self.assertFalse(
                claim.exact_human_approval_link_mac_matches(payload, tampered)
            )
            for invalid in (
                b"",
                bytearray(payload),
                b"x" * (APPROVAL_LINK_MAC_MAX_PAYLOAD_BYTES + 1),
            ):
                with self.assertRaises(ExactHumanApprovalError) as captured:
                    claim.exact_human_approval_link_mac(  # type: ignore[arg-type]
                        invalid
                    )
                self.assertEqual(
                    captured.exception.code,
                    "exact_human_approval_link_payload_invalid",
                )
        finally:
            claim.close()

    def test_integrity_mac_reauthenticates_current_started_claim_and_is_thread_safe(self) -> None:
        claim = self._claim()
        payload = b'{"entry":"concurrent"}\n'
        barrier = threading.Barrier(8)
        results: list[str] = []
        failures: list[str] = []

        def worker() -> None:
            try:
                barrier.wait()
                results.append(claim.approval_integrity_mac(payload))
            except BaseException as error:  # pragma: no cover - diagnostic
                failures.append(type(error).__name__)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            self.assertEqual(failures, [])
            self.assertEqual(len(results), 8)
            self.assertEqual(len(set(results)), 1)

            path = self.root / CLAIMS_RELATIVE_ROOT / (claim.approval_id + ".json")
            document = json.loads(path.read_text(encoding="utf-8"))
            document["private_tamper"] = "PRIVATE current-claim bytes"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ExactHumanApprovalError) as tampered:
                claim.approval_integrity_mac(payload)
            self.assertNotIn("PRIVATE", str(tampered.exception))
        finally:
            claim.close()

    def test_unsafe_archive_or_claim_parent_fails_closed(self) -> None:
        not_archive = Path(self.temporary.name) / "not-archive"
        not_archive.mkdir()
        with self.assertRaises(ExactHumanApprovalError):
            claim_exact_human_approval(
                not_archive,
                self.context,
                self.decision,
                AUTH_KEY,
            )


if __name__ == "__main__":
    unittest.main()
