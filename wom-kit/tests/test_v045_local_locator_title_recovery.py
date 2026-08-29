from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    local_locator_recovery,
    local_recovery_execution,
    local_title_recovery,
)
from wom_kit.exact_human_approval import (
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    _execute_exact_human_approved_write_core,
)
from wom_kit.local_locator_recovery import (
    notion_locator_local_recovery_execution_plan,
    notion_locator_mirror_recovery_execution_plan,
    notion_locator_mirror_recovery_plan,
    notion_locator_orphan_recovery_execution_plan,
    notion_locator_orphan_recovery_plan,
    verified_notion_locator_resolution_evidence,
)
from wom_kit.local_title_recovery import (
    zet_identifier_title_recovery_execution_plan,
    zet_identifier_title_recovery_plan,
    zet_title_field_local_execution_plan,
    zet_title_field_local_recovery_plan,
    zet_title_recovery_execution_plan,
)
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.local_recovery_execution import (
    _run_with_store,
    execute_local_recovery,
    load_local_recovery_plan,
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


class _ApproveNative:
    def show(self, **_kwargs: object) -> tuple[int, bool]:
        return APPROVE_BUTTON_ID, True


class _StableKeyProvider:
    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        del create_if_missing
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


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

    def execute(self, plan, *, mode: str, authority=None):
        indexed = archive_services.index_archive(plan.archive_root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        with exact_operation_writer_lock(plan.archive_root) as lock:
            return _run_with_store(
                plan,
                authority,
                FileExactOperationCheckpointStore(
                    plan.archive_root,
                    writer_lock=lock,
                ),
                mode=mode,
                resume=False,
                progress_hook=None,
            )

    def execute_authenticated(
        self,
        plan,
        *,
        mode: str = "apply",
        key_provider: _StableKeyProvider | None = None,
    ):
        keys = key_provider or _StableKeyProvider()

        def approved_workflow(archive_root, context, writer):
            return _execute_exact_human_approved_write_core(
                archive_root,
                context,
                writer,
                native=_ApproveNative(),
                key_provider=keys,
            )

        with mock.patch.object(
            local_recovery_execution,
            "_execute_exact_human_approved_write",
            new=approved_workflow,
        ):
            result = execute_local_recovery(plan, mode=mode)
        return result, keys

    def locator_audit_authenticated(
        self,
        root: Path,
        key_provider: _StableKeyProvider,
    ) -> dict[str, Any]:
        with mock.patch(
            "wom_kit.exact_human_approval_workflow._production_key_provider",
            return_value=key_provider,
        ):
            return archive_services.notion_import_locator_loss_audit(root)

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

    @staticmethod
    def create_directory_junction(link: Path, target: Path) -> None:
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            raise OSError("Windows junction creation failed")

    @staticmethod
    def remove_directory_junction(link: Path) -> None:
        os.rmdir(link)

    def write_markup_receipt(
        self,
        root: Path,
        *,
        before: bytes,
        after: bytes,
        token: str,
        binding_manifest_sha256: str | None = None,
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
        if binding_manifest_sha256 is not None:
            receipt["binding_manifest_sha256"] = binding_manifest_sha256
        receipt_path = root.joinpath(*receipt_relative.split("/"))
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return receipt_relative

    def approval_authority(self) -> ExactOperationApprovalAuthority:
        return ExactOperationApprovalAuthority.from_reference(
            {
                "schema_version": (
                    "wom-kit/exact-human-approval-reference/v0.1"
                ),
                "approval_id": "approval_" + "a" * 32,
                "context_sha256": "sha256:" + "b" * 64,
                "approval_authority_sha256": "sha256:" + "c" * 64,
                "one_use": True,
            }
        )

    def write_verified_reference_history(
        self,
        root: Path,
        *,
        token: str,
        newline: str = "\n",
    ) -> tuple[str, bytes, bytes]:
        marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
        source_fragment = f'<file src="{marker}"></file>'
        before = self.write_notion_zettel(
            root,
            title="Current Human Title",
            body=source_fragment + newline,
        )
        object_id = (
            "sha256:"
            "acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
        )
        replacement = f"[Attached objet](wom-objet:{object_id})"
        after = self.write_notion_zettel(
            root,
            title="Current Human Title",
            body=replacement + newline,
        )
        binding_document = {
            "schema": (
                completion_workflows.MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA
            ),
            "archive_id": archive_services.read_archive_id(root),
            "bindings": [
                {
                    "zettel_id": ZETTEL_ID,
                    "tag_sha256": completion_workflows._sha256_bytes(
                        source_fragment.encode("utf-8")
                    ),
                    "binding_kind": "objet",
                    "binding_id": object_id,
                }
            ],
        }
        binding_raw = json.dumps(binding_document).encode("utf-8")
        binding_path = (
            root
            / ".wom-scratch"
            / "markup-bindings"
            / f"reviewed-{token}.json"
        )
        binding_path.parent.mkdir(parents=True, exist_ok=True)
        binding_path.write_bytes(binding_raw)
        receipt_relative = self.write_markup_receipt(
            root,
            before=before,
            after=after,
            token=token,
            binding_manifest_sha256=hashlib.sha256(binding_raw).hexdigest(),
        )
        return receipt_relative, before, after

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
            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            self.assertEqual(indexed["index_state"], "current", indexed)
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            self.assertIn(
                marker,
                self.zettel_path(root).read_text(encoding="utf-8"),
            )
            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(
                audit["summary"]["verified_reference_classified_count"],
                1,
            )
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                0,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_state"],
                "known",
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_count"],
                1,
            )

            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=execution.manifest.manifest_sha256,
            )
            reverted, _keys = self.execute_authenticated(
                loaded,
                mode="revert",
                key_provider=keys,
            )
            self.assertTrue(reverted["ok"], reverted)
            self.assertNotIn(
                marker,
                self.zettel_path(root).read_text(encoding="utf-8"),
            )

    def test_normal_maintain_authenticated_post_apply_audit_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            before = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=f"prefix {marker} suffix\n",
            )
            after = before.replace(marker.encode("utf-8"), b"")
            receipt_relative = self.write_markup_receipt(
                root,
                before=before,
                after=after,
                token="6",
            )
            self.zettel_path(root).write_bytes(before)

            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            self.assertEqual(
                execution.public_summary["normal_maintain_count"],
                1,
            )
            self.assertEqual(
                execution.public_summary["restore_ready_count"],
                0,
            )

            indexed = archive_services.index_archive(root)
            self.assertTrue(indexed["ok"], indexed)
            self.assertEqual(indexed["index_state"], "current", indexed)
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(self.zettel_path(root).read_bytes(), before)

            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(
                audit["summary"]["verified_reference_classified_count"],
                1,
            )
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                0,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_state"],
                "known",
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_count"],
                1,
            )

            self.zettel_path(root).write_bytes(
                before.replace(b"suffix", b"changed", 1)
            )
            drifted = self.locator_audit_authenticated(root, keys)
            self.assertEqual(
                drifted["summary"]["unresolved_occurrence_state"],
                "unknown",
            )
            self.assertIn(
                "verified_reference_resolution_body_drifted",
                drifted["summary"]["unresolved_occurrence_reason_codes"],
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

    def test_verified_reference_resolution_receipt_closes_exact_loss_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            source_fragment = f'<file src="{marker}"></file>'
            before = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=source_fragment + "\n",
            )
            object_id = (
                "sha256:"
                "acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            replacement = f"[Attached objet](wom-objet:{object_id})"
            after = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=replacement + "\n",
            )
            binding_document = {
                "schema": (
                    completion_workflows
                    .MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA
                ),
                "archive_id": archive_services.read_archive_id(root),
                "bindings": [
                    {
                        "zettel_id": ZETTEL_ID,
                        "tag_sha256": completion_workflows._sha256_bytes(
                            source_fragment.encode("utf-8")
                        ),
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    }
                ],
            }
            binding_raw = json.dumps(binding_document).encode("utf-8")
            binding_path = (
                root
                / ".wom-scratch"
                / "markup-bindings"
                / "reviewed.json"
            )
            binding_path.parent.mkdir(parents=True, exist_ok=True)
            binding_path.write_bytes(binding_raw)
            receipt_relative = self.write_markup_receipt(
                root,
                before=before,
                after=after,
                token="3",
                binding_manifest_sha256=hashlib.sha256(
                    binding_raw
                ).hexdigest(),
            )

            result = notion_locator_orphan_recovery_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(
                result["summary"][
                    "resolved_by_verified_reference_count"
                ],
                1,
            )
            self.assertEqual(result["summary"]["restore_ready_count"], 0)
            self.assertEqual(
                result["summary"]["marker_restore_manifest_item_count"],
                0,
            )
            self.assertEqual(
                result["exact_operation_manifest"]["item_count"],
                1,
            )
            rendered = json.dumps(result)
            self.assertNotIn(ZETTEL_ID, rendered)
            self.assertNotIn(object_id, rendered)
            self.assertNotIn(source_fragment, rendered)
            self.assertNotIn(replacement, rendered)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "notion-import-locator-loss-audit",
                        str(root),
                        "--all-markup-receipts",
                        "--expected-orphan-row-count",
                        "1",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            cli_result = json.loads(stdout.getvalue())
            self.assertEqual(
                cli_result["orphan_recovery"]["summary"][
                    "resolved_by_verified_reference_count"
                ],
                1,
            )

            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=1,
            )
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(self.zettel_path(root).read_bytes(), after)

            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(
                audit["summary"][
                    "verified_reference_resolution_count"
                ],
                1,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_state"],
                "known",
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_count"],
                0,
            )

            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=execution.manifest.manifest_sha256,
            )
            reverted, _keys = self.execute_authenticated(
                loaded,
                mode="revert",
                key_provider=keys,
            )
            self.assertTrue(reverted["ok"], reverted)
            after_revert = self.locator_audit_authenticated(root, keys)
            self.assertEqual(
                after_revert["summary"]["unresolved_occurrence_state"],
                "unknown",
            )

    def test_self_hashed_resolution_receipt_without_succeeded_claim_is_not_trusted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            receipt, _before, _after = self.write_verified_reference_history(
                root,
                token="d",
            )
            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt],
                expected_orphan_row_count=1,
            )
            applied = self.execute(
                execution,
                mode="apply",
                authority=self.approval_authority(),
            )
            self.assertTrue(applied["ok"], applied)
            self.assertNotIn(
                "completion_authentication",
                applied["execution"],
            )

            evidence = verified_notion_locator_resolution_evidence(root)
            self.assertEqual(evidence["verified_ledger_count"], 0)
            self.assertEqual(evidence["verified_resolution_row_count"], 0)
            self.assertIn(
                "local_locator_resolution_receipt_missing",
                evidence["blockers"],
            )
            audit = archive_services.notion_import_locator_loss_audit(root)
            self.assertFalse(audit["ok"], audit)
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                0,
            )

    def test_verified_reference_resolution_receipt_reduces_partial_loss_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            bound_fragment = f'<file src="{marker}"></file>'
            before = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=(
                    bound_fragment
                    + "\n"
                    + f'<span source="{marker}">visible</span>\n'
                ),
                omitted_count=2,
            )
            object_id = (
                "sha256:"
                "acc6e73fb84988ecb538dfc0ceb883b88694e469a05172a5aeb0cce8902ce136"
            )
            after = self.write_notion_zettel(
                root,
                title="Current Human Title",
                body=f"[Attached objet](wom-objet:{object_id})\nvisible\n",
                omitted_count=2,
            )
            binding_document = {
                "schema": (
                    completion_workflows
                    .MARKUP_REFERENCE_BINDING_MANIFEST_SCHEMA
                ),
                "archive_id": archive_services.read_archive_id(root),
                "bindings": [
                    {
                        "zettel_id": ZETTEL_ID,
                        "tag_sha256": completion_workflows._sha256_bytes(
                            bound_fragment.encode("utf-8")
                        ),
                        "binding_kind": "objet",
                        "binding_id": object_id,
                    }
                ],
            }
            binding_raw = json.dumps(binding_document).encode("utf-8")
            binding_path = (
                root
                / ".wom-scratch"
                / "markup-bindings"
                / "partial.json"
            )
            binding_path.parent.mkdir(parents=True, exist_ok=True)
            binding_path.write_bytes(binding_raw)
            receipt_relative = self.write_markup_receipt(
                root,
                before=before,
                after=after,
                token="4",
                binding_manifest_sha256=hashlib.sha256(
                    binding_raw
                ).hexdigest(),
            )
            result = notion_locator_orphan_recovery_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=2,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(
                result["summary"][
                    "resolved_by_verified_reference_count"
                ],
                1,
            )
            self.assertEqual(result["summary"]["review_pending_count"], 1)
            self.assertEqual(
                result["items"][0]["state"],
                "partially_resolved_by_verified_reference",
            )

            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt_relative],
                expected_orphan_row_count=2,
            )
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(
                audit["summary"][
                    "verified_reference_resolution_count"
                ],
                1,
            )
            self.assertEqual(
                audit["summary"][
                    "verified_reference_review_pending_count"
                ],
                1,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_state"],
                "known",
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_count"],
                1,
            )

    def test_verified_reference_resolution_accepts_crlf_body_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            receipt, _before, after = self.write_verified_reference_history(
                root,
                token="5",
                newline="\r\n",
            )
            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt],
                expected_orphan_row_count=1,
            )
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(self.zettel_path(root).read_bytes(), after)

            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                1,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_count"],
                0,
            )

    def test_composite_locator_recovery_receipt_closes_orphan_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            receipt, _before, _after = self.write_verified_reference_history(
                root,
                token="6",
            )
            archive_id = archive_services.read_archive_id(root)
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            second_zettel_id = "zet_20260829_combined_locator_target"
            second_source_id = "b" * 32
            (root / "zettels" / f"{second_zettel_id}.md").write_text(
                "---\n"
                f"id: {second_zettel_id}\n"
                "title: Combined locator target\n"
                "status: canonical\n"
                f"archive_id: {archive_id}\n"
                "facets:\n"
                f"  source_page_id: {second_source_id}\n"
                "  source_system: notion_db3\n"
                "  source_locator_omitted_count: 1\n"
                "assets: []\n"
                "edges: []\n"
                "---\n"
                f"{marker}\n",
                encoding="utf-8",
                newline="",
            )
            mirror = parent / "pages.markdown.jsonl"
            mirror.write_text(
                json.dumps(
                    {
                        "page_id": second_source_id,
                        "markdown": f"private [{PRIVATE_URL}]({PRIVATE_URL})",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            execution = notion_locator_local_recovery_execution_plan(
                root,
                source_mirror=mirror,
                markup_receipts=[receipt],
                expected_zettel_count=1,
                expected_pair_count=1,
                expected_orphan_row_count=1,
            )
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(
                applied["execution"]["operation_evidence"]["schema"],
                "wom-kit/local-recovery-composite-evidence/v1",
            )

            audit = self.locator_audit_authenticated(root, keys)
            self.assertTrue(audit["ok"], audit)
            self.assertNotIn(
                "local_locator_resolution_receipt_missing",
                audit["blockers"],
            )
            self.assertEqual(
                audit["summary"][
                    "verified_reference_resolution_ledger_count"
                ],
                1,
            )
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                1,
            )

    def test_current_identity_or_omission_drift_never_resolves(self) -> None:
        mutations = {
            "archive": (
                lambda raw, archive_id: raw.replace(
                    f"archive_id: {archive_id}".encode("utf-8"),
                    b"archive_id: archive_other_identity",
                    1,
                ),
                "current_canonical_identity_changed",
            ),
            "status": (
                lambda raw, _archive_id: raw.replace(
                    b"status: canonical", b"status: draft", 1
                ),
                "current_canonical_identity_changed",
            ),
            "omission": (
                lambda raw, _archive_id: raw.replace(
                    b"source_locator_omitted_count: 1",
                    b"source_locator_omitted_count: 2",
                    1,
                ),
                "current_omission_identity_changed",
            ),
        }
        for ordinal, (name, (mutate, expected_blocker)) in enumerate(
            mutations.items(),
            start=7,
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = self.archive(Path(tmp))
                receipt, _before, after = self.write_verified_reference_history(
                    root,
                    token=str(ordinal),
                )
                archive_id = archive_services.read_archive_id(root)
                self.zettel_path(root).write_bytes(mutate(after, archive_id))
                result = notion_locator_orphan_recovery_plan(
                    root,
                    markup_receipts=[receipt],
                    expected_orphan_row_count=1,
                )
                self.assertTrue(result["ok"], result)
                self.assertEqual(
                    result["summary"][
                        "resolved_by_verified_reference_count"
                    ],
                    0,
                )
                self.assertEqual(result["summary"]["review_pending_count"], 1)
                self.assertIn(expected_blocker, result["items"][0]["blocker_codes"])

    def test_applied_resolution_is_invalidated_by_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            receipt, _before, after = self.write_verified_reference_history(
                root,
                token="a",
            )
            execution = notion_locator_orphan_recovery_execution_plan(
                root,
                markup_receipts=[receipt],
                expected_orphan_row_count=1,
            )
            applied, keys = self.execute_authenticated(execution)
            self.assertTrue(applied["ok"], applied)
            archive_id = archive_services.read_archive_id(root)
            self.zettel_path(root).write_bytes(
                after.replace(
                    f"archive_id: {archive_id}".encode("utf-8"),
                    b"archive_id: archive_other_identity",
                    1,
                )
            )
            audit = self.locator_audit_authenticated(root, keys)
            self.assertEqual(
                audit["summary"]["verified_reference_resolution_count"],
                0,
            )
            self.assertEqual(
                audit["summary"]["unresolved_occurrence_state"],
                "unknown",
            )
            self.assertIn(
                "verified_reference_resolution_identity_drifted",
                audit["summary"]["unresolved_occurrence_reason_codes"],
            )

    def test_progress_starts_before_archive_enumeration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            events: list[tuple[str, str, int | None, int | None]] = []
            original = archive_services.iter_zettel_paths

            def enumerate_after_progress(selected_root: Path):
                self.assertTrue(events)
                self.assertEqual(events[0], ("notion-locator-loss", "start", 0, 1))
                return original(selected_root)

            with mock.patch.object(
                archive_services,
                "iter_zettel_paths",
                side_effect=enumerate_after_progress,
            ):
                result = archive_services.notion_import_locator_loss_audit(
                    root,
                    progress_callback=lambda *event: events.append(event),
                )
            self.assertTrue(result["ok"], result)

    def test_conflicting_resolution_candidates_remove_all_target_trust(self) -> None:
        by_target: dict[str, dict[str, object]] = {}
        conflicts: set[str] = set()
        target = "sha256:" + "d" * 64
        first = {"resolved_occurrence_count": 1}
        second = {"resolved_occurrence_count": 2}
        self.assertFalse(
            local_locator_recovery._merge_verified_resolution_candidate(
                by_target,
                conflicts,
                target_identity=target,
                candidate=first,
            )
        )
        self.assertTrue(
            local_locator_recovery._merge_verified_resolution_candidate(
                by_target,
                conflicts,
                target_identity=target,
                candidate=second,
            )
        )
        self.assertNotIn(target, by_target)
        self.assertIn(target, conflicts)
        self.assertFalse(
            local_locator_recovery._merge_verified_resolution_candidate(
                by_target,
                conflicts,
                target_identity=target,
                candidate=first,
            )
        )
        self.assertNotIn(target, by_target)

    def test_orphan_zettel_count_is_unique_across_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            first, before, after = self.write_verified_reference_history(
                root,
                token="b",
            )
            first_document = json.loads(
                root.joinpath(*first.split("/")).read_text(encoding="utf-8")
            )
            second = self.write_markup_receipt(
                root,
                before=before,
                after=after,
                token="c",
                binding_manifest_sha256=first_document[
                    "binding_manifest_sha256"
                ],
            )
            result = notion_locator_orphan_recovery_plan(
                root,
                markup_receipts=[first, second],
                expected_orphan_row_count=2,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["orphan_row_count"], 2)
            self.assertEqual(result["summary"]["orphan_zettel_count"], 1)

    def test_legacy_v01_resolution_ledger_is_counted_but_never_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            legacy = {
                "schema": (
                    "wom-kit/notion-locator-orphan-recovery-ledger/v0.1"
                ),
                "archive_identity_sha256": (
                    exact_human_approval_archive_identity_sha256(
                        archive_services.read_archive_id(root)
                    )
                ),
                "classification_items": [],
                "operation_evidence": {
                    "schema": "wom-kit/notion-locator-orphan-recovery-evidence/v1",
                    "counts": {"orphan_row_count": 0},
                    "digests": {"orphan_row_set_sha256": "sha256:" + "0" * 64},
                    "private_values_echoed": False,
                },
                "private_values_echoed": False,
            }
            raw = (
                json.dumps(
                    legacy,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("ascii")
                + b"\n"
            )
            directory = (
                root
                / "profiles"
                / "local"
                / "local-recovery"
                / "ledgers"
                / "notion_locator_orphan"
            )
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{hashlib.sha256(raw).hexdigest()}.json").write_bytes(raw)
            evidence = verified_notion_locator_resolution_evidence(root)
            self.assertEqual(evidence["skipped_legacy_ledger_count"], 1)
            self.assertEqual(evidence["verified_ledger_count"], 0)
            self.assertEqual(evidence["verified_resolution_row_count"], 0)
            self.assertEqual(evidence["blockers"], [])

    def test_identifier_title_source_accepts_exact_file_or_containing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            identifier_title = "a" * 32
            self.write_notion_zettel(
                root,
                title=identifier_title,
                body="private body must stay private\n",
            )
            mirror_directory = parent / "private-client-source-mirror"
            mirror_directory.mkdir()
            markdown_path = self.write_title_mirrors(
                mirror_directory,
                source_title=HUMAN_TITLE,
                markdown="private source body must stay private\n",
            )

            file_result = zet_identifier_title_recovery_plan(
                root,
                source_mirror=markdown_path,
                expected_identifier_title_count=1,
            )
            directory_result = zet_identifier_title_recovery_plan(
                root,
                source_mirror=mirror_directory,
                expected_identifier_title_count=1,
            )

            self.assertTrue(file_result["ok"], file_result)
            self.assertTrue(directory_result["ok"], directory_result)
            self.assertEqual(
                directory_result["summary"],
                file_result["summary"],
            )
            self.assertEqual(
                directory_result["exact_operation_manifest"],
                file_result["exact_operation_manifest"],
            )
            rendered = json.dumps(directory_result)
            self.assertNotIn(str(mirror_directory), rendered)
            self.assertNotIn(HUMAN_TITLE, rendered)
            self.assertNotIn("private source body", rendered)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_identifier_title_source_directory_swap_to_junction_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            self.write_notion_zettel(
                root,
                title="d" * 32,
                body="private canonical body must stay private\n",
            )
            source_mirror = parent / "private-source-slot"
            source_mirror.mkdir()
            self.write_title_mirrors(
                source_mirror,
                source_title=HUMAN_TITLE,
                markdown="private original source body\n",
            )
            outside = parent / "private-outside-source"
            outside.mkdir()
            outside_title = "private attacker-controlled title"
            self.write_title_mirrors(
                outside,
                source_title=outside_title,
                markdown="private attacker-controlled body\n",
            )
            parked = parent / "private-source-slot-parked"
            original = archive_services._bound_child_directory
            injected = False
            junction_created = False

            @contextmanager
            def swap_before_child_bind(
                selected_root,
                selected_parent,
                child_path,
                enumerated_stat,
            ):
                nonlocal injected, junction_created
                if child_path == source_mirror and not injected:
                    injected = True
                    source_mirror.rename(parked)
                    try:
                        self.create_directory_junction(source_mirror, outside)
                    except OSError:
                        parked.rename(source_mirror)
                        self.skipTest(
                            "Windows directory junctions are unavailable"
                        )
                    junction_created = True
                try:
                    with original(
                        selected_root,
                        selected_parent,
                        child_path,
                        enumerated_stat,
                    ) as binding:
                        yield binding
                finally:
                    if junction_created:
                        self.remove_directory_junction(source_mirror)
                        junction_created = False
                    if parked.exists():
                        parked.rename(source_mirror)

            with mock.patch.object(
                local_title_recovery.archive_services,
                "_bound_child_directory",
                new=swap_before_child_bind,
            ):
                result = zet_identifier_title_recovery_plan(
                    root,
                    source_mirror=source_mirror,
                    expected_identifier_title_count=1,
                )

            self.assertTrue(injected)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["exact_operation_manifest"], None)
            self.assertIn(
                result["summary"]["source_mirror_reason_code"],
                {
                    "identifier_title_source_mirror_entry_unsafe",
                    "identifier_title_source_mirror_changed_during_read",
                },
            )
            rendered = json.dumps(result)
            self.assertNotIn(outside_title, rendered)
            self.assertNotIn("private attacker-controlled body", rendered)
            self.assertNotIn("private canonical body", rendered)

    def test_identifier_title_source_pair_member_swap_after_scan_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            self.write_notion_zettel(
                root,
                title="e" * 32,
                body="private canonical body must stay private\n",
            )
            source_mirror = parent / "private-pair-source"
            source_mirror.mkdir()
            markdown_path = self.write_title_mirrors(
                source_mirror,
                source_title=HUMAN_TITLE,
                markdown="private original source body\n",
            )
            title_path = markdown_path.with_name("pages.index.jsonl")
            replacement_path = source_mirror / "private-replacement.tmp"
            replacement_title = "private swapped title"
            replacement_path.write_text(
                json.dumps(
                    {
                        "page_id": SOURCE_ID,
                        "index": replacement_title,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            original = archive_services._hold_bound_regular_file
            injected = False

            @contextmanager
            def swap_before_file_hold(
                selected_parent,
                selected_path,
                enumerated_stat,
            ):
                nonlocal injected
                if selected_path == title_path and not injected:
                    injected = True
                    os.replace(replacement_path, title_path)
                with original(
                    selected_parent,
                    selected_path,
                    enumerated_stat,
                ) as binding:
                    yield binding

            with mock.patch.object(
                local_title_recovery.archive_services,
                "_hold_bound_regular_file",
                new=swap_before_file_hold,
            ):
                result = zet_identifier_title_recovery_plan(
                    root,
                    source_mirror=source_mirror,
                    expected_identifier_title_count=1,
                )

            self.assertTrue(injected)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["exact_operation_manifest"], None)
            self.assertEqual(
                result["summary"]["source_mirror_reason_code"],
                "identifier_title_source_mirror_changed_during_read",
            )
            rendered = json.dumps(result)
            self.assertNotIn(replacement_title, rendered)
            self.assertNotIn("private canonical body", rendered)

    def test_identifier_title_source_layout_refusals_are_specific_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            self.write_notion_zettel(
                root,
                title="b" * 32,
                body="private canonical body must stay private\n",
            )

            missing = parent / "private-missing-source-mirror"
            empty = parent / "private-empty-source-mirror"
            empty.mkdir()
            incomplete = parent / "private-incomplete-source-mirror"
            incomplete.mkdir()
            (incomplete / "pages.markdown.jsonl").write_text(
                "private incomplete bytes",
                encoding="utf-8",
            )
            wrong_entrypoint_dir = parent / "private-wrong-entrypoint"
            wrong_entrypoint_dir.mkdir()
            _markdown_path = self.write_title_mirrors(
                wrong_entrypoint_dir,
                source_title="private source title must stay private",
                markdown="private source body must stay private\n",
            )
            wrong_entrypoint = wrong_entrypoint_dir / "pages.index.jsonl"
            wrong_layout = parent / "private-wrong-layout"
            wrong_layout.mkdir()
            (wrong_layout / "pages.markdown.jsonl").mkdir()
            (wrong_layout / "pages.index.jsonl").write_text(
                "private wrong-layout bytes",
                encoding="utf-8",
            )

            cases = (
                (
                    missing,
                    "identifier_title_source_mirror_missing",
                ),
                (
                    empty,
                    "identifier_title_source_mirror_pair_missing",
                ),
                (
                    incomplete,
                    "identifier_title_source_mirror_pair_incomplete",
                ),
                (
                    wrong_entrypoint,
                    "identifier_title_source_mirror_entrypoint_invalid",
                ),
                (
                    wrong_layout,
                    "identifier_title_source_mirror_layout_invalid",
                ),
            )
            for source_mirror, expected_reason in cases:
                with self.subTest(expected_reason=expected_reason):
                    result = zet_identifier_title_recovery_plan(
                        root,
                        source_mirror=source_mirror,
                        expected_identifier_title_count=1,
                    )
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["state"], "blocked")
                    self.assertEqual(
                        result["summary"]["source_mirror_reason_code"],
                        expected_reason,
                    )
                    self.assertEqual(
                        result["blockers"],
                        [
                            "identifier_title_recovery_evidence_invalid",
                            expected_reason,
                        ],
                    )
                    rendered = json.dumps(result)
                    self.assertNotIn(str(source_mirror), rendered)
                    self.assertNotIn("private source title", rendered)
                    self.assertNotIn("private source body", rendered)
                    self.assertNotIn("private canonical body", rendered)

    def test_identifier_title_source_ambiguous_layout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = self.archive(parent)
            self.write_notion_zettel(
                root,
                title="c" * 32,
                body="private canonical body must stay private\n",
            )
            source_mirror = parent / "private-ambiguous-source-mirror"
            source_mirror.mkdir()
            fake_entries = iter(
                (
                    SimpleNamespace(name="pages.markdown.jsonl"),
                    SimpleNamespace(name="PAGES.MARKDOWN.JSONL"),
                    SimpleNamespace(name="pages.index.jsonl"),
                )
            )
            with mock.patch(
                "wom_kit.local_title_recovery.os.scandir"
            ) as scandir:
                scandir.return_value.__enter__.return_value = fake_entries
                result = zet_identifier_title_recovery_plan(
                    root,
                    source_mirror=source_mirror,
                    expected_identifier_title_count=1,
                )

            reason = "identifier_title_source_mirror_layout_ambiguous"
            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["summary"]["source_mirror_reason_code"],
                reason,
            )
            self.assertEqual(
                result["blockers"],
                ["identifier_title_recovery_evidence_invalid", reason],
            )
            rendered = json.dumps(result)
            self.assertNotIn(str(source_mirror), rendered)
            self.assertNotIn("private canonical body", rendered)

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

    def test_locator_recovery_text_preview_explains_classification(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            archive_cli._print_local_recovery_execution_result(
                {
                    "ok": True,
                    "state": "ready_for_native_approval",
                    "domain": "notion_locator_orphan",
                    "manifest": {"item_count": 1},
                    "summary": {
                        "orphan_row_count": 7,
                        "classified_orphan_row_count": 7,
                        "resolved_by_verified_reference_count": 5,
                        "restore_ready_count": 0,
                        "review_pending_count": 2,
                    },
                },
                "text",
            )
        rendered = stdout.getvalue()
        self.assertIn("locator rows classified: 7/7", rendered)
        self.assertIn(
            "already resolved by verified references: 5",
            rendered,
        )
        self.assertIn("omission markers safe to restore: 0", rendered)
        self.assertIn("rows held for review: 2", rendered)


if __name__ == "__main__":
    unittest.main()
