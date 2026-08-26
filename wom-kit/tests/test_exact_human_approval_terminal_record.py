from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import wom_kit.exact_human_approval as exact_human_approval_module
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    TERMINAL_RECORD_AUTHENTICATION_SCHEMA_VERSION,
    TERMINAL_RECORD_MAC_DOMAIN,
    TERMINAL_RECORD_MAC_MAX_PAYLOAD_BYTES,
    ExactHumanApprovalError,
    _audit_exact_human_approval_terminal_record_core,
    _canonical_bytes,
    _claim_exact_human_approval_core,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    _ExactHumanApprovalDecision,
)


AUTH_KEY = bytes(range(32))
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


class ExactHumanApprovalTerminalRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test\n",
            encoding="utf-8",
        )
        self.context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.mint_zet,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256("archive:test")
            ),
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
            reviewer_claim="person:local-operator",
            review_binding_codes=("body_digest",),
            warning_codes=(),
        )
        self.decision = _ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
        )
        self.payload = _canonical_bytes(
            {
                "authentication_schema": (
                    TERMINAL_RECORD_AUTHENTICATION_SCHEMA_VERSION
                ),
                "result": "content_free",
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _claim(self, suffix: str):
        return _claim_exact_human_approval_core(
            self.root,
            self.context,
            self.decision,
            AUTH_KEY,
            clock=lambda: datetime(
                2026,
                8,
                26,
                3,
                0,
                tzinfo=timezone.utc,
            ),
            random_hex=lambda _size: suffix * 32,
        )

    def _audit(
        self,
        reference,
        mac,
        *,
        allowed_statuses=("succeeded",),
        evidence=None,
        payload=None,
        key=memoryview(AUTH_KEY),
    ) -> bool:
        return _audit_exact_human_approval_terminal_record_core(
            self.root,
            reference,
            expected_operation=ExactHumanApprovalOperation.mint_zet,
            expected_plan_sha256=SHA_B,
            expected_target_binding_sha256=SHA_C,
            allowed_statuses=allowed_statuses,
            expected_succeeded_evidence_digests=evidence,
            payload=self.payload if payload is None else payload,
            expected_mac=mac,
            receipt_authentication_key=key,
        )

    def test_signer_is_reference_bound_and_works_after_success(
        self,
    ) -> None:
        claim = self._claim("1")
        reference = claim.public_reference()
        try:
            started_mac = claim.exact_terminal_record_mac(self.payload)
            expected = "hmac-sha256:" + hmac.new(
                AUTH_KEY,
                TERMINAL_RECORD_MAC_DOMAIN
                + _canonical_bytes(reference)
                + self.payload,
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(hmac.compare_digest(started_mac, expected))
            self.assertNotEqual(
                started_mac,
                "hmac-sha256:"
                + hmac.new(
                    AUTH_KEY,
                    TERMINAL_RECORD_MAC_DOMAIN + self.payload,
                    hashlib.sha256,
                ).hexdigest(),
            )
            self.assertTrue(
                self._audit(
                    reference,
                    started_mac,
                    allowed_statuses=("started",),
                )
            )

            claim.finalize_succeeded()
            succeeded_mac = claim.exact_terminal_record_mac(self.payload)
            self.assertTrue(hmac.compare_digest(succeeded_mac, started_mac))
        finally:
            claim.close()

        failed = self._claim("2")
        failed.finalize_failed("writer_failed")
        try:
            with self.assertRaises(ExactHumanApprovalError) as terminal:
                failed.exact_terminal_record_mac(self.payload)
            self.assertEqual(
                terminal.exception.code,
                "exact_human_approval_claim_state_invalid",
            )
        finally:
            failed.close()

    def test_signer_requires_one_bounded_canonical_json_object(self) -> None:
        claim = self._claim("1")
        invalid_payloads = (
            b"",
            bytearray(self.payload),
            memoryview(self.payload),
            b'{"b":2, "a":1}\n',
            b"[]\n",
            b"not-json\n",
            b'{"value":"'
            + b"x" * TERMINAL_RECORD_MAC_MAX_PAYLOAD_BYTES
            + b'"}\n',
        )
        try:
            for payload in invalid_payloads:
                with self.subTest(payload_type=type(payload).__name__):
                    with self.assertRaises(ExactHumanApprovalError) as captured:
                        claim.exact_terminal_record_mac(
                            payload  # type: ignore[arg-type]
                        )
                    self.assertEqual(
                        captured.exception.code,
                        "exact_human_approval_terminal_record_payload_invalid",
                    )
        finally:
            claim.close()

    def test_core_audits_exact_succeeded_claim_and_wipes_its_key_copy(self) -> None:
        claim = self._claim("1")
        try:
            claim.finalize_succeeded()
            reference = claim.public_reference()
            evidence = claim.succeeded_evidence_digests(self.context)
            mac = claim.exact_terminal_record_mac(self.payload)
        finally:
            claim.close()

        captured_keys: list[bytearray] = []
        original_read_claim = exact_human_approval_module._read_claim

        def recording_read_claim(*args, **kwargs):
            captured_keys.append(kwargs["key"])
            return original_read_claim(*args, **kwargs)

        observed: list[tuple[object, object]] = []
        original_compare = hmac.compare_digest

        def recording_compare(left, right):
            observed.append((left, right))
            return original_compare(left, right)

        with mock.patch.object(
            exact_human_approval_module,
            "_read_claim",
            side_effect=recording_read_claim,
        ), mock.patch.object(
            exact_human_approval_module.hmac,
            "compare_digest",
            side_effect=recording_compare,
        ):
            self.assertTrue(self._audit(reference, mac, evidence=evidence))

        self.assertEqual(len(captured_keys), 1)
        self.assertEqual(set(captured_keys[0]), {0})
        self.assertIn((mac, mac), observed)

    def test_core_rejects_reference_binding_and_evidence_tamper(
        self,
    ) -> None:
        claim = self._claim("1")
        try:
            claim.finalize_succeeded()
            reference = claim.public_reference()
            evidence = claim.succeeded_evidence_digests(self.context)
            mac = claim.exact_terminal_record_mac(self.payload)
        finally:
            claim.close()

        fake_reference = dict(reference)
        fake_reference["approval_id"] = "approval_" + "f" * 32
        changed_reference = dict(reference)
        changed_reference["approval_authority_sha256"] = SHA_A
        changed_evidence = dict(evidence)
        changed_evidence["claim_receipt_sha256"] = SHA_A
        changed_mac = mac[:-1] + ("0" if mac[-1] != "0" else "1")
        noncanonical = json.dumps(
            {"result": "content_free", "authentication_schema": "changed"},
            ensure_ascii=False,
        ).encode("utf-8")

        cases = (
            self._audit(fake_reference, mac, evidence=evidence),
            self._audit(changed_reference, mac, evidence=evidence),
            self._audit(reference, mac, allowed_statuses=("started",)),
            self._audit(reference, mac, evidence=changed_evidence),
            self._audit(reference, changed_mac, evidence=evidence),
            self._audit(reference, mac, evidence=evidence, payload=noncanonical),
            self._audit(
                reference,
                mac,
                evidence=evidence,
                key=AUTH_KEY,  # type: ignore[arg-type]
            ),
        )
        self.assertEqual(cases, (False,) * len(cases))

        claim_path = (
            self.root
            / CLAIMS_RELATIVE_ROOT
            / f"{reference['approval_id']}.json"
        )
        document = json.loads(claim_path.read_text(encoding="utf-8"))
        document["status"] = "started"
        claim_path.write_bytes(_canonical_bytes(document))
        self.assertFalse(self._audit(reference, mac, evidence=evidence))

    def test_current_claim_audits_another_started_or_succeeded(
        self,
    ) -> None:
        historical = self._claim("1")
        current = self._claim("2")
        try:
            historical.finalize_succeeded()
            reference = historical.public_reference()
            evidence = historical.succeeded_evidence_digests(self.context)
            mac = historical.exact_terminal_record_mac(self.payload)

            expected = {
                "reference": reference,
                "expected_operation": ExactHumanApprovalOperation.mint_zet,
                "expected_plan_sha256": SHA_B,
                "expected_target_binding_sha256": SHA_C,
                "allowed_statuses": ("succeeded",),
                "expected_succeeded_evidence": evidence,
                "payload": self.payload,
                "expected_mac": mac,
            }
            self.assertTrue(current.exact_terminal_record_matches(**expected))
            current.finalize_succeeded()
            self.assertTrue(current.exact_terminal_record_matches(**expected))

            expected["expected_mac"] = "hmac-sha256:" + "0" * 64
            self.assertFalse(current.exact_terminal_record_matches(**expected))
        finally:
            historical.close()
            current.close()

    def test_missing_claim_tree_is_read_only_and_returns_false(self) -> None:
        other_root = Path(self.temporary.name) / "other-archive"
        other_root.mkdir()
        (other_root / "archive.yml").write_text(
            "archive_id: archive:other\n",
            encoding="utf-8",
        )
        reference = {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "f" * 32,
            "context_sha256": SHA_A,
            "approval_authority_sha256": SHA_B,
            "one_use": True,
        }
        self.assertFalse(
            _audit_exact_human_approval_terminal_record_core(
                other_root,
                reference,
                expected_operation=ExactHumanApprovalOperation.mint_zet,
                expected_plan_sha256=SHA_B,
                expected_target_binding_sha256=SHA_C,
                allowed_statuses=("succeeded",),
                expected_succeeded_evidence_digests=None,
                payload=self.payload,
                expected_mac="hmac-sha256:" + "0" * 64,
                receipt_authentication_key=memoryview(AUTH_KEY),
            )
        )
        self.assertFalse((other_root / "profiles").exists())


if __name__ == "__main__":
    unittest.main()
