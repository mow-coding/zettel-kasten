from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import exact_human_approval_link
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
    _claim_exact_human_approval_core as claim_exact_human_approval,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_link import (
    LINKS_RELATIVE_ROOT,
    ExactHumanApprovalLinkError,
    exact_human_approval_link_upgrades_original_operation,
    read_exact_human_approval_link,
    verify_exact_human_approval_link,
    write_exact_human_approval_link,
)
from wom_kit.exact_human_approval_windows import (
    ExactHumanApprovalContext,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)


AUTH_KEY = bytes(range(32))
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
PRIVATE_TEXT = "PRIVATE SOURCE BODY MUST NEVER ECHO"
PRIVATE_PATH_TEXT = "PRIVATE-person-secret-path"
ARCHIVE_ID = "archive:test-approval-link"


class ExactHumanApprovalLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / PRIVATE_PATH_TEXT
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            f"archive_id: {ARCHIVE_ID}\n", encoding="utf-8"
        )
        self.operation = ExactHumanApprovalOperation.create_draft
        self.source_relative = (
            "receipts/source-fidelity/drafts/" + "1" * 64 + ".json"
        )
        self.source_raw = (
            json.dumps(
                {
                    "schema": "test/source-operation/v0.1",
                    "private_body": PRIVATE_TEXT,
                },
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        self.source_path = self.root.joinpath(*self.source_relative.split("/"))
        self.source_path.parent.mkdir(parents=True)
        self.source_path.write_bytes(self.source_raw)
        self.source_sha256 = "sha256:" + hashlib.sha256(
            self.source_raw
        ).hexdigest()
        self.claims: list[ClaimedExactHumanApproval] = []
        self.context, self.claim = self._claim("1")
        self.reference = self.claim.public_reference()

    def tearDown(self) -> None:
        for claim in self.claims:
            claim.close()
        self.temporary.cleanup()

    def _claim(
        self,
        fill: str,
        *,
        operation: ExactHumanApprovalOperation | None = None,
        plan_sha256: str = SHA_C,
        target_binding_sha256: str = SHA_D,
    ) -> tuple[ExactHumanApprovalContext, ClaimedExactHumanApproval]:
        selected_operation = operation or self.operation
        context = ExactHumanApprovalContext(
            operation=selected_operation,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                ARCHIVE_ID
            ),
            plan_sha256=plan_sha256,
            target_binding_sha256=target_binding_sha256,
            reviewer_claim="person:local-operator",
            review_binding_codes=("operation_receipt_digest", "target_binding"),
            warning_codes=(),
        )
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=plan_sha256,
            target_binding_sha256=target_binding_sha256,
        )
        claim = claim_exact_human_approval(
            self.root,
            context,
            decision,
            AUTH_KEY,
            clock=lambda: datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            random_hex=lambda _size: fill * 32,
        )
        self.claims.append(claim)
        return context, claim

    def _write(
        self,
        *,
        claim: ClaimedExactHumanApproval | None = None,
        context: ExactHumanApprovalContext | None = None,
        operation: ExactHumanApprovalOperation | None = None,
        source_relative: Path | str | None = None,
        source_sha256: str | None = None,
        effect: str = "created",
        random_hex=None,
    ) -> dict[str, object]:
        selected_claim = claim or self.claim
        selected_context = context or self.context
        kwargs = {
            "approval_claim": selected_claim,
            "approval_context": selected_context,
            "operation": operation or self.operation,
            "plan_sha256": SHA_C,
            "target_binding_sha256": SHA_D,
            "source_operation_receipt": source_relative or self.source_relative,
            "expected_source_operation_receipt_sha256": (
                source_sha256 or self.source_sha256
            ),
            "effect": effect,
        }
        if random_hex is not None:
            kwargs["random_hex"] = random_hex
        return write_exact_human_approval_link(self.root, **kwargs)

    def _link_path(
        self, claim: ClaimedExactHumanApproval | None = None
    ) -> Path:
        selected = claim or self.claim
        return self.root.joinpath(
            *LINKS_RELATIVE_ROOT.split("/"), f"{selected.approval_id}.json"
        )

    def _read(
        self, claim: ClaimedExactHumanApproval | None = None, *, key=AUTH_KEY
    ) -> dict:
        selected = claim or self.claim
        return read_exact_human_approval_link(
            self.root,
            selected.approval_id,
            receipt_authentication_key=key,
        )

    def test_created_link_is_mac_authenticated_schema_valid_and_content_free(self) -> None:
        result = self._write(random_hex=lambda _size: "2" * 16)
        self.assertTrue(result["ok"])
        self.assertTrue(result["created"])
        self.assertTrue(result["original_operation_evidence_upgraded"])
        self.assertEqual(result["claim_status_at_return"], "started")
        self.assertTrue(result["claim_finalization_required"])
        self.assertEqual(self.claim.status, "started")
        self.assertNotIn(PRIVATE_TEXT, json.dumps(result))
        self.assertNotIn(PRIVATE_PATH_TEXT, json.dumps(result))

        raw = self._link_path().read_bytes()
        document = json.loads(raw.decode("ascii"))
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "exact-human-approval-link-receipt-v0.1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)
        self.assertEqual(document["exact_human_approval"], self.reference)
        self.assertEqual(document["operation"], "create_draft")
        self.assertEqual(document["effect"], "created")
        self.assertEqual(
            document["authentication"]["schema_version"],
            "wom-kit/exact-human-approval-link-authentication/v0.1",
        )
        self.assertEqual(document["authentication"]["algorithm"], "hmac-sha256")
        self.assertNotIn(PRIVATE_TEXT.encode("utf-8"), raw)
        self.assertNotIn(str(self.root).encode("utf-8"), raw)
        self.assertEqual(raw, exact_human_approval_link._canonical_bytes(document))

        with self.assertRaises(ExactHumanApprovalLinkError) as uncertain:
            self._read()
        self.assertEqual(
            uncertain.exception.code,
            "exact_human_approval_link_approval_claim_invalid",
        )
        self.claim.finalize_succeeded()
        verified_document = self._read()
        self.assertEqual(verified_document["effect"], "created")
        self.assertTrue(
            exact_human_approval_link_upgrades_original_operation(
                self.root,
                self.claim.approval_id,
                receipt_authentication_key=AUTH_KEY,
            )
        )
        verified = verify_exact_human_approval_link(
            self.root,
            exact_human_approval=self.reference,
            operation=self.operation,
            plan_sha256=SHA_C,
            target_binding_sha256=SHA_D,
            source_operation_receipt=self.source_relative,
            expected_source_operation_receipt_sha256=self.source_sha256,
            effect="created",
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertTrue(verified["verified"])

    def test_recomputed_digest_effect_flip_cannot_upgrade_history(self) -> None:
        self._write(effect="already_present_exact")
        self.claim.finalize_succeeded()
        self.assertFalse(
            exact_human_approval_link_upgrades_original_operation(
                self.root,
                self.claim.approval_id,
                receipt_authentication_key=AUTH_KEY,
            )
        )
        path = self._link_path()
        document = json.loads(path.read_text(encoding="ascii"))
        document["effect"] = "created"
        document["original_operation_evidence_upgraded"] = True
        document["link_sha256"] = exact_human_approval_link._link_digest(document)
        path.write_bytes(exact_human_approval_link._canonical_bytes(document))

        with self.assertRaises(ExactHumanApprovalLinkError) as tampered:
            self._read()
        self.assertEqual(
            tampered.exception.code,
            "exact_human_approval_link_authentication_invalid",
        )
        with self.assertRaises(ExactHumanApprovalLinkError):
            exact_human_approval_link_upgrades_original_operation(
                self.root,
                self.claim.approval_id,
                receipt_authentication_key=AUTH_KEY,
            )

    def test_read_requires_right_key_and_same_archive_succeeded_claim(self) -> None:
        self._write()
        with self.assertRaises(ExactHumanApprovalLinkError) as wrong_key:
            self._read(key=b"x" * 32)
        self.assertEqual(
            wrong_key.exception.code,
            "exact_human_approval_link_authentication_invalid",
        )
        with self.assertRaises(ExactHumanApprovalLinkError) as malformed_key:
            self._read(key=b"short")
        self.assertEqual(
            malformed_key.exception.code,
            "exact_human_approval_link_key_invalid",
        )
        self.claim.finalize_succeeded()
        claim_path = (
            self.root
            / CLAIMS_RELATIVE_ROOT
            / f"{self.claim.approval_id}.json"
        )
        claim_document = json.loads(claim_path.read_text(encoding="utf-8"))
        claim_document["private_tamper"] = PRIVATE_TEXT
        claim_path.write_text(json.dumps(claim_document), encoding="utf-8")
        with self.assertRaises(ExactHumanApprovalLinkError) as claim_tamper:
            self._read()
        self.assertEqual(
            claim_tamper.exception.code,
            "exact_human_approval_link_approval_claim_invalid",
        )
        self.assertNotIn(PRIVATE_TEXT, str(claim_tamper.exception))

    def test_writer_requires_concrete_matching_started_claim_and_context(self) -> None:
        with self.assertRaises(ExactHumanApprovalLinkError) as fake_claim:
            write_exact_human_approval_link(
                self.root,
                approval_claim=object(),  # type: ignore[arg-type]
                approval_context=self.context,
                operation=self.operation,
                plan_sha256=SHA_C,
                target_binding_sha256=SHA_D,
                source_operation_receipt=self.source_relative,
                expected_source_operation_receipt_sha256=self.source_sha256,
                effect="created",
            )
        self.assertEqual(
            fake_claim.exception.code,
            "exact_human_approval_link_approval_claim_invalid",
        )
        wrong_context, wrong_claim = self._claim(
            "2",
            operation=ExactHumanApprovalOperation.source_fidelity_session_evidence,
        )
        with self.assertRaises(ExactHumanApprovalLinkError) as wrong_binding:
            self._write(claim=wrong_claim, context=wrong_context)
        self.assertEqual(
            wrong_binding.exception.code,
            "exact_human_approval_link_binding_mismatch",
        )
        self.assertFalse(self._link_path(wrong_claim).exists())
        self.claim.finalize_succeeded()
        with self.assertRaises(ExactHumanApprovalLinkError) as terminal:
            self._write()
        self.assertEqual(
            terminal.exception.code,
            "exact_human_approval_link_approval_claim_invalid",
        )

    def test_session_evidence_requires_its_receipt_namespace(self) -> None:
        session_relative = (
            "receipts/source-fidelity/session-evidence/" + "3" * 64 + ".json"
        )
        session_path = self.root.joinpath(*session_relative.split("/"))
        session_path.parent.mkdir(parents=True)
        session_raw = b'{"schema":"test/session-evidence"}\n'
        session_path.write_bytes(session_raw)
        session_sha = "sha256:" + hashlib.sha256(session_raw).hexdigest()
        context, claim = self._claim(
            "3",
            operation=ExactHumanApprovalOperation.source_fidelity_session_evidence,
        )
        result = self._write(
            claim=claim,
            context=context,
            operation=ExactHumanApprovalOperation.source_fidelity_session_evidence,
            source_relative=session_relative,
            source_sha256=session_sha,
        )
        self.assertEqual(result["operation"], "source_fidelity_session_evidence")
        claim.finalize_succeeded()
        self.assertEqual(
            self._read(claim)["source_operation_receipt"]["relative_path"],
            session_relative,
        )
        other_context, other_claim = self._claim("4")
        with self.assertRaises(ExactHumanApprovalLinkError) as wrong_namespace:
            self._write(
                claim=other_claim,
                context=other_context,
                source_relative=session_relative,
                source_sha256=session_sha,
            )
        self.assertEqual(
            wrong_namespace.exception.code,
            "exact_human_approval_link_source_receipt_ref_invalid",
        )

    def test_source_and_link_tamper_fail_closed_without_private_echo(self) -> None:
        self._write()
        self.claim.finalize_succeeded()
        self.source_path.write_text(PRIVATE_TEXT + " changed", encoding="utf-8")
        with self.assertRaises(ExactHumanApprovalLinkError) as source_tamper:
            self._read()
        self.assertEqual(
            source_tamper.exception.code,
            "exact_human_approval_link_source_receipt_sha256_mismatch",
        )
        self.assertNotIn(PRIVATE_TEXT, str(source_tamper.exception))

        self.source_path.write_bytes(self.source_raw)
        document = json.loads(self._link_path().read_text(encoding="ascii"))
        document["authentication"]["mac"] = "hmac-sha256:" + "0" * 64
        document["private_value"] = PRIVATE_TEXT
        self._link_path().write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(ExactHumanApprovalLinkError) as link_tamper:
            self._read()
        self.assertIn(
            link_tamper.exception.code,
            {
                "exact_human_approval_link_document_invalid",
                "exact_human_approval_link_authentication_invalid",
            },
        )
        self.assertNotIn(PRIVATE_TEXT, str(link_tamper.exception))

    def test_replay_and_concurrency_publish_one_complete_link(self) -> None:
        barrier = threading.Barrier(2)

        def publish() -> object:
            barrier.wait()
            try:
                return self._write()
            except ExactHumanApprovalLinkError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: publish(), range(2)))
        successes = [item for item in outcomes if isinstance(item, dict)]
        failures = [
            item for item in outcomes if isinstance(item, ExactHumanApprovalLinkError)
        ]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].code, "exact_human_approval_link_replayed")
        self.assertEqual(self.claim.status, "started")
        self.claim.finalize_succeeded()
        self.assertEqual(self._read()["effect"], "created")
        self.assertEqual(list(self._link_path().parent.glob(".*.tmp-*")), [])

    def test_atomic_publication_failure_leaves_started_claim_and_no_partial(self) -> None:
        with mock.patch.object(
            exact_human_approval_link.os,
            "link",
            side_effect=OSError(PRIVATE_TEXT),
        ):
            with self.assertRaises(ExactHumanApprovalLinkError) as captured:
                self._write(random_hex=lambda _size: "5" * 16)
        self.assertEqual(
            captured.exception.code,
            "exact_human_approval_link_commit_failed",
        )
        self.assertNotIn(PRIVATE_TEXT, str(captured.exception))
        self.assertEqual(self.claim.status, "started")
        self.assertFalse(self._link_path().exists())
        links = self._link_path().parent
        self.assertEqual(list(links.glob(".*.tmp-*")), [])

    def test_relative_path_boundary_and_reparse_source_are_enforced(self) -> None:
        for source_ref in (
            f"C:/{PRIVATE_PATH_TEXT}/receipt.json",
            f"receipts/source-fidelity/drafts/../{PRIVATE_PATH_TEXT}.json",
            f"receipts\\source-fidelity\\drafts\\{PRIVATE_PATH_TEXT}.json",
            self.source_path,
        ):
            with self.subTest(source_ref=os.fspath(source_ref)):
                with self.assertRaises(ExactHumanApprovalLinkError) as captured:
                    self._write(source_relative=source_ref)
                self.assertEqual(
                    captured.exception.code,
                    "exact_human_approval_link_source_receipt_ref_invalid",
                )
                self.assertNotIn(PRIVATE_PATH_TEXT, str(captured.exception))

        source_info = os.lstat(self.source_path)
        real_is_reparse = exact_human_approval_link._is_reparse

        def source_is_reparse(info) -> bool:
            return bool(
                exact_human_approval_link._same_file(info, source_info)
                or real_is_reparse(info)
            )

        with mock.patch.object(
            exact_human_approval_link,
            "_is_reparse",
            side_effect=source_is_reparse,
        ):
            with self.assertRaises(ExactHumanApprovalLinkError) as source_link:
                self._write()
        self.assertEqual(
            source_link.exception.code,
            "exact_human_approval_link_source_receipt_unsafe",
        )

    def test_temp_write_uses_exclusive_create(self) -> None:
        real_open = exact_human_approval_link.os.open
        observed_flags: list[int] = []

        def recording_open(path, flags, *args, **kwargs):
            if ".tmp-" in os.fspath(path):
                observed_flags.append(flags)
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(
            exact_human_approval_link.os, "open", side_effect=recording_open
        ):
            self._write(random_hex=lambda _size: "6" * 16)
        self.assertTrue(observed_flags)
        self.assertTrue(all(flags & os.O_EXCL for flags in observed_flags))
        self.assertTrue(all(flags & os.O_CREAT for flags in observed_flags))


if __name__ == "__main__":
    unittest.main()
