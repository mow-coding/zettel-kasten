from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, completion_workflows
from wom_kit import target_sha_evolution


ARCHIVE_ID = "archive:personal:sha-evolution-test"
ZETTEL_ID = "zet_sha_evolution_test"
ZETTEL_PATH = f"zettels/{ZETTEL_ID}.md"


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


class TargetShaEvolutionIndexTests(unittest.TestCase):
    @staticmethod
    def _archive(parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            f"archive_id: {ARCHIVE_ID}\n",
            encoding="utf-8",
        )
        (root / "receipts" / "objects" / "zettel-links" / "reverts").mkdir(
            parents=True
        )
        return root

    @staticmethod
    def _write_link_receipt(
        root: Path,
        *,
        before_sha256: str,
        after_sha256: str,
        created_at: str,
        object_label: str,
        generation: int = 1,
        document_generation: int | None = None,
        filename_prefix: str | None = None,
    ) -> tuple[Path, bytes]:
        object_id = f"sha256:{_sha('objet:' + object_label)}"
        role = "evidence"
        link_seed = {
            "archive_id": ARCHIVE_ID,
            "zettel_id": ZETTEL_ID,
            "object_id": object_id,
            "role": role,
        }
        link_digest = hashlib.sha256(
            completion_workflows._canonical_json_bytes(link_seed)
        ).hexdigest()
        transaction_sha256 = _sha("transaction:" + object_label)
        swap, previous = archive_services.regular_file_canonical_swap_paths(
            Path(ZETTEL_PATH),
            f"sha256:{transaction_sha256}",
            swap_suffix=(
                completion_workflows.ZETTEL_OBJET_LINK_CANONICAL_SWAP_SUFFIX
            ),
        )
        receipt = {
            "schema": completion_workflows.ZETTEL_OBJET_LINK_RECEIPT_SCHEMA,
            "action": "add_zettel_objet_link",
            "archive_id": ARCHIVE_ID,
            "zettel_id": ZETTEL_ID,
            "zettel_path": ZETTEL_PATH,
            "object_id": object_id,
            "role": role,
            "label_sha256": (
                completion_workflows.ZETTEL_OBJET_LINK_ABSENT_LABEL_SHA256
            ),
            "link_id": f"asset:sha256:{link_digest}",
            "plan_sha256": _sha("plan:" + object_label),
            "manifest_record_set_sha256": _sha(
                "manifest:" + object_label
            ),
            "receipt_generation": (
                generation
                if document_generation is None
                else document_generation
            ),
            "before_zettel_sha256": before_sha256,
            "after_zettel_sha256": after_sha256,
            "before_snapshot_path": (
                f"{completion_workflows.ZETTEL_OBJET_LINK_SNAPSHOT_DIR}/"
                f"{before_sha256}.zettel.md"
            ),
            "snapshot_state": "absent",
            "snapshot_sha256": before_sha256,
            "support_effect_set_sha256": _sha("support:" + object_label),
            "transaction_sha256": transaction_sha256,
            "canonical_swap_path": swap.as_posix(),
            "canonical_previous_path": previous.as_posix(),
            "canonical_swap_state": "clean",
            "control_artifact_path": (
                "receipts/objects/zettel-links/.locks/"
                f"{_sha('lock:' + object_label)}.lock"
            ),
            "control_artifact_state": "absent",
            "control_artifact_sha256": (
                completion_workflows.ZETTEL_OBJET_LINK_LOCK_SHA256
            ),
            "reviewed_by": "person:synthetic-test",
            "created_at": created_at,
            "exact_human_approval": {
                "schema_version": (
                    "wom-kit/operation-exact-human-approval/v0.1"
                ),
                "operation": "zettel_objet_link",
                "plan_sha256": f"sha256:{_sha('approval-plan:' + object_label)}",
                "target_binding_sha256": (
                    f"sha256:{_sha('approval-target:' + object_label)}"
                ),
                "exact_human_approval": {
                    "schema_version": (
                        "wom-kit/exact-human-approval-reference/v0.1"
                    ),
                    "approval_id": f"approval_{_sha('approval:' + object_label)[:32]}",
                    "context_sha256": (
                        f"sha256:{_sha('context:' + object_label)}"
                    ),
                    "approval_authority_sha256": (
                        f"sha256:{_sha('authority:' + object_label)}"
                    ),
                    "one_use": True,
                },
            },
            "privacy": {
                "label_included": False,
                "zettel_body_included": False,
                "object_bytes_read": False,
                "provider_called": False,
            },
        }
        raw = completion_workflows._canonical_json_bytes(receipt)
        prefix = filename_prefix or link_digest[:24]
        path = (
            root
            / "receipts"
            / "objects"
            / "zettel-links"
            / f"link.{prefix}.g{generation:04d}.json"
        )
        path.write_bytes(raw)
        return path, raw

    @staticmethod
    def _write_revert_receipt(
        root: Path,
        *,
        source_raw: bytes,
        restored_sha256: str,
        created_at: str,
        source_sha256_override: str | None = None,
    ) -> Path:
        source_sha256 = source_sha256_override or hashlib.sha256(
            source_raw
        ).hexdigest()
        receipt = {
            "schema": (
                completion_workflows.ZETTEL_OBJET_LINK_REVERT_RECEIPT_SCHEMA
            ),
            "action": "restore_zettel_before_objet_link",
            "archive_id": ARCHIVE_ID,
            "zettel_id": ZETTEL_ID,
            "source_receipt_sha256": source_sha256,
            "revert_plan_sha256": _sha("revert-plan:" + created_at),
            "restored_zettel_sha256": restored_sha256,
            "reviewed_by": "person:synthetic-test",
            "created_at": created_at,
        }
        path = (
            root
            / "receipts"
            / "objects"
            / "zettel-links"
            / "reverts"
            / f"{source_sha256[:24]}.json"
        )
        path.write_bytes(completion_workflows._canonical_json_bytes(receipt))
        return path

    @staticmethod
    def _evidence(
        index: target_sha_evolution.ZettelObjetTargetShaEvolutionIndex,
        *,
        expected: str,
        current: str,
        cutoff: str = "2026-08-27T00:00:00Z",
    ) -> dict[str, object] | None:
        return index.evidence(
            archive_id=ARCHIVE_ID,
            zettel_id=ZETTEL_ID,
            zettel_path=ZETTEL_PATH,
            expected_sha256=expected,
            current_sha256=current,
            cutoff_created_at=cutoff,
        )

    def test_one_hop_returns_only_internal_exact_byte_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp)).resolve()
            before = _sha("before")
            after = _sha("after")
            self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=after,
                created_at="2026-08-27T00:00:01Z",
                object_label="one-hop",
            )

            index = target_sha_evolution.build_zettel_objet_target_sha_evolution_index(
                root
            )
            evidence = self._evidence(index, expected=before, current=after)
            assessment = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=before,
                current_sha256=after,
                cutoff_created_at="2026-08-27T00:00:00Z",
            )

            self.assertTrue(index.complete, index.blockers)
            self.assertEqual(
                index.summary()["receipt_counts"],
                {
                    "receipt_directory_entries": 2,
                    "receipt_candidates": 1,
                    "validated_link_receipts": 1,
                    "revert_directory_entries": 0,
                    "revert_candidates": 0,
                    "validated_revert_receipts": 0,
                },
            )
            self.assertTrue(assessment["proven"])
            self.assertFalse(assessment["ambiguous"])
            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(
                evidence["state"],
                "exact_byte_transition_internal_evidence",
            )
            self.assertEqual(evidence["transition_count"], 1)
            self.assertEqual(evidence["transition_kinds"], ["zettel_objet_link"])
            self.assertEqual(
                evidence["cryptographic_authentication"],
                {
                    "claimed": False,
                    "mac_verified": False,
                    "signature_verified": False,
                },
            )

    def test_multi_hop_requires_one_chronological_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp)).resolve()
            first = _sha("first")
            second = _sha("second")
            third = _sha("third")
            self._write_link_receipt(
                root,
                before_sha256=first,
                after_sha256=second,
                created_at="2026-08-27T00:00:01Z",
                object_label="multi-one",
            )
            self._write_link_receipt(
                root,
                before_sha256=second,
                after_sha256=third,
                created_at="2026-08-27T00:00:02Z",
                object_label="multi-two",
            )

            index = target_sha_evolution.build_zettel_objet_target_sha_evolution_index(
                root
            )
            evidence = self._evidence(index, expected=first, current=third)

            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(evidence["transition_count"], 2)
            self.assertEqual(
                evidence["transition_kinds"],
                ["zettel_objet_link", "zettel_objet_link"],
            )

    def test_revert_is_bound_to_source_bytes_and_reverses_the_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            before = _sha("before-revert")
            after = _sha("after-revert")
            _path, source_raw = self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=after,
                created_at="2026-08-27T00:00:01Z",
                object_label="reverted",
            )
            self._write_revert_receipt(
                root,
                source_raw=source_raw,
                restored_sha256=before,
                created_at="2026-08-27T00:00:03Z",
            )

            index = target_sha_evolution.build_zettel_objet_target_sha_evolution_index(
                root
            )
            evidence = self._evidence(
                index,
                expected=after,
                current=before,
                cutoff="2026-08-27T00:00:02Z",
            )

            self.assertTrue(index.complete, index.blockers)
            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(
                evidence["transition_kinds"],
                ["zettel_objet_link_revert"],
            )
            cycle = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=before,
                current_sha256=_sha("unreachable-after-cycle"),
                cutoff_created_at="2026-08-27T00:00:00Z",
            )
            self.assertEqual(
                cycle["reason_code"],
                "target_sha_transition_cycle_ambiguous",
            )
            self.assertTrue(cycle["ambiguous"])
            # Before the link, following both link and revert would cycle back
            # to the starting digest, so it must not be called evolution.
            self.assertIsNone(
                self._evidence(index, expected=before, current=before)
            )

    def test_branch_is_ambiguous_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            before = _sha("branch-before")
            first_after = _sha("branch-after-one")
            second_after = _sha("branch-after-two")
            self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=first_after,
                created_at="2026-08-27T00:00:01Z",
                object_label="branch-one",
            )
            self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=second_after,
                created_at="2026-08-27T00:00:02Z",
                object_label="branch-two",
            )

            index = target_sha_evolution.build_zettel_objet_target_sha_evolution_index(
                root
            )
            assessment = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=before,
                current_sha256=first_after,
                cutoff_created_at="2026-08-27T00:00:00Z",
            )

            self.assertTrue(index.complete, index.blockers)
            self.assertEqual(
                assessment["reason_code"],
                "target_sha_transition_branch_ambiguous",
            )
            self.assertTrue(assessment["ambiguous"])
            self.assertFalse(assessment["proven"])
            self.assertIsNone(
                self._evidence(index, expected=before, current=first_after)
            )
            self.assertIsNone(
                self._evidence(index, expected=before, current=second_after)
            )

    def test_cutoff_excludes_older_or_equal_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            first = _sha("cutoff-first")
            second = _sha("cutoff-second")
            third = _sha("cutoff-third")
            self._write_link_receipt(
                root,
                before_sha256=first,
                after_sha256=second,
                created_at="2026-08-27T00:00:01Z",
                object_label="cutoff-old",
            )
            self._write_link_receipt(
                root,
                before_sha256=second,
                after_sha256=third,
                created_at="2026-08-27T00:00:03Z",
                object_label="cutoff-new",
            )

            index = target_sha_evolution.build_zettel_objet_target_sha_evolution_index(
                root
            )
            cutoff_assessment = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=first,
                current_sha256=third,
                cutoff_created_at="2026-08-27T00:00:01Z",
            )

            self.assertEqual(
                cutoff_assessment["reason_code"],
                "expected_sha_not_observed_after_cutoff",
            )
            self.assertEqual(
                cutoff_assessment["cutoff"]["eligible_transition_count"],
                1,
            )
            self.assertIsNone(
                self._evidence(
                    index,
                    expected=first,
                    current=third,
                    cutoff="2026-08-27T00:00:01Z",
                )
            )
            self.assertIsNotNone(
                self._evidence(
                    index,
                    expected=second,
                    current=third,
                    cutoff="2026-08-27T00:00:01Z",
                )
            )

    def test_assessment_distinguishes_mismatch_unchanged_and_bad_cutoff(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            expected = _sha("assessment-expected")
            current = _sha("assessment-current")
            index = (
                target_sha_evolution
                .build_zettel_objet_target_sha_evolution_index(root)
            )

            mismatch = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=expected,
                current_sha256=current,
                cutoff_created_at="2026-08-27T00:00:00Z",
            )
            unchanged = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=expected,
                current_sha256=expected,
                cutoff_created_at="2026-08-27T00:00:00Z",
            )
            bad_cutoff = index.assess(
                archive_id=ARCHIVE_ID,
                zettel_id=ZETTEL_ID,
                zettel_path=ZETTEL_PATH,
                expected_sha256=expected,
                current_sha256=current,
                cutoff_created_at="not-a-timestamp",
            )

            self.assertEqual(mismatch["state"], "target_sha_mismatch_unproven")
            self.assertEqual(
                mismatch["reason_code"],
                "no_validated_target_transitions",
            )
            self.assertEqual(unchanged["state"], "target_sha_unchanged")
            self.assertEqual(
                bad_cutoff["state"],
                "target_sha_evolution_query_invalid",
            )
            self.assertFalse(bad_cutoff["cutoff"]["applied"])

    def test_filename_generation_and_source_sha_tampering_fail_closed(self) -> None:
        cases = ("generation", "prefix", "source_sha")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = self._archive(Path(tmp))
                before = _sha(f"{case}:before")
                after = _sha(f"{case}:after")
                _path, source_raw = self._write_link_receipt(
                    root,
                    before_sha256=before,
                    after_sha256=after,
                    created_at="2026-08-27T00:00:01Z",
                    object_label=case,
                    document_generation=(2 if case == "generation" else None),
                    filename_prefix=("f" * 24 if case == "prefix" else None),
                )
                if case == "source_sha":
                    self._write_revert_receipt(
                        root,
                        source_raw=source_raw,
                        restored_sha256=before,
                        created_at="2026-08-27T00:00:02Z",
                        source_sha256_override=_sha("not-the-source-receipt"),
                    )

                index = (
                    target_sha_evolution
                    .build_zettel_objet_target_sha_evolution_index(root)
                )

                self.assertFalse(index.complete)
                assessment = index.assess(
                    archive_id=ARCHIVE_ID,
                    zettel_id=ZETTEL_ID,
                    zettel_path=ZETTEL_PATH,
                    expected_sha256=before,
                    current_sha256=after,
                    cutoff_created_at="2026-08-27T00:00:00Z",
                )
                self.assertEqual(
                    assessment["state"],
                    "target_sha_evolution_index_incomplete",
                )
                self.assertFalse(assessment["proven"])
                self.assertIsNone(
                    self._evidence(index, expected=before, current=after)
                )

    def test_directories_are_scanned_once_and_queries_do_not_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            before = _sha("scan-before")
            after = _sha("scan-after")
            _path, source_raw = self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=after,
                created_at="2026-08-27T00:00:01Z",
                object_label="scan-once",
            )
            self._write_revert_receipt(
                root,
                source_raw=source_raw,
                restored_sha256=before,
                created_at="2026-08-27T00:00:03Z",
            )
            real_scandir = os.scandir
            scans: list[object] = []

            def observed_scandir(path: object):
                scans.append(path)
                return real_scandir(path)

            with mock.patch.object(
                target_sha_evolution.os,
                "scandir",
                side_effect=observed_scandir,
            ):
                index = (
                    target_sha_evolution
                    .build_zettel_objet_target_sha_evolution_index(root)
                )
                self._evidence(index, expected=before, current=after)
                self._evidence(
                    index,
                    expected=after,
                    current=before,
                    cutoff="2026-08-27T00:00:02Z",
                )

            self.assertTrue(index.complete, index.blockers)
            self.assertEqual(len(scans), 2)
            self.assertEqual(
                index.summary()["receipt_counts"],
                {
                    "receipt_directory_entries": 2,
                    "receipt_candidates": 1,
                    "validated_link_receipts": 1,
                    "revert_directory_entries": 1,
                    "revert_candidates": 1,
                    "validated_revert_receipts": 1,
                },
            )

    def test_doctor_mint_target_one_hop_becomes_content_private_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            target = root / ZETTEL_PATH
            target.parent.mkdir(parents=True)
            target.write_text("current canonical bytes\n", encoding="utf-8")
            expected = _sha("mint-anchor")
            current = hashlib.sha256(target.read_bytes()).hexdigest()
            self._write_link_receipt(
                root,
                before_sha256=expected,
                after_sha256=current,
                created_at="2026-08-27T00:00:02Z",
                object_label="doctor-one-hop",
            )
            receipt_path = root / "receipts" / "mint" / "one.mint.json"
            receipt_path.parent.mkdir(parents=True)
            private_id = "zet_private_must_not_echo"
            receipt = {
                "action": "mint_zettel",
                "archive_id": ARCHIVE_ID,
                "timestamp": "2026-08-27T00:00:01Z",
                "zettel": {"id": ZETTEL_ID, "title": "PRIVATE TITLE"},
                "target": {
                    "path": ZETTEL_PATH,
                    "sha256": expected,
                    "private_marker": private_id,
                },
            }
            doctor = archive_cli.Doctor(root)
            real_builder = (
                target_sha_evolution
                .build_zettel_objet_target_sha_evolution_index
            )
            with mock.patch.object(
                target_sha_evolution,
                "build_zettel_objet_target_sha_evolution_index",
                wraps=real_builder,
            ) as build_index:
                doctor._check_mint_receipt_file_ref(
                    receipt,
                    receipt_path,
                    "target",
                )
                doctor._check_mint_receipt_file_ref(
                    receipt,
                    receipt_path,
                    "target",
                )

            codes = [item.code for item in doctor.diagnostics]
            self.assertIn(
                "mint_receipt_target_sha_evolved_by_direct_objet_receipts",
                codes,
            )
            self.assertNotIn("mint_receipt_sha_mismatch", codes)
            build_index.assert_called_once_with(root.resolve())
            proof = next(
                item
                for item in doctor.diagnostics
                if item.code
                == "mint_receipt_target_sha_evolved_by_direct_objet_receipts"
            )
            projected = json.dumps(proof.details, sort_keys=True)
            self.assertNotIn(ARCHIVE_ID, projected)
            self.assertNotIn(ZETTEL_ID, projected)
            self.assertNotIn(ZETTEL_PATH, projected)
            self.assertNotIn(private_id, projected)
            self.assertEqual(
                proof.details["cryptographic_authentication"],
                {
                    "claimed": False,
                    "mac_verified": False,
                    "signature_verified": False,
                },
            )

    def test_doctor_retired_target_uses_its_own_timestamp_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp))
            target = root / ZETTEL_PATH
            target.parent.mkdir(parents=True)
            target.write_text("retired current bytes\n", encoding="utf-8")
            mint_sha = _sha("mint-target")
            retirement_sha = _sha("retirement-target")
            current = hashlib.sha256(target.read_bytes()).hexdigest()
            self._write_link_receipt(
                root,
                before_sha256=mint_sha,
                after_sha256=retirement_sha,
                created_at="2026-08-27T00:00:02Z",
                object_label="before-retirement",
            )
            self._write_link_receipt(
                root,
                before_sha256=retirement_sha,
                after_sha256=current,
                created_at="2026-08-27T00:00:04Z",
                object_label="after-retirement",
            )
            receipt_path = (
                root
                / "receipts"
                / "mint"
                / "retired-drafts"
                / "one.retire-draft.json"
            )
            receipt_path.parent.mkdir(parents=True)
            retired = {
                "action": "retire_minted_draft",
                "archive_id": ARCHIVE_ID,
                "timestamp": "2026-08-27T00:00:03Z",
                "zettel": {"id": ZETTEL_ID},
                "target": {"path": ZETTEL_PATH, "sha256": retirement_sha},
                "mint_receipt": {"path": "receipts/mint/one.mint.json"},
            }
            doctor = archive_cli.Doctor(root)
            doctor._check_retired_draft_existing_ref(
                retired,
                receipt_path,
                "target",
            )
            self.assertIn(
                "mint_retired_draft_target_sha_evolved_by_direct_objet_receipts",
                [item.code for item in doctor.diagnostics],
            )

            too_late = dict(retired)
            too_late["timestamp"] = "2026-08-27T00:00:05Z"
            doctor_late = archive_cli.Doctor(root)
            doctor_late._check_retired_draft_existing_ref(
                too_late,
                receipt_path,
                "target",
            )
            self.assertIn(
                "mint_retired_draft_sha_mismatch",
                [item.code for item in doctor_late.diagnostics],
            )

    def test_scan_limits_stop_further_directory_and_receipt_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp)).resolve()
            receipt_root = root / "receipts" / "objects" / "zettel-links"
            for index in range(12):
                (receipt_root / f"ignored-{index:02d}.txt").write_text(
                    "x",
                    encoding="utf-8",
                )
            documents, entry_count, _candidate_count, blockers = (
                target_sha_evolution._scan_evidence_directory(
                    root,
                    receipt_root,
                    kind="receipt",
                    max_entries=2,
                    max_total_bytes=1024,
                    max_receipt_bytes=1024,
                )
            )
            self.assertEqual(documents, [])
            self.assertEqual(entry_count, 3)
            self.assertIn(
                "target_sha_evolution_receipt_entry_limit_exceeded",
                blockers,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp)).resolve()
            before = _sha("byte-limit-before")
            after = _sha("byte-limit-after")
            self._write_link_receipt(
                root,
                before_sha256=before,
                after_sha256=after,
                created_at="2026-08-27T00:00:01Z",
                object_label="byte-limit-one",
            )
            self._write_link_receipt(
                root,
                before_sha256=after,
                after_sha256=_sha("byte-limit-third"),
                created_at="2026-08-27T00:00:02Z",
                object_label="byte-limit-two",
            )
            receipt_root = root / "receipts" / "objects" / "zettel-links"
            reader = (
                completion_workflows
                ._read_validated_zettel_objet_link_receipt
            )
            with mock.patch.object(
                completion_workflows,
                "_read_validated_zettel_objet_link_receipt",
                wraps=reader,
            ) as observed_reader:
                _documents, _entries, _candidates, blockers = (
                    target_sha_evolution._scan_evidence_directory(
                        root,
                        receipt_root,
                        kind="receipt",
                        max_entries=100,
                        max_total_bytes=1,
                        max_receipt_bytes=64 * 1024,
                    )
                )
            self.assertEqual(observed_reader.call_count, 1)
            self.assertIn(
                "target_sha_evolution_receipt_byte_limit_exceeded",
                blockers,
            )

    def test_retired_target_exact_duplicate_folds_into_one_mint_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive(Path(tmp)).resolve()
            target = root / ZETTEL_PATH
            target.parent.mkdir(parents=True)
            target.write_text(
                "---\n"
                f"id: {ZETTEL_ID}\n"
                "status: canonical\n"
                "title: Duplicate fold\n"
                "edges: []\n"
                "---\n\nCurrent bytes.\n",
                encoding="utf-8",
            )
            expected = _sha("historical-target")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            mint_relative = "receipts/mint/duplicate.mint.json"
            mint_path = root / mint_relative
            mint_path.parent.mkdir(parents=True)
            mint = {
                "action": "mint_zettel",
                "archive_id": ARCHIVE_ID,
                "timestamp": "2026-08-27T00:00:01Z",
                "zettel": {"id": ZETTEL_ID},
                "target": {"path": ZETTEL_PATH, "sha256": expected},
            }
            retired = {
                "action": "retire_minted_draft",
                "archive_id": ARCHIVE_ID,
                "timestamp": "2026-08-27T00:00:02Z",
                "zettel": {"id": ZETTEL_ID},
                "target": {"path": ZETTEL_PATH, "sha256": expected},
                "mint_receipt": {"path": mint_relative},
            }
            retired_path = (
                root
                / "receipts"
                / "mint"
                / "retired-drafts"
                / "duplicate.retire-draft.json"
            )
            retired_path.parent.mkdir(parents=True)
            doctor = archive_cli.Doctor(root)
            doctor._check_mint_receipt_file_ref(mint, mint_path, "target")
            doctor._check_retired_draft_existing_ref(
                retired,
                retired_path,
                "target",
            )

            codes = [item.code for item in doctor.diagnostics]
            self.assertEqual(codes.count("mint_receipt_sha_mismatch"), 1)
            self.assertNotIn("mint_retired_draft_sha_mismatch", codes)
            self.assertEqual(doctor._retired_target_duplicate_fold_count, 1)
            self.assertIn(
                (ZETTEL_PATH, expected, actual),
                doctor._canonical_mint_target_mismatches,
            )


if __name__ == "__main__":
    unittest.main()
