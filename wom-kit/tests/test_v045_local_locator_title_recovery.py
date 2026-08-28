from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from wom_kit import archive_cli, archive_services, completion_workflows
from wom_kit.local_locator_recovery import (
    notion_locator_mirror_recovery_execution_plan,
    notion_locator_mirror_recovery_plan,
    notion_locator_orphan_recovery_execution_plan,
    notion_locator_orphan_recovery_plan,
)
from wom_kit.local_title_recovery import (
    zet_identifier_title_recovery_execution_plan,
    zet_identifier_title_recovery_plan,
    zet_title_field_local_execution_plan,
    zet_title_field_local_recovery_plan,
    zet_title_recovery_execution_plan,
)
from wom_kit.exact_operation_manifest import (
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.local_recovery_execution import (
    _run_with_store,
    persist_local_recovery_control,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
SOURCE_ID = "123456781234123412341234567890ab"
PRIVATE_URL = "https://private.example.invalid/provider/record-8841"
HUMAN_TITLE = "Recovered Human Source Title"


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class V045LocalLocatorTitleRecoveryTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        indexed = archive_services.index_archive(root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        return root

    def zettel_path(self, root: Path) -> Path:
        return root / "zettels" / f"{ZETTEL_ID}.md"

    def execute(self, plan, *, mode: str):
        indexed = archive_services.index_archive(plan.archive_root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        with exact_operation_writer_lock(plan.archive_root) as lock:
            return _run_with_store(
                plan,
                None,
                FileExactOperationCheckpointStore(
                    plan.archive_root,
                    writer_lock=lock,
                ),
                mode=mode,
                resume=False,
                progress_hook=None,
            )

    def write_notion_zettel(
        self,
        root: Path,
        *,
        title: str,
        body: str,
        omitted_count: int = 1,
    ) -> bytes:
        path = self.zettel_path(root)
        archive_id = archive_services.read_archive_id(root)
        raw = (
            "---\n"
            f"id: {ZETTEL_ID}\n"
            f"title: {json.dumps(title, ensure_ascii=False)}\n"
            "status: canonical\n"
            f"archive_id: {archive_id}\n"
            "facets:\n"
            f"  source_page_id: {SOURCE_ID}\n"
            "  source_system: notion_db3\n"
            f"  source_locator_omitted_count: {omitted_count}\n"
            "assets: []\n"
            "edges: []\n"
            "---\n"
            f"{body}"
        ).encode("utf-8")
        path.write_bytes(raw)
        return raw

    def write_title_mirrors(
        self,
        parent: Path,
        *,
        source_title: str,
        markdown: str,
    ) -> Path:
        markdown_path = parent / "pages.markdown.jsonl"
        markdown_path.write_text(
            json.dumps(
                {
                    "page_id": SOURCE_ID,
                    "markdown": markdown,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (parent / "pages.index.jsonl").write_text(
            json.dumps(
                {
                    "page_id": SOURCE_ID,
                    "index": source_title,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return markdown_path

    def write_markup_receipt(
        self,
        root: Path,
        *,
        before: bytes,
        after: bytes,
        token: str,
    ) -> str:
        before_digest = hashlib.sha256(before).hexdigest()
        after_digest = hashlib.sha256(after).hexdigest()
        transaction = (
            ".wom-scratch/markup-normalization/transactions/" + token * 64
        )
        before_relative = (
            f"{transaction}/snapshots/000000.before.{before_digest}.bin"
        )
        after_relative = (
            f"{transaction}/snapshots/000000.after.{after_digest}.bin"
        )
        for relative, raw in (
            (before_relative, before),
            (after_relative, after),
        ):
            path = root.joinpath(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        receipt_relative = (
            "receipts/markup-normalization/" + token * 64 + ".json"
        )
        receipt = {
            "schema": completion_workflows.MARKUP_NORMALIZATION_RECEIPT_SCHEMA,
            "archive_id": archive_services.read_archive_id(root),
            "plan_sha256": token * 64,
            "item_count": 1,
            "items": [
                {
                    "index": 0,
                    "zettel_id": ZETTEL_ID,
                    "path": f"zettels/{ZETTEL_ID}.md",
                    "before_sha256": before_digest,
                    "after_sha256": after_digest,
                    "snapshot_path": before_relative,
                    "before_snapshot_path": before_relative,
                    "after_snapshot_path": after_relative,
                }
            ],
        }
        receipt_path = root.joinpath(*receipt_relative.split("/"))
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return receipt_relative

    def test_mirror_plan_classifies_complete_pair_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            self.write_notion_zettel(
                root,
                title="Current Human Title",
                body="[source locator omitted]\n",
            )
            mirror = parent / "pages.markdown.jsonl"
            mirror.write_text(
                json.dumps(
                    {
                        "page_id": SOURCE_ID,
                        "markdown": f"private [{PRIVATE_URL}]({PRIVATE_URL})",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = notion_locator_mirror_recovery_plan(
                root,
                source_mirror=mirror,
                expected_zettel_count=1,
                expected_pair_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["target_zettel_count"], 1)
            self.assertEqual(result["summary"]["locator_pair_count"], 1)
            self.assertEqual(
                result["summary"]["classified_pair_count"], 1
            )
            manifest = result["exact_operation_manifest"]
            self.assertEqual(manifest["item_count"], 2)
            self.assertEqual(
                result["summary"]["locator_record_manifest_item_count"], 1
            )
            self.assertEqual(
                result["summary"]["classification_ledger_item_count"], 1
            )
            evidence = manifest["operation_evidence"]
            self.assertEqual(evidence["counts"]["locator_pair_count"], 1)
            self.assertIn("locator_pair_set_sha256", evidence["digests"])
            rendered = json.dumps(result)
            self.assertNotIn(PRIVATE_URL, rendered)
            self.assertNotIn(SOURCE_ID, rendered)
            self.assertNotIn(ZETTEL_ID, rendered)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "external-locator-record",
                        str(root),
                        "--source-mirror",
                        str(mirror),
                        "--expected-zettel-count",
                        "1",
                        "--expected-pair-count",
                        "1",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            cli_plan = json.loads(stdout.getvalue())
            self.assertEqual(cli_plan["domain"], "notion_locator_mirror")
            self.assertFalse(cli_plan["writes"])
            self.assertFalse(cli_plan["private_values_echoed"])

            execution = notion_locator_mirror_recovery_execution_plan(
                root,
                source_mirror=mirror,
                expected_zettel_count=1,
                expected_pair_count=1,
            )
            applied = self.execute(execution, mode="apply")
            self.assertTrue(applied["ok"], applied)
            locator_relative = completion_workflows._record_relative(ZETTEL_ID)
            locator_path = root.joinpath(*locator_relative.split("/"))
            self.assertTrue(locator_path.is_file())
            locator_record = json.loads(locator_path.read_text(encoding="utf-8"))
            self.assertTrue(
                completion_workflows._locator_record_is_valid(
                    locator_record,
                    archive_id=archive_services.read_archive_id(root),
                    zettel_id=ZETTEL_ID,
                )
            )
            reverted = self.execute(execution, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertFalse(locator_path.exists())

            mismatch = notion_locator_mirror_recovery_plan(
                root,
                source_mirror=mirror,
                expected_zettel_count=1,
                expected_pair_count=2,
            )
            self.assertFalse(mismatch["ok"])
            self.assertIsNone(mismatch["exact_operation_manifest"])
            self.assertIn(
                "local_locator_expected_pair_count_mismatch",
                mismatch["blockers"],
            )

    def test_markup_receipt_reconstructs_exact_orphan_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            before = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=f"prefix {marker} suffix\n",
            )
            after = before.replace(marker.encode("utf-8"), b"")
            self.zettel_path(root).write_bytes(after)
            before_digest = hashlib.sha256(before).hexdigest()
            after_digest = hashlib.sha256(after).hexdigest()
            transaction = (
                ".wom-scratch/markup-normalization/transactions/"
                + "1" * 64
            )
            before_relative = (
                f"{transaction}/snapshots/000000.before.{before_digest}.bin"
            )
            after_relative = (
                f"{transaction}/snapshots/000000.after.{after_digest}.bin"
            )
            for relative, raw in (
                (before_relative, before),
                (after_relative, after),
            ):
                path = root.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            receipt_relative = (
                "receipts/markup-normalization/" + "1" * 64 + ".json"
            )
            receipt = {
                "schema": completion_workflows.MARKUP_NORMALIZATION_RECEIPT_SCHEMA,
                "archive_id": archive_services.read_archive_id(root),
                "plan_sha256": "1" * 64,
                "item_count": 1,
                "items": [
                    {
                        "index": 0,
                        "zettel_id": ZETTEL_ID,
                        "path": f"zettels/{ZETTEL_ID}.md",
                        "before_sha256": before_digest,
                        "after_sha256": after_digest,
                        "snapshot_path": before_relative,
                        "before_snapshot_path": before_relative,
                        "after_snapshot_path": after_relative,
                    }
                ],
            }
            receipt_path = root.joinpath(*receipt_relative.split("/"))
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            result = notion_locator_orphan_recovery_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["orphan_row_count"], 1)
            self.assertEqual(result["summary"]["restore_ready_count"], 1)
            self.assertEqual(result["summary"]["review_pending_count"], 0)
            manifest = result["exact_operation_manifest"]
            self.assertEqual(manifest["item_count"], 2)
            self.assertEqual(
                result["summary"]["marker_restore_manifest_item_count"], 1
            )
            self.assertEqual(
                result["summary"]["classification_ledger_item_count"], 1
            )
            self.assertEqual(
                manifest["operation_evidence"]["counts"][
                    "classified_orphan_row_count"
                ],
                1,
            )

            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            applied = self.execute(execution, mode="apply")
            self.assertTrue(applied["ok"], applied)
            self.assertIn(
                marker,
                self.zettel_path(root).read_text(encoding="utf-8"),
            )
            reverted = self.execute(execution, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertNotIn(
                marker,
                self.zettel_path(root).read_text(encoding="utf-8"),
            )

    def test_markup_receipt_never_rolls_back_other_normalization_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            before = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=(
                    f'<span style="color:red"></span>\n'
                    f'<file src="{marker}"></file>\n'
                ),
            )
            valid_reference = (
                "[Attached objet](wom-objet:sha256:" + "a" * 64 + ")\n"
            )
            after = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=valid_reference,
            )
            receipt_relative = self.write_markup_receipt(
                root,
                before=before,
                after=after,
                token="2",
            )
            result = notion_locator_orphan_recovery_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["restore_ready_count"], 0)
            self.assertEqual(result["summary"]["review_pending_count"], 1)
            self.assertEqual(
                result["summary"]["marker_restore_manifest_item_count"], 0
            )
            self.assertEqual(result["exact_operation_manifest"]["item_count"], 1)
            rendered = json.dumps(result)
            self.assertNotIn(valid_reference.strip(), rendered)

            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            applied = self.execute(execution, mode="apply")
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(self.zettel_path(root).read_bytes(), after)

    def test_suffix_identifier_uses_own_source_index_title_not_body_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            identifier_title = "a" * 32 + " (1)"
            self.write_notion_zettel(
                root,
                title=identifier_title,
                body="\\{wrong body title\\}에 대한 정보를 담은 *zet*입니다.\n\nprivate body\n",
            )
            self.assertTrue(
                archive_services.zet_title_is_identifier_shaped(
                    identifier_title
                )
            )
            self.assertFalse(
                archive_services.zet_title_is_identifier_shaped(
                    "A normal title (1)"
                )
            )
            source_index = self.write_title_mirrors(
                parent,
                source_title=HUMAN_TITLE,
                markdown=(
                    "# A body section that is not the source title\n\n"
                    "\\{wrong body title\\}에 대한 정보를 담은 *zet*입니다.\n"
                ),
            )
            result = zet_identifier_title_recovery_plan(
                root,
                source_mirror=source_index,
                expected_identifier_title_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["identifier_title_count"], 1)
            self.assertEqual(
                result["summary"]["exact_recovery_ready_count"], 1
            )
            self.assertEqual(
                result["summary"][
                    "duplicate_suffix_identifier_title_count"
                ],
                1,
            )
            self.assertEqual(result["exact_operation_manifest"]["item_count"], 2)
            self.assertEqual(
                result["summary"]["title_change_manifest_item_count"], 1
            )
            self.assertEqual(
                result["summary"]["classification_ledger_item_count"], 1
            )
            rendered = json.dumps(result)
            self.assertNotIn(HUMAN_TITLE, rendered)
            self.assertNotIn(SOURCE_ID, rendered)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "zet-title-remap-write",
                        str(root),
                        "--source-mirror",
                        str(source_index),
                        "--expected-identifier-title-count",
                        "1",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            cli_plan = json.loads(stdout.getvalue())
            self.assertEqual(cli_plan["domain"], "zet_title_recovery")
            self.assertFalse(cli_plan["writes"])
            self.assertFalse(cli_plan["private_values_echoed"])

            execution = zet_title_recovery_execution_plan(
                root,
                source_mirror=source_index,
                expected_identifier_title_count=1,
            )
            applied = self.execute(execution, mode="apply")
            self.assertTrue(applied["ok"], applied)
            frontmatter, _body = archive_services.require_readable_zettel_content(
                self.zettel_path(root)
            )
            self.assertEqual(frontmatter["title"], HUMAN_TITLE)
            persist_local_recovery_control(execution)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "zet-title-remap-write",
                        str(root),
                        "--revert-recovery",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            preview = json.loads(stdout.getvalue())
            self.assertEqual(preview["state"], "ready_to_revert")
            self.assertTrue(
                preview["control_discovery"]["auto_discovered"]
            )
            reverted = self.execute(execution, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            frontmatter, _body = archive_services.require_readable_zettel_content(
                self.zettel_path(root)
            )
            self.assertEqual(frontmatter["title"], identifier_title)

    def test_identifier_title_without_source_index_value_never_uses_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            identifier_title = "b" * 32
            private_body_title = "Private body sentence must not become a title"
            self.write_notion_zettel(
                root,
                title=identifier_title,
                body=private_body_title + "\n",
            )
            source_mirror = self.write_title_mirrors(
                parent,
                source_title="",
                markdown=private_body_title + "\n",
            )
            result = zet_identifier_title_recovery_plan(
                root,
                source_mirror=source_mirror,
                expected_identifier_title_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["exact_recovery_ready_count"], 0)
            self.assertEqual(result["summary"]["source_title_unavailable_count"], 1)
            self.assertEqual(result["summary"]["title_change_manifest_item_count"], 0)
            self.assertNotIn(private_body_title, json.dumps(result))

    def test_title_receipt_audit_uses_title_field_not_whole_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            before_title = "b" * 32
            before = self.write_notion_zettel(
                root,
                title=before_title,
                body="before body\n",
            )
            after_title = "Applied Human Title"
            after = before.replace(
                json.dumps(before_title).encode("utf-8"),
                json.dumps(after_title).encode("utf-8"),
                1,
            )
            # A later body edit deliberately destroys the old whole-file hash.
            current = after.replace(b"before body", b"later body edit")
            self.zettel_path(root).write_bytes(current)
            snapshot = archive_services.zet_revision_before_snapshot_descriptor(
                before
            )
            snapshot_path = root.joinpath(
                *snapshot["logical_key"].split("/")
            )
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_bytes(before)
            proposal_digest = "1" * 64
            receipt_relative = (
                "receipts/revisions/title-remap/"
                f"{proposal_digest}.zet-title-remap.json"
            )
            item = {
                "row_index": 0,
                "zettel_id": ZETTEL_ID,
                "canonical_path": f"zettels/{ZETTEL_ID}.md",
                "basis": "source_export_property",
                "before_file_sha256": _sha(before),
                "after_file_sha256": _sha(after),
                "before_title_sha256": _sha(before_title.encode("utf-8")),
                "after_title_sha256": _sha(after_title.encode("utf-8")),
                "body_sha256": _sha(b"before body\n"),
                "before_snapshot": snapshot,
            }
            receipt = {
                "schema": archive_services.ZET_TITLE_REMAP_RECEIPT_SCHEMA,
                "action": "zet_title_remap_write",
                "status": "applied",
                "applied_at": "2026-08-23T00:00:00Z",
                "archive_id": archive_services.read_archive_id(root),
                "proposal_sha256": "sha256:" + proposal_digest,
                "plan_digest": "sha256:" + "2" * 64,
                "write_plan_digest": "sha256:" + "3" * 64,
                "reviewed_by": "person:test",
                "human_affirmation": "all_proposed_titles_reviewed",
                "item_count": 1,
                "items": [item],
                "mutation_contract": {
                    "field_replaced": "frontmatter.title",
                    "body_bytes_preserved": True,
                    "other_frontmatter_semantics_preserved": True,
                    "updated_at_changed": False,
                    "prior_byte_snapshots_verified_before_first_canonical_write": True,
                    "rollback_on_runtime_failure": True,
                    "crash_recovery_journal_written": True,
                },
                "privacy_guards": {
                    "old_title_text_stored_in_receipt": False,
                    "new_title_text_stored_in_receipt": False,
                    "body_text_stored_in_receipt": False,
                    "provider_api_called": False,
                    "model_called": False,
                    "secret_store_or_environment_read": False,
                },
            }
            receipt_path = root.joinpath(*receipt_relative.split("/"))
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_raw = (
                json.dumps(receipt, ensure_ascii=False) + "\n"
            ).encode("utf-8")
            receipt_path.write_bytes(receipt_raw)

            audit = zet_title_field_local_recovery_plan(root)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(audit["summary"]["title_receipt_item_count"], 1)
            self.assertEqual(
                audit["summary"]["applied_title_matches_count"], 1
            )
            self.assertEqual(audit["summary"]["title_divergent_count"], 0)

            revert = zet_title_field_local_recovery_plan(
                root,
                receipt_path=receipt_relative,
                expected_receipt_sha256=_sha(receipt_raw),
                build_revert_manifest=True,
            )
            self.assertTrue(revert["ok"], revert)
            self.assertEqual(revert["exact_operation_manifest"]["item_count"], 2)
            self.assertEqual(
                revert["summary"]["title_change_manifest_item_count"], 1
            )
            self.assertEqual(
                revert["summary"]["classification_ledger_item_count"], 1
            )
            self.assertEqual(
                revert["exact_operation_manifest"]["items"][0]["fields"][0][
                    "field_ref"
                ],
                "frontmatter.title",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "zet-title-remap-revert",
                        str(root),
                        "--receipt",
                        receipt_relative,
                        "--expected-receipt-sha256",
                        _sha(receipt_raw),
                        "--field-local",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            cli_plan = json.loads(stdout.getvalue())
            self.assertEqual(cli_plan["domain"], "zet_title_field_revert")
            self.assertFalse(cli_plan["writes"])
            self.assertFalse(cli_plan["private_values_echoed"])

            execution = zet_title_field_local_execution_plan(
                root,
                receipt_path=receipt_relative,
                expected_receipt_sha256=_sha(receipt_raw),
                build_revert_manifest=True,
            )
            applied = self.execute(execution, mode="apply")
            self.assertTrue(applied["ok"], applied)
            frontmatter, body = archive_services.require_readable_zettel_content(
                self.zettel_path(root)
            )
            self.assertEqual(frontmatter["title"], before_title)
            self.assertIn("later body edit", body)
            reverted = self.execute(execution, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            frontmatter, body = archive_services.require_readable_zettel_content(
                self.zettel_path(root)
            )
            self.assertEqual(frontmatter["title"], after_title)
            self.assertIn("later body edit", body)

    def test_expected_counts_require_their_evidence_mode(self) -> None:
        cases = [
            (
                archive_cli.command_notion_import_locator_evidence_plan,
                SimpleNamespace(
                    dry_run=True,
                    source_mirror=None,
                    expected_zettel_count=1,
                    expected_pair_count=None,
                ),
                "--source-mirror",
            ),
            (
                archive_cli.command_notion_import_locator_loss_audit,
                SimpleNamespace(
                    dry_run=True,
                    markup_receipt=None,
                    expected_orphan_row_count=1,
                ),
                "--markup-receipt",
            ),
            (
                archive_cli.command_zet_title_remap_receipt_audit,
                SimpleNamespace(
                    dry_run=True,
                    source_mirror=None,
                    expected_identifier_title_count=1,
                ),
                "--source-mirror",
            ),
        ]
        for command, args, expected in cases:
            with self.subTest(command=command.__name__):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    status = command(args)
                self.assertEqual(status, 1)
                self.assertIn(expected, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
