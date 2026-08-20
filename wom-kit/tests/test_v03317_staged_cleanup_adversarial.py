from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
import sys
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services, completion_workflows

try:  # unittest package discovery
    from . import test_v03317_staged_cleanup_evidence as evidence_tests
except ImportError:  # direct pytest/file execution
    import test_v03317_staged_cleanup_evidence as evidence_tests


class StagedCleanupAdversarialV03317Tests(unittest.TestCase):
    maxDiff = None

    def _fixture(
        self,
        temporary_root: Path,
        *,
        derived_bytes: bytes | None,
        include_plain_item: bool,
        batch_id: str,
    ) -> dict[str, object]:
        helper = evidence_tests.StagedCleanupEvidenceV03317Tests()
        return helper._apply_fixture(
            temporary_root,
            derived_bytes=derived_bytes,
            include_plain_item=include_plain_item,
            batch_id=batch_id,
        )

    @staticmethod
    def _manifest_path(archive_root: Path) -> Path:
        return archive_root / "objects" / "manifests" / "files.jsonl"

    @staticmethod
    def _jsonl(path: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _staged_object_ids(fixture: dict[str, object]) -> set[str]:
        archive_root = fixture["archive_root"]
        assert isinstance(archive_root, Path)
        staged_paths = fixture["staged_paths"]
        assert isinstance(staged_paths, list)
        return {
            "sha256:" + hashlib.sha256((archive_root / relative).read_bytes()).hexdigest()
            for relative in staged_paths
            if isinstance(relative, str)
        }

    @staticmethod
    def _target_derived_entry(result: dict[str, object]) -> dict[str, object]:
        entries = result.get("entries")
        assert isinstance(entries, list)
        candidates = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("preservation_kind") != "objet"
        ]
        if len(candidates) != 1:
            raise AssertionError(f"expected one derived candidate, got: {candidates!r}")
        return candidates[0]

    def test_minimal_fake_manifest_rows_cannot_prove_preservation(self) -> None:
        """Exact store bytes plus object_id/logical_key alone are not authority."""

        with tempfile.TemporaryDirectory(prefix="wom-v03317-fake-manifest-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-fake-manifest",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            object_ids = self._staged_object_ids(fixture)
            fake_rows = []
            for object_id in sorted(object_ids):
                digest = object_id.removeprefix("sha256:")
                fake_rows.append(
                    {
                        "object_id": object_id,
                        "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
                    }
                )
            self._write_jsonl(self._manifest_path(archive_root), fake_rows)

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )

            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertEqual(result["state"], "not_safe_to_cleanup")
            self.assertEqual(result["summary"]["not_preserved"], len(object_ids))
            self.assertTrue(
                all(not entry["manifest_record_present"] for entry in result["entries"])
            )

    def test_ordinary_receipt_missing_and_invalid_are_distinct_from_store_gaps(
        self,
    ) -> None:
        for mode in ("missing", "invalid"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(
                prefix=f"wom-v03317-ordinary-receipt-{mode}-"
            ) as tmp:
                fixture = self._fixture(
                    Path(tmp),
                    derived_bytes=None,
                    include_plain_item=True,
                    batch_id=f"letter130-ordinary-receipt-{mode}",
                )
                archive_root = fixture["archive_root"]
                applied = fixture["applied"]
                self.assertIsInstance(archive_root, Path)
                self.assertIsInstance(applied, dict)
                receipt_relative = applied["summary"]["capture_receipt_path"]
                receipt_path = archive_root / receipt_relative
                if mode == "missing":
                    receipt_path.unlink()
                else:
                    document = json.loads(receipt_path.read_text(encoding="utf-8"))
                    document["items"][0]["stored_sha256_verified"] = False
                    receipt_path.write_text(
                        json.dumps(
                            document,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                result = archive_services.staged_cleanup_check(
                    archive_root,
                    fixture["staged_relative"],
                )

                self.assertTrue(result["ok"], result)
                self.assertFalse(result["safe_to_cleanup"], result)
                expected_reason = f"objet_capture_receipt_{mode}"
                matching = [
                    entry
                    for entry in result["entries"]
                    if entry["reason_code"] == expected_reason
                ]
                self.assertGreaterEqual(len(matching), 1, result)
                self.assertTrue(
                    all(entry["manifest_record_present"] for entry in matching)
                )
                self.assertTrue(
                    all(entry["preserved_bytes_verified"] for entry in matching)
                )
                self.assertTrue(
                    all(
                        entry["capture_receipt_present"] is (mode == "invalid")
                        for entry in matching
                    )
                )

    def test_synthetic_skip_and_invalid_envelope_cannot_authorize_cleanup(
        self,
    ) -> None:
        """Non-booleans and an aborted/unreviewed envelope fail closed."""

        with tempfile.TemporaryDirectory(
            prefix="wom-v03317-ordinary-receipt-envelope-"
        ) as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-ordinary-receipt-envelope",
            )
            archive_root = fixture["archive_root"]
            applied = fixture["applied"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(applied, dict)
            receipt_relative = applied["summary"]["capture_receipt_path"]
            receipt_path = archive_root / receipt_relative
            document = json.loads(receipt_path.read_text(encoding="utf-8"))
            target = document["items"][0]
            target["planned_action"] = "skip_already_present"
            target["action"] = "skip_already_present"
            target["stored_sha256_verified"] = "NOT_A_BOOLEAN"
            target["manifest_record_appended"] = False
            document["ok"] = False
            document["aborted"] = True
            document["reviewed_by"] = None
            document["selection_manifest_sha256"] = "not-a-digest"
            document["blockers"] = ["synthetic_receipt_must_not_authorize_cleanup"]
            receipt_path.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )

            self.assertTrue(result["ok"], result)
            self.assertFalse(result["safe_to_cleanup"], result)
            invalid = [
                entry
                for entry in result["entries"]
                if entry["reason_code"] == "objet_capture_receipt_invalid"
            ]
            self.assertEqual(len(invalid), len(result["entries"]), result)
            self.assertTrue(
                all(entry["capture_receipt_present"] for entry in invalid),
                result,
            )

    def test_partial_outer_receipt_still_proves_its_successful_ordinary_item(
        self,
    ) -> None:
        """A mixed official-shaped receipt is not rejected as a whole."""

        with tempfile.TemporaryDirectory(
            prefix="wom-v03317-ordinary-receipt-partial-"
        ) as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-ordinary-receipt-partial",
            )
            archive_root = fixture["archive_root"]
            applied = fixture["applied"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(applied, dict)
            receipt_relative = applied["summary"]["capture_receipt_path"]
            receipt_path = archive_root / receipt_relative
            document = json.loads(receipt_path.read_text(encoding="utf-8"))
            successful_object_id = document["items"][0]["object_id"]
            blocked = document["items"][1]
            blocked.update(
                planned_action="blocked",
                action="blocked",
                stored_sha256_verified=False,
                manifest_record_appended=False,
                blockers=["source_unreadable"],
                status_class="blocked",
            )
            document["ok"] = False
            document["status_class"] = "partial"
            document["blockers"] = ["source_unreadable"]
            document["summary"] = archive_services.objet_capture_summary(
                document["items"],
                approve=True,
            )
            receipt_path.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )

            self.assertFalse(result["safe_to_cleanup"], result)
            successful = next(
                entry
                for entry in result["files"]
                if entry["object_id"] == successful_object_id
            )
            self.assertEqual(successful["status"], "preserved", result)
            self.assertTrue(successful["manifest_record_present"], result)
            self.assertTrue(successful["preserved_bytes_verified"], result)
            self.assertEqual(result["summary"]["preserved"], 1, result)
            self.assertEqual(result["summary"]["not_preserved"], 1, result)

    def test_conflicting_duplicate_object_id_cannot_hide_behind_one_valid_row(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-duplicate-manifest-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-duplicate-manifest",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            manifest = self._manifest_path(archive_root)
            rows = self._jsonl(manifest)
            object_id = next(iter(self._staged_object_ids(fixture)))
            target = next(row for row in rows if row.get("object_id") == object_id)
            conflicting = dict(target)
            conflicting["logical_key"] = "objects/not-canonical/conflict"
            rows.append(conflicting)
            self._write_jsonl(manifest, rows)

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )

            self.assertFalse(result["safe_to_cleanup"], result)
            matching = [
                entry
                for entry in result["files"]
                if entry.get("object_id") == object_id
            ]
            self.assertEqual(len(matching), 1)
            self.assertFalse(matching[0]["manifest_record_present"])

    def test_ordinary_and_derived_manifest_size_mismatches_refuse_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-size-ordinary-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-size-ordinary",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            manifest = self._manifest_path(archive_root)
            rows = self._jsonl(manifest)
            object_id = next(iter(self._staged_object_ids(fixture)))
            target = next(row for row in rows if row.get("object_id") == object_id)
            target["size_bytes"] = int(target["size_bytes"]) + 1
            self._write_jsonl(manifest, rows)

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            self.assertFalse(result["safe_to_cleanup"], result)
            matching = [
                entry
                for entry in result["files"]
                if entry.get("object_id") == object_id
            ]
            self.assertEqual(len(matching), 1)
            self.assertFalse(matching[0]["manifest_record_present"])

        with tempfile.TemporaryDirectory(prefix="wom-v03317-size-derived-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=b"letter 130 exact derived bytes\n",
                include_plain_item=False,
                batch_id="letter130-size-derived",
            )
            archive_root = fixture["archive_root"]
            derived_manifest = fixture["derived_manifest_path"]
            derived_text_id = fixture["derived_text_id"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(derived_manifest, Path)
            rows = self._jsonl(derived_manifest)
            target = next(
                row for row in rows if row.get("derived_text_id") == derived_text_id
            )
            target["size_bytes"] = int(target["size_bytes"]) + 1
            self._write_jsonl(derived_manifest, rows)

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            target_entry = self._target_derived_entry(result)
            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertEqual(target_entry["reason_code"], "derived_text_manifest_invalid")
            self.assertTrue(target_entry["manifest_record_present"])

    def test_later_official_replay_receipt_is_accepted_by_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-later-replay-") as tmp:
            batch_id = "letter130-later-replay"
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=b"letter 130 later replay exact bytes\n",
                include_plain_item=False,
                batch_id=batch_id,
            )
            archive_root = fixture["archive_root"]
            old_receipt = fixture["derived_receipt_path"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(old_receipt, Path)
            old_receipt.unlink()

            # Receipt names have second-resolution timestamp prefixes. Ensure the
            # official replay proves lookup is content-linked, not old-prefix-linked.
            time.sleep(1.1)
            request_path = archive_root / "staging" / f"{batch_id}.json"
            plan = completion_workflows.objet_capture_batch_plan(
                archive_root,
                manifest_path=request_path,
            )
            self.assertTrue(plan["ok"], plan)
            # Reproduce a historical pre-v0.4 replay receipt without reopening
            # the public compound writer.
            with patch.object(
                archive_services,
                "_derived_text_register",
                archive_services._derived_text_register_legacy_core,
            ):
                applied = (
                    completion_workflows._objet_capture_batch_apply_legacy_core(
                        archive_root,
                        manifest_path=request_path,
                        expected_plan_sha256=plan["summary"]["plan_sha256"],
                        reviewed_by="person:letter130-replay-test",
                    )
                )
            self.assertTrue(applied["ok"], applied)

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            target = self._target_derived_entry(result)
            self.assertTrue(result["safe_to_cleanup"], result)
            self.assertEqual(target["status"], "preserved")
            self.assertTrue(target["capture_receipt_present"])
            self.assertEqual(
                target["reason_code"],
                "derived_text_exact_bytes_manifest_store_and_receipt_verified",
            )
            new_receipts = list(
                (archive_root / archive_services.DERIVED_TEXT_CAPTURE_RECEIPTS_DIR).glob(
                    "*.json"
                )
            )
            self.assertTrue(new_receipts)
            self.assertTrue(all(path.name != old_receipt.name for path in new_receipts))

    def test_official_repair_append_receipt_remains_valid_evidence(self) -> None:
        """A successful official manifest repair must remain cleanup evidence."""

        with tempfile.TemporaryDirectory(prefix="wom-v03317-repair-receipt-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=b"letter 130 repair append exact bytes\n",
                include_plain_item=False,
                batch_id="letter130-repair-receipt",
            )
            archive_root = fixture["archive_root"]
            derived_manifest = fixture["derived_manifest_path"]
            derived_receipt = fixture["derived_receipt_path"]
            derived_record = fixture["derived_record"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(derived_manifest, Path)
            self.assertIsInstance(derived_receipt, Path)
            self.assertIsInstance(derived_record, dict)

            # Leave the verified store in place while removing only the old
            # manifest row and receipt. The official replay must choose its
            # documented repair_append path and mint replacement evidence.
            derived_receipt.unlink()
            rows = [
                row
                for row in self._jsonl(derived_manifest)
                if row.get("derived_text_id") != fixture["derived_text_id"]
            ]
            self._write_jsonl(derived_manifest, rows)

            with patch.object(
                archive_services,
                "_derived_text_register",
                archive_services._derived_text_register_legacy_core,
            ):
                repaired = archive_services._derived_text_capture_run(
                    archive_root,
                    text_file=fixture["derived_path"],
                    source_object_id=derived_record["source_object_id"],
                    derivation_kind=derived_record["derivation_kind"],
                    tool_name=derived_record["tool_name"],
                    tool_version=derived_record["tool_version"],
                    review_status=derived_record["review_status"],
                    approve=True,
                    reviewed_by="person:letter130-repair-test",
                    language=derived_record.get("language"),
                    born_digital=bool(
                        derived_record.get("born_digital", False)
                    ),
                )
            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["planned_action"], "repair_append")
            self.assertEqual(repaired["action"], "repair_appended")
            self.assertTrue(repaired["manifest_record_appended"])
            self.assertIs(repaired["stored_sha256_verified"], False)

            repaired_receipt_path = archive_root / str(repaired["receipt_path"])
            forged_receipt = json.loads(
                repaired_receipt_path.read_text(encoding="utf-8")
            )
            forged_receipt["stored_sha256_verified"] = True
            repaired_receipt_path.write_text(
                json.dumps(
                    forged_receipt,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            forged_result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            forged_target = self._target_derived_entry(forged_result)
            self.assertFalse(forged_result["safe_to_cleanup"], forged_result)
            self.assertEqual(
                forged_target["reason_code"],
                "derived_text_capture_receipt_invalid",
            )

            forged_receipt["stored_sha256_verified"] = False
            repaired_receipt_path.write_text(
                json.dumps(
                    forged_receipt,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            target = self._target_derived_entry(result)
            self.assertTrue(result["safe_to_cleanup"], result)
            self.assertEqual(target["status"], "preserved")
            self.assertTrue(target["capture_receipt_present"])
            self.assertEqual(
                target["reason_code"],
                "derived_text_exact_bytes_manifest_store_and_receipt_verified",
            )

    def test_target_malformed_receipt_is_invalid_but_absence_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-receipt-truth-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=b"letter 130 receipt truth exact bytes\n",
                include_plain_item=False,
                batch_id="letter130-receipt-truth",
            )
            archive_root = fixture["archive_root"]
            receipt = fixture["derived_receipt_path"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(receipt, Path)
            receipt.unlink()

            missing = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            missing_entry = self._target_derived_entry(missing)
            self.assertEqual(
                missing_entry["reason_code"],
                "derived_text_capture_receipt_missing",
            )
            self.assertFalse(missing_entry["capture_receipt_present"])

            receipt.write_text('{"schema":', encoding="utf-8")
            malformed = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            malformed_entry = self._target_derived_entry(malformed)
            self.assertEqual(
                malformed_entry["reason_code"],
                "derived_text_capture_receipt_invalid",
            )
            self.assertTrue(malformed_entry["capture_receipt_present"])

            unrelated = receipt.with_name(receipt.stem.rsplit("-", 1)[0] + "-unrelated.json")
            receipt.replace(unrelated)
            unrelated_result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
            )
            unrelated_entry = self._target_derived_entry(unrelated_result)
            self.assertEqual(
                unrelated_entry["reason_code"],
                "derived_text_capture_receipt_missing",
            )
            self.assertFalse(unrelated_entry["capture_receipt_present"])

    def test_staged_tree_addition_during_inspection_blocks_verdict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-staged-race-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-staged-race",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            real_digest = archive_services._staged_cleanup_stable_file_digest
            injected = False

            def add_after_read(*args: object, **kwargs: object):
                nonlocal injected
                observed = real_digest(*args, **kwargs)
                if not injected and observed[0] is not None:
                    injected = True
                    (archive_root / fixture["staged_relative"] / "appeared-late.bin").write_bytes(
                        b"not part of the initial staging snapshot\n"
                    )
                return observed

            with patch.object(
                archive_services,
                "_staged_cleanup_stable_file_digest",
                side_effect=add_after_read,
            ):
                result = archive_services.staged_cleanup_check(
                    archive_root,
                    fixture["staged_relative"],
                )

            self.assertTrue(injected)
            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["state"], "inspection_blocked")
            self.assertIn("staged_tree_changed_during_inspection", result["blockers"])

    def test_store_evidence_deleted_after_verification_blocks_verdict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-evidence-race-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-evidence-race",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            object_id = next(iter(self._staged_object_ids(fixture)))
            digest = object_id.removeprefix("sha256:")
            store = archive_root / "objects" / "sha256" / digest[:2] / digest
            self.assertTrue(store.is_file())
            real_snapshot = archive_services._staged_cleanup_staged_tree_snapshot
            calls = 0

            def delete_after_final_staged_snapshot(*args: object, **kwargs: object):
                nonlocal calls
                snapshot = real_snapshot(*args, **kwargs)
                calls += 1
                if calls == 2:
                    store.unlink()
                return snapshot

            with patch.object(
                archive_services,
                "_staged_cleanup_staged_tree_snapshot",
                side_effect=delete_after_final_staged_snapshot,
            ):
                result = archive_services.staged_cleanup_check(
                    archive_root,
                    fixture["staged_relative"],
                )

            self.assertEqual(calls, 2)
            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["state"], "inspection_blocked")
            self.assertIn(
                "staged_evidence_changed_during_inspection",
                result["blockers"],
            )

    def test_same_size_same_mtime_in_place_evidence_tamper_blocks_verdict(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-evidence-rehash-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=b"letter 130 exact authority bytes\n",
                include_plain_item=True,
                batch_id="letter130-evidence-rehash",
            )
            archive_root = fixture["archive_root"]
            store = fixture["derived_store_path"]
            self.assertIsInstance(archive_root, Path)
            self.assertIsInstance(store, Path)
            original = store.read_bytes()
            replacement = bytes([original[0] ^ 1]) + original[1:]
            self.assertEqual(len(replacement), len(original))
            original_stat = store.stat()
            real_observation = archive_services._staged_cleanup_store_observation
            injected = False

            def mutate_after_verified_read(*args: object, **kwargs: object):
                nonlocal injected
                observed = real_observation(*args, **kwargs)
                if not injected and observed[0] is True:
                    injected = True
                    store.write_bytes(replacement)
                    os.utime(
                        store,
                        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                    )
                    self.assertEqual(store.stat().st_ino, original_stat.st_ino)
                    self.assertEqual(store.stat().st_size, original_stat.st_size)
                    self.assertEqual(store.stat().st_mtime_ns, original_stat.st_mtime_ns)
                return observed

            with patch.object(
                archive_services,
                "_staged_cleanup_store_observation",
                side_effect=mutate_after_verified_read,
            ):
                result = archive_services.staged_cleanup_check(
                    archive_root,
                    fixture["staged_relative"],
                )

            self.assertTrue(injected)
            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["state"], "inspection_blocked")
            self.assertIn(
                "staged_evidence_changed_during_inspection",
                result["blockers"],
            )

    def test_path_only_deferment_never_authorizes_cleanup_after_byte_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-v03317-deferred-bytes-") as tmp:
            fixture = self._fixture(
                Path(tmp),
                derived_bytes=None,
                include_plain_item=True,
                batch_id="letter130-deferred-bytes",
            )
            archive_root = fixture["archive_root"]
            self.assertIsInstance(archive_root, Path)
            staged_root = archive_root / fixture["staged_relative"]
            deferred_entry = staged_root / "later.txt"
            deferred_entry.write_bytes(b"first unique version\n")
            deferred_path = Path(tmp) / "deferred.json"
            deferred_path.write_text(
                json.dumps({"deferred": ["later.txt"]}),
                encoding="utf-8",
            )
            deferred_entry.write_bytes(b"different unique replacement bytes\n")

            result = archive_services.staged_cleanup_check(
                archive_root,
                fixture["staged_relative"],
                deferred_path=deferred_path,
            )

            self.assertTrue(result["ok"], result)
            self.assertFalse(result["safe_to_cleanup"], result)
            self.assertEqual(result["state"], "not_safe_to_cleanup")
            self.assertEqual(result["summary"]["deferred"], 1)
            self.assertIn(
                "staged_entry_explicitly_deferred",
                result["reason_codes"],
            )


if __name__ == "__main__":
    unittest.main()
