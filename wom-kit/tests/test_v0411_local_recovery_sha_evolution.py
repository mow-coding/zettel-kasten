from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wom_kit import archive_cli, archive_services, local_recovery_sha_evolution
from wom_kit.exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationItem,
    ExactOperationManifest,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
    hash_field_value,
)
from wom_kit.local_recovery_execution import (
    LocalRecoveryFieldSpec,
    _frontmatter_value_replacement,
    _persist_resume_locator,
    _run_with_store,
    build_local_recovery_plan,
    local_recovery_zettel_identity_sha256,
    persist_local_recovery_control,
)
from wom_kit.local_recovery_sha_evolution import (
    build_local_recovery_assets_evolution_index,
    classify_current_bytes_against_mint_sha,
    classify_field_scoped_assets_evolution,
)
KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
TARGET_RELATIVE = "zettels/zet_20260827_assets_evolution_test.md"
ZETTEL_ID = "zet_20260827_assets_evolution_test"
PRIVATE_TITLE = "PRIVATE ASSETS EVOLUTION TITLE 4821"
OBJECT_ID = "sha256:" + "a" * 64


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class V0411LocalRecoveryShaEvolutionTests(unittest.TestCase):
    def make_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        target = root.joinpath(*TARGET_RELATIVE.split("/"))
        archive_id = archive_services.read_archive_id(root)
        target.write_text(
            "---\n"
            f"id: {ZETTEL_ID}\n"
            f"archive_id: {archive_id}\n"
            f"title: {PRIVATE_TITLE}\n"
            "status: canonical\n"
            "kind: concept\n"
            "created_at: '2026-08-20T00:00:00Z'\n"
            "updated_at: '2026-08-20T00:00:00Z'\n"
            "tags:\n"
            "  - private-test\n"
            "assets: []\n"
            "---\n\n"
            "Private body that must remain byte-for-byte stable.\n",
            encoding="utf-8",
            newline="",
        )
        return root

    def make_plan(
        self,
        root: Path,
        *,
        source_digit: str,
    ):
        archive_id = archive_services.read_archive_id(root)
        pre_value = _canonical([])
        post_assets = [{"object_id": OBJECT_ID, "role": "source"}]
        post_value = _canonical(post_assets)
        source_value = _canonical(
            {
                "capture_receipt_sha256": "sha256:" + source_digit * 64,
                "receipt_ordinal": 0,
                "object_id": OBJECT_ID,
                "source_ids": ["source:test"],
            }
        )
        target_identity = local_recovery_zettel_identity_sha256(
            archive_id,
            ZETTEL_ID,
            TARGET_RELATIVE,
        )
        item = ExactOperationItem(
            ordinal=0,
            item_id="item:000000",
            target_kind="zettel",
            target_ref=_sha(
                _canonical(
                    {
                        "archive_id": archive_id,
                        "zettel_id": ZETTEL_ID,
                        "zettel_path": TARGET_RELATIVE,
                    }
                )
            ),
            target_identity_sha256=target_identity,
            fields=(
                ExactFieldEffect(
                    field_ref="frontmatter.assets",
                    pre_sha256=hash_field_value(pre_value),
                    post_sha256=hash_field_value(post_value),
                    source_sha256=hash_field_value(source_value),
                ),
            ),
        )
        manifest = ExactOperationManifest.build(
            operation="local_recovery",
            archive_identity_sha256=(
                archive_services.exact_human_approval_archive_identity_sha256(
                    archive_id
                )
            ),
            items=(item,),
        )
        spec = LocalRecoveryFieldSpec(
            item_id=item.item_id,
            target_kind=item.target_kind,
            target_ref=item.target_ref,
            target_identity_sha256=item.target_identity_sha256,
            field_ref="frontmatter.assets",
            target_relative=TARGET_RELATIVE,
            zettel_id=ZETTEL_ID,
            pre_value=pre_value,
            post_value=post_value,
            source_value=source_value,
        )
        return build_local_recovery_plan(
            root,
            domain="zettel_objet_link",
            manifest=manifest,
            specs=(spec,),
        )

    @staticmethod
    def authority(digit: str) -> ExactOperationApprovalAuthority:
        return ExactOperationApprovalAuthority.from_reference(
            {
                "schema_version": (
                    "wom-kit/exact-human-approval-reference/v0.1"
                ),
                "approval_id": "approval_" + digit * 32,
                "context_sha256": "sha256:" + digit * 64,
                "approval_authority_sha256": (
                    "sha256:" + chr(ord(digit) + 1) * 64
                ),
                "one_use": True,
            }
        )

    def execute_plan(
        self,
        root: Path,
        *,
        source_digit: str,
        authority_digit: str,
    ) -> tuple[object, str]:
        plan = self.make_plan(root, source_digit=source_digit)
        persist_local_recovery_control(plan)
        authority = self.authority(authority_digit)
        _locator, execution = _persist_resume_locator(
            plan,
            plan.manifest,
            authority,
            mode="apply",
        )
        with exact_operation_writer_lock(root) as lock:
            result = _run_with_store(
                plan,
                authority,
                FileExactOperationCheckpointStore(root, writer_lock=lock),
                mode="apply",
                resume=False,
                progress_hook=None,
            )
        self.assertTrue(result["ok"], result)
        return plan, execution

    def completed_fixture(
        self,
        parent: Path,
    ) -> tuple[Path, bytes, bytes, str]:
        root = self.make_archive(parent)
        target = root.joinpath(*TARGET_RELATIVE.split("/"))
        anchor = target.read_bytes()
        _plan, execution = self.execute_plan(
            root,
            source_digit="1",
            authority_digit="2",
        )
        return root, anchor, target.read_bytes(), execution

    def classify(
        self,
        root: Path,
        anchor: bytes,
        current: bytes,
    ) -> dict[str, object]:
        index = build_local_recovery_assets_evolution_index(root)
        return classify_field_scoped_assets_evolution(
            index,
            target_relative=TARGET_RELATIVE,
            mint_anchor_bytes=anchor,
            mint_anchor_sha256=_sha(anchor),
            mint_cutoff="2026-08-21T00:00:00Z",
            current_bytes=current,
        )

    def test_completed_state_chain_cannot_prove_post_mint_chronology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            index = build_local_recovery_assets_evolution_index(root)
            result = classify_field_scoped_assets_evolution(
                index,
                target_relative=TARGET_RELATIVE,
                mint_anchor_bytes=anchor,
                mint_anchor_sha256=_sha(anchor),
                mint_cutoff="2026-08-21T00:00:00Z",
                current_bytes=current,
            )

            self.assertFalse(result["success"], result)
            self.assertEqual(
                result["proof_tier"],
                "field_scoped_assets_state_evidence_without_chronology",
            )
            self.assertEqual(
                result["reason_codes"],
                ["local_recovery_completion_time_not_evidence_bound"],
            )
            self.assertEqual(result["matched_evidence_count"], 1)
            self.assertTrue(result["field_state_transition_proven"])
            self.assertFalse(
                result["chronological_post_mint_evolution_proven"]
            )
            self.assertFalse(result["mint_sha_mismatch_softening_allowed"])
            self.assertFalse(result["full_file_sha_chain_proven"])
            self.assertFalse(result["cryptographic_approval_claimed"])
            self.assertEqual(index.scan_counts["transition_count"], 1)
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(PRIVATE_TITLE, rendered)
            self.assertNotIn(OBJECT_ID, rendered)
            self.assertNotIn(TARGET_RELATIVE, rendered)

    def test_mint_anchor_bytes_are_reconstructed_only_from_exact_assets_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            index = build_local_recovery_assets_evolution_index(root)

            result = classify_current_bytes_against_mint_sha(
                index,
                target_relative=TARGET_RELATIVE,
                mint_anchor_sha256=_sha(anchor),
                mint_cutoff="2026-08-21T00:00:00Z",
                current_bytes=current,
            )

            self.assertFalse(result["success"], result)
            self.assertEqual(
                result["proof_tier"],
                "field_scoped_assets_state_evidence_without_chronology",
            )
            self.assertTrue(result["field_state_transition_proven"])
            self.assertFalse(result["mint_sha_mismatch_softening_allowed"])
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(PRIVATE_TITLE, rendered)
            self.assertNotIn(OBJECT_ID, rendered)
            self.assertNotIn(TARGET_RELATIVE, rendered)

            changed_other_field = current.replace(
                b"kind: concept",
                b"kind: literature",
                1,
            )
            unsupported = classify_current_bytes_against_mint_sha(
                index,
                target_relative=TARGET_RELATIVE,
                mint_anchor_sha256=_sha(anchor),
                mint_cutoff="2026-08-21T00:00:00Z",
                current_bytes=changed_other_field,
            )
            self.assertIn(
                "mint_anchor_bytes_not_reconstructable_from_assets_evidence",
                unsupported["reason_codes"],
            )

    def test_doctor_keeps_error_and_attaches_content_private_assets_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            target = root.joinpath(*TARGET_RELATIVE.split("/"))
            self.assertEqual(target.read_bytes(), current)
            receipt_path = root / "receipts" / "mint" / "synthetic.mint.json"
            receipt = {
                "action": "mint_zettel",
                "archive_id": archive_services.read_archive_id(root),
                "timestamp": "2026-08-21T00:00:00Z",
                "zettel": {"id": ZETTEL_ID, "title": PRIVATE_TITLE},
                "target": {
                    "path": TARGET_RELATIVE,
                    "sha256": hashlib.sha256(anchor).hexdigest(),
                },
            }
            doctor = archive_cli.Doctor(root)

            doctor._check_mint_receipt_file_ref(
                receipt,
                receipt_path,
                "target",
            )

            mismatch = next(
                item
                for item in doctor.diagnostics
                if item.code == "mint_receipt_sha_mismatch"
            )
            self.assertEqual(
                mismatch.details["classification"],
                "field_scoped_assets_state_evidence_without_chronology",
            )
            self.assertFalse(mismatch.details["mint_sha_mismatch_softened"])
            rendered = json.dumps(mismatch.details, ensure_ascii=False)
            self.assertNotIn(PRIVATE_TITLE, rendered)
            self.assertNotIn(OBJECT_ID, rendered)
            self.assertNotIn(TARGET_RELATIVE, rendered)
            self.assertEqual(
                doctor._local_recovery_assets_without_chronology_count,
                1,
            )

    def test_title_body_other_frontmatter_and_updated_at_changes_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            text = current.decode("utf-8")
            cases = {
                "title": (
                    text.replace(PRIVATE_TITLE, "Changed private title", 1).encode(),
                    "title_changed_outside_assets_scope",
                ),
                "body": (
                    (text + "Changed body.\n").encode(),
                    "body_changed_outside_assets_scope",
                ),
                "other_frontmatter": (
                    text.replace(
                        "kind: concept",
                        "kind: literature",
                        1,
                    ).encode(),
                    "frontmatter_changed_outside_assets_scope",
                ),
                "updated_at": (
                    text.replace(
                        "updated_at: '2026-08-20T00:00:00Z'",
                        "updated_at: '2026-08-27T00:00:00Z'",
                        1,
                    ).encode(),
                    "updated_at_change_not_evidence_bound",
                ),
            }
            index = build_local_recovery_assets_evolution_index(root)
            for name, (changed, reason) in cases.items():
                with self.subTest(name=name):
                    result = classify_field_scoped_assets_evolution(
                        index,
                        target_relative=TARGET_RELATIVE,
                        mint_anchor_bytes=anchor,
                        mint_anchor_sha256=_sha(anchor),
                        mint_cutoff="2026-08-21T00:00:00Z",
                        current_bytes=changed,
                    )
                    self.assertFalse(result["success"], result)
                    self.assertEqual(result["proof_tier"], "unsupported")
                    self.assertIn(reason, result["reason_codes"])

    def test_current_assets_must_equal_an_exact_post_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            changed = _frontmatter_value_replacement(
                current,
                "assets",
                [
                    {"object_id": OBJECT_ID, "role": "source"},
                    {"object_id": "sha256:" + "b" * 64, "role": "source"},
                ],
            )
            result = self.classify(root, anchor, changed)
            self.assertFalse(result["success"], result)
            self.assertIn(
                "assets_post_state_not_evidence_bound",
                result["reason_codes"],
            )

    def test_missing_final_receipt_is_not_completion_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, execution = self.completed_fixture(Path(tmp))
            final = (
                root
                / "receipts"
                / "ops"
                / "exact-operations"
                / f"{execution.removeprefix('sha256:')}.json"
            )
            final.unlink()
            result = self.classify(root, anchor, current)
            self.assertFalse(result["success"], result)
            self.assertIn(
                "local_recovery_assets_execution_incomplete",
                result["reason_codes"],
            )

    def test_control_and_checkpoint_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, execution = self.completed_fixture(Path(tmp))
            control = next(
                (
                    root
                    / "profiles"
                    / "local"
                    / "local-recovery"
                    / "controls"
                ).iterdir()
            )
            control.write_bytes(control.read_bytes()[:-1] + b" \n")
            result = self.classify(root, anchor, current)
            self.assertFalse(result["success"], result)
            self.assertIn(
                "local_recovery_assets_control_invalid",
                result["reason_codes"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, execution = self.completed_fixture(Path(tmp))
            checkpoint = (
                root
                / "profiles"
                / "local"
                / "exact-operations"
                / "checkpoints"
                / f"{execution.removeprefix('sha256:')}.jsonl"
            )
            raw = checkpoint.read_bytes()
            checkpoint.write_bytes(raw.replace(b'"sequence":0', b'"sequence":9', 1))
            result = self.classify(root, anchor, current)
            self.assertFalse(result["success"], result)
            self.assertIn(
                "local_recovery_assets_execution_evidence_invalid",
                result["reason_codes"],
            )

    def test_two_completed_lineages_for_same_transition_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, _current, _execution = self.completed_fixture(Path(tmp))
            root.joinpath(*TARGET_RELATIVE.split("/")).write_bytes(anchor)
            self.execute_plan(
                root,
                source_digit="3",
                authority_digit="4",
            )
            current = root.joinpath(*TARGET_RELATIVE.split("/")).read_bytes()
            result = self.classify(root, anchor, current)
            self.assertFalse(result["success"], result)
            self.assertEqual(result["proof_tier"], "ambiguous")
            self.assertIn(
                "local_recovery_assets_evidence_ambiguous",
                result["reason_codes"],
            )

    def test_relevant_supersession_presence_blocks_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, execution = self.completed_fixture(Path(tmp))
            compensation = "sha256:" + "c" * 64
            compensation_authority = self.authority("6").document()
            basis = {
                "schema_version": (
                    "wom-kit/local-recovery-supersession-pending/v0.1"
                ),
                "status": "pending",
                "parent_apply_manifest_sha256": "sha256:" + "1" * 64,
                "parent_apply_operation_manifest_sha256": (
                    "sha256:" + "2" * 64
                ),
                "parent_apply_execution_sha256": execution,
                "parent_apply_approval_id": "approval_" + "3" * 32,
                "compensation_manifest_sha256": "sha256:" + "4" * 64,
                "compensation_operation_manifest_sha256": (
                    "sha256:" + "5" * 64
                ),
                "compensation_execution_sha256": compensation,
                "compensation_approval_authority": compensation_authority,
                "compensation_resume_locator_sha256": "sha256:" + "7" * 64,
                "compensation_field_count": 1,
                "private_values_echoed": False,
                "paths_echoed": False,
            }
            document = {**basis, "supersession_sha256": _sha(_canonical(basis))}
            directory = (
                root
                / "profiles"
                / "local"
                / "local-recovery"
                / "supersessions"
            )
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (
                f"{execution.removeprefix('sha256:')}."
                f"{compensation.removeprefix('sha256:')}.pending.json"
            )
            path.write_bytes(_canonical(document) + b"\n")
            result = self.classify(root, anchor, current)
            self.assertFalse(result["success"], result)
            self.assertIn(
                "local_recovery_assets_supersession_present",
                result["reason_codes"],
            )

    def test_evidence_directories_are_scanned_once_and_index_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            original_scan = (
                local_recovery_sha_evolution._safe_directory_entries_once
            )
            with mock.patch.object(
                local_recovery_sha_evolution,
                "_safe_directory_entries_once",
                wraps=original_scan,
            ) as scan:
                index = build_local_recovery_assets_evolution_index(root)
                for _ in range(5):
                    result = classify_field_scoped_assets_evolution(
                        index,
                        target_relative=TARGET_RELATIVE,
                        mint_anchor_bytes=anchor,
                        mint_anchor_sha256=_sha(anchor),
                        mint_cutoff="2026-08-21T00:00:00Z",
                        current_bytes=current,
                    )
                    self.assertFalse(result["success"], result)
                    self.assertTrue(result["field_state_transition_proven"])
                    self.assertEqual(
                        result["reason_codes"],
                        ["local_recovery_completion_time_not_evidence_bound"],
                    )

            scanned_relatives = [call.args[1] for call in scan.call_args_list]
            self.assertEqual(
                scanned_relatives,
                [
                    "profiles/local/local-recovery/controls",
                    "profiles/local/local-recovery/resume",
                    "receipts/ops/exact-operations",
                    "profiles/local/exact-operations/checkpoints",
                    "profiles/local/local-recovery/supersessions",
                ],
            )
            for kind in (
                "control",
                "locator",
                "final",
                "checkpoint",
                "supersession",
            ):
                self.assertEqual(
                    index.scan_counts[f"{kind}_directory_scans"],
                    1,
                )
            self.assertEqual(index.scan_counts["plan_load_count"], 1)
            self.assertEqual(
                index.scan_counts["final_receipt_validation_count"],
                1,
            )
            self.assertEqual(
                index.scan_counts["checkpoint_validation_count"],
                1,
            )

    def test_invalid_target_and_mint_cutoff_are_distinguished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, anchor, current, _execution = self.completed_fixture(Path(tmp))
            index = build_local_recovery_assets_evolution_index(root)

            invalid_target = classify_field_scoped_assets_evolution(
                index,
                target_relative="zettels/../private.md",
                mint_anchor_bytes=anchor,
                mint_anchor_sha256=_sha(anchor),
                mint_cutoff="2026-08-21T00:00:00Z",
                current_bytes=current,
            )
            self.assertEqual(
                invalid_target["reason_codes"],
                ["local_recovery_assets_target_invalid"],
            )

            invalid_cutoff = classify_field_scoped_assets_evolution(
                index,
                target_relative=TARGET_RELATIVE,
                mint_anchor_bytes=anchor,
                mint_anchor_sha256=_sha(anchor),
                mint_cutoff="2026-08-21T00:00:00",
                current_bytes=current,
            )
            self.assertEqual(
                invalid_cutoff["reason_codes"],
                ["mint_cutoff_invalid"],
            )


if __name__ == "__main__":
    unittest.main()
