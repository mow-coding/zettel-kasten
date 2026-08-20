from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services, completion_workflows


STAGED_CLEANUP_SCHEMA = "wom-kit/staged-cleanup-check/v0.3.317"
SAFE_STATE = "safe_to_cleanup"
UNSAFE_STATE = "not_safe_to_cleanup"

ENTRY_KEYS = {
    "entry_ref",
    "status",
    "preservation_kind",
    "reason_code",
    "manifest_record_present",
    "capture_receipt_present",
    "preserved_bytes_verified",
    "source_entry_readable",
}
LEGACY_FILE_KEYS = {
    "path",
    "status",
    "object_id",
    "preserved_bytes_verified",
    "manifest_record_present",
    "referencing_zets",
}

OBJET_PRESERVED_REASON = "objet_bytes_manifest_store_and_receipt_verified"
DERIVED_EXACT_PRESERVED_REASON = (
    "derived_text_exact_bytes_manifest_store_and_receipt_verified"
)
DERIVED_TRANSFORMED_REASON = (
    "derived_text_source_bytes_changed_by_normalization"
)

EVIDENCE_CASES = {
    "manifest_missing": "derived_text_manifest_missing",
    "manifest_invalid": "derived_text_manifest_invalid",
    "store_missing": "derived_text_store_missing",
    "store_sha256_mismatch": "derived_text_store_sha256_mismatch",
    "capture_receipt_missing": "derived_text_capture_receipt_missing",
    "capture_receipt_invalid": "derived_text_capture_receipt_invalid",
}


class StagedCleanupEvidenceV03317Tests(unittest.TestCase):
    maxDiff = None

    def _fake_archive(self, target: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", target)
        (target / ".wom-sandbox").write_text("sandbox\n", encoding="utf-8")
        return target

    def _write_source_receipt(self, archive_root: Path) -> str:
        relative = "receipts/sources/letter130.source-intake-plan.json"
        path = archive_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "lifecycle_action": "source_intake_plan",
                    "blockers": [],
                    "content_access": dict(
                        archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
                    ),
                    "source_refs_for_draft": [],
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return relative

    def _write_batch_request(
        self,
        archive_root: Path,
        items: list[dict[str, Any]],
        *,
        batch_id: str,
    ) -> Path:
        request = {
            "schema": completion_workflows.OBJET_CAPTURE_BATCH_REQUEST_SCHEMA,
            "batch_id": batch_id,
            "items": items,
        }
        path = archive_root / "staging" / f"{batch_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return path

    def _apply_fixture(
        self,
        temp_root: Path,
        *,
        derived_bytes: bytes | None,
        include_plain_item: bool,
        batch_id: str,
    ) -> dict[str, Any]:
        archive_root = self._fake_archive(temp_root / "archive")
        source_receipt = self._write_source_receipt(archive_root)
        staged_root = archive_root / "staging" / "incoming"
        staged_root.mkdir(parents=True, exist_ok=True)

        ordinary_name = "PRIVATE_LETTER130_ORDINARY_9917.pdf"
        paired_name = "PRIVATE_LETTER130_PAIRED_SOURCE_9917.pdf"
        derived_name = "PRIVATE_LETTER130_DERIVED_9917.txt"
        ordinary_bytes = b"%PDF-1.4\nPRIVATE_LETTER130_ORDINARY_BODY_9917\n"
        paired_bytes = b"%PDF-1.4\nPRIVATE_LETTER130_PAIRED_BODY_9917\n"

        items: list[dict[str, Any]] = []
        staged_paths: list[str] = []
        private_tokens: list[str] = [
            ordinary_name,
            paired_name,
            derived_name,
            ordinary_bytes.decode("ascii"),
            paired_bytes.decode("ascii"),
        ]

        if include_plain_item:
            ordinary_path = staged_root / ordinary_name
            ordinary_path.write_bytes(ordinary_bytes)
            ordinary_relative = ordinary_path.relative_to(archive_root).as_posix()
            staged_paths.append(ordinary_relative)
            ordinary_digest = hashlib.sha256(ordinary_bytes).hexdigest()
            private_tokens.extend(
                [ordinary_relative, ordinary_digest, f"sha256:{ordinary_digest}"]
            )
            items.append(
                {
                    "item_id": "ordinary-item",
                    "staged_path": ordinary_relative,
                    "source_intake_receipt_path": source_receipt,
                }
            )

        paired_path = staged_root / paired_name
        paired_path.write_bytes(paired_bytes)
        paired_relative = paired_path.relative_to(archive_root).as_posix()
        staged_paths.append(paired_relative)
        paired_digest = hashlib.sha256(paired_bytes).hexdigest()
        private_tokens.extend(
            [paired_relative, paired_digest, f"sha256:{paired_digest}"]
        )
        paired_item: dict[str, Any] = {
            "item_id": "paired-item",
            "staged_path": paired_relative,
            "source_intake_receipt_path": source_receipt,
        }

        derived_path: Path | None = None
        derived_raw_digest: str | None = None
        if derived_bytes is not None:
            derived_path = staged_root / derived_name
            derived_path.write_bytes(derived_bytes)
            derived_relative = derived_path.relative_to(archive_root).as_posix()
            staged_paths.append(derived_relative)
            derived_raw_digest = hashlib.sha256(derived_bytes).hexdigest()
            private_tokens.extend(
                [
                    derived_relative,
                    derived_raw_digest,
                    f"sha256:{derived_raw_digest}",
                    str(derived_path),
                ]
            )
            try:
                private_tokens.append(derived_bytes.decode("utf-8-sig"))
            except UnicodeDecodeError:
                pass
            paired_item.update(
                {
                    "derived_text_staged_path": derived_relative,
                    "derivation_kind": "parser",
                    "tool_name": "letter130-parser",
                    "tool_version": "1.0.0",
                    "review_status": "unreviewed",
                    "language": "ko",
                    "born_digital": True,
                }
            )
        items.append(paired_item)

        private_tokens.extend(
            [
                str(archive_root),
                str(staged_root),
                *staged_paths,
            ]
        )
        request_path = self._write_batch_request(
            archive_root,
            items,
            batch_id=batch_id,
        )
        plan = completion_workflows.objet_capture_batch_plan(
            archive_root,
            manifest_path=request_path,
        )
        self.assertTrue(plan["ok"], plan)
        # Install bounded pre-v0.4 capture evidence so the tests below keep
        # exercising the read-only cleanup verifier.  The public v0.4 batch
        # writer and its derived-text register remain deliberately fail-closed.
        public_derived_text_register = archive_services._derived_text_register
        with patch.object(
            archive_services,
            "_derived_text_register",
            archive_services._derived_text_register_legacy_core,
        ):
            applied = completion_workflows._objet_capture_batch_apply_legacy_core(
                archive_root,
                manifest_path=request_path,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter130-test",
            )
        self.assertIs(
            archive_services._derived_text_register,
            public_derived_text_register,
        )
        self.assertTrue(applied["ok"], applied)

        fixture: dict[str, Any] = {
            "archive_root": archive_root,
            "staged_relative": "staging/incoming",
            "staged_paths": staged_paths,
            "private_tokens": list(dict.fromkeys(private_tokens)),
            "applied": applied,
            "derived_path": derived_path,
            "derived_raw_digest": derived_raw_digest,
        }
        if derived_bytes is None:
            return fixture

        capture_receipt_relative = applied["summary"]["capture_receipt_path"]
        self.assertIsInstance(capture_receipt_relative, str)
        capture_receipt_path = archive_root / capture_receipt_relative
        capture_receipt = json.loads(capture_receipt_path.read_text(encoding="utf-8"))
        paired_receipt_item = next(
            item
            for item in capture_receipt["items"]
            if item.get("item_id") == "paired-item"
        )
        derived_result = paired_receipt_item["derived_text"]
        derived_text_id = derived_result["derived_text_id"]
        derived_receipt_relative = derived_result["receipt_path"]
        derived_receipt_path = archive_root / derived_receipt_relative
        derived_records = archive_services.load_derived_text_records(archive_root)
        derived_record = next(
            record
            for record in derived_records
            if record.get("derived_text_id") == derived_text_id
        )
        derived_store_path = archive_root / derived_record["text_logical_key"]
        private_tokens.extend(
            [
                derived_text_id,
                str(derived_store_path),
                str(derived_receipt_path),
                derived_record["text_sha256"],
            ]
        )
        fixture.update(
            {
                "capture_receipt_path": capture_receipt_path,
                "derived_receipt_path": derived_receipt_path,
                "derived_text_id": derived_text_id,
                "derived_record": derived_record,
                "derived_store_path": derived_store_path,
                "derived_manifest_path": (
                    archive_root
                    / archive_services.DERIVED_TEXT_MANIFEST_RELATIVE_PATH
                ),
                "private_tokens": list(dict.fromkeys(private_tokens)),
            }
        )
        return fixture

    @staticmethod
    def _file_snapshot(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    def _assert_result_contract(
        self,
        result: dict[str, Any],
        *,
        expected_entry_count: int,
        expected_state: str,
        expected_reason_codes: list[str],
    ) -> None:
        self.assertEqual(result["schema"], STAGED_CLEANUP_SCHEMA)
        self.assertEqual(result["state"], expected_state)
        self.assertEqual(result["reason_codes"], expected_reason_codes)
        self.assertEqual(len(result["entries"]), expected_entry_count)
        self.assertEqual(
            [entry["entry_ref"] for entry in result["entries"]],
            [
                f"staged-entry:{index:04d}"
                for index in range(1, expected_entry_count + 1)
            ],
        )
        for entry in result["entries"]:
            self.assertEqual(set(entry), ENTRY_KEYS)
            self.assertRegex(entry["entry_ref"], r"^staged-entry:[0-9]{4}$")
            self.assertIsInstance(entry["status"], str)
            self.assertIsInstance(entry["preservation_kind"], str)
            self.assertIsInstance(entry["reason_code"], str)
            self.assertIsInstance(entry["manifest_record_present"], bool)
            self.assertIsInstance(entry["capture_receipt_present"], bool)
            self.assertIsInstance(entry["preserved_bytes_verified"], bool)
            self.assertIsInstance(entry["source_entry_readable"], bool)

        self.assertIn("files", result, "the v0.3.2 legacy projection remains additive")
        self.assertEqual(len(result["files"]), expected_entry_count)
        for legacy_entry in result["files"]:
            self.assertEqual(set(legacy_entry), LEGACY_FILE_KEYS)

    def _assert_content_free_projection(
        self,
        result: dict[str, Any],
        fixture: dict[str, Any],
    ) -> None:
        projection = json.dumps(
            {
                "reason_codes": result["reason_codes"],
                "entries": result["entries"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for token in fixture["private_tokens"]:
            if token:
                self.assertNotIn(token, projection)
        self.assertIsNone(
            re.search(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", projection)
        )
        for forbidden_key in (
            "path",
            "object_id",
            "derived_text_id",
            "sha256",
            "text_sha256",
            "source_text_sha256",
            "body",
            "content",
        ):
            self.assertNotIn(f'"{forbidden_key}"', projection)

    def _rewrite_target_derived_manifest(
        self,
        fixture: dict[str, Any],
        *,
        remove: bool = False,
        make_invalid: bool = False,
    ) -> None:
        records = archive_services.load_derived_text_records(
            fixture["archive_root"]
        )
        rewritten: list[dict[str, Any]] = []
        target_seen = False
        for record in records:
            if record.get("derived_text_id") != fixture["derived_text_id"]:
                rewritten.append(record)
                continue
            target_seen = True
            if remove:
                continue
            candidate = dict(record)
            if make_invalid:
                candidate["derived_text_id"] = "derived-text:sha256:invalid"
            rewritten.append(candidate)
        self.assertTrue(target_seen)
        fixture["derived_manifest_path"].write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n"
                for record in rewritten
            ),
            encoding="utf-8",
        )

    def _mutate_evidence(
        self,
        fixture: dict[str, Any],
        case: str,
    ) -> None:
        if case == "manifest_missing":
            self._rewrite_target_derived_manifest(fixture, remove=True)
        elif case == "manifest_invalid":
            self._rewrite_target_derived_manifest(fixture, make_invalid=True)
        elif case == "store_missing":
            fixture["derived_store_path"].unlink()
        elif case == "store_sha256_mismatch":
            fixture["derived_store_path"].write_bytes(
                b"PRIVATE_LETTER130_CORRUPTED_STORE_9917\n"
            )
        elif case == "capture_receipt_missing":
            fixture["derived_receipt_path"].unlink()
        elif case == "capture_receipt_invalid":
            fixture["derived_receipt_path"].write_text(
                "{\"schema\":",
                encoding="utf-8",
            )
        else:  # pragma: no cover - the closed case table is test-owned.
            self.fail(f"unknown evidence case: {case}")

    def test_mixed_ordinary_and_bom_free_paired_text_are_all_preserved(
        self,
    ) -> None:
        derived_bytes = b"PRIVATE_LETTER130_BOM_FREE_DERIVED_BODY_9917\n"
        with tempfile.TemporaryDirectory(prefix="wom-v03317-cleanup-") as tmp:
            fixture = self._apply_fixture(
                Path(tmp),
                derived_bytes=derived_bytes,
                include_plain_item=True,
                batch_id="letter130-mixed-bom-free",
            )
            before = self._file_snapshot(fixture["archive_root"])
            result = archive_services.staged_cleanup_check(
                fixture["archive_root"],
                fixture["staged_relative"],
            )
            after = self._file_snapshot(fixture["archive_root"])

            self._assert_result_contract(
                result,
                expected_entry_count=3,
                expected_state=SAFE_STATE,
                expected_reason_codes=[],
            )
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["safe_to_cleanup"], result)
            self.assertEqual(
                result["summary"],
                {
                    "preserved": 3,
                    "deferred": 0,
                    "not_preserved": 0,
                    "unsafe": 0,
                },
            )
            self.assertEqual(
                [entry["preservation_kind"] for entry in result["entries"]].count(
                    "objet"
                ),
                2,
            )
            derived_entry = next(
                entry
                for entry in result["entries"]
                if entry["preservation_kind"] == "derived_text_exact_bytes"
            )
            self.assertEqual(derived_entry["status"], "preserved")
            self.assertEqual(
                derived_entry["reason_code"],
                DERIVED_EXACT_PRESERVED_REASON,
            )
            self.assertTrue(derived_entry["manifest_record_present"])
            self.assertTrue(derived_entry["capture_receipt_present"])
            self.assertTrue(derived_entry["preserved_bytes_verified"])
            self.assertTrue(derived_entry["source_entry_readable"])
            for entry in result["entries"]:
                if entry["preservation_kind"] == "objet":
                    self.assertEqual(entry["status"], "preserved")
                    self.assertEqual(entry["reason_code"], OBJET_PRESERVED_REASON)
            self.assertEqual(
                {entry["status"] for entry in result["files"]},
                {"preserved"},
            )
            self.assertEqual(after, before, "the evidence projection remains report-only")
            self._assert_content_free_projection(result, fixture)

            repeated = archive_services.staged_cleanup_check(
                fixture["archive_root"],
                fixture["staged_relative"],
            )
            self.assertEqual(repeated["entries"], result["entries"])
            self.assertEqual(repeated["reason_codes"], result["reason_codes"])

    def test_transcoded_paired_text_keeps_raw_staged_entry_not_preserved(
        self,
    ) -> None:
        text = "PRIVATE_LETTER130_TRANSFORMED_DERIVED_BODY_9917\n"
        cases = {
            "utf8_bom": b"\xef\xbb\xbf" + text.encode("utf-8"),
            "utf16": text.encode("utf-16"),
        }
        for label, derived_bytes in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(
                    prefix=f"wom-v03317-{label}-"
                ) as tmp:
                    fixture = self._apply_fixture(
                        Path(tmp),
                        derived_bytes=derived_bytes,
                        include_plain_item=False,
                        batch_id=f"letter130-{label}",
                    )
                    result = archive_services.staged_cleanup_check(
                        fixture["archive_root"],
                        fixture["staged_relative"],
                    )

                    self._assert_result_contract(
                        result,
                        expected_entry_count=2,
                        expected_state=UNSAFE_STATE,
                        expected_reason_codes=[DERIVED_TRANSFORMED_REASON],
                    )
                    self.assertTrue(result["ok"], result)
                    self.assertFalse(result["safe_to_cleanup"], result)
                    self.assertEqual(result["summary"]["preserved"], 1)
                    self.assertEqual(result["summary"]["not_preserved"], 1)
                    failed = next(
                        entry
                        for entry in result["entries"]
                        if entry["status"] == "not_preserved"
                    )
                    self.assertEqual(failed["preservation_kind"], "none")
                    self.assertEqual(
                        failed["reason_code"],
                        DERIVED_TRANSFORMED_REASON,
                    )
                    self.assertTrue(failed["manifest_record_present"])
                    self.assertTrue(failed["capture_receipt_present"])
                    self.assertFalse(failed["preserved_bytes_verified"])
                    self.assertTrue(failed["source_entry_readable"])
                    self._assert_content_free_projection(result, fixture)

    def test_exact_derived_text_evidence_gaps_have_fixed_content_free_reasons(
        self,
    ) -> None:
        derived_bytes = b"PRIVATE_LETTER130_EVIDENCE_DERIVED_BODY_9917\n"
        for case, expected_reason in EVIDENCE_CASES.items():
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory(
                    prefix=f"wom-v03317-{case}-"
                ) as tmp:
                    fixture = self._apply_fixture(
                        Path(tmp),
                        derived_bytes=derived_bytes,
                        include_plain_item=False,
                        batch_id=f"letter130-{case}",
                    )
                    self._mutate_evidence(fixture, case)
                    result = archive_services.staged_cleanup_check(
                        fixture["archive_root"],
                        fixture["staged_relative"],
                    )

                    self._assert_result_contract(
                        result,
                        expected_entry_count=2,
                        expected_state=UNSAFE_STATE,
                        expected_reason_codes=[expected_reason],
                    )
                    self.assertTrue(result["ok"], result)
                    self.assertFalse(result["safe_to_cleanup"], result)
                    failed = next(
                        entry
                        for entry in result["entries"]
                        if entry["status"] == "not_preserved"
                    )
                    self.assertEqual(failed["preservation_kind"], "none")
                    self.assertEqual(failed["reason_code"], expected_reason)
                    self.assertTrue(failed["source_entry_readable"])

                    if case == "manifest_missing":
                        self.assertFalse(failed["manifest_record_present"])
                        self.assertTrue(failed["preserved_bytes_verified"])
                        self.assertTrue(failed["capture_receipt_present"])
                    elif case == "manifest_invalid":
                        self.assertTrue(failed["manifest_record_present"])
                        self.assertTrue(failed["preserved_bytes_verified"])
                        self.assertTrue(failed["capture_receipt_present"])
                    elif case.startswith("store_"):
                        self.assertTrue(failed["manifest_record_present"])
                        self.assertFalse(failed["preserved_bytes_verified"])
                        self.assertTrue(failed["capture_receipt_present"])
                    elif case == "capture_receipt_missing":
                        self.assertTrue(failed["manifest_record_present"])
                        self.assertTrue(failed["preserved_bytes_verified"])
                        self.assertFalse(failed["capture_receipt_present"])
                    elif case == "capture_receipt_invalid":
                        self.assertTrue(failed["manifest_record_present"])
                        self.assertTrue(failed["preserved_bytes_verified"])
                        self.assertTrue(failed["capture_receipt_present"])
                    self._assert_content_free_projection(result, fixture)

    def test_ordinary_objet_lane_and_legacy_files_projection_remain_compatible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-ordinary-") as tmp:
            fixture = self._apply_fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=False,
                batch_id="letter130-ordinary-only",
            )
            result = archive_services.staged_cleanup_check(
                fixture["archive_root"],
                fixture["staged_relative"],
            )

            self._assert_result_contract(
                result,
                expected_entry_count=1,
                expected_state=SAFE_STATE,
                expected_reason_codes=[],
            )
            self.assertTrue(result["ok"], result)
            self.assertTrue(result["safe_to_cleanup"], result)
            entry = result["entries"][0]
            self.assertEqual(entry["status"], "preserved")
            self.assertEqual(entry["preservation_kind"], "objet")
            self.assertEqual(entry["reason_code"], OBJET_PRESERVED_REASON)
            self.assertTrue(entry["manifest_record_present"])
            self.assertTrue(entry["capture_receipt_present"])
            self.assertTrue(entry["preserved_bytes_verified"])
            self.assertTrue(entry["source_entry_readable"])

            legacy = result["files"][0]
            self.assertEqual(
                legacy["path"],
                fixture["staged_paths"][0].rsplit("/", 1)[-1],
            )
            self.assertEqual(legacy["status"], "preserved")
            self.assertTrue(legacy["manifest_record_present"])
            self.assertTrue(legacy["preserved_bytes_verified"])
            self._assert_content_free_projection(result, fixture)


if __name__ == "__main__":
    unittest.main()
