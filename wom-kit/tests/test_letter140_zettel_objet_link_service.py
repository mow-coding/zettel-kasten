from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from wom_kit import archive_services, completion_workflows, operation_approval_binding
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ROLE = "evidence"
REVIEWER = "person:letter140-test"


class Letter140ZettelObjetLinkServiceTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        self.reindex(root)
        return root

    def reindex(self, root: Path) -> dict[str, object]:
        indexed = archive_services.index_archive(root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        return indexed

    def assert_index_dirty(self, root: Path) -> None:
        evidence = archive_services.require_current_zettel_index(root)
        self.assertFalse(evidence["ok"], evidence)
        self.assertIn("archive_index_dirty", evidence["reason_codes"])

    def plan(self, root: Path, *, label: str | None = None) -> dict[str, object]:
        result = completion_workflows.zettel_objet_link_plan(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
            label=label,
        )
        self.assertTrue(result["ok"], result)
        return result

    def claim(self, root: Path, plan: dict[str, object]):
        binding = operation_approval_binding.zettel_objet_link_approval_binding(
            plan
        )
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim=REVIEWER,
        )
        claim = claim_exact_human_approval(
            root,
            context,
            ExactHumanApprovalDecision(
                approved=True,
                synthetic_acknowledged=False,
                reason_code="exact_human_approval_approved",
                plan_sha256=context.plan_sha256,
                target_binding_sha256=context.target_binding_sha256,
            ),
            bytearray(b"L" * 32),
        )
        return binding, claim

    def apply(
        self,
        root: Path,
        plan: dict[str, object],
        binding,
        claim,
        *,
        exact_plan: str | None = None,
        exact_target: str | None = None,
        label: str | None = None,
    ) -> dict[str, object]:
        return completion_workflows.zettel_objet_link_apply(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
            label=label,
            expected_plan_sha256=str(plan["summary"]["plan_sha256"]),
            reviewed_by=REVIEWER,
            expected_exact_approval_plan_sha256=(
                exact_plan or binding.plan_sha256
            ),
            expected_exact_approval_target_binding_sha256=(
                exact_target or binding.target_binding_sha256
            ),
            exact_human_approval_claim=claim,
        )

    @staticmethod
    def finish_claim(claim, *, succeeded: bool) -> None:
        try:
            if claim.status == "started":
                if succeeded:
                    claim.finalize_succeeded()
                else:
                    claim.finalize_failed("operation_blocked")
        finally:
            claim.close()

    @staticmethod
    def zettel_path(root: Path) -> Path:
        return root / "zettels" / f"{ZETTEL_ID}.md"

    @staticmethod
    def manifest_path(root: Path) -> Path:
        return root / "objects" / "manifests" / "files.jsonl"

    def target_manifest_record(self, root: Path) -> dict[str, object]:
        return next(
            json.loads(line)
            for line in self.manifest_path(root)
            .read_text(encoding="utf-8")
            .splitlines()
            if OBJECT_ID in line
        )

    @staticmethod
    def path_from_plan(root: Path, plan: dict[str, object], key: str) -> Path:
        relative = str(plan["summary"][key])
        return root.joinpath(*relative.split("/"))

    def seed_control_lock(self, root: Path, plan: dict[str, object]) -> Path:
        path = self.path_from_plan(root, plan, "control_artifact_path")
        archive_services._write_bytes_create_if_absent(
            path,
            completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES,
        )
        return path

    @staticmethod
    def create_directory_junction(link: Path, target: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise OSError("Windows junction creation failed")

    @staticmethod
    def remove_directory_junction(link: Path) -> None:
        os.rmdir(link)

    def test_missing_claim_blocks_before_any_archive_read(self) -> None:
        with mock.patch.object(
            completion_workflows,
            "_zettel_objet_link_plan_core",
            side_effect=AssertionError("archive planning must not run"),
        ) as planner:
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_required",
            ):
                completion_workflows.zettel_objet_link_apply(
                    Path("does-not-need-to-exist"),
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                    expected_plan_sha256="0" * 64,
                    reviewed_by=REVIEWER,
                    expected_exact_approval_plan_sha256="sha256:" + "1" * 64,
                    expected_exact_approval_target_binding_sha256=(
                        "sha256:" + "2" * 64
                    ),
                )
        planner.assert_not_called()

    def test_approval_frontmatter_validation_blocks_ambiguous_or_wrong_zettel(
        self,
    ) -> None:
        cases = (
            (
                "duplicate_key",
                lambda text: text.replace(
                    "title: Fake thought while eating alone",
                    "title: FIRST_PRIVATE_TITLE\r\n"
                    "title: SECOND_PRIVATE_TITLE",
                    1,
                ),
            ),
            (
                "nested_schema_invalid",
                lambda text: text.replace(
                    "assets: []",
                    "assets:\r\n"
                    f"  - object_id: {OBJECT_ID}\r\n"
                    "    role:\r\n"
                    "      - invalid",
                    1,
                ),
            ),
            (
                "archive_identity_mismatch",
                lambda text: text.replace(
                    "archive_id: archive:personal:fake-life",
                    "archive_id: archive:personal:wrong-archive",
                    1,
                ),
            ),
        )
        for name, mutate in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                zettel = self.zettel_path(root)
                changed = mutate(zettel.read_text(encoding="utf-8"))
                zettel.write_text(changed, encoding="utf-8", newline="")
                before = zettel.read_bytes()

                plan = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

                self.assertFalse(plan["ok"], plan)
                self.assertIn(
                    "zettel_identity_projection_stale",
                    plan["blockers"],
                )
                self.assertEqual(plan["summary"], {})
                self.assertEqual(plan["data"], {})
                self.assertEqual(zettel.read_bytes(), before)
                self.assertFalse(
                    (
                        root
                        / "receipts"
                        / "objects"
                        / "zettel-links"
                    ).exists()
                )
                self.assertEqual(plan["would_change"], [])

    def test_success_preserves_exact_leading_body_bytes(self) -> None:
        cases = (
            (
                "four_space_markdown_code_block",
                b"    print('SAFE_SYNTHETIC')\r\n\r\nparagraph\r\n",
                False,
            ),
            ("leading_tab", b"\tSAFE_SYNTHETIC\nparagraph\n", False),
            ("leading_blank_lines", b"\r\n\nparagraph\n", False),
            (
                "utf8_bom_and_four_spaces",
                b"    SAFE_SYNTHETIC\nparagraph\n",
                True,
            ),
        )
        for name, exact_body, with_bom in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                zettel = self.zettel_path(root)
                original_text = zettel.read_text(encoding="utf-8")
                original_match = archive_services.FRONTMATTER_RE.match(original_text)
                self.assertIsNotNone(original_match)
                assert original_match is not None
                frontmatter_bytes = original_text[: original_match.end()].encode(
                    "utf-8"
                )
                bom = b"\xef\xbb\xbf" if with_bom else b""
                zettel.write_bytes(bom + frontmatter_bytes + exact_body)
                before = zettel.read_bytes()
                self.reindex(root)

                plan = self.plan(root)
                binding, claim = self.claim(root, plan)
                succeeded = False
                try:
                    result = self.apply(root, plan, binding, claim)
                    self.assertTrue(result["ok"], result)
                    succeeded = True

                    after = zettel.read_bytes()
                    after_text = after.decode("utf-8")
                    self.assertFalse(after_text.startswith("\ufeff"))
                    after_match = archive_services.FRONTMATTER_RE.match(after_text)
                    self.assertIsNotNone(after_match)
                    assert after_match is not None
                    self.assertEqual(
                        after_text[after_match.end() :].encode("utf-8"),
                        exact_body,
                    )
                    boundary = (
                        archive_services.parse_approval_zettel_content_boundary(
                            after_text
                        )
                    )
                    self.assertEqual(boundary["state"], "readable")
                    self.assertIn(
                        {"object_id": OBJECT_ID, "role": ROLE},
                        boundary["frontmatter"]["assets"],
                    )
                    snapshot = self.path_from_plan(root, plan, "snapshot_path")
                    self.assertEqual(snapshot.read_bytes(), before)
                finally:
                    self.finish_claim(claim, succeeded=succeeded)

    def test_strict_manifest_rejects_duplicates_and_every_malformed_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            manifest = self.manifest_path(root)
            rows = manifest.read_text(encoding="utf-8").splitlines()
            duplicate = next(row for row in rows if OBJECT_ID in row)
            manifest.write_text(
                manifest.read_text(encoding="utf-8") + duplicate + "\n",
                encoding="utf-8",
            )
            self.reindex(root)
            plan = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(plan["ok"], plan)
            self.assertIn(
                "zettel_objet_link_manifest_record_ambiguous",
                plan["blockers"],
            )
            self.assertEqual(plan["summary"]["manifest_record_count"], 2)
            self.assertTrue(plan["data"]["manifest_record_set_complete"])
            self.assertFalse(plan["data"]["manifest_record_set_unique"])

        malformed_rows = ("{not-json", "[]", '{"object_id":"x","object_id":"y"}')
        for malformed in malformed_rows:
            with self.subTest(row=malformed), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                manifest = self.manifest_path(root)
                manifest.write_text(
                    manifest.read_text(encoding="utf-8") + malformed + "\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "archive_index_manifest_invalid",
                ):
                    archive_services.archive_index_strict_manifest_snapshot(
                        root
                    )
                plan = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )
                self.assertFalse(plan["ok"], plan)
                self.assertEqual(plan["blockers"], ["manifest_changed"])
                self.assertEqual(plan["reason_codes"], ["manifest_changed"])
                self.assertEqual(plan["summary"], {})
                self.assertEqual(plan["data"], {})

    def test_strict_manifest_rejects_incomplete_mismatched_and_nonfinite_rows(
        self,
    ) -> None:
        nonfinite_prefix = (
            '{"object_id":"'
            + OBJECT_ID
            + '","sha256":"'
            + OBJECT_ID.removeprefix("sha256:")
            + '","logical_key":"objects/safe/nonfinite.bin",'
            '"locations":[{"provider":"local"}],'
            '"provenance":{"confidence":'
        )
        cases: tuple[tuple[str, dict[str, object] | str], ...] = (
            ("lone_object_id", {"object_id": OBJECT_ID}),
            (
                "sha256_mismatch",
                {
                    "object_id": OBJECT_ID,
                    "sha256": "f" * 64,
                    "logical_key": "objects/safe/mismatch.bin",
                    "locations": [{"provider": "local"}],
                    "provenance": {},
                },
            ),
            ("non_finite_nan", nonfinite_prefix + "NaN}}"),
            ("non_finite_infinity", nonfinite_prefix + "Infinity}}"),
            (
                "non_finite_negative_infinity",
                nonfinite_prefix + "-Infinity}}",
            ),
        )
        for name, row in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                serialized = row if isinstance(row, str) else json.dumps(row)
                self.manifest_path(root).write_text(
                    serialized + "\n",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "archive_index_manifest_invalid",
                ):
                    archive_services.archive_index_strict_manifest_snapshot(
                        root
                    )

                plan = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

                self.assertFalse(plan["ok"], plan)
                self.assertEqual(plan["blockers"], ["manifest_changed"])
                self.assertEqual(plan["reason_codes"], ["manifest_changed"])
                self.assertEqual(plan["summary"], {})
                self.assertEqual(plan["data"], {})

    def test_strict_manifest_enforces_depth_node_and_record_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            record = self.target_manifest_record(root)
            nested: object = "leaf"
            for _ in range(
                completion_workflows.ZETTEL_OBJET_LINK_MAX_MANIFEST_JSON_DEPTH
                + 1
            ):
                nested = [nested]
            record["provenance"] = {"nested": nested}
            self.manifest_path(root).write_text(
                json.dumps(record) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "archive_index_manifest_invalid",
            ):
                archive_services.archive_index_strict_manifest_snapshot(root)
            plan = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(plan["ok"], plan)
            self.assertEqual(plan["blockers"], ["manifest_changed"])
            self.assertEqual(plan["reason_codes"], ["manifest_changed"])
            self.assertEqual(plan["summary"], {})
            self.assertEqual(plan["data"], {})

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            with mock.patch.object(
                archive_services,
                "ZETTEL_OBJET_LINK_MANIFEST_MAX_JSON_NODES",
                1,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "archive_index_manifest_invalid",
                ):
                    archive_services.archive_index_strict_manifest_snapshot(
                        root
                    )

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            with mock.patch.object(
                archive_services,
                "ZETTEL_OBJET_LINK_MANIFEST_MAX_RECORDS",
                1,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "archive_index_manifest_too_many_records",
                ):
                    archive_services.archive_index_strict_manifest_snapshot(
                        root
                    )

    def test_snapshot_matrix_fails_closed_and_reuses_only_exact_regular(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            absent = self.plan(root)
            self.assertEqual(absent["summary"]["snapshot_state"], "absent")
            snapshot = self.path_from_plan(root, absent, "snapshot_path")
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(b"wrong")
            wrong = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(wrong["ok"], wrong)
            self.assertIn(
                "zettel_objet_link_snapshot_invalid", wrong["blockers"]
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            absent = self.plan(root)
            snapshot = self.path_from_plan(root, absent, "snapshot_path")
            snapshot.mkdir(parents=True)
            nonregular = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(nonregular["ok"], nonregular)
            self.assertIn(
                "zettel_objet_link_snapshot_invalid",
                nonregular["blockers"],
            )

        for unsafe_reason in ("symlink", "reparse"):
            with self.subTest(reason=unsafe_reason), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                absent = self.plan(root)
                snapshot = self.path_from_plan(root, absent, "snapshot_path")
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_bytes(self.zettel_path(root).read_bytes())
                real_read = (
                    archive_services._read_activity_group_regular_bytes_bound
                )

                def unsafe_read(
                    archive_root: Path,
                    binding: dict[str, object],
                    path: Path,
                    *,
                    max_bytes: int,
                ) -> bytes:
                    if (
                        Path(path).name == snapshot.name
                        and Path(path).parent.name == "snapshots"
                    ):
                        raise OSError(unsafe_reason)
                    return real_read(
                        archive_root,
                        binding,
                        Path(path),
                        max_bytes=max_bytes,
                    )

                with mock.patch.object(
                    archive_services,
                    "_read_activity_group_regular_bytes_bound",
                    side_effect=unsafe_read,
                ):
                    unsafe = completion_workflows.zettel_objet_link_plan(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )
                self.assertFalse(unsafe["ok"], unsafe)
                self.assertIn(
                    "zettel_objet_link_snapshot_invalid",
                    unsafe["blockers"],
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            absent = self.plan(root)
            snapshot = self.path_from_plan(root, absent, "snapshot_path")
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(self.zettel_path(root).read_bytes())
            exact = self.plan(root)
            self.assertEqual(
                exact["summary"]["snapshot_state"], "existing_exact"
            )
            self.assertEqual(
                exact["summary"]["snapshot_sha256"],
                exact["summary"]["zettel_sha256"],
            )

    def test_control_artifact_is_exact_bound_and_first_use_transition_succeeds(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            self.assertEqual(
                plan["summary"]["control_artifact_state"], "absent"
            )
            control = self.path_from_plan(
                root, plan, "control_artifact_path"
            )
            binding, claim = self.claim(root, plan)
            try:
                result = self.apply(root, plan, binding, claim)
                self.assertTrue(result["ok"], result)
                self.assertEqual(
                    result["summary"]["control_artifact_state"], "created"
                )
                self.assertIn(
                    str(plan["summary"]["control_artifact_path"]),
                    result["files_written"],
                )
                self.assertEqual(
                    control.read_bytes(),
                    completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES,
                )
                self.assertTrue(
                    plan["data"][
                        "parent_directory_effects_implied_by_bound_artifact_paths"
                    ]
                )
            finally:
                self.finish_claim(claim, succeeded=True)

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            initial = self.plan(root)
            control = self.seed_control_lock(root, initial)
            existing = self.plan(root)
            self.assertEqual(
                existing["summary"]["control_artifact_state"],
                "existing_exact",
            )
            binding, claim = self.claim(root, existing)
            try:
                result = self.apply(root, existing, binding, claim)
                self.assertTrue(result["ok"], result)
                self.assertEqual(
                    result["summary"]["control_artifact_state"],
                    "reused_existing_exact",
                )
                self.assertNotIn(
                    str(existing["summary"]["control_artifact_path"]),
                    result["files_written"],
                )
                self.assertEqual(
                    control.read_bytes(),
                    completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES,
                )
            finally:
                self.finish_claim(claim, succeeded=True)

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            control = self.path_from_plan(
                root, plan, "control_artifact_path"
            )
            control.parent.mkdir(parents=True, exist_ok=True)
            control.write_bytes(b"wrong")
            blocked = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(blocked["ok"], blocked)
            self.assertIn(
                "zettel_objet_link_lock_artifact_invalid",
                blocked["blockers"],
            )

    def test_success_writes_exact_v02_receipt_and_canonical_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            label = "Reviewed private source label"
            plan = self.plan(root, label=label)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            try:
                result = self.apply(
                    root, plan, binding, claim, label=label
                )
                self.assertTrue(result["ok"], result)
                after = self.zettel_path(root).read_bytes()
                self.assertEqual(
                    hashlib.sha256(after).hexdigest(),
                    result["summary"]["zettel_sha256"],
                )
                frontmatter, _body = archive_services.require_readable_zettel_content(
                    self.zettel_path(root)
                )
                self.assertIn(
                    {"object_id": OBJECT_ID, "role": ROLE, "label": label},
                    frontmatter["assets"],
                )
                snapshot = self.path_from_plan(root, plan, "snapshot_path")
                self.assertEqual(snapshot.read_bytes(), before)
                receipt_path = self.path_from_plan(
                    root, plan, "receipt_path"
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                schema = json.loads(
                    (
                        KIT_ROOT
                        / "schemas"
                        / "zettel-objet-link-receipt.schema.json"
                    ).read_text(encoding="utf-8")
                )
                Draft202012Validator(schema).validate(receipt)
                self.assertEqual(
                    receipt["schema"],
                    "wom-kit/zettel-objet-link-receipt/v0.2",
                )
                self.assertEqual(
                    receipt["exact_human_approval"]["operation"],
                    "zettel_objet_link",
                )
                self.assertEqual(
                    receipt["control_artifact_state"], "absent"
                )
                self.assertEqual(
                    receipt["control_artifact_sha256"],
                    completion_workflows.ZETTEL_OBJET_LINK_LOCK_SHA256,
                )
                self.assertEqual(
                    archive_services._stable_exact_bytes_observation(
                        receipt_path,
                        completion_workflows._canonical_json_bytes(receipt),
                    ),
                    "verified_exact",
                )
                found = completion_workflows.zettel_objet_link_receipts(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )
                self.assertTrue(found["ok"], found)
                self.assertEqual(
                    found["summary"]["validated_receipt_count"], 1
                )
                self.assertEqual(
                    found["summary"]["selected_receipt_path"],
                    plan["summary"]["receipt_path"],
                )

                tampered = dict(receipt)
                foreign_transaction = (
                    ("f" if receipt["transaction_sha256"][0] != "f" else "e")
                    + receipt["transaction_sha256"][1:]
                )
                _foreign_swap, foreign_previous = (
                    archive_services.regular_file_canonical_swap_paths(
                        Path(str(receipt["zettel_path"])),
                        f"sha256:{foreign_transaction}",
                        swap_suffix=(
                            completion_workflows.ZETTEL_OBJET_LINK_CANONICAL_SWAP_SUFFIX
                        ),
                    )
                )
                tampered["canonical_previous_path"] = (
                    foreign_previous.as_posix()
                )
                receipt_path.write_bytes(
                    completion_workflows._canonical_json_bytes(tampered)
                )
                rejected, _raw = (
                    completion_workflows._read_validated_zettel_objet_link_receipt(
                        receipt_path
                    )
                )
                self.assertIsNone(rejected)
            finally:
                self.finish_claim(claim, succeeded=True)

    def test_binding_mismatch_and_under_lock_toctou_never_write_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            try:
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "operation_approval_binding_mismatch",
                ):
                    self.apply(
                        root,
                        plan,
                        binding,
                        claim,
                        exact_target="sha256:" + "f" * 64,
                    )
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertFalse(
                    self.path_from_plan(root, plan, "snapshot_path").exists()
                )
                self.assertFalse(
                    self.path_from_plan(root, plan, "receipt_path").exists()
                )
                self.assertFalse(
                    self.path_from_plan(
                        root, plan, "control_artifact_path"
                    ).exists()
                )
            finally:
                self.finish_claim(claim, succeeded=False)

        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            initial = self.plan(root)
            self.seed_control_lock(root, initial)
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            manifest = self.manifest_path(root)
            rows = manifest.read_text(encoding="utf-8").splitlines()
            duplicate = next(row for row in rows if OBJECT_ID in row)
            real_enter = completion_workflows._ZettelObjetLinkLock.__enter__

            def drift_after_lock(lock_self):
                entered = real_enter(lock_self)
                manifest.write_text(
                    manifest.read_text(encoding="utf-8")
                    + duplicate
                    + "\n",
                    encoding="utf-8",
                )
                return entered

            try:
                with mock.patch.object(
                    completion_workflows._ZettelObjetLinkLock,
                    "__enter__",
                    drift_after_lock,
                ):
                    result = self.apply(root, plan, binding, claim)
                self.assertFalse(result["ok"], result)
                self.assertIn(
                    "manifest_changed",
                    result["blockers"],
                )
                self.assertIn(
                    "zettel_objet_link_plan_changed",
                    result["blockers"],
                )
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertFalse(
                    self.path_from_plan(root, plan, "snapshot_path").exists()
                )
                self.assertFalse(
                    self.path_from_plan(root, plan, "receipt_path").exists()
                )
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_approved_support_parent_junction_substitution_never_writes_outside(
        self,
    ) -> None:
        for artifact_kind in ("control", "snapshot", "receipt"):
            with (
                self.subTest(artifact_kind=artifact_kind),
                tempfile.TemporaryDirectory() as tmp,
            ):
                tmp_root = Path(tmp)
                root = self.archive(tmp_root)
                plan = self.plan(root)
                before = self.zettel_path(root).read_bytes()
                control_path = self.path_from_plan(
                    root,
                    plan,
                    "control_artifact_path",
                )
                snapshot_path = self.path_from_plan(
                    root,
                    plan,
                    "snapshot_path",
                )
                receipt_path = self.path_from_plan(
                    root,
                    plan,
                    "receipt_path",
                )
                if artifact_kind == "control":
                    trigger_parent = control_path.parent
                    attack_parent = control_path.parent
                elif artifact_kind == "snapshot":
                    trigger_parent = snapshot_path.parent
                    attack_parent = snapshot_path.parent
                else:
                    # Receipt is the ancestor of both support subdirectories.
                    # Inject it immediately before the first bound descendant
                    # chain is acquired, after the exact claim was rechecked.
                    trigger_parent = control_path.parent
                    attack_parent = receipt_path.parent
                expected_trigger_parent = trigger_parent.resolve()

                outside = tmp_root / f"outside-{artifact_kind}"
                outside.mkdir()
                sentinel = outside / "PRIVATE_OUTSIDE_SENTINEL.txt"
                sentinel_bytes = (
                    f"PRIVATE_{artifact_kind.upper()}_JUNCTION_SENTINEL"
                ).encode("utf-8")
                sentinel.write_bytes(sentinel_bytes)
                binding, claim = self.claim(root, plan)
                real_bound_chain = (
                    archive_services._activity_group_bound_directory_chain
                )
                injected = False
                junction_unavailable = False
                bound_chain_targets: list[Path] = []

                @contextmanager
                def inject_junction_after_approval(
                    archive_root: Path,
                    target: Path,
                    *,
                    create: bool = False,
                ):
                    nonlocal injected, junction_unavailable
                    resolved_target = Path(target).resolve()
                    bound_chain_targets.append(resolved_target)
                    if (
                        not injected
                        and resolved_target == expected_trigger_parent
                    ):
                        try:
                            self.create_directory_junction(
                                attack_parent,
                                outside,
                            )
                        except OSError:
                            junction_unavailable = True
                            raise
                        injected = True
                    with real_bound_chain(
                        archive_root,
                        target,
                        create=create,
                    ) as parent_binding:
                        yield parent_binding

                try:
                    with mock.patch.object(
                        archive_services,
                        "_activity_group_bound_directory_chain",
                        new=inject_junction_after_approval,
                    ):
                        try:
                            blocked_result = self.apply(
                                root,
                                plan,
                                binding,
                                claim,
                            )
                        except OSError:
                            blocked_result = None
                    if junction_unavailable:
                        self.skipTest(
                            "Windows directory junctions are unavailable"
                        )
                    self.assertIn(
                        expected_trigger_parent,
                        bound_chain_targets,
                    )
                    self.assertTrue(injected, blocked_result)
                    if blocked_result is not None:
                        self.assertFalse(blocked_result["ok"], blocked_result)
                    self.assertEqual(
                        self.zettel_path(root).read_bytes(),
                        before,
                    )
                    self.assertEqual(claim.status, "started")
                    self.assertEqual(
                        list(outside.iterdir()),
                        [sentinel],
                    )
                    self.assertEqual(sentinel.read_bytes(), sentinel_bytes)
                    self.assertFalse(
                        (outside / control_path.name).exists()
                    )
                    self.assertFalse(
                        (outside / snapshot_path.name).exists()
                    )
                    self.assertFalse(
                        (outside / receipt_path.name).exists()
                    )
                finally:
                    if injected and attack_parent.exists():
                        self.remove_directory_junction(attack_parent)
                    self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows held-parent contract")
    def test_support_parent_swap_is_blocked_through_each_bound_write(
        self,
    ) -> None:
        for artifact_kind in ("control", "snapshot", "receipt"):
            with (
                self.subTest(artifact_kind=artifact_kind),
                tempfile.TemporaryDirectory() as tmp,
            ):
                tmp_root = Path(tmp)
                root = self.archive(tmp_root)
                plan = self.plan(root)
                control_path = self.path_from_plan(
                    root,
                    plan,
                    "control_artifact_path",
                )
                snapshot_path = self.path_from_plan(
                    root,
                    plan,
                    "snapshot_path",
                )
                receipt_path = self.path_from_plan(
                    root,
                    plan,
                    "receipt_path",
                )
                target_path = {
                    "control": control_path,
                    "snapshot": snapshot_path,
                    "receipt": receipt_path,
                }[artifact_kind]
                attack_parent = target_path.parent
                hidden_parent = attack_parent.with_name(
                    attack_parent.name + "-hidden"
                )
                outside = tmp_root / f"outside-held-{artifact_kind}"
                outside.mkdir()
                binding, claim = self.claim(root, plan)
                real_bound_write = (
                    archive_services._write_activity_group_bytes_new_file_bound
                )
                swap_attempted = False
                swap_blocked = False
                junction_injected = False

                def attempt_parent_swap(
                    parent_binding: dict[str, object],
                    path: Path,
                    raw: bytes,
                ) -> None:
                    nonlocal swap_attempted, swap_blocked, junction_injected
                    if (
                        not swap_attempted
                        and Path(path).resolve() == target_path.resolve()
                    ):
                        swap_attempted = True
                        try:
                            attack_parent.rename(hidden_parent)
                        except OSError:
                            swap_blocked = True
                        else:
                            self.create_directory_junction(
                                attack_parent,
                                outside,
                            )
                            junction_injected = True
                    real_bound_write(parent_binding, path, raw)

                succeeded = False
                try:
                    with mock.patch.object(
                        archive_services,
                        "_write_activity_group_bytes_new_file_bound",
                        side_effect=attempt_parent_swap,
                    ):
                        result = self.apply(root, plan, binding, claim)
                    self.assertTrue(swap_attempted)
                    self.assertTrue(swap_blocked)
                    self.assertFalse(junction_injected)
                    self.assertTrue(result["ok"], result)
                    succeeded = True
                    self.assertEqual(list(outside.iterdir()), [])
                    self.assertFalse((outside / target_path.name).exists())
                    self.assertTrue(target_path.is_file())
                finally:
                    if junction_injected and attack_parent.exists():
                        self.remove_directory_junction(attack_parent)
                    if hidden_parent.exists() and not attack_parent.exists():
                        hidden_parent.rename(attack_parent)
                    self.finish_claim(claim, succeeded=succeeded)

    def test_v02_receipt_lookup_requires_current_exact_manifest_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            binding, claim = self.claim(root, plan)
            succeeded = False
            try:
                result = self.apply(root, plan, binding, claim)
                self.assertTrue(result["ok"], result)
                succeeded = True
                manifest = self.manifest_path(root)
                surviving_rows = [
                    line
                    for line in manifest.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if OBJECT_ID not in line
                ]
                manifest.write_text(
                    "\n".join(surviving_rows) + "\n",
                    encoding="utf-8",
                )

                found = completion_workflows.zettel_objet_link_receipts(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

                self.assertFalse(found["ok"], found)
                self.assertIn(
                    "zettel_objet_link_receipts_validation_failed",
                    found["blockers"],
                )
                self.assertEqual(
                    found["summary"]["validated_receipt_count"], 0
                )
                self.assertIsNone(
                    found["summary"]["selected_receipt_path"]
                )
            finally:
                self.finish_claim(claim, succeeded=succeeded)

    @unittest.skipUnless(os.name == "nt", "Windows dirty-projection watcher")
    def test_manifest_removed_after_prewrite_check_never_returns_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows
                ._reprove_zettel_objet_link_dirty_projection
            )
            reproof_called = False

            def remove_target_during_reproof(*args, **kwargs):
                nonlocal reproof_called
                reproof_called = True
                manifest = self.manifest_path(root)
                surviving_rows = [
                    line
                    for line in manifest.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if OBJECT_ID not in line
                ]
                manifest.write_text(
                    "\n".join(surviving_rows) + "\n",
                    encoding="utf-8",
                )
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=remove_target_during_reproof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_manifest_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(reproof_called)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
                found = completion_workflows.zettel_objet_link_receipts(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )
                self.assertTrue(found["ok"], found)
                self.assertEqual(found["state"], "not_found")
                self.assertEqual(
                    found["summary"]["validated_receipt_count"], 0
                )
                self.assertIsNone(
                    found["summary"]["selected_receipt_path"]
                )
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows dirty-projection watcher")
    def test_duplicate_id_created_after_fresh_plan_never_returns_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            duplicate = root / "inbox" / "late-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows
                ._reprove_zettel_objet_link_dirty_projection
            )
            reproof_called = False

            def insert_duplicate_during_reproof(*args, **kwargs):
                nonlocal reproof_called
                reproof_called = True
                shutil.copyfile(self.zettel_path(root), duplicate)
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=insert_duplicate_during_reproof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(reproof_called)
                self.assertTrue(duplicate.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows dirty-projection watcher")
    def test_manifest_and_duplicate_final_proofs_share_one_stable_point(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            manifest = self.manifest_path(root)
            duplicate = root / "inbox" / "cross-proof-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows
                ._reprove_zettel_objet_link_dirty_projection
            )
            reproof_called = False

            def cross_drift_after_reproof(*args, **kwargs):
                nonlocal reproof_called
                reproof_called = True
                # The indexed proof itself sees a clean tree and manifest.
                # Both authorities then change before the writer can seal the
                # delta.  The surrounding Windows watchers must reject even
                # the transient duplicate that is gone by verification time.
                proof = real_reprove(*args, **kwargs)
                shutil.copyfile(self.zettel_path(root), duplicate)
                duplicate.unlink()
                manifest.unlink()
                return proof

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=cross_drift_after_reproof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(reproof_called)
                self.assertFalse(manifest.exists())
                self.assertFalse(duplicate.exists())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows dirty-projection watcher")
    def test_cross_root_rename_during_dirty_projection_reproof_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            source = root / "inbox" / "moving-duplicate.md"
            destination = root / "zettels" / "moving-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows
                ._reprove_zettel_objet_link_dirty_projection
            )
            reproof_called = False
            moved = False

            def move_duplicate_during_reproof(*args, **kwargs):
                nonlocal reproof_called, moved
                reproof_called = True
                shutil.copyfile(self.zettel_path(root), source)
                os.replace(source, destination)
                moved = True
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=move_duplicate_during_reproof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(reproof_called)
                self.assertTrue(moved)
                self.assertFalse(source.exists())
                self.assertTrue(destination.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows dirty-projection watcher")
    def test_in_place_duplicate_during_dirty_projection_reproof_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            other = root / "inbox" / "other.md"
            other.write_bytes(
                self.zettel_path(root).read_bytes().replace(
                    ZETTEL_ID.encode("utf-8"),
                    b"zet_20260828_link_race_other",
                    1,
                )
            )
            self.reindex(root)
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows
                ._reprove_zettel_objet_link_dirty_projection
            )
            reproof_called = False
            mutated = False
            mutated_bytes: bytes | None = None

            def mutate_indexed_zettel_during_reproof(*args, **kwargs):
                nonlocal reproof_called, mutated, mutated_bytes
                reproof_called = True
                mutated_bytes = self.zettel_path(root).read_bytes()
                other.write_bytes(mutated_bytes)
                mutated = True
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=mutate_indexed_zettel_during_reproof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(reproof_called)
                self.assertTrue(mutated)
                self.assertTrue(other.is_file())
                self.assertEqual(other.read_bytes(), mutated_bytes)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Linux portable final-proof fence",
    )
    def test_linux_manifest_removed_during_final_proof_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            binding, claim = self.claim(root, plan)
            real_manifest_check = (
                completion_workflows
                ._require_exact_zettel_objet_manifest_target
            )
            check_count = 0

            def remove_target_after_final_manifest_proof(*args, **kwargs):
                nonlocal check_count
                check_count += 1
                result = real_manifest_check(*args, **kwargs)
                if check_count == 2:
                    manifest = self.manifest_path(root)
                    surviving_rows = [
                        line
                        for line in manifest.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if OBJECT_ID not in line
                    ]
                    manifest.write_text(
                        "\n".join(surviving_rows) + "\n",
                        encoding="utf-8",
                    )
                return result

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_require_exact_zettel_objet_manifest_target",
                    side_effect=remove_target_after_final_manifest_proof,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_manifest_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(check_count, 2)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Linux portable final-proof fence",
    )
    def test_linux_duplicate_created_before_final_authority_check_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            duplicate = root / "inbox" / "late-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_manifest_check = (
                completion_workflows
                ._require_exact_zettel_objet_manifest_target
            )
            check_count = 0

            def insert_duplicate_before_final_authority_check(*args, **kwargs):
                nonlocal check_count
                check_count += 1
                if check_count == 2:
                    shutil.copyfile(self.zettel_path(root), duplicate)
                return real_manifest_check(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_require_exact_zettel_objet_manifest_target",
                    side_effect=insert_duplicate_before_final_authority_check,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(check_count, 2)
                self.assertTrue(duplicate.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Linux portable final-proof fence",
    )
    def test_linux_manifest_and_duplicate_proofs_share_stable_point(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            manifest = self.manifest_path(root)
            duplicate = root / "inbox" / "cross-proof-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_manifest_check = (
                completion_workflows
                ._require_exact_zettel_objet_manifest_target
            )
            real_resolve = (
                completion_workflows
                ._resolve_zettel_objet_link_target_bound
            )
            check_count = 0
            resolve_count = 0

            def replace_manifest_proof_with_duplicate(*args, **kwargs):
                nonlocal check_count
                check_count += 1
                if check_count == 2:
                    shutil.copyfile(self.zettel_path(root), duplicate)
                result = real_manifest_check(*args, **kwargs)
                if check_count == 2:
                    manifest.unlink()
                return result

            def remove_duplicate_before_final_resolver(*args, **kwargs):
                nonlocal resolve_count
                resolve_count += 1
                if resolve_count == 1:
                    duplicate.unlink()
                return real_resolve(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_require_exact_zettel_objet_manifest_target",
                    side_effect=replace_manifest_proof_with_duplicate,
                ), mock.patch.object(
                    completion_workflows,
                    "_resolve_zettel_objet_link_target_bound",
                    side_effect=remove_duplicate_before_final_resolver,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_manifest_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(check_count, 2)
                self.assertEqual(resolve_count, 1)
                self.assertFalse(manifest.exists())
                self.assertFalse(duplicate.exists())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Linux portable final-proof fence",
    )
    def test_linux_cross_root_rename_during_final_resolver_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            source = root / "inbox" / "moving-duplicate.md"
            destination = root / "zettels" / "moving-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_resolve = (
                completion_workflows
                ._resolve_zettel_objet_link_target_bound
            )
            real_scandir = os.scandir
            resolve_count = 0
            moved = False

            def race_only_final_resolver(*args, **kwargs):
                nonlocal resolve_count, moved
                resolve_count += 1
                if resolve_count != 1:
                    return real_resolve(*args, **kwargs)
                shutil.copyfile(self.zettel_path(root), source)
                scan_exit_count = 0

                @contextmanager
                def move_after_zettels_snapshot(target):
                    nonlocal scan_exit_count, moved
                    with real_scandir(target) as entries:
                        yield entries
                    scan_exit_count += 1
                    target_is_zettels = False
                    if not isinstance(target, int):
                        try:
                            target_is_zettels = (
                                Path(target).resolve()
                                == (root / "zettels")
                            )
                        except (OSError, TypeError, ValueError):
                            target_is_zettels = False
                    if not moved and (
                        target_is_zettels or scan_exit_count == 2
                    ):
                        os.replace(source, destination)
                        moved = True

                with mock.patch.object(
                    completion_workflows.os,
                    "scandir",
                    new=move_after_zettels_snapshot,
                ):
                    return real_resolve(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_resolve_zettel_objet_link_target_bound",
                    side_effect=race_only_final_resolver,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(resolve_count, 1)
                self.assertTrue(moved)
                self.assertFalse(source.exists())
                self.assertTrue(destination.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Linux portable final-proof fence",
    )
    def test_linux_in_place_duplicate_during_final_resolver_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp)).resolve()
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            receipt = self.path_from_plan(root, plan, "receipt_path")
            other = root / "inbox" / "other.md"
            binding, claim = self.claim(root, plan)
            real_resolve = (
                completion_workflows
                ._resolve_zettel_objet_link_target_bound
            )
            real_read = (
                completion_workflows
                ._read_zettel_objet_candidate_bound_observation
            )
            resolve_count = 0
            mutated = False

            def race_only_final_resolver(*args, **kwargs):
                nonlocal resolve_count, mutated
                resolve_count += 1
                if resolve_count != 1:
                    return real_resolve(*args, **kwargs)
                shutil.copyfile(
                    root
                    / "zettels"
                    / "zet_20110228_fake_school_record.md",
                    other,
                )

                def mutate_after_other_read(*read_args, **read_kwargs):
                    nonlocal mutated
                    observed = real_read(*read_args, **read_kwargs)
                    if (
                        Path(read_args[2]).resolve() == other
                        and not mutated
                    ):
                        other.write_bytes(self.zettel_path(root).read_bytes())
                        mutated = True
                    return observed

                with mock.patch.object(
                    completion_workflows,
                    "_read_zettel_objet_candidate_bound_observation",
                    side_effect=mutate_after_other_read,
                ):
                    return real_resolve(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_resolve_zettel_objet_link_target_bound",
                    side_effect=race_only_final_resolver,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(resolve_count, 1)
                self.assertTrue(mutated)
                self.assertTrue(other.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assert_index_dirty(root)
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    def test_writer_and_readback_failures_roll_back_data_effects(self) -> None:
        modes = ("receipt_write", "canonical_readback", "receipt_readback")
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                plan = self.plan(root)
                before = self.zettel_path(root).read_bytes()
                snapshot = self.path_from_plan(root, plan, "snapshot_path")
                receipt = self.path_from_plan(root, plan, "receipt_path")
                control = self.path_from_plan(
                    root, plan, "control_artifact_path"
                )
                binding, claim = self.claim(root, plan)
                real_create = (
                    archive_services._write_activity_group_bytes_new_file_bound
                )
                real_read = (
                    archive_services._read_activity_group_regular_bytes_bound
                )
                receipt_observation_failed = False
                canonical_observation_failed = False

                def create(
                    parent_binding: dict[str, object],
                    path: Path,
                    value: bytes,
                ) -> None:
                    if (
                        mode == "receipt_write"
                        and Path(path).resolve() == receipt.resolve()
                    ):
                        raise OSError("synthetic receipt failure")
                    real_create(parent_binding, Path(path), value)

                def read(
                    archive_root: Path,
                    parent_binding: dict[str, object],
                    path: Path,
                    *,
                    max_bytes: int,
                ) -> bytes:
                    nonlocal receipt_observation_failed
                    nonlocal canonical_observation_failed
                    raw = real_read(
                        archive_root,
                        parent_binding,
                        Path(path),
                        max_bytes=max_bytes,
                    )
                    if (
                        mode == "canonical_readback"
                        and Path(path).resolve()
                        == self.zettel_path(root).resolve()
                        and raw != before
                        and not canonical_observation_failed
                    ):
                        canonical_observation_failed = True
                        raise OSError("synthetic canonical readback failure")
                    if (
                        mode == "receipt_readback"
                        and Path(path).resolve() == receipt.resolve()
                        and not receipt_observation_failed
                    ):
                        receipt_observation_failed = True
                        raise OSError("synthetic receipt readback failure")
                    return raw

                try:
                    with mock.patch.object(
                        archive_services,
                        "_write_activity_group_bytes_new_file_bound",
                        side_effect=create,
                    ), mock.patch.object(
                        archive_services,
                        "_read_activity_group_regular_bytes_bound",
                        side_effect=read,
                    ):
                        with self.assertRaises(OSError):
                            self.apply(root, plan, binding, claim)
                    self.assertEqual(
                        self.zettel_path(root).read_bytes(), before
                    )
                    self.assertEqual(snapshot.read_bytes(), before)
                    self.assertEqual(
                        receipt.exists(), mode == "receipt_readback"
                    )
                    self.assertEqual(
                        control.read_bytes(),
                        completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES,
                    )
                    self.assertEqual(claim.status, "started")
                finally:
                    self.finish_claim(claim, succeeded=False)

    def test_unverified_rollback_preserves_exact_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            before = self.zettel_path(root).read_bytes()
            snapshot = self.path_from_plan(root, plan, "snapshot_path")
            receipt = self.path_from_plan(root, plan, "receipt_path")
            binding, claim = self.claim(root, plan)
            real_replace = (
                archive_services._replace_regular_file_bytes_compare_and_swap
            )
            real_read = archive_services._read_activity_group_regular_bytes_bound
            replace_count = 0
            receipt_readback_failed = False

            def replace(*args, **kwargs) -> bool:
                nonlocal replace_count
                replace_count += 1
                if replace_count == 2:
                    raise OSError("synthetic rollback publication failure")
                return real_replace(*args, **kwargs)

            def read(
                archive_root: Path,
                parent_binding: dict[str, object],
                path: Path,
                *,
                max_bytes: int,
            ) -> bytes:
                nonlocal receipt_readback_failed
                raw = real_read(
                    archive_root,
                    parent_binding,
                    Path(path),
                    max_bytes=max_bytes,
                )
                if (
                    Path(path).resolve() == receipt.resolve()
                    and not receipt_readback_failed
                ):
                    receipt_readback_failed = True
                    raise OSError("synthetic receipt readback failure")
                return raw

            try:
                with mock.patch.object(
                    archive_services,
                    "_replace_regular_file_bytes_compare_and_swap",
                    side_effect=replace,
                ), mock.patch.object(
                    archive_services,
                    "_read_activity_group_regular_bytes_bound",
                    side_effect=read,
                ):
                    with self.assertRaises(OSError):
                        self.apply(root, plan, binding, claim)

                self.assertNotEqual(self.zettel_path(root).read_bytes(), before)
                self.assertEqual(snapshot.read_bytes(), before)
                self.assertTrue(receipt.is_file())
                self.assertEqual(claim.status, "started")
            finally:
                self.finish_claim(claim, succeeded=False)

    def test_v01_receipt_remains_readable_and_revert_plannable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.plan(root)
            zettel = self.zettel_path(root)
            before = zettel.read_bytes()
            before_sha = hashlib.sha256(before).hexdigest()
            frontmatter, body = archive_services.require_readable_zettel_content(
                zettel
            )
            updated = dict(frontmatter)
            updated["assets"] = [
                *list(frontmatter.get("assets") or []),
                {"object_id": OBJECT_ID, "role": ROLE},
            ]
            updated["updated_at"] = "2026-08-20T00:00:00Z"
            after = (
                "---\n"
                + archive_services.dump_yaml(updated)
                + "---\n"
                + body
            ).encode("utf-8")
            after_sha = hashlib.sha256(after).hexdigest()
            snapshot = self.path_from_plan(root, plan, "snapshot_path")
            receipt_path = self.path_from_plan(root, plan, "receipt_path")
            receipt = {
                "schema": "wom-kit/zettel-objet-link-receipt/v0.1",
                "action": "add_zettel_objet_link",
                "archive_id": archive_services.read_archive_id(root),
                "zettel_id": ZETTEL_ID,
                "zettel_path": f"zettels/{ZETTEL_ID}.md",
                "object_id": OBJECT_ID,
                "role": ROLE,
                "label_sha256": None,
                "link_id": plan["summary"]["link_id"],
                "plan_sha256": plan["summary"]["plan_sha256"],
                "before_zettel_sha256": before_sha,
                "after_zettel_sha256": after_sha,
                "before_snapshot_path": plan["summary"]["snapshot_path"],
                "reviewed_by": "person:historical-fixture",
                "created_at": "2026-08-20T00:00:00Z",
                "privacy": {
                    "label_included": False,
                    "zettel_body_included": False,
                    "object_bytes_read": False,
                    "provider_called": False,
                },
            }
            schema = json.loads(
                (
                    KIT_ROOT
                    / "schemas"
                    / "zettel-objet-link-receipt.schema.json"
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator(schema).validate(receipt)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(before)
            zettel.write_bytes(after)
            receipt_path.write_bytes(
                completion_workflows._canonical_json_bytes(receipt)
            )

            found = completion_workflows.zettel_objet_link_receipts(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertTrue(found["ok"], found)
            self.assertEqual(found["summary"]["validated_receipt_count"], 1)
            self.assertEqual(
                found["summary"]["selected_receipt_path"],
                plan["summary"]["receipt_path"],
            )
            revert = completion_workflows.zettel_objet_link_revert_plan(
                root,
                receipt=plan["summary"]["receipt_path"],
            )
            self.assertTrue(revert["ok"], revert)


if __name__ == "__main__":
    unittest.main()
