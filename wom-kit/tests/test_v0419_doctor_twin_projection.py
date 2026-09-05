from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services


KIT_ROOT = Path(__file__).resolve().parents[1]


class DoctorTwinProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = runpy.run_path(
            str(KIT_ROOT / "tools" / "benchmark_doctor_letter148_scale.py")
        )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-doctor-twin-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.fixture["_copy_archive_skeleton"](self.root)
        self.zettel_id = "zet_20260827_letter148_minted_00000"
        self.source_relative = f"inbox/{self.zettel_id}.md"
        self.target_relative = f"zettels/{self.zettel_id}.md"
        self.snapshot_relative = f"receipts/mint/drafts/{self.zettel_id}.md"
        self.receipt_relative = f"receipts/mint/{self.zettel_id}.mint.json"
        self.source = self.root / self.source_relative
        self.target = self.root / self.target_relative
        self.snapshot = self.root / self.snapshot_relative
        self.receipt_path = self.root / self.receipt_relative
        self.data = self.fixture["_source_frontmatter"](self.zettel_id)
        body = "Independent synthetic source body."
        source_bytes = self.fixture["_render_zettel"](self.data, body)
        self.target_data = self.fixture["_minted_canonical_frontmatter"](
            self.zettel_id,
            title="Independent synthetic target",
            receipt_path=self.receipt_relative,
            snapshot_path=self.snapshot_relative,
        )
        target_bytes = self.fixture["_render_zettel"](self.target_data, body)
        for path, raw in (
            (self.source, source_bytes),
            (self.snapshot, source_bytes),
            (self.target, target_bytes),
        ):
            self.fixture["_write_bytes"](path, raw)
        self.receipt = self.fixture["_build_applied_mint_receipt"](
            self.root,
            zettel_id=self.zettel_id,
            title="Independent synthetic target",
            source_path=self.source,
            source_relative=self.source_relative,
            source_frontmatter=self.data,
            source_body=body,
            target_relative=self.target_relative,
            target_sha256=hashlib.sha256(target_bytes).hexdigest(),
            receipt_relative=self.receipt_relative,
            snapshot_relative=self.snapshot_relative,
            validate_fixture_schema=True,
        )
        self.write_receipt(self.receipt)

    def write_receipt(self, receipt) -> None:
        self.fixture["_write_bytes"](
            self.receipt_path, self.fixture["_json_bytes"](receipt)
        )

    def test_genuine_twin_diagnostic_never_calls_writer_or_index_planner(self) -> None:
        doctor = archive_cli.Doctor(self.root)
        with (
            mock.patch.object(archive_services, "is_minted_inbox_draft_twin", side_effect=AssertionError("writer helper")),
            mock.patch.object(archive_services, "minted_draft_retirement_plan", side_effect=AssertionError("writer plan")),
            mock.patch.object(archive_services, "require_current_zettel_index", side_effect=AssertionError("index scan")),
        ):
            doctor._check_zettel_file(self.source, "draft")
        twins = [item for item in doctor.diagnostics if item.code == "minted_inbox_draft_twin_pending_retire"]
        self.assertEqual(len(twins), 1)
        self.assertIn("independently", twins[0].message)

    def test_unmatched_drafts_do_not_trigger_archive_index_scans(self) -> None:
        doctor = archive_cli.Doctor(self.root)
        with mock.patch.object(
            archive_services, "require_current_zettel_index", side_effect=AssertionError("index scan")
        ), mock.patch.object(
            archive_services, "minted_draft_retirement_plan", side_effect=AssertionError("writer plan")
        ):
            for index in range(100):
                data = self.fixture["_source_frontmatter"](
                    f"zet_20260827_unminted_{index:05d}"
                )
                path = self.root / "inbox" / f"unminted-{index:05d}.md"
                self.fixture["_write_bytes"](
                    path, self.fixture["_render_zettel"](data, "Unminted evidence.")
                )
                self.assertFalse(doctor._observed_minted_draft_twin(path, data))

    def test_bad_receipt_bindings_do_not_become_twin_evidence(self) -> None:
        cases = (
            ("dry_run", True),
            ("authority_mode", "unknown"),
            ("source", {**self.receipt["source"], "path": "inbox/other.md"}),
            ("source", {**self.receipt["source"], "sha256": "0" * 64}),
            ("snapshot", {**self.receipt["snapshot"], "sha256": "0" * 64}),
            ("snapshot", {**self.receipt["snapshot"], "path": "../outside.md"}),
            ("target", {**self.receipt["target"], "sha256": "0" * 64}),
            ("zettel", {"id": "zet_20260827_wrong_00000"}),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                receipt = json.loads(json.dumps(self.receipt))
                receipt[field] = value
                self.write_receipt(receipt)
                doctor = archive_cli.Doctor(self.root)
                self.assertFalse(doctor._observed_minted_draft_twin(self.source, self.data))

    def test_same_doctor_does_not_reuse_twin_after_source_changes(self) -> None:
        doctor = archive_cli.Doctor(self.root)
        self.assertTrue(doctor._observed_minted_draft_twin(self.source, self.data))
        self.source.write_bytes(self.source.read_bytes() + b"changed")
        self.assertFalse(doctor._observed_minted_draft_twin(self.source, self.data))

    def test_exact_snapshot_hash_can_differ_only_by_verified_newline_bom(self) -> None:
        snapshot_bytes = b"\xef\xbb\xbf" + self.snapshot.read_bytes().replace(b"\n", b"\r\n")
        self.snapshot.write_bytes(snapshot_bytes)
        self.receipt["snapshot"]["sha256"] = hashlib.sha256(snapshot_bytes).hexdigest()
        self.write_receipt(self.receipt)
        doctor = archive_cli.Doctor(self.root)
        self.assertTrue(doctor._observed_minted_draft_twin(self.source, self.data))

    def test_retired_slot_and_canonical_backlink_fail_closed(self) -> None:
        retired = self.root / archive_services.MINT_RETIRED_DRAFT_RECEIPTS_DIR / f"{self.zettel_id}.retire-draft.json"
        retired.mkdir()
        self.assertFalse(archive_cli.Doctor(self.root)._observed_minted_draft_twin(self.source, self.data))
        retired.rmdir()
        self.target_data["mint"]["receipt_path"] = "receipts/mint/another.mint.json"
        raw = self.fixture["_render_zettel"](self.target_data, "Independent synthetic source body.")
        self.target.write_bytes(raw)
        self.receipt["target"]["sha256"] = hashlib.sha256(raw).hexdigest()
        self.write_receipt(self.receipt)
        self.assertFalse(archive_cli.Doctor(self.root)._observed_minted_draft_twin(self.source, self.data))

    def test_read_only_twin_evidence_does_not_authorize_real_retirement_plan(self) -> None:
        self.assertTrue(archive_cli.Doctor(self.root)._observed_minted_draft_twin(self.source, self.data))
        with mock.patch.object(
            archive_services, "require_current_zettel_index", return_value={"ok": False}
        ) as fresh_index:
            plan = archive_services.minted_draft_retirement_plan(
                self.root, relative_path=self.source_relative
            )
        self.assertFalse(plan["ok"])
        self.assertIn(archive_services.INDEX_REBUILD_REQUIRED, plan["blockers"])
        self.assertGreaterEqual(fresh_index.call_count, 1)


if __name__ == "__main__":
    unittest.main()
