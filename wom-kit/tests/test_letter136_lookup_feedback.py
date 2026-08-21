from __future__ import annotations

import io
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import (  # noqa: E402
    archive_cli,
    archive_services,
    completion_workflows,
    mcp_server,
    operator_feedback_body,
)


class Letter136LookupFeedbackTests(unittest.TestCase):
    ZETTEL_ID = "zet_20240504_fake_lunch_thought"
    OBJECT_ID = (
        "sha256:9dabf9b965a3f789b1b36100f3f70515"
        "ce8dfd81b411b1503e1e2c3304303647"
    )
    PRIVATE_LABEL = "Private reviewed label must never echo"
    PRIVATE_BODY_MARKER = "Private feedback prose must never echo"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)

    def run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    def install_historical_link_fixture(
        self,
        *,
        zettel_id: str | None = None,
        relative_path: str | None = None,
        role: str = "source_document",
        label: str | None = PRIVATE_LABEL,
    ) -> dict[str, object]:
        """Install one bounded v0.3 link history without calling its blocked writer."""

        selected_zettel_id = zettel_id or (
            None if relative_path is not None else self.ZETTEL_ID
        )
        plan = completion_workflows.zettel_objet_link_plan(
            self.root,
            zettel_id=selected_zettel_id,
            relative_path=relative_path,
            object_id=self.OBJECT_ID,
            role=role,
            label=label,
        )
        self.assertTrue(plan["ok"], plan)

        zettel_path = archive_services.resolve_zettel_path(
            self.root,
            zettel_id=selected_zettel_id,
            relative_path=relative_path,
        )
        before_bytes = zettel_path.read_bytes()
        before_sha256 = hashlib.sha256(before_bytes).hexdigest()
        frontmatter, body = archive_services.require_readable_zettel_content(
            zettel_path
        )
        asset = {"object_id": self.OBJECT_ID, "role": role}
        if label is not None:
            asset["label"] = label
        updated_frontmatter = dict(frontmatter)
        updated_frontmatter["assets"] = [
            *list(frontmatter.get("assets") or []),
            asset,
        ]
        updated_frontmatter["updated_at"] = "2026-08-20T00:00:00Z"
        after_bytes = (
            "---\n"
            + archive_services.dump_yaml(updated_frontmatter)
            + "---\n"
            + body
        ).encode("utf-8")
        after_sha256 = hashlib.sha256(after_bytes).hexdigest()

        archive_id = archive_services.read_archive_id(self.root)
        safe_zettel_id = str(frontmatter["id"])
        seed = {
            "archive_id": archive_id,
            "zettel_id": safe_zettel_id,
            "object_id": self.OBJECT_ID,
            "role": role,
        }
        link_digest = hashlib.sha256(
            (
                json.dumps(
                    seed,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()
        link_id = f"asset:sha256:{link_digest}"
        self.assertEqual(plan["summary"]["link_id"], link_id)
        snapshot_relative = (
            "receipts/objects/zettel-links/snapshots/"
            f"{before_sha256}.zettel.md"
        )
        receipt_relative = str(plan["summary"]["receipt_path"])
        receipt = {
            "schema": "wom-kit/zettel-objet-link-receipt/v0.1",
            "action": "add_zettel_objet_link",
            "archive_id": archive_id,
            "zettel_id": safe_zettel_id,
            "zettel_path": archive_services.archive_relative_path(
                zettel_path,
                self.root,
            ),
            "object_id": self.OBJECT_ID,
            "role": role,
            "label_sha256": (
                hashlib.sha256(label.encode("utf-8")).hexdigest()
                if label is not None
                else None
            ),
            "link_id": link_id,
            "plan_sha256": plan["summary"]["plan_sha256"],
            "before_zettel_sha256": before_sha256,
            "after_zettel_sha256": after_sha256,
            "before_snapshot_path": snapshot_relative,
            "reviewed_by": "person:historical-fixture",
            "created_at": "2026-08-20T00:00:00Z",
            "privacy": {
                "label_included": False,
                "zettel_body_included": False,
                "object_bytes_read": False,
                "provider_called": False,
            },
        }
        snapshot_path = self.root.joinpath(*snapshot_relative.split("/"))
        receipt_path = self.root.joinpath(*receipt_relative.split("/"))
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(before_bytes)
        zettel_path.write_bytes(after_bytes)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "ok": True,
            "summary": {
                **plan["summary"],
                "receipt_path": receipt_relative,
                "link_id": link_id,
            },
        }

    def feedback_request(self, feedback_id: str) -> Path:
        request_dir = (
            self.root
            / "profiles"
            / "local"
            / "operator-feedback"
            / "requests"
        )
        request_dir.mkdir(parents=True, exist_ok=True)
        request_path = request_dir / f"{feedback_id}.json"
        request = {
            "schema": operator_feedback_body.REQUEST_SCHEMA,
            "feedback_id": feedback_id,
            "title": "Reviewed operator feedback",
            "sections": {
                "environment": "Local WOM archive on Windows.",
                "task": "Create body evidence before metadata.",
                "observed_failure": self.PRIVATE_BODY_MARKER,
                "suspected_cause": "The earlier order was reversed.",
                "requested_resolution": "Verify body authority first.",
                "reproduction": "Approve a body, then preview the record.",
            },
        }
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return request_path

    def approve_feedback_body(self, feedback_id: str) -> dict[str, object]:
        request_path = self.feedback_request(feedback_id)
        plan = operator_feedback_body.plan_operator_feedback_body(
            self.root,
            request_path,
        )
        self.assertTrue(plan["ok"], plan)
        approved = operator_feedback_body.approve_operator_feedback_body(
            self.root,
            request_path,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="person:test",
        )
        self.assertTrue(approved["ok"], approved)
        return approved

    def test_receipt_lookup_validates_current_state_for_cli_and_mcp(self) -> None:
        applied = self.install_historical_link_fixture()
        receipt_path = str(applied["summary"]["receipt_path"])

        result = completion_workflows.zettel_objet_link_receipts(
            self.root,
            zettel_id=self.ZETTEL_ID,
            object_id=self.OBJECT_ID,
            dry_run=True,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "revert_ready")
        self.assertEqual(result["summary"]["selected_receipt_path"], receipt_path)
        self.assertEqual(result["summary"]["candidate_receipt_count"], 1)
        self.assertEqual(result["summary"]["validated_receipt_count"], 1)
        self.assertEqual(result["summary"]["revert_ready_count"], 1)
        self.assertTrue(result["summary"]["matching_candidate_set_validated"])
        self.assertFalse(result["summary"]["history_completeness_proven"])
        self.assertFalse(result["data"]["direct_correction_supported"])
        self.assertEqual(
            result["data"]["correction_route"],
            "receipt_lookup_preview_then_conservative_correction_handoff",
        )
        self.assertIn("fixed closed", result["next_safe_actions"][0])
        self.assertNotIn("then preview and approve", result["next_safe_actions"][0])
        self.assertIn(
            "no_mac_or_signature",
            result["data"]["receipt_validation"],
        )
        self.assertFalse(result["data"]["mac_or_signature_verified"])
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(self.PRIVATE_LABEL, serialized)
        self.assertFalse(result["privacy_guards"]["label_echoed"])
        self.assertFalse(result["privacy_guards"]["zettel_body_echoed"])
        self.assertFalse(result["privacy_guards"]["zettel_path_echoed"])
        self.assertFalse(result["privacy_guards"]["object_bytes_read"])
        self.assertFalse(result["privacy_guards"]["writes"])

        cli_code, cli_output = self.run_cli(
            [
                "zettel-objet-link-receipts",
                str(self.root),
                "--zettel-id",
                self.ZETTEL_ID,
                "--object-id",
                self.OBJECT_ID,
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(cli_code, 0, cli_output)
        self.assertEqual(
            json.loads(cli_output)["summary"]["selected_receipt_path"],
            receipt_path,
        )
        self.assertNotIn(self.PRIVATE_LABEL, cli_output)

        mcp_result = mcp_server.handle_tools_call(
            {
                "name": "zettel_objet_link_receipts",
                "arguments": {
                    "archive_root": str(self.root),
                    "zettel_id": self.ZETTEL_ID,
                    "object_id": self.OBJECT_ID,
                    "dry_run": True,
                },
            }
        )
        structured = mcp_result["structuredContent"]
        self.assertEqual(structured["summary"]["selected_receipt_path"], receipt_path)
        self.assertNotIn(
            self.PRIVATE_LABEL,
            json.dumps(mcp_result, ensure_ascii=False, sort_keys=True),
        )

    def test_receipt_lookup_fails_closed_on_tampering_and_later_edit(self) -> None:
        applied = self.install_historical_link_fixture()
        receipt_path = self.root / str(applied["summary"]["receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["link_id"] = "asset:sha256:" + ("0" * 64)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        tampered = completion_workflows.zettel_objet_link_receipts(
            self.root,
            zettel_id=self.ZETTEL_ID,
            object_id=self.OBJECT_ID,
            dry_run=True,
        )
        self.assertFalse(tampered["ok"])
        self.assertEqual(tampered["data"]["receipts"], [])
        self.assertIn(
            "zettel_objet_link_receipts_validation_failed",
            tampered["blockers"],
        )

        # Restore the immutable receipt bytes for the independent current-state
        # check. The synthetic fixture only is mutated; no real archive is used.
        receipt["link_id"] = str(applied["summary"]["link_id"])
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        zettel_path = self.root / "zettels" / f"{self.ZETTEL_ID}.md"
        zettel_path.write_bytes(zettel_path.read_bytes() + b"\nLater reviewed edit.\n")

        historical = completion_workflows.zettel_objet_link_receipts(
            self.root,
            zettel_id=self.ZETTEL_ID,
            object_id=self.OBJECT_ID,
            dry_run=True,
        )
        self.assertTrue(historical["ok"], historical)
        self.assertEqual(historical["state"], "found")
        self.assertIsNone(historical["summary"]["selected_receipt_path"])
        self.assertEqual(
            historical["data"]["receipts"][0]["lifecycle_state"],
            "historical_current_zettel_changed",
        )
        self.assertIn(
            "Do not revert from historical receipts",
            historical["next_safe_actions"][0],
        )

    def test_receipt_lookup_never_reflects_target_filename(self) -> None:
        original = self.root / "zettels" / f"{self.ZETTEL_ID}.md"
        private_relative = "zettels/private-client-filename.md"
        private_path = self.root / private_relative
        original.replace(private_path)
        self.install_historical_link_fixture(
            relative_path=private_relative,
            role="source_document",
            label=self.PRIVATE_LABEL,
        )

        result = completion_workflows.zettel_objet_link_receipts(
            self.root,
            relative_path=private_relative,
            object_id=self.OBJECT_ID,
            dry_run=True,
        )
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertTrue(result["ok"], result)
        self.assertNotIn("zettel_path", result["summary"])
        self.assertNotIn(private_relative, rendered)
        self.assertNotIn(private_path.name, rendered)
        self.assertFalse(result["privacy_guards"]["zettel_path_echoed"])
        self.assertFalse(result["privacy_guards"]["local_absolute_path_echoed"])

    def test_receipt_lookup_blocks_when_target_changes_during_observation(self) -> None:
        self.install_historical_link_fixture()
        target = (self.root / "zettels" / f"{self.ZETTEL_ID}.md").resolve()
        original_read = archive_services._read_activity_group_regular_bytes_bound
        target_reads = 0

        def changed_final_target_read(
            root: Path,
            parent_binding: dict[str, object],
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> bytes:
            nonlocal target_reads
            raw = original_read(
                root,
                parent_binding,
                path,
                *args,
                **kwargs,
            )
            if Path(path).resolve() == target:
                target_reads += 1
                # The stable resolver reads the selected Markdown once and
                # revalidates it twice. Mutate only the later receipt-level
                # read so this test keeps covering its named final guard.
                if target_reads == 4:
                    return raw + b"\nConcurrent reviewed edit.\n"
            return raw

        with mock.patch.object(
            archive_services,
            "_read_activity_group_regular_bytes_bound",
            side_effect=changed_final_target_read,
        ):
            result = completion_workflows.zettel_objet_link_receipts(
                self.root,
                zettel_id=self.ZETTEL_ID,
                object_id=self.OBJECT_ID,
                dry_run=True,
            )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["data"]["receipts"], [])
        self.assertIn(
            "zettel_objet_link_receipts_zettel_changed_during_lookup",
            result["blockers"],
        )

    def test_feedback_record_verifies_body_first_without_echoing_values(self) -> None:
        feedback_id = "wom-feedback-letter136-verified"
        body = self.approve_feedback_body(feedback_id)
        feedback_ref = str(body["feedback_ref"])

        preview = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=feedback_ref,
            status="draft",
            intent="create",
            dry_run=True,
        )

        self.assertTrue(preview["ok"], preview)
        self.assertTrue(preview["summary"]["feedback_body_authority_verified"])
        self.assertRegex(
            str(preview["summary"]["feedback_body_receipt_sha256"]),
            r"^[0-9a-f]{64}$",
        )
        self.assertTrue(preview["data"]["feedback_body_preflight"]["performed"])
        self.assertTrue(
            preview["data"]["feedback_body_preflight"][
                "approval_receipt_ref_available"
            ]
        )
        self.assertTrue(preview["privacy_guards"]["feedback_body_read"])
        self.assertFalse(preview["privacy_guards"]["feedback_body_value_echoed"])
        serialized = json.dumps(preview, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(feedback_ref, serialized)
        self.assertNotIn(self.PRIVATE_BODY_MARKER, serialized)

        approved = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=feedback_ref,
            status="draft",
            intent="create",
            approve=True,
            reviewed_by="person:test",
        )
        self.assertTrue(approved["ok"], approved)
        checked = operator_feedback_body.check_operator_feedback_body(
            self.root,
            feedback_id,
        )
        self.assertTrue(checked["ok"], checked)

    def test_feedback_preflight_blocks_receipt_change_during_observation(self) -> None:
        feedback_id = "wom-feedback-letter136-changing-receipt"
        body = self.approve_feedback_body(feedback_id)
        feedback_ref = str(body["feedback_ref"])
        receipt = (
            self.root / str(body["proposed_receipt_relative_path"])
        ).resolve()
        original_read = archive_services._bounded_stable_regular_file_read
        receipt_reads = 0

        def changed_second_receipt_read(
            path: Path,
            *args: object,
            **kwargs: object,
        ) -> tuple[bytes | None, str | None]:
            nonlocal receipt_reads
            raw, reason = original_read(path, *args, **kwargs)
            if Path(path).resolve() == receipt:
                receipt_reads += 1
                if receipt_reads == 2 and raw is not None and reason is None:
                    return raw + b" ", None
            return raw, reason

        with mock.patch.object(
            archive_services,
            "_bounded_stable_regular_file_read",
            side_effect=changed_second_receipt_read,
        ):
            result = archive_services.operator_feedback_record(
                self.root,
                feedback_id=feedback_id,
                feedback_ref=feedback_ref,
                status="draft",
                intent="create",
                dry_run=True,
            )

        self.assertFalse(result["ok"], result)
        self.assertIn(
            "feedback_body_authority_unverified",
            result["blocker_codes"],
        )
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(feedback_ref, rendered)
        self.assertNotIn(self.PRIVATE_BODY_MARKER, rendered)

    def test_feedback_create_blocks_unverified_body_but_warns_legacy_and_guides_withdrawal(self) -> None:
        feedback_id = "wom-feedback-letter136-missing"
        missing_ref = "feedback-body-sha256:" + ("1" * 64)
        missing = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=missing_ref,
            status="draft",
            intent="create",
            dry_run=True,
        )
        self.assertFalse(missing["ok"])
        self.assertIn(
            "feedback_body_authority_unverified",
            missing["blocker_codes"],
        )
        self.assertNotIn(missing_ref, json.dumps(missing, sort_keys=True))

        legacy_ref = "feedback:legacy-letter136"
        legacy = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=legacy_ref,
            status="draft",
            intent="create",
            dry_run=True,
        )
        self.assertTrue(legacy["ok"], legacy)
        self.assertIn(
            "feedback_body_reference_unverified",
            legacy["warning_codes"],
        )
        self.assertFalse(legacy["data"]["feedback_body_preflight"]["performed"])
        self.assertTrue(legacy["data"]["safe_withdrawal"]["supported"])
        self.assertEqual(
            legacy["data"]["safe_withdrawal"]["target_status"],
            "archived",
        )
        self.assertFalse(
            legacy["data"]["safe_withdrawal"]["feedback_ref_rebinding_allowed"]
        )
        self.assertNotIn(legacy_ref, json.dumps(legacy, sort_keys=True))

        created = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=legacy_ref,
            status="draft",
            intent="create",
            approve=True,
            reviewed_by="person:test",
        )
        self.assertTrue(created["ok"], created)
        withdrawal_preview = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=legacy_ref,
            status="archived",
            intent="update",
            dry_run=True,
        )
        self.assertTrue(withdrawal_preview["ok"], withdrawal_preview)
        withdrawn = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref=legacy_ref,
            status="archived",
            intent="update",
            expected_record_sha256=withdrawal_preview["summary"][
                "current_record_sha256"
            ],
            approve=True,
            reviewed_by="person:test",
        )
        self.assertTrue(withdrawn["ok"], withdrawn)
        record = archive_services.load_yaml(
            (
                self.root
                / "ops"
                / "feedback"
                / f"{feedback_id}.yml"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(record["status"], "archived")
        self.assertEqual(record["feedback_ref"], legacy_ref)

        rebind = archive_services.operator_feedback_record(
            self.root,
            feedback_id=feedback_id,
            feedback_ref="feedback:different",
            status="archived",
            intent="update",
            dry_run=True,
        )
        self.assertFalse(rebind["ok"])
        self.assertIn("feedback_ref_rebind_forbidden", rebind["blocker_codes"])


if __name__ == "__main__":
    unittest.main()
