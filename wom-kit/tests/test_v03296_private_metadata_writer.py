from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services
from wom_kit import private_objet_metadata_writer as writer
from wom_kit import private_objet_metadata_writer_contract as contract


OBJECT_HEX = "1" * 64
OBJECT_ID = "sha256:" + OBJECT_HEX
SNAPSHOT = "sha256:" + ("2" * 64)
OBSERVATION = "sha256:" + ("3" * 64)
REVIEW = "sha256:" + ("4" * 64)


def _intake(filename: str = "private-canary.hwpx") -> dict[str, object]:
    return {
        "schema": contract.INTAKE_SCHEMA,
        "object_id": OBJECT_ID,
        "privacy_class": "private_archive",
        "name_observation": {
            "original_filename": filename,
            "name_input_profile": "literal_unicode",
        },
        "media_observation": {
            "value": "application/octet-stream",
            "basis": "source_declared",
        },
        "size_bytes_observed": 123,
        "size_bytes_basis": "source_observed",
        "source_provenance": {
            "source_system": "synthetic",
            "source_record_id": None,
            "source_attachment_id": "private-source-canary",
            "source_snapshot_sha256": SNAPSHOT,
            "observation_evidence_sha256": OBSERVATION,
            "evidence_kind": "source_attachment_metadata",
            "captured_at": "2026-08-01T00:00:00Z",
        },
        "review_evidence": {
            "review_evidence_sha256": REVIEW,
            "review_status": "human_reviewed",
        },
    }


class PrivateObjetMetadataWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "objects" / "manifests").mkdir(parents=True)
        (self.root / "private").mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: synthetic-private-writer\n",
            encoding="utf-8",
        )
        object_row = {
            "object_id": OBJECT_ID,
            "sha256": OBJECT_HEX,
            "logical_key": f"objects/sha256/11/{OBJECT_HEX}",
            "locations": [{"provider": "synthetic"}],
            "provenance": {"source": "synthetic"},
        }
        (self.root / "objects" / "manifests" / "files.jsonl").write_bytes(
            json.dumps(
                object_row,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        self.intake_relative = "private/intake.json"
        self.intake_path = self.root / "private" / "intake.json"
        self.intake_bytes = contract.canonical_json_bytes(_intake())
        self.intake_path.write_bytes(self.intake_bytes)
        self.intake_sha256 = (
            "sha256:" + hashlib.sha256(self.intake_bytes).hexdigest()
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _absent_snapshot(self, name: str) -> writer._FileSnapshot:
        return writer._FileSnapshot(
            self.root / name,
            None,
            writer._absent_state(),
            None,
        )

    def _present_snapshot(
        self,
        name: str,
        raw: bytes,
        *,
        row_count: int = 1,
        link_count: int = 1,
        identity: tuple[int, int] = (7, 1),
        valid: bool = True,
    ) -> writer._FileSnapshot:
        state = (
            writer._present_state(raw, row_count, link_count)
            if valid
            else writer._present_invalid_state(raw, link_count)
        )
        return writer._FileSnapshot(
            self.root / name,
            raw,
            state,
            identity,
        )

    def _classification_fixture(self) -> dict[str, object]:
        dry_run = archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )
        self.assertEqual(dry_run["action"], "append")
        plan = dry_run["plan"]
        row_result = contract.build_private_metadata_row(_intake())
        self.assertTrue(row_result["accepted"])
        row = row_result["row"]
        receipt_document = writer._receipt_for_append_plan(
            plan,
            reviewed_by="operator:unit-test",
            privacy_class="private_archive",
        )
        journal_document = writer._journal_for_receipt(receipt_document)
        self.assertTrue(
            contract.validate_private_metadata_write_journal_semantics(
                journal_document,
                canonical_row=row,
            )["accepted"]
        )
        stored_row = row_result["stored_row_bytes"]
        receipt_raw = contract.stored_json_bytes(receipt_document)
        journal_raw = contract.stored_json_bytes(journal_document)
        before_manifest = self._absent_snapshot("private-before.jsonl")
        after_manifest = self._present_snapshot(
            "private-after.jsonl",
            stored_row,
            identity=(7, 10),
        )
        self.assertEqual(
            before_manifest.state,
            journal_document["private_manifest_before"],
        )
        self.assertEqual(
            after_manifest.state,
            journal_document["private_manifest_after"],
        )
        absent_temps = {
            "journal_temp": self._absent_snapshot("journal.tmp"),
            "manifest_temp": self._absent_snapshot("manifest.tmp"),
            "receipt_temp": self._absent_snapshot("receipt.tmp"),
        }
        return {
            "row": row,
            "canonical_row_sha256": row_result["canonical_row_sha256"],
            "authority_key_sha256": contract.authority_key_sha256(
                OBSERVATION
            ),
            "receipt_document": receipt_document,
            "journal_document": journal_document,
            "stored_row": stored_row,
            "receipt_raw": receipt_raw,
            "journal_raw": journal_raw,
            "before_manifest": before_manifest,
            "after_manifest": after_manifest,
            "absent_receipt": self._absent_snapshot("receipt.json"),
            "absent_journal": self._absent_snapshot("journal.json"),
            "absent_temps": absent_temps,
        }

    def _dry_run(self) -> dict[str, object]:
        return archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )

    def _install_applied_receipt(
        self,
        plan: dict[str, object],
        *,
        receipt: dict[str, object] | None = None,
        intake: dict[str, object] | None = None,
    ) -> dict[str, object]:
        source_intake = intake or _intake()
        row_result = contract.build_private_metadata_row(source_intake)
        self.assertTrue(row_result["accepted"])
        manifest = (
            self.root
            / "objects"
            / "manifests"
            / "private-source-metadata.jsonl"
        )
        manifest.write_bytes(
            (manifest.read_bytes() if manifest.exists() else b"")
            + row_result["stored_row_bytes"]
        )
        durable_receipt = receipt or writer._receipt_for_append_plan(
            plan,
            reviewed_by="operator:unit-test",
            privacy_class=source_intake["privacy_class"],
        )
        receipt_path = self.root / PurePosixPath(
            plan["receipt_relative_path"]
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(contract.stored_json_bytes(durable_receipt))
        for relative in (
            contract.OBJECT_MANIFEST_LOCK,
            contract.PRIVATE_METADATA_LOCK,
        ):
            (self.root / PurePosixPath(relative)).write_bytes(b"")
        return durable_receipt

    def _rehash_journal(
        self,
        journal: dict[str, object],
    ) -> None:
        receipt = journal["receipt_document"]
        receipt["plan_sha256"] = contract.sha256_digest(
            contract.canonical_json_bytes(receipt["plan_binding"])
        )
        journal["plan_sha256"] = receipt["plan_sha256"]
        journal["receipt_sha256"] = contract.sha256_digest(
            contract.stored_json_bytes(receipt)
        )

    def _classify(
        self,
        fixture: dict[str, object],
        *,
        private_manifest: writer._FileSnapshot,
        private_rows: list[dict[str, object]],
        receipt: writer._FileSnapshot,
        receipt_document: dict[str, object] | None,
        journal: writer._FileSnapshot,
        journal_document: dict[str, object] | None,
        temp_snapshots: dict[str, writer._FileSnapshot],
        temp_documents: dict[str, dict[str, object] | None],
    ) -> tuple[str, list[str], str, str, int, int, str | None]:
        return writer._classify_current_action(
            private_manifest=private_manifest,
            private_rows=private_rows,
            row=fixture["row"],
            canonical_row_sha256=fixture["canonical_row_sha256"],
            intake_sha256=self.intake_sha256,
            review_evidence_sha256=REVIEW,
            authority_key_sha256=fixture["authority_key_sha256"],
            receipt=receipt,
            receipt_document=receipt_document,
            journal=journal,
            journal_document=journal_document,
            temp_snapshots=temp_snapshots,
            temp_documents=temp_documents,
        )

    def test_clean_dry_run_builds_closed_content_free_append_plan(self) -> None:
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        result = archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "append")
        self.assertEqual(result["intake_sha256"], self.intake_sha256)
        self.assertEqual(
            result["plan"]["resource_binding"]["basis"],
            "append_worst_case_actor",
        )
        self.assertTrue(
            contract.validate_private_metadata_write_plan_semantics(
                result["plan"]
            )["accepted"]
        )
        serialized = json.dumps(result, ensure_ascii=False)
        for canary in (
            "private-canary.hwpx",
            "private-source-canary",
            self.intake_relative,
            str(self.root),
        ):
            self.assertNotIn(canary, serialized)

    def test_digest_mismatch_and_unsafe_path_are_content_free(self) -> None:
        mismatch = archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256="sha256:" + ("9" * 64),
            dry_run=True,
            approve=False,
        )
        self.assertEqual(mismatch["plan"], None)
        self.assertEqual(
            mismatch["blockers"],
            ["private_metadata_intake_digest_mismatch"],
        )
        unsafe = archive_services.private_objet_source_metadata_write(
            self.root,
            intake="../private-canary.hwpx",
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )
        self.assertEqual(unsafe["plan"], None)
        self.assertEqual(
            unsafe["blockers"],
            ["private_metadata_intake_path_unsafe"],
        )
        self.assertNotIn(
            "private-canary.hwpx",
            json.dumps(unsafe, ensure_ascii=False),
        )

    def test_current_bound_failures_return_one_ordered_preplan_hold(
        self,
    ) -> None:
        with (
            mock.patch.object(writer, "OBJECT_MANIFEST_MAX_ROWS", 0),
            mock.patch.object(writer, "OBJECT_MANIFEST_MAX_ROW_BYTES", 1),
        ):
            result = archive_services.private_objet_source_metadata_write(
                self.root,
                intake=self.intake_relative,
                expected_intake_sha256=self.intake_sha256,
                dry_run=True,
                approve=False,
            )
        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertEqual(
            result["blockers"],
            [
                "private_metadata_object_manifest_rows_limit_exceeded",
                "private_metadata_object_manifest_row_bytes_limit_exceeded",
            ],
        )

    def test_cli_surface_returns_same_plan(self) -> None:
        result = archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "objet-source-metadata-write",
                str(self.root),
                "--intake",
                self.intake_relative,
                "--expected-intake-sha256",
                self.intake_sha256,
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(args.func, archive_cli.command_objet_source_metadata_write)
        cli_result = archive_services.private_objet_source_metadata_write(
            Path(args.archive_root),
            intake=args.intake,
            expected_intake_sha256=args.expected_intake_sha256,
            expected_plan_sha256=args.expected_plan_sha256,
            dry_run=args.dry_run,
            approve=args.approve,
            reviewed_by=args.reviewed_by,
            affirm_private_metadata_reviewed=(
                args.affirm_private_metadata_reviewed
            ),
            affirm_external_writers_quiescent=(
                args.affirm_external_writers_quiescent
            ),
        )
        self.assertEqual(cli_result["plan_sha256"], result["plan_sha256"])

    def test_rollback_accepts_absent_full_and_strict_prefix_manifest_temp(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            identity=(7, 20),
        )
        stored_row = fixture["stored_row"]
        variants = {
            "absent": self._absent_snapshot("manifest.tmp"),
            "full": self._present_snapshot(
                "manifest.tmp",
                stored_row,
                identity=(7, 21),
            ),
            "strict_prefix": self._present_snapshot(
                "manifest.tmp",
                stored_row[:17],
                identity=(7, 22),
                valid=False,
            ),
            "empty_strict_prefix": self._present_snapshot(
                "manifest.tmp",
                b"",
                identity=(7, 23),
                valid=False,
            ),
        }
        for name, manifest_temp in variants.items():
            with self.subTest(name=name):
                temps = dict(fixture["absent_temps"])
                temps["manifest_temp"] = manifest_temp
                classified = self._classify(
                    fixture,
                    private_manifest=fixture["before_manifest"],
                    private_rows=[],
                    receipt=fixture["absent_receipt"],
                    receipt_document=None,
                    journal=journal,
                    journal_document=fixture["journal_document"],
                    temp_snapshots=temps,
                    temp_documents={
                        "journal_temp": None,
                        "manifest_temp": None,
                        "receipt_temp": None,
                    },
                )
                self.assertEqual(classified[0], "rollback_required")
                self.assertEqual(classified[1], [])

    def test_rollback_accepts_standalone_journal_temp_and_exact_twin(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal_temp = self._present_snapshot(
            "journal.tmp",
            fixture["journal_raw"],
            identity=(7, 30),
        )
        temps = dict(fixture["absent_temps"])
        temps["journal_temp"] = journal_temp
        standalone = self._classify(
            fixture,
            private_manifest=fixture["before_manifest"],
            private_rows=[],
            receipt=fixture["absent_receipt"],
            receipt_document=None,
            journal=fixture["absent_journal"],
            journal_document=None,
            temp_snapshots=temps,
            temp_documents={
                "journal_temp": fixture["journal_document"],
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(standalone[0], "rollback_required")

        fixed_twin = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            link_count=2,
            identity=(7, 31),
        )
        temp_twin = self._present_snapshot(
            "journal.tmp",
            fixture["journal_raw"],
            link_count=2,
            identity=(7, 31),
        )
        temps["journal_temp"] = temp_twin
        twin = self._classify(
            fixture,
            private_manifest=fixture["before_manifest"],
            private_rows=[],
            receipt=fixture["absent_receipt"],
            receipt_document=None,
            journal=fixed_twin,
            journal_document=fixture["journal_document"],
            temp_snapshots=temps,
            temp_documents={
                "journal_temp": fixture["journal_document"],
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(twin[0], "rollback_required")

    def test_equal_journal_bytes_under_different_identities_are_manual_hold(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        for link_count in (1, 2):
            with self.subTest(link_count=link_count):
                fixed = self._present_snapshot(
                    "journal.json",
                    fixture["journal_raw"],
                    link_count=link_count,
                    identity=(7, 40),
                )
                temp = self._present_snapshot(
                    "journal.tmp",
                    fixture["journal_raw"],
                    link_count=link_count,
                    identity=(7, 41),
                )
                temps = dict(fixture["absent_temps"])
                temps["journal_temp"] = temp
                classified = self._classify(
                    fixture,
                    private_manifest=fixture["before_manifest"],
                    private_rows=[],
                    receipt=fixture["absent_receipt"],
                    receipt_document=None,
                    journal=fixed,
                    journal_document=fixture["journal_document"],
                    temp_snapshots=temps,
                    temp_documents={
                        "journal_temp": fixture["journal_document"],
                        "manifest_temp": None,
                        "receipt_temp": None,
                    },
                )
                self.assertEqual(classified[0], "manual_hold")
                self.assertEqual(
                    classified[1],
                    ["private_metadata_unexpected_hardlink"],
                )

    def test_recovery_accepts_absent_full_and_strict_prefix_receipt_temp(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            identity=(7, 50),
        )
        variants = {
            "absent": (
                self._absent_snapshot("receipt.tmp"),
                None,
            ),
            "full": (
                self._present_snapshot(
                    "receipt.tmp",
                    fixture["receipt_raw"],
                    identity=(7, 51),
                ),
                fixture["receipt_document"],
            ),
            "strict_prefix": (
                self._present_snapshot(
                    "receipt.tmp",
                    fixture["receipt_raw"][:19],
                    identity=(7, 52),
                    valid=False,
                ),
                None,
            ),
            "empty_strict_prefix": (
                self._present_snapshot(
                    "receipt.tmp",
                    b"",
                    identity=(7, 53),
                    valid=False,
                ),
                None,
            ),
        }
        for name, (receipt_temp, receipt_temp_document) in variants.items():
            with self.subTest(name=name):
                temps = dict(fixture["absent_temps"])
                temps["receipt_temp"] = receipt_temp
                classified = self._classify(
                    fixture,
                    private_manifest=fixture["after_manifest"],
                    private_rows=[fixture["row"]],
                    receipt=fixture["absent_receipt"],
                    receipt_document=None,
                    journal=journal,
                    journal_document=fixture["journal_document"],
                    temp_snapshots=temps,
                    temp_documents={
                        "journal_temp": None,
                        "manifest_temp": None,
                        "receipt_temp": receipt_temp_document,
                    },
                )
                self.assertEqual(classified[0], "recovery_required")
                self.assertEqual(classified[1], [])

    def test_missing_receipt_chain_cannot_grant_recovery(self) -> None:
        fixture = self._classification_fixture()
        (
            self.root / "objects" / "manifests" / "private-source-metadata.jsonl"
        ).write_bytes(fixture["stored_row"])
        (
            self.root
            / "objects"
            / "manifests"
            / ".private-source-metadata-write.journal.json"
        ).write_bytes(fixture["journal_raw"])
        result = archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )
        self.assertEqual(result["action"], "manual_hold")
        if result["plan"] is not None:
            self.assertNotEqual(
                result["plan"]["action"],
                "recovery_required",
            )
            self.assertIsNone(result["plan"]["blocked_context"])
        self.assertIn(
            "private_metadata_receipt_directory_chain_impossible",
            result["blockers"],
        )

    def test_rollback_and_recovery_reject_nonprefix_or_arbitrary_temps(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            identity=(7, 60),
        )
        cases = []

        rollback_nonprefix = dict(fixture["absent_temps"])
        rollback_nonprefix["manifest_temp"] = self._present_snapshot(
            "manifest.tmp",
            b"not-a-prefix",
            identity=(7, 61),
            valid=False,
        )
        cases.append(
            (
                "rollback_nonprefix_manifest",
                fixture["before_manifest"],
                [],
                rollback_nonprefix,
                {
                    "journal_temp": None,
                    "manifest_temp": None,
                    "receipt_temp": None,
                },
            )
        )

        rollback_receipt_temp = dict(fixture["absent_temps"])
        rollback_receipt_temp["receipt_temp"] = self._present_snapshot(
            "receipt.tmp",
            fixture["receipt_raw"],
            identity=(7, 62),
        )
        cases.append(
            (
                "rollback_arbitrary_receipt_temp",
                fixture["before_manifest"],
                [],
                rollback_receipt_temp,
                {
                    "journal_temp": None,
                    "manifest_temp": None,
                    "receipt_temp": fixture["receipt_document"],
                },
            )
        )

        recovery_manifest_temp = dict(fixture["absent_temps"])
        recovery_manifest_temp["manifest_temp"] = self._present_snapshot(
            "manifest.tmp",
            fixture["stored_row"],
            identity=(7, 63),
        )
        cases.append(
            (
                "recovery_arbitrary_manifest_temp",
                fixture["after_manifest"],
                [fixture["row"]],
                recovery_manifest_temp,
                {
                    "journal_temp": None,
                    "manifest_temp": None,
                    "receipt_temp": None,
                },
            )
        )

        recovery_nonprefix = dict(fixture["absent_temps"])
        recovery_nonprefix["receipt_temp"] = self._present_snapshot(
            "receipt.tmp",
            b"not-a-prefix",
            identity=(7, 64),
            valid=False,
        )
        cases.append(
            (
                "recovery_nonprefix_receipt",
                fixture["after_manifest"],
                [fixture["row"]],
                recovery_nonprefix,
                {
                    "journal_temp": None,
                    "manifest_temp": None,
                    "receipt_temp": None,
                },
            )
        )

        for name, manifest, rows, temps, temp_documents in cases:
            with self.subTest(name=name):
                classified = self._classify(
                    fixture,
                    private_manifest=manifest,
                    private_rows=rows,
                    receipt=fixture["absent_receipt"],
                    receipt_document=None,
                    journal=journal,
                    journal_document=fixture["journal_document"],
                    temp_snapshots=temps,
                    temp_documents=temp_documents,
                )
                self.assertEqual(classified[0], "manual_hold")
                self.assertEqual(
                    classified[1],
                    [
                        "private_metadata_recovery_evidence_missing_or_ambiguous"
                    ],
                )

        fixed_twin = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            link_count=2,
            identity=(7, 65),
        )
        journal_temp_twin = self._present_snapshot(
            "journal.tmp",
            fixture["journal_raw"],
            link_count=2,
            identity=(7, 65),
        )
        recovery_twin_temps = dict(fixture["absent_temps"])
        recovery_twin_temps["journal_temp"] = journal_temp_twin
        recovery_with_journal_twin = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=fixture["absent_receipt"],
            receipt_document=None,
            journal=fixed_twin,
            journal_document=fixture["journal_document"],
            temp_snapshots=recovery_twin_temps,
            temp_documents={
                "journal_temp": fixture["journal_document"],
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(recovery_with_journal_twin[0], "manual_hold")
        self.assertEqual(
            recovery_with_journal_twin[1],
            ["private_metadata_recovery_evidence_missing_or_ambiguous"],
        )

    def test_already_applied_accepts_clean_or_exact_receipt_twin(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        clean_receipt = self._present_snapshot(
            "receipt.json",
            fixture["receipt_raw"],
            identity=(7, 70),
        )
        clean = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=clean_receipt,
            receipt_document=fixture["receipt_document"],
            journal=fixture["absent_journal"],
            journal_document=None,
            temp_snapshots=dict(fixture["absent_temps"]),
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(clean[0], "already_applied")

        journal = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            identity=(7, 71),
        )
        residue_without_temp = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=clean_receipt,
            receipt_document=fixture["receipt_document"],
            journal=journal,
            journal_document=fixture["journal_document"],
            temp_snapshots=dict(fixture["absent_temps"]),
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(residue_without_temp[0], "already_applied")

        receipt_twin = self._present_snapshot(
            "receipt.json",
            fixture["receipt_raw"],
            link_count=2,
            identity=(7, 72),
        )
        receipt_temp_twin = self._present_snapshot(
            "receipt.tmp",
            fixture["receipt_raw"],
            link_count=2,
            identity=(7, 72),
        )
        temps = dict(fixture["absent_temps"])
        temps["receipt_temp"] = receipt_temp_twin
        residue = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=receipt_twin,
            receipt_document=fixture["receipt_document"],
            journal=journal,
            journal_document=fixture["journal_document"],
            temp_snapshots=temps,
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": fixture["receipt_document"],
            },
        )
        self.assertEqual(residue[0], "already_applied")

    def test_already_applied_rejects_different_inode_twin_and_extra_temp(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal = self._present_snapshot(
            "journal.json",
            fixture["journal_raw"],
            identity=(7, 80),
        )
        final_receipt = self._present_snapshot(
            "receipt.json",
            fixture["receipt_raw"],
            link_count=2,
            identity=(7, 81),
        )
        different_inode_temp = self._present_snapshot(
            "receipt.tmp",
            fixture["receipt_raw"],
            link_count=2,
            identity=(7, 82),
        )
        temps = dict(fixture["absent_temps"])
        temps["receipt_temp"] = different_inode_temp
        different_inode = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=final_receipt,
            receipt_document=fixture["receipt_document"],
            journal=journal,
            journal_document=fixture["journal_document"],
            temp_snapshots=temps,
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": fixture["receipt_document"],
            },
        )
        self.assertEqual(different_inode[0], "manual_hold")
        self.assertEqual(
            different_inode[1],
            ["private_metadata_unexpected_hardlink"],
        )

        clean_receipt = self._present_snapshot(
            "receipt.json",
            fixture["receipt_raw"],
            identity=(7, 83),
        )
        extra_temp = dict(fixture["absent_temps"])
        extra_temp["manifest_temp"] = self._present_snapshot(
            "manifest.tmp",
            fixture["stored_row"],
            identity=(7, 84),
        )
        arbitrary = self._classify(
            fixture,
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            receipt=clean_receipt,
            receipt_document=fixture["receipt_document"],
            journal=fixture["absent_journal"],
            journal_document=None,
            temp_snapshots=extra_temp,
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(arbitrary[0], "manual_hold")
        self.assertEqual(
            arbitrary[1],
            ["private_metadata_recovery_evidence_missing_or_ambiguous"],
        )

    def test_replay_collects_intake_review_then_collision_reasons(self) -> None:
        fixture = self._classification_fixture()
        incoming_row = deepcopy(fixture["row"])
        incoming_row["size_bytes"] = 456
        incoming_row["label_candidates"][0][
            "review_evidence_sha256"
        ] = "sha256:" + ("8" * 64)
        incoming_digest = contract.sha256_digest(
            contract.canonical_json_bytes(incoming_row)
        )
        receipt = self._present_snapshot(
            "receipt.json",
            fixture["receipt_raw"],
            identity=(7, 90),
        )
        classified = writer._classify_current_action(
            private_manifest=fixture["after_manifest"],
            private_rows=[fixture["row"]],
            row=incoming_row,
            canonical_row_sha256=incoming_digest,
            intake_sha256="sha256:" + ("7" * 64),
            review_evidence_sha256="sha256:" + ("8" * 64),
            authority_key_sha256=fixture["authority_key_sha256"],
            receipt=receipt,
            receipt_document=fixture["receipt_document"],
            journal=fixture["absent_journal"],
            journal_document=None,
            temp_snapshots=dict(fixture["absent_temps"]),
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(classified[0], "manual_hold")
        self.assertEqual(
            classified[1],
            [
                "private_metadata_authority_intake_digest_mismatch",
                "private_metadata_authority_review_evidence_digest_mismatch",
                "private_metadata_observation_authority_collision",
            ],
        )

    def test_valid_shape_journal_cross_field_mismatch_is_exact_reason(
        self,
    ) -> None:
        fixture = self._classification_fixture()
        journal_document = deepcopy(fixture["journal_document"])
        journal_document["private_manifest_after"] = writer._absent_state()
        self.assertTrue(
            contract.validate_private_metadata_write_journal(
                journal_document
            )["accepted"]
        )
        self.assertFalse(
            contract.validate_private_metadata_write_journal_semantics(
                journal_document
            )["accepted"]
        )
        journal_raw = contract.stored_json_bytes(journal_document)
        journal = self._present_snapshot(
            "journal.json",
            journal_raw,
            identity=(7, 91),
        )
        classified = self._classify(
            fixture,
            private_manifest=fixture["before_manifest"],
            private_rows=[],
            receipt=fixture["absent_receipt"],
            receipt_document=None,
            journal=journal,
            journal_document=journal_document,
            temp_snapshots=dict(fixture["absent_temps"]),
            temp_documents={
                "journal_temp": None,
                "manifest_temp": None,
                "receipt_temp": None,
            },
        )
        self.assertEqual(classified[0], "manual_hold")
        self.assertEqual(
            classified[1],
            ["private_metadata_journal_cross_field_mismatch"],
        )

    def test_historical_receipt_accepts_exact_object_manifest_prefix_growth(
        self,
    ) -> None:
        initial = self._dry_run()
        self.assertEqual(initial["action"], "append")
        self._install_applied_receipt(initial["plan"])
        later_hex = "a" * 64
        later_row = {
            "object_id": "sha256:" + later_hex,
            "sha256": later_hex,
            "logical_key": f"objects/sha256/aa/{later_hex}",
            "locations": [{"provider": "synthetic"}],
            "provenance": {"source": "synthetic-later-append"},
        }
        object_manifest = (
            self.root / "objects" / "manifests" / "files.jsonl"
        )
        object_manifest.write_bytes(
            object_manifest.read_bytes()
            + json.dumps(
                later_row,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )

        replay = self._dry_run()

        self.assertTrue(replay["ok"])
        self.assertEqual(replay["action"], "already_applied")
        self.assertEqual(replay["blockers"], [])

    def test_complete_real_receipt_chain_uses_one_linear_object_parse(
        self,
    ) -> None:
        object_manifest = (
            self.root / "objects" / "manifests" / "files.jsonl"
        )
        object_manifest.write_bytes(b"")
        prior_receipt_count = 12
        incoming: dict[str, object] | None = None
        for index in range(prior_receipt_count + 1):
            object_hex = f"{index + 100:064x}"
            object_id = "sha256:" + object_hex
            object_row = {
                "object_id": object_id,
                "sha256": object_hex,
                "logical_key": (
                    f"objects/sha256/{object_hex[:2]}/{object_hex}"
                ),
                "locations": [{"provider": "synthetic"}],
                "provenance": {"source": "linear-chain-proof"},
            }
            object_manifest.write_bytes(
                object_manifest.read_bytes()
                + json.dumps(
                    object_row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            intake = _intake(f"linear-chain-{index}.bin")
            intake["object_id"] = object_id
            intake["source_provenance"]["source_attachment_id"] = (
                f"linear-chain-{index}"
            )
            intake["source_provenance"][
                "observation_evidence_sha256"
            ] = "sha256:" + f"{index + 1000:064x}"
            intake["review_evidence"]["review_evidence_sha256"] = (
                "sha256:" + f"{index + 2000:064x}"
            )
            intake_bytes = contract.canonical_json_bytes(intake)
            self.intake_path.write_bytes(intake_bytes)
            self.intake_sha256 = contract.sha256_digest(intake_bytes)
            if index == prior_receipt_count:
                incoming = intake
                break
            plan_result = self._dry_run()
            self.assertEqual(plan_result["action"], "append")
            self._install_applied_receipt(
                plan_result["plan"],
                intake=intake,
            )

        assert incoming is not None
        row_result = contract.build_private_metadata_row(incoming)
        self.assertTrue(row_result["accepted"])
        work = writer._ObjectManifestAuthorityWork()
        context, _, _ = writer._build_planning_context(
            self.root.resolve(),
            archive_id="synthetic-private-writer",
            intake=incoming,
            intake_sha256=self.intake_sha256,
            row_result=row_result,
            object_manifest_authority_work=work,
        )

        expected_rows = prior_receipt_count + 1
        self.assertEqual(context.action, "append")
        self.assertEqual(context.authority_chain_validation, "valid_complete")
        self.assertEqual(work.parsed_bytes, len(object_manifest.read_bytes()))
        self.assertEqual(work.parsed_rows, expected_rows)
        self.assertEqual(work.prefix_lookups, expected_rows)
        self.assertEqual(work.prefix_lookup_units, expected_rows)

    def test_forged_non_prefix_receipt_is_exact_preplan_hold(self) -> None:
        initial = self._dry_run()
        receipt = writer._receipt_for_append_plan(
            initial["plan"],
            reviewed_by="operator:unit-test",
            privacy_class="private_archive",
        )
        forged_state = deepcopy(receipt["object_manifest_state"])
        forged_state["sha256"] = "sha256:" + ("f" * 64)
        receipt["object_manifest_state"] = forged_state
        receipt["plan_binding"]["object_manifest_state"] = deepcopy(
            forged_state
        )
        receipt["plan_sha256"] = contract.sha256_digest(
            contract.canonical_json_bytes(receipt["plan_binding"])
        )
        self.assertTrue(
            contract.validate_private_metadata_write_receipt_semantics(
                receipt
            )["accepted"]
        )
        self._install_applied_receipt(initial["plan"], receipt=receipt)

        result = self._dry_run()

        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_receipt_plan_authority_chain_mismatch"],
        )

    def test_foreign_archive_receipt_is_exact_preplan_hold(self) -> None:
        initial = self._dry_run()
        self._install_applied_receipt(initial["plan"])
        (self.root / "archive.yml").write_text(
            "archive_id: synthetic-private-writer-b\n",
            encoding="utf-8",
        )

        result = self._dry_run()

        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_receipt_plan_authority_chain_mismatch"],
        )

    def test_forged_embedded_receipt_authority_is_exact_preplan_hold(
        self,
    ) -> None:
        initial = self._dry_run()
        receipt = writer._receipt_for_append_plan(
            initial["plan"],
            reviewed_by="operator:unit-test",
            privacy_class="private_archive",
        )
        forged_authority = "sha256:" + ("f" * 64)
        receipt["plan_binding"]["authority_key_sha256"] = forged_authority
        receipt["plan_binding"]["receipt_relative_path"] = (
            contract.receipt_relative_path(forged_authority)
        )
        receipt["plan_sha256"] = contract.sha256_digest(
            contract.canonical_json_bytes(receipt["plan_binding"])
        )
        self._install_applied_receipt(initial["plan"], receipt=receipt)

        result = self._dry_run()

        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_receipt_plan_authority_chain_mismatch"],
        )

    def test_contextually_foreign_journals_are_exact_preplan_holds(
        self,
    ) -> None:
        initial = self._dry_run()
        original_receipt = writer._receipt_for_append_plan(
            initial["plan"],
            reviewed_by="operator:unit-test",
            privacy_class="private_archive",
        )
        original_journal = writer._journal_for_receipt(original_receipt)
        fixed_journal = (
            self.root
            / "objects"
            / "manifests"
            / ".private-source-metadata-write.journal.json"
        )

        def foreign_archive(journal: dict[str, object]) -> None:
            receipt = journal["receipt_document"]
            receipt["archive_id"] = "synthetic-private-writez"
            receipt["plan_binding"]["archive_id"] = (
                "synthetic-private-writez"
            )

        def foreign_intake(journal: dict[str, object]) -> None:
            digest = "sha256:" + ("e" * 64)
            receipt = journal["receipt_document"]
            receipt["intake_sha256"] = digest
            receipt["plan_binding"]["intake_sha256"] = digest

        def foreign_object(journal: dict[str, object]) -> None:
            digest = "sha256:" + ("d" * 64)
            receipt = journal["receipt_document"]
            receipt["object_id"] = digest
            receipt["plan_binding"]["object_id"] = digest

        def forged_object_predecessor(
            journal: dict[str, object],
        ) -> None:
            state = deepcopy(journal["object_manifest_state"])
            state["sha256"] = "sha256:" + ("c" * 64)
            journal["object_manifest_state"] = state
            receipt = journal["receipt_document"]
            receipt["object_manifest_state"] = deepcopy(state)
            receipt["plan_binding"]["object_manifest_state"] = deepcopy(
                state
            )

        for mutate in (
            foreign_archive,
            foreign_intake,
            foreign_object,
            forged_object_predecessor,
        ):
            with self.subTest(mutation=mutate.__name__):
                journal = deepcopy(original_journal)
                mutate(journal)
                self._rehash_journal(journal)
                self.assertTrue(
                    contract.validate_private_metadata_write_journal_semantics(
                        journal
                    )["accepted"]
                )
                fixed_journal.write_bytes(
                    contract.stored_json_bytes(journal)
                )

                result = self._dry_run()

                self.assertEqual(result["action"], "manual_hold")
                self.assertIsNone(result["plan"])
                self.assertIsNone(result["plan_sha256"])
                self.assertIsNone(result["hold_context"])
                self.assertEqual(
                    result["blockers"],
                    ["private_metadata_journal_cross_field_mismatch"],
                )
                fixed_journal.unlink()

    def test_foreign_private_predecessor_journal_is_exact_preplan_hold(
        self,
    ) -> None:
        current_intake = _intake()
        current_bytes = contract.canonical_json_bytes(current_intake)
        current_sha256 = contract.sha256_digest(current_bytes)
        prior_intake = deepcopy(current_intake)
        prior_intake["name_observation"]["original_filename"] = "prior.hwpx"
        prior_intake["source_provenance"]["source_attachment_id"] = (
            "prior-source-canary"
        )
        prior_intake["source_provenance"][
            "observation_evidence_sha256"
        ] = "sha256:" + ("8" * 64)
        prior_intake["review_evidence"]["review_evidence_sha256"] = (
            "sha256:" + ("9" * 64)
        )
        prior_bytes = contract.canonical_json_bytes(prior_intake)
        self.intake_path.write_bytes(prior_bytes)
        self.intake_sha256 = contract.sha256_digest(prior_bytes)
        prior_plan = self._dry_run()
        self.assertEqual(prior_plan["action"], "append")
        self._install_applied_receipt(
            prior_plan["plan"],
            intake=prior_intake,
        )

        self.intake_path.write_bytes(current_bytes)
        self.intake_sha256 = current_sha256
        current_plan = self._dry_run()
        self.assertEqual(current_plan["action"], "append")
        receipt = writer._receipt_for_append_plan(
            current_plan["plan"],
            reviewed_by="operator:unit-test",
            privacy_class="private_archive",
        )
        journal = writer._journal_for_receipt(receipt)
        self.assertTrue(
            contract.validate_private_metadata_write_journal_semantics(
                journal
            )["accepted"]
        )

        (
            self.root
            / "objects"
            / "manifests"
            / "private-source-metadata.jsonl"
        ).unlink()
        shutil.rmtree(self.root / "receipts")
        for relative in (
            contract.OBJECT_MANIFEST_LOCK,
            contract.PRIVATE_METADATA_LOCK,
        ):
            (self.root / PurePosixPath(relative)).unlink()
        (
            self.root
            / "objects"
            / "manifests"
            / ".private-source-metadata-write.journal.json"
        ).write_bytes(contract.stored_json_bytes(journal))

        result = self._dry_run()

        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_journal_cross_field_mismatch"],
        )


if __name__ == "__main__":
    unittest.main()
