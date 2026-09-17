"""v0.4.23 (beta letter 160 ②): a binary original (PDF, spreadsheet, image) may be
the fidelity source of a faithful_summary or sanitized_derivative draft, bound by
its byte digest on the `bytes` comparison basis. verbatim keeps requiring UTF-8
text. Synthetic archive only; approval claims are injected."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from wom_kit import archive_services

import test_v03313_source_fidelity as _fixture_module

KIT_ROOT = Path(__file__).resolve().parents[1]
# Not valid UTF-8 (0xff 0xfe) and carries NUL bytes, like a real xlsx/pdf header.
BINARY_SOURCE = b"PK\x03\x04\x14\x00\x00\x00\x08\x00\xff\xfe\x00\x01binary spreadsheet bytes\x00\r\n" * 3


class BinaryFidelitySourceTests(unittest.TestCase):
    # Reuse the v0.3.313 fixture (archive template, manifested objet, approval
    # helper); the module reference keeps the loader from collecting it twice.
    _Fixture = _fixture_module.SourceFidelityV03313Tests
    setUp = _Fixture.setUp
    manifested_source = _Fixture.manifested_source
    ai_kwargs = _Fixture.ai_kwargs
    exact_claim = _Fixture.exact_claim
    create_approved = _Fixture.create_approved

    def receipt_schema(self) -> Draft202012Validator:
        schema = json.loads(
            (KIT_ROOT / "schemas" / "source-fidelity-draft-receipt.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def test_verbatim_still_refuses_a_binary_source(self) -> None:
        object_id = self.manifested_source(BINARY_SOURCE)
        preview = archive_services.create_draft_zettel(
            self.root, dry_run=True, **self.ai_kwargs(object_id, draft_id="zet_20260917_101_binary_verbatim")
        )
        self.assertFalse(preview["ok"])
        self.assertIn("source_fidelity_source_not_utf8", preview["blockers"])
        self.assertNotIn(object_id, json.dumps(preview, ensure_ascii=False))
        self.assertIn("comparison_basis: bytes", json.dumps(preview.get("next_safe_actions") or preview))

    def test_summary_draft_binds_a_binary_original_by_byte_digest(self) -> None:
        object_id = self.manifested_source(BINARY_SOURCE)
        raw_digest = object_id.removeprefix("sha256:")
        kwargs = self.ai_kwargs(
            object_id, draft_id="zet_20260917_102_binary_summary",
            body="A reviewed summary of a spreadsheet that the draft never embeds.",
            mode="faithful_summary", audience="private_self",
        )
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, **kwargs)
        self.assertTrue(preview["ok"], preview)
        safe = preview["source_fidelity"]
        self.assertEqual(safe["comparison_basis"], "bytes")
        self.assertFalse(safe["mechanically_verified"])
        self.assertNotIn("source", safe)
        self.assertNotIn(object_id, json.dumps(preview, ensure_ascii=False))

        result = self.create_approved(kwargs, preview=preview)
        self.assertTrue(result["ok"], result)
        receipt_path = self.root / result["source_fidelity_draft_receipt_path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.receipt_schema().validate(receipt)
        fidelity = receipt["source_fidelity"]
        self.assertEqual(fidelity["mode"], "faithful_summary")
        self.assertEqual(fidelity["comparison_basis"], "bytes")
        self.assertIsNone(fidelity["region"])
        self.assertFalse(fidelity["mechanically_verified"])
        self.assertTrue(fidelity["human_review_required"])
        source = fidelity["source"]
        self.assertEqual(source["comparison_basis"], "bytes")
        self.assertEqual(source["raw_sha256"], raw_digest)
        self.assertEqual(source["normalized_sha256"], raw_digest)
        self.assertEqual(source["raw_size_bytes"], len(BINARY_SOURCE))
        self.assertEqual(source["normalized_size_bytes"], len(BINARY_SOURCE))
        self.assertFalse(source["newline_transformation_applied"])
        self.assertFalse(source["source_text_stored"])
        self.assertFalse(source["source_locator_stored"])
        # the receipt body never carries the source bytes or their text
        self.assertNotIn("binary spreadsheet bytes", receipt_path.read_text(encoding="utf-8"))

        # the draft re-verifies on the stored bytes basis (mint preflight path)
        verification = archive_services._source_fidelity_verify_for_mint(
            self.root, self.root / result["path"], affirmations=None
        )
        self.assertTrue(verification["ok"], verification)
        # and an exact replay is idempotent
        replay = self.create_approved(kwargs, preview=preview)
        self.assertTrue(replay["idempotent_replay"], replay)
        self.assertEqual(replay["created_paths"], [])

    def test_sanitized_derivative_accepts_a_binary_source_too(self) -> None:
        object_id = self.manifested_source(BINARY_SOURCE + b"\x00\x00tail")
        kwargs = self.ai_kwargs(
            object_id, draft_id="zet_20260917_103_binary_derivative",
            body="A sanitized derivative of a private binary original.",
            mode="sanitized_derivative", audience="client_report",
        )
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, **kwargs)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["source_fidelity"]["comparison_basis"], "bytes")

    def test_text_sources_keep_the_utf8_basis_byte_for_byte(self) -> None:
        object_id = self.manifested_source("텍스트 원본\r\n둘째 줄\n".encode("utf-8"))
        kwargs = self.ai_kwargs(
            object_id, draft_id="zet_20260917_104_text_summary",
            body="A summary of a text source.", mode="faithful_summary", audience="private_self",
        )
        preview = archive_services.create_draft_zettel(self.root, dry_run=True, **kwargs)
        self.assertTrue(preview["ok"], preview)
        self.assertEqual(preview["source_fidelity"]["comparison_basis"], "utf8_newlines_lf")
        result = self.create_approved(kwargs, preview=preview)
        receipt = json.loads((self.root / result["source_fidelity_draft_receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["source_fidelity"]["comparison_basis"], "utf8_newlines_lf")
        self.assertTrue(receipt["source_fidelity"]["source"]["newline_transformation_applied"])

    def test_stored_validators_refuse_inconsistent_bytes_receipts(self) -> None:
        object_id = self.manifested_source(BINARY_SOURCE)
        kwargs = self.ai_kwargs(
            object_id, draft_id="zet_20260917_105_binary_validators",
            body="A reviewed summary used to exercise the validators.",
            mode="faithful_summary", audience="private_self",
        )
        result = self.create_approved(kwargs)
        receipt = json.loads((self.root / result["source_fidelity_draft_receipt_path"]).read_text(encoding="utf-8"))
        fidelity = receipt["source_fidelity"]
        self.assertTrue(archive_services._source_fidelity_private_receipt_shape_valid_v1(receipt))

        def variant(**changes):
            document = json.loads(json.dumps(receipt))
            block = document["source_fidelity"]
            for key, value in changes.items():
                target, _, field = key.partition("__")
                (block["source"] if target == "source" else block)[field or target] = value
            return document

        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(variant(mode="verbatim")))
        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(
            variant(source__newline_transformation_applied=True)))
        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(
            variant(source__normalized_sha256="0" * 64)))
        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(
            variant(source__comparison_basis="utf8_newlines_lf")))
        self.assertFalse(archive_services._source_fidelity_private_receipt_shape_valid_v1(
            variant(comparison_basis="wire")))
        # the schema refuses an unknown basis as well
        with self.assertRaises(Exception):
            self.receipt_schema().validate(variant(comparison_basis="wire"))
        self.assertEqual(fidelity["comparison_basis"], "bytes")

    def test_policy_projection_lists_both_bases(self) -> None:
        policy = archive_services.source_fidelity_policy()
        self.assertEqual(policy["comparison_basis"], "utf8_newlines_lf")
        self.assertEqual(policy["comparison_bases"], ["utf8_newlines_lf", "bytes"])
        self.assertEqual(policy["binary_source_modes"], ["faithful_summary", "sanitized_derivative"])


if __name__ == "__main__":
    unittest.main()
