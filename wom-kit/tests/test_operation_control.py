from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli, operation_control


TEST_TERMINAL_DELIVERY_CAPABILITY = "hmac-sha256:" + "c" * 64


class OperationControlTests(unittest.TestCase):
    def start_journal(
        self,
        root: Path,
        *,
        command: str = "index",
        relative: str = ".wom-scratch/diagnostics/result.json",
    ) -> tuple[operation_control.OperationRunJournal, Path]:
        root.mkdir(parents=True, exist_ok=True)
        journal = operation_control.OperationRunJournal.prepare(
            root,
            output_relative=relative,
            command=command,
            run_id="a" * 32,
        )
        return journal, root.joinpath(*relative.split("/"))

    def write_result(
        self,
        journal: operation_control.OperationRunJournal,
        output_path: Path,
        *,
        ok: bool = True,
        exit_code: int = 0,
        command_result_available: bool = True,
        payload_fields: dict[str, object] | None = None,
    ) -> None:
        payload = {
            "ok": ok,
            "cli_execution": {
                "status": "completed",
                "run_id": journal.run_id,
                "command": journal.command,
                "exit_code": exit_code,
                "result_available": command_result_available,
            },
            "cli_output_artifact": {
                "command": journal.command,
                "operation": journal.metadata(),
            },
        }
        if payload_fields is not None:
            payload.update(payload_fields)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def write_project_terminal_result(
        self,
        root: Path,
        journal: operation_control.OperationRunJournal,
        output_path: Path,
        *,
        capsule_bytes: bytes,
        publish_consumed_capsule: bool,
    ) -> str:
        terminal = {
            "schema": (
                "wom-kit/project-version-update-terminal-finalization/v0.1"
            ),
            "update_result_verified_in_current_invocation": True,
            "update_result_reauthenticated_from_durable_handoff": False,
            "claim_succeeded_verified": True,
            "transaction_completed_checkpoint_verified": True,
            "lock_absence_verified": True,
            "transaction_cleanup_completed": True,
            "service_resource_close_verified": True,
            "git_runner_close_verified": True,
            "attention_required": True,
            "domain_writer_reentry_allowed": False,
            "automatic_retry_allowed": False,
            "cleanup_proof_used_as_success_authority": False,
            "durable_terminal_handoff_ready": True,
            "durable_terminal_handoff_replayed": False,
            "durable_result_delivery_acknowledged": False,
            "private_paths_echoed": False,
            "private_identifiers_echoed": False,
        }
        domain = {
            "ok": True,
            "status": "updated_restart_required",
            "terminal_finalization": terminal,
            "post_update_attention_required": True,
        }
        self.write_result(
            journal,
            output_path,
            payload_fields={
                key: value for key, value in domain.items() if key != "ok"
            },
        )
        document = json.loads(output_path.read_text(encoding="utf-8"))
        handoff_sha256 = "sha256:" + hashlib.sha256(capsule_bytes).hexdigest()
        output_relative = output_path.relative_to(root).as_posix()
        delivery_binding = {
            "schema": (
                "wom-kit/project-version-update-terminal-delivery-binding/v0.4.16"
            ),
            "terminal_handoff_sha256": handoff_sha256,
            "result_payload_sha256": (
                operation_control._canonical_document_sha256(domain)
            ),
            "output_relative_sha256": (
                "sha256:"
                + hashlib.sha256(output_relative.encode("utf-8")).hexdigest()
            ),
            "run_id": journal.run_id,
            "operation_ref": journal.operation_ref,
        }
        delivery_proof = "hmac-sha256:" + hmac.new(
            TEST_TERMINAL_DELIVERY_CAPABILITY.encode("ascii"),
            b"wom-kit/project-version-update-terminal-delivery-proof/v0.4.16\x00"
            + operation_control.project_update_transaction.canonical_json_bytes(
                delivery_binding
            ),
            hashlib.sha256,
        ).hexdigest()
        document["cli_execution"]["terminal_delivery"] = {
            **delivery_binding,
            "proof": delivery_proof,
        }
        output_path.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if publish_consumed_capsule:
            consumed = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + handoff_sha256.removeprefix("sha256:")
                + ".json"
            )
            consumed.parent.mkdir(parents=True, exist_ok=True)
            consumed.write_bytes(capsule_bytes)
        return handoff_sha256

    def prepare_pending_project_delivery(
        self,
        root: Path,
        *,
        relative: str,
        capsule_bytes: bytes,
    ) -> tuple[operation_control.OperationRunJournal, Path, str]:
        journal, output = self.start_journal(
            root,
            command="project-version-update",
            relative=relative,
        )
        handoff_sha256 = self.write_project_terminal_result(
            root,
            journal,
            output,
            capsule_bytes=capsule_bytes,
            publish_consumed_capsule=False,
        )
        self.assertTrue(
            journal.complete(
                exit_code=0,
                result_available=True,
                result_ok=True,
                result_path=output,
                terminal_delivery_acknowledged=False,
                terminal_handoff_sha256=handoff_sha256,
            )
        )
        guard = root / operation_control.PROJECT_UPDATE_TERMINAL_GUARD_RELATIVE
        guard.parent.mkdir(parents=True, exist_ok=True)
        if not guard.exists():
            guard.write_bytes(b"\x00")
        display_pending = root / (
            operation_control
            .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
        )
        display_pending.parent.mkdir(parents=True, exist_ok=True)
        if display_pending.exists():
            self.assertEqual(display_pending.read_bytes(), capsule_bytes)
        else:
            display_pending.write_bytes(capsule_bytes)
        return journal, output, handoff_sha256

    def test_terminal_status_revalidates_complete_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            self.write_result(journal, output)
            self.assertTrue(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                )
            )

            result = operation_control.inspect_operation(
                root, journal.operation_ref
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "completed_result_available")
            self.assertTrue(result["terminal"])
            self.assertTrue(result["result"]["available"])
            self.assertTrue(result["result"]["binding_verified"])
            self.assertFalse(result["result"]["domain_truth_verified"])
            rendered = json.dumps(result)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("result_sha256", rendered)

    def test_failure_artifact_is_not_reported_as_a_domain_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=".zettel-kasten/diagnostics/update-result.json",
            )
            self.write_result(
                journal,
                output,
                ok=False,
                exit_code=1,
                command_result_available=False,
            )
            self.assertFalse(
                journal.complete(
                    exit_code=1,
                    result_available=True,
                    result_ok=False,
                    result_path=output,
                )
            )

            result = operation_control.inspect_operation(
                root, journal.operation_ref
            )

            self.assertFalse(result["ok"])
            self.assertEqual(
                result["state"],
                "completed_failure_artifact_available",
            )
            self.assertTrue(result["result"]["artifact_available"])
            self.assertFalse(result["result"]["available"])
            self.assertFalse(
                result["result"]["command_result_available"]
            )
            self.assertTrue(
                result["result"]["failure_artifact_available"]
            )
            self.assertIsNone(result["result"]["domain"])
            self.assertTrue(result["control"]["recovery_required"])

    def test_project_update_terminal_projection_requires_complete_truth(self) -> None:
        terminal = {
            "schema": (
                "wom-kit/project-version-update-terminal-finalization/v0.1"
            ),
            "update_result_verified_in_current_invocation": True,
            "update_result_reauthenticated_from_durable_handoff": False,
            "claim_succeeded_verified": True,
            "transaction_completed_checkpoint_verified": True,
            "lock_absence_verified": True,
            "transaction_cleanup_completed": True,
            "service_resource_close_verified": True,
            "git_runner_close_verified": True,
            "attention_required": True,
            "domain_writer_reentry_allowed": False,
            "automatic_retry_allowed": False,
            "cleanup_proof_used_as_success_authority": False,
            "durable_terminal_handoff_ready": True,
            "durable_terminal_handoff_replayed": False,
            "durable_result_delivery_acknowledged": False,
            "private_paths_echoed": False,
            "private_identifiers_echoed": False,
        }
        payload = {
            "ok": True,
            "status": "updated_restart_required",
            "terminal_finalization": terminal,
        }

        projected = operation_control._safe_domain_projection(
            payload,
            command="project-version-update",
        )

        self.assertIsNotNone(projected)
        self.assertEqual(projected["terminal_finalization"], terminal)

        malformed = []
        for field, value in (
            ("claim_succeeded_verified", False),
            ("transaction_completed_checkpoint_verified", False),
            ("lock_absence_verified", False),
            ("automatic_retry_allowed", True),
            ("private_paths_echoed", True),
            ("attention_required", False),
            ("durable_result_delivery_acknowledged", True),
        ):
            changed = dict(terminal)
            changed[field] = value
            malformed.append(changed)
        missing = dict(terminal)
        missing.pop("durable_terminal_handoff_ready")
        malformed.append(missing)
        extra = dict(terminal)
        extra["private_surprise"] = False
        malformed.append(extra)
        forged_clean_delivery = dict(terminal)
        forged_clean_delivery["durable_result_delivery_acknowledged"] = True
        forged_clean_delivery["attention_required"] = False
        malformed.append(forged_clean_delivery)

        for changed in malformed:
            with self.subTest(changed=changed):
                observed = operation_control._safe_domain_projection(
                    {**payload, "terminal_finalization": changed},
                    command="project-version-update",
                )
                self.assertIsNotNone(observed)
                self.assertIsNone(observed["terminal_finalization"])

    def test_project_update_delivery_requires_terminal_journal_and_exact_consumed_capsule(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            first, first_output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/update-result-one.json"
                ),
            )
            first_capsule = b'{"state":"terminal_ready","update":1}\n'
            first_handoff = self.write_project_terminal_result(
                root,
                first,
                first_output,
                capsule_bytes=first_capsule,
                publish_consumed_capsule=True,
            )
            self.assertTrue(
                first.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=first_output,
                    terminal_delivery_acknowledged=False,
                    terminal_handoff_sha256=first_handoff,
                )
            )
            first_status = operation_control.inspect_operation(
                root,
                first.operation_ref,
            )
            first_terminal = first_status["result"]["domain"][
                "terminal_finalization"
            ]
            self.assertTrue(first_status["ok"], first_status)
            self.assertTrue(
                first_terminal["durable_result_delivery_acknowledged"]
            )
            self.assertFalse(first_terminal["attention_required"])
            self.assertTrue(
                first_status["durability_flush"]["attempted"]
            )
            self.assertTrue(
                first_status["durability_flush"]["verified"]
            )
            self.assertTrue(first_status["privacy_guards"]["writes"])
            self.assertFalse(first_status["dry_run"])
            cancelled_delivery_status = operation_control.unsupported_cancel(
                root,
                first.operation_ref,
                approve=False,
                reviewed_by=None,
                expected_control_digest=None,
            )
            self.assertFalse(cancelled_delivery_status["ok"])
            self.assertTrue(
                cancelled_delivery_status["privacy_guards"]["writes"]
            )
            self.assertTrue(
                cancelled_delivery_status["durability_flush"]["verified"]
            )

            second, second_output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/update-result-two.json"
                ),
            )
            second_capsule = b'{"state":"terminal_ready","update":2}\n'
            second_handoff = self.write_project_terminal_result(
                root,
                second,
                second_output,
                capsule_bytes=second_capsule,
                publish_consumed_capsule=False,
            )
            self.assertTrue(
                second.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=second_output,
                    terminal_delivery_acknowledged=False,
                    terminal_handoff_sha256=second_handoff,
                )
            )
            second_pending = operation_control.inspect_operation(
                root,
                second.operation_ref,
            )
            second_terminal = second_pending["result"]["domain"][
                "terminal_finalization"
            ]
            self.assertFalse(
                second_terminal["durable_result_delivery_acknowledged"]
            )
            self.assertTrue(second_terminal["attention_required"])

            active_handoff = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
            )
            active_handoff.write_bytes(second_capsule)

            first_again = operation_control.inspect_operation(
                root,
                first.operation_ref,
            )
            self.assertTrue(
                first_again["result"]["domain"]["terminal_finalization"][
                    "durable_result_delivery_acknowledged"
                ]
            )
            second_consumed = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + second_handoff.removeprefix("sha256:")
                + ".json"
            )
            second_consumed.parent.mkdir(parents=True, exist_ok=True)
            second_consumed.write_bytes(second_capsule)
            copied_before_rename = operation_control.inspect_operation(
                root,
                second.operation_ref,
            )
            self.assertFalse(
                copied_before_rename["result"]["domain"][
                    "terminal_finalization"
                ]["durable_result_delivery_acknowledged"]
            )
            active_handoff.unlink()
            with patch.object(
                operation_control,
                "_require_operation_journal_durable",
                return_value=None,
            ), patch.object(
                operation_control.project_update_transaction,
                "_require_directory_durable",
                side_effect=(
                    operation_control.project_update_transaction
                    .ProjectUpdateTransactionError(
                        "project_update_transaction_durability_unverified"
                    )
                ),
            ) as durability:
                visible_but_not_durable = (
                    operation_control.inspect_operation(
                        root,
                        second.operation_ref,
                    )
                )
            self.assertGreaterEqual(durability.call_count, 1)
            self.assertFalse(
                visible_but_not_durable["result"]["domain"][
                    "terminal_finalization"
                ]["durable_result_delivery_acknowledged"]
            )
            self.assertTrue(
                visible_but_not_durable["durability_flush"][
                    "attempted"
                ]
            )
            self.assertFalse(
                visible_but_not_durable["durability_flush"]["verified"]
            )
            self.assertTrue(
                visible_but_not_durable["privacy_guards"]["writes"]
            )
            self.assertFalse(visible_but_not_durable["dry_run"])
            second_delivered = operation_control.inspect_operation(
                root,
                second.operation_ref,
            )
            self.assertTrue(
                second_delivered["result"]["domain"][
                    "terminal_finalization"
                ]["durable_result_delivery_acknowledged"]
            )

            unfinished, unfinished_output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/update-result-unfinished.json"
                ),
            )
            self.write_project_terminal_result(
                root,
                unfinished,
                unfinished_output,
                capsule_bytes=(
                    b'{"state":"terminal_ready","update":3}\n'
                ),
                publish_consumed_capsule=True,
            )
            unfinished.close()
            with patch.object(
                operation_control,
                "HEARTBEAT_STALE_SECONDS",
                -1,
            ):
                unfinished_status = operation_control.inspect_operation(
                    root,
                    unfinished.operation_ref,
                )
            self.assertFalse(unfinished_status["ok"])
            self.assertEqual(
                unfinished_status["blockers"],
                ["operation_terminal_publication_unverified"],
            )

    def test_project_update_delivery_rejects_journal_handoff_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=".zettel-kasten/diagnostics/result.json",
            )
            capsule = b'{"terminal":"capsule-b"}\n'
            actual_handoff = self.write_project_terminal_result(
                root,
                journal,
                output,
                capsule_bytes=capsule,
                publish_consumed_capsule=True,
            )
            mismatched_handoff = "sha256:" + "a" * 64
            self.assertNotEqual(actual_handoff, mismatched_handoff)
            self.assertFalse(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                    terminal_delivery_acknowledged=False,
                    terminal_handoff_sha256=mismatched_handoff,
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=".zettel-kasten/diagnostics/missing-proof.json",
            )
            self.write_result(
                journal,
                output,
                payload_fields={"status": "updated_restart_required"},
            )
            self.assertFalse(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                    terminal_delivery_acknowledged=False,
                    terminal_handoff_sha256="sha256:" + "b" * 64,
                )
            )

    def test_project_update_terminal_journal_rejects_premature_delivery_true(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/premature-ack.json"
                ),
            )
            self.write_result(
                journal,
                output,
                payload_fields={"status": "updated_restart_required"},
            )
            self.assertFalse(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                    terminal_delivery_acknowledged=True,
                )
            )

    def test_project_update_without_handoff_has_no_delivery_pending_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/no-handoff.json"
                ),
            )
            self.write_result(
                journal,
                output,
                payload_fields={"status": "no_change"},
            )
            self.assertTrue(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                    terminal_delivery_acknowledged=None,
                )
            )

            result = operation_control.inspect_operation(
                root,
                journal.operation_ref,
            )

            self.assertTrue(result["ok"], result)
            self.assertIsNone(
                result["result"]["domain"]["terminal_finalization"]
            )
            self.assertFalse(result["durability_flush"]["attempted"])
            self.assertFalse(result["durability_flush"]["verified"])
            self.assertFalse(result["privacy_guards"]["writes"])

    def test_pending_terminal_delivery_absent_namespace_is_ordinary_none(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / ".zettel-kasten" / "private").mkdir(parents=True)

            self.assertIsNone(
                operation_control
                .discover_pending_project_update_terminal_delivery(
                    root,
                    allow_active_handoff=True,
                )
            )

    def test_display_pending_discovery_and_consumed_history_are_exact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            first, _output, handoff = self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/first.json",
                capsule_bytes=b'{"terminal":"first"}\n',
            )
            candidate = (
                operation_control.discover_pending_project_update_terminal_delivery(
                    root
                )
            )
            self.assertIsNotNone(candidate)
            self.assertTrue(candidate.display_pending)
            self.assertFalse(candidate.active_handoff)
            rendered_candidate = repr(candidate)
            self.assertNotIn(str(root), rendered_candidate)
            self.assertNotIn(first.operation_ref, rendered_candidate)
            self.assertNotIn(first.run_id, rendered_candidate)
            self.assertIsNone(
                operation_control.verify_pending_project_update_terminal_delivery(
                    candidate,
                    delivery_capability="hmac-sha256:" + "e" * 64,
                )
            )
            self.assertEqual(
                operation_control.verify_pending_project_update_terminal_delivery(
                    candidate,
                    delivery_capability=TEST_TERMINAL_DELIVERY_CAPABILITY,
                ),
                candidate,
            )
            status = operation_control.inspect_operation(
                root,
                first.operation_ref,
            )
            self.assertTrue(status["ok"], status)
            terminal = status["result"]["domain"]["terminal_finalization"]
            self.assertTrue(terminal["durable_result_delivery_acknowledged"])
            self.assertFalse(terminal["attention_required"])

            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            consumed = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + handoff.removeprefix("sha256:")
                + ".json"
            )
            pending.replace(consumed)
            operation_control.project_update_transaction._require_directory_durable(
                consumed.parent
            )
            self.assertIsNone(
                operation_control.discover_pending_project_update_terminal_delivery(
                    root
                )
            )
            historical = operation_control.inspect_operation(
                root,
                first.operation_ref,
            )
            self.assertTrue(historical["ok"], historical)
            self.assertTrue(
                historical["result"]["domain"]["terminal_finalization"][
                    "durable_result_delivery_acknowledged"
                ]
            )

            second, _output, _handoff = self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/second.json",
                capsule_bytes=b'{"terminal":"second"}\n',
            )
            selected = (
                operation_control.discover_pending_project_update_terminal_delivery(
                    root
                )
            )
            self.assertIsNotNone(selected)
            self.assertEqual(selected.operation_ref, second.operation_ref)


    def test_pending_terminal_delivery_rejects_multiple_and_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "multiple"
            self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/one.json",
                capsule_bytes=b'{"terminal":1}\n',
            )
            self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/two.json",
                capsule_bytes=b'{"terminal":1}\n',
            )
            with self.assertRaises(operation_control.OperationControlError) as raised:
                operation_control.discover_pending_project_update_terminal_delivery(
                    root
                )
            self.assertEqual(
                raised.exception.code,
                "operation_terminal_delivery_ambiguous",
            )

        for mutation in ("output", "consumed", "active"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "mutated"
                journal, output, handoff = self.prepare_pending_project_delivery(
                    root,
                    relative=".zettel-kasten/diagnostics/result.json",
                    capsule_bytes=b'{"terminal":"exact"}\n',
                )
                if mutation == "output":
                    output.write_text("{}\n", encoding="utf-8")
                elif mutation == "consumed":
                    consumed = root / (
                        operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                        + handoff.removeprefix("sha256:")
                        + ".json"
                    )
                    consumed.write_bytes(b'{"terminal":"forged"}\n')
                else:
                    active = root / (
                        operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
                    )
                    active.write_bytes(b'{"terminal":"different-live"}\n')
                with self.assertRaises(
                    operation_control.OperationControlError
                ) as raised:
                    operation_control.discover_pending_project_update_terminal_delivery(
                        root
                    )
                self.assertEqual(
                    raised.exception.code,
                    (
                        "operation_terminal_delivery_ambiguous"
                        if mutation == "active"
                        else "operation_terminal_delivery_invalid"
                    ),
                )
                rendered = str(raised.exception)
                self.assertNotIn(str(root), rendered)
                self.assertNotIn(journal.operation_ref, rendered)





    def test_active_terminal_candidate_reuses_exact_existing_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, _output, _handoff = (
                self.prepare_pending_project_delivery(
                    root,
                    relative=(
                        ".zettel-kasten/diagnostics/active.json"
                    ),
                    capsule_bytes=b'{"terminal":"active"}\n',
                )
            )
            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            active = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
            )
            pending.replace(active)
            operation_control.project_update_transaction._require_directory_durable(
                active.parent
            )
            self.assertIsNone(
                operation_control
                .discover_pending_project_update_terminal_delivery(root)
            )
            candidate = (
                operation_control
                .discover_pending_project_update_terminal_delivery(
                    root,
                    allow_active_handoff=True,
                )
            )
            self.assertIsNotNone(candidate)
            self.assertTrue(candidate.active_handoff)
            self.assertFalse(candidate.display_pending)
            self.assertEqual(candidate.operation_ref, journal.operation_ref)
            self.assertEqual(
                operation_control
                .verify_pending_project_update_terminal_delivery(
                    candidate,
                    delivery_capability=(
                        TEST_TERMINAL_DELIVERY_CAPABILITY
                    ),
                ),
                candidate,
            )

    def test_current_handoff_hash_separates_disposable_history_from_live_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            history, historical_output, historical_handoff = (
                self.prepare_pending_project_delivery(
                    root,
                    relative=(
                        ".zettel-kasten/diagnostics/history.json"
                    ),
                    capsule_bytes=b'{"terminal":"history"}\n',
                )
            )
            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            historical_consumed = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + historical_handoff.removeprefix("sha256:")
                + ".json"
            )
            pending.replace(historical_consumed)
            operation_control.project_update_transaction._require_directory_durable(
                historical_consumed.parent
            )

            # Historical result artifacts are explicitly disposable. Their
            # absence must not prevent an unrelated active handoff, with no
            # current output binding yet, from reaching authenticated cleanup.
            historical_output.unlink()
            active = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
            )
            active.write_bytes(b'{"terminal":"new-unbound"}\n')
            operation_control.project_update_transaction._require_directory_durable(
                active.parent
            )
            self.assertIsNone(
                operation_control.discover_pending_project_update_terminal_delivery(
                    root,
                    allow_active_handoff=True,
                )
            )

            # Once a current hash-bound journal exists, the same historical
            # loss remains irrelevant and exactly that current output wins.
            active.unlink()
            current, _current_output, _current_handoff = (
                self.prepare_pending_project_delivery(
                    root,
                    relative=(
                        ".zettel-kasten/diagnostics/current.json"
                    ),
                    capsule_bytes=b'{"terminal":"current"}\n',
                )
            )
            pending.replace(active)
            operation_control.project_update_transaction._require_directory_durable(
                active.parent
            )
            selected = (
                operation_control.discover_pending_project_update_terminal_delivery(
                    root,
                    allow_active_handoff=True,
                )
            )
            self.assertIsNotNone(selected)
            self.assertEqual(selected.operation_ref, current.operation_ref)
            self.assertNotEqual(selected.operation_ref, history.operation_ref)

    def test_current_hash_bound_output_failure_is_not_candidate_absence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output, _handoff = self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/current.json",
                capsule_bytes=b'{"terminal":"current"}\n',
            )
            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            active = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
            )
            pending.replace(active)
            operation_control.project_update_transaction._require_directory_durable(
                active.parent
            )
            output.unlink()
            with self.assertRaises(
                operation_control.OperationControlError
            ) as raised:
                operation_control.discover_pending_project_update_terminal_delivery(
                    root,
                    allow_active_handoff=True,
                )
            self.assertEqual(
                raised.exception.code,
                "operation_terminal_delivery_invalid",
            )
            self.assertNotIn(str(root), str(raised.exception))
            self.assertNotIn(journal.operation_ref, str(raised.exception))

    def test_current_candidate_requires_journal_file_and_parent_durability(
        self,
    ) -> None:
        for boundary in ("file", "parent"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                journal, _output, _handoff = (
                    self.prepare_pending_project_delivery(
                        root,
                        relative=(
                            ".zettel-kasten/diagnostics/current.json"
                        ),
                        capsule_bytes=b'{"terminal":"current"}\n',
                    )
                )
                pending = root / (
                    operation_control
                    .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
                )
                active = root / (
                    operation_control.PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE
                )
                pending.replace(active)
                operation_control.project_update_transaction._require_directory_durable(
                    active.parent
                )
                target = (
                    patch.object(
                        operation_control.os,
                        "fsync",
                        side_effect=OSError("synthetic file flush failure"),
                    )
                    if boundary == "file"
                    else patch.object(
                        operation_control.project_update_transaction,
                        "_require_directory_durable",
                        side_effect=(
                            operation_control.project_update_transaction
                            .ProjectUpdateTransactionError(
                                "project_update_transaction_durability_unverified"
                            )
                        ),
                    )
                )
                with target:
                    with self.assertRaises(
                        operation_control.OperationControlError
                    ) as raised:
                        operation_control.discover_pending_project_update_terminal_delivery(
                            root,
                            allow_active_handoff=True,
                        )
                self.assertEqual(
                    raised.exception.code,
                    "operation_terminal_delivery_commit_unverified",
                )
                candidate = (
                    operation_control.discover_pending_project_update_terminal_delivery(
                        root,
                        allow_active_handoff=True,
                    )
                )
                self.assertIsNotNone(candidate)
                self.assertEqual(candidate.operation_ref, journal.operation_ref)

    def test_display_pending_requires_parent_durability_before_discovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            self.prepare_pending_project_delivery(
                root,
                relative=".zettel-kasten/diagnostics/result.json",
                capsule_bytes=b'{"terminal":"pending"}\n',
            )
            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            failure = (
                operation_control.project_update_transaction
                .ProjectUpdateTransactionError(
                    "project_update_transaction_durability_unverified"
                )
            )
            with patch.object(
                operation_control,
                "_require_operation_journal_durable",
                return_value=None,
            ), patch.object(
                operation_control.project_update_transaction,
                "_require_directory_durable",
                side_effect=failure,
            ) as durable:
                with self.assertRaises(
                    operation_control.OperationControlError
                ) as raised:
                    operation_control.discover_pending_project_update_terminal_delivery(
                        root
                    )
            self.assertEqual(
                raised.exception.code,
                "operation_terminal_delivery_durability_unverified",
            )
            durable.assert_called_once_with(pending.parent)
            candidate = (
                operation_control.discover_pending_project_update_terminal_delivery(
                    root
                )
            )
            self.assertIsNotNone(candidate)
            self.assertTrue(candidate.display_pending)

    def test_consumed_namespace_durability_failure_blocks_until_retry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            _journal, _output, handoff = (
                self.prepare_pending_project_delivery(
                    root,
                    relative=(
                        ".zettel-kasten/diagnostics/consumed.json"
                    ),
                    capsule_bytes=b'{"terminal":"consumed"}\n',
                )
            )
            pending = root / (
                operation_control
                .PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            )
            consumed = root / (
                operation_control.PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + handoff.removeprefix("sha256:")
                + ".json"
            )
            pending.replace(consumed)
            with patch.object(
                operation_control.project_update_transaction,
                "_require_directory_durable",
                side_effect=(
                    operation_control.project_update_transaction
                    .ProjectUpdateTransactionError(
                        "project_update_transaction_durability_unverified"
                    )
                ),
            ):
                with self.assertRaises(
                    operation_control.OperationControlError
                ) as raised:
                    operation_control.discover_pending_project_update_terminal_delivery(
                        root
                    )
            self.assertEqual(
                raised.exception.code,
                "operation_terminal_delivery_durability_unverified",
            )
            self.assertIsNone(
                operation_control
                .discover_pending_project_update_terminal_delivery(root)
            )

    def test_legacy_v01_journal_remains_readable_for_status_wait_and_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            journal, output = self.start_journal(
                root,
                command="project-version-update",
                relative=(
                    ".zettel-kasten/diagnostics/legacy-result.json"
                ),
            )
            self.write_result(
                journal,
                output,
                payload_fields={"status": "updated_restart_required"},
            )
            self.assertTrue(
                journal.complete(
                    exit_code=0,
                    result_available=True,
                    result_ok=True,
                    result_path=output,
                )
            )
            legacy_lines: list[str] = []
            previous: str | None = None
            for raw_line in journal.journal_path.read_text(
                encoding="ascii"
            ).splitlines():
                record = json.loads(raw_line)
                record["schema"] = (
                    operation_control.LEGACY_OPERATION_JOURNAL_SCHEMA
                )
                record.pop("terminal_delivery_acknowledged", None)
                record.pop("terminal_handoff_sha256", None)
                record["previous_record_sha256"] = previous
                record["record_sha256"] = operation_control._record_digest(
                    record
                )
                previous = record["record_sha256"]
                legacy_lines.append(
                    json.dumps(
                        record,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            journal.journal_path.write_text(
                "\n".join(legacy_lines) + "\n",
                encoding="ascii",
            )

            status = operation_control.inspect_operation(
                root,
                journal.operation_ref,
            )
            waited = operation_control.wait_operation(
                root,
                journal.operation_ref,
                1,
            )
            recovery = operation_control.recovery_plan(
                root,
                journal.operation_ref,
            )
            for observed in (status, waited, recovery):
                self.assertTrue(observed["ok"], observed)
                self.assertEqual(
                    observed["state"],
                    "completed_result_available",
                )

    def test_project_update_success_status_routes_are_exact_and_punctuation_free(
        self,
    ) -> None:
        dry_run_actions = [
            "Treat this completed result as dry-run only and review the full bound output",
            "If review still supports the update, use a separate fresh project-version-update approval",
        ]
        expected_routes = {
            "ready_for_approval": dry_run_actions,
            "ready_to_fetch_on_approve": dry_run_actions,
            "preview_only_platform_unsupported": [
                "No update was applied; run a fresh project-version-update --dry-run on supported Windows before considering a separate approval"
            ],
            "updated_restart_required": [
                "Start a new process and run archive version <project-or-archive-root> --format json before claiming the update active"
            ],
            "no_change": [
                "No write or restart is required; run archive version <project-or-archive-root> --format json to verify the project is already current"
            ],
            "future_success_state": [
                "Do not infer update, approval, or restart state from this unrecognized successful status",
                "Review the complete bound output and run a fresh project-version-update --dry-run before taking another action",
            ],
        }

        for status, expected in expected_routes.items():
            with self.subTest(status=status):
                actions = operation_control._project_update_completed_next_actions(
                    {
                        "command": "project-version-update",
                        "status": status,
                        "completion_ok": True,
                    }
                )

                self.assertEqual(actions, expected)
                self.assertTrue(actions)
                self.assertTrue(
                    all(action == action.rstrip(".!?;:,") for action in actions)
                )

        failed_domains = [
            {
                "target_tag": "v0.3.315",
                "collision_refs": ["update-entry:0001"],
                "materialization_plan_sha256": "sha256:" + "b" * 64,
            },
            {"blocker_codes": ["materialization_collision"]},
            {"blocker_codes": ["other_blocker"]},
        ]
        for fields in failed_domains:
            with self.subTest(failed_route=fields):
                actions = operation_control._project_update_completed_next_actions(
                    {
                        "command": "project-version-update",
                        "status": "blocked",
                        "completion_ok": False,
                        **fields,
                    }
                )

                self.assertTrue(actions)
                self.assertTrue(
                    all(action == action.rstrip(".!?;:,") for action in actions)
                )

        cleanup_attention = (
            operation_control._project_update_completed_next_actions(
                {
                    "command": "project-version-update",
                    "status": "updated_restart_required",
                    "completion_ok": True,
                    "terminal_finalization": {
                        "attention_required": True,
                    },
                }
            )
        )
        self.assertEqual(
            cleanup_attention[0],
            "Preserve terminal cleanup evidence and do not rerun the completed project update writer",
        )

    def test_project_update_success_status_routes_match_status_wait_and_recovery_plan(
        self,
    ) -> None:
        expected_routes = {
            "ready_for_approval": [
                "Treat this completed result as dry-run only and review the full bound output",
                "If review still supports the update, use a separate fresh project-version-update approval",
            ],
            "ready_to_fetch_on_approve": [
                "Treat this completed result as dry-run only and review the full bound output",
                "If review still supports the update, use a separate fresh project-version-update approval",
            ],
            "preview_only_platform_unsupported": [
                "No update was applied; run a fresh project-version-update --dry-run on supported Windows before considering a separate approval"
            ],
            "updated_restart_required": [
                "Start a new process and run archive version <project-or-archive-root> --format json before claiming the update active"
            ],
            "no_change": [
                "No write or restart is required; run archive version <project-or-archive-root> --format json to verify the project is already current"
            ],
            "future_success_state": [
                "Do not infer update, approval, or restart state from this unrecognized successful status",
                "Review the complete bound output and run a fresh project-version-update --dry-run before taking another action",
            ],
        }

        for status, expected in expected_routes.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                journal, output = self.start_journal(
                    root,
                    command="project-version-update",
                    relative=".zettel-kasten/diagnostics/update-result.json",
                )
                self.write_result(
                    journal,
                    output,
                    payload_fields={
                        "status": status,
                        "target": {"tag": "v0.3.315"},
                    },
                )
                self.assertTrue(
                    journal.complete(
                        exit_code=0,
                        result_available=True,
                        result_ok=True,
                        result_path=output,
                    )
                )

                status_result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )
                wait_result = operation_control.wait_operation(
                    root, journal.operation_ref, 1
                )
                recovery_result = operation_control.recovery_plan(
                    root, journal.operation_ref
                )

                for result in (status_result, wait_result, recovery_result):
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(
                        result["state"], "completed_result_available"
                    )
                    self.assertEqual(result["next_safe_actions"], expected)
                    self.assertTrue(
                        all(
                            action == action.rstrip(".!?;:,")
                            for action in result["next_safe_actions"]
                        )
                    )

    def test_missing_or_tampered_result_fails_closed(self) -> None:
        for mutation in ("missing", "tampered"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                journal, output = self.start_journal(root)
                self.write_result(journal, output)
                self.assertTrue(
                    journal.complete(
                        exit_code=0,
                        result_available=True,
                        result_ok=True,
                        result_path=output,
                    )
                )
                if mutation == "missing":
                    output.unlink()
                else:
                    output.write_text("{}\n", encoding="utf-8")

                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["state"], "recovery_required")
                self.assertTrue(result["control"]["recovery_required"])
                self.assertIn(
                    "operation_result_missing_or_unverifiable",
                    result["blockers"],
                )

    def test_stale_nonterminal_reconciles_only_matching_complete_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            self.write_result(journal, output)
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertTrue(result["ok"], result)
            self.assertTrue(result["terminal"])
            self.assertEqual(
                result["terminal_source"], "complete_output_reconciliation"
            )
            self.assertTrue(result["result"]["binding_verified"])

    def test_stale_without_output_is_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], ["operation_observation_stale"])

    def test_torn_tampered_and_future_journals_fail_closed(self) -> None:
        for mutation in ("torn", "tampered", "future"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                journal, _output = self.start_journal(root)
                journal.close()
                raw = journal.journal_path.read_bytes()
                if mutation == "torn":
                    journal.journal_path.write_bytes(raw + b"{")
                    expected = "operation_journal_torn"
                else:
                    record = json.loads(raw.decode("ascii"))
                    if mutation == "tampered":
                        record["stage"] = "unknown"
                        expected = "operation_journal_invalid"
                    else:
                        record["observed_at"] = "2999-01-01T00:00:00Z"
                        record["record_sha256"] = operation_control._record_digest(record)
                        expected = "operation_journal_future_timestamp"
                    journal.journal_path.write_text(
                        json.dumps(record, sort_keys=True, separators=(",", ":"))
                        + "\n",
                        encoding="ascii",
                    )

                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["blockers"], [expected])

    def test_copied_journal_is_bound_to_original_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "target"
            journal, _output = self.start_journal(source)
            journal.close()
            copied = (
                target
                / ".wom-scratch"
                / "diagnostics"
                / ".operations"
                / journal.journal_path.name
            )
            copied.parent.mkdir(parents=True)
            shutil.copy2(journal.journal_path, copied)

            result = operation_control.inspect_operation(
                target, journal.operation_ref
            )

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["blockers"], ["operation_root_mismatch"])

    def test_wait_deadline_is_not_cancel_or_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            clock = [0.0]

            def advance(seconds: float) -> None:
                clock[0] += seconds

            result = operation_control.wait_operation(
                root,
                journal.operation_ref,
                1,
                _clock=lambda: clock[0],
                _sleep=advance,
            )
            journal.close()

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["wait"]["outcome"], "deadline_reached")
            self.assertFalse(result["wait"]["cancel_requested"])
            self.assertFalse(result["control"]["cancel_requested"])

    def test_append_during_read_uses_complete_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            journal.close()
            original_fstat = operation_control.os.fstat
            injected = [False]

            def append_before_first_fstat(descriptor: int):
                if not injected[0]:
                    injected[0] = True
                    with journal._lock:
                        journal._append("heartbeat", terminal=False)
                return original_fstat(descriptor)

            with patch.object(
                operation_control.os, "fstat", side_effect=append_before_first_fstat
            ):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "running_observed")

    def test_result_scan_is_bounded_before_unbounded_directory_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, output = self.start_journal(root)
            journal.close()
            for index in range(operation_control.MAX_RESULT_SCAN_ENTRIES):
                output.with_name(f"noise-{index:05d}.txt").write_bytes(b"x")

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["blockers"], ["operation_result_verification_bounded"]
            )

    def test_wrong_path_self_claim_and_ambiguous_matches_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, expected_output = self.start_journal(root)
            self.write_result(journal, expected_output)
            wrong_output = expected_output.with_name("wrong.json")
            shutil.copy2(expected_output, wrong_output)
            expected_output.unlink()
            journal.close()

            with patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1):
                wrong_path_result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(wrong_path_result["ok"], wrong_path_result)
            self.assertEqual(
                wrong_path_result["blockers"], ["operation_observation_stale"]
            )

            shutil.copy2(wrong_output, expected_output)
            with (
                patch.object(operation_control, "HEARTBEAT_STALE_SECONDS", -1),
                patch.object(
                    operation_control,
                    "_output_ref",
                    return_value=journal.output_ref,
                ),
            ):
                ambiguous_result = operation_control.inspect_operation(
                    root, journal.operation_ref
                )

            self.assertFalse(ambiguous_result["ok"], ambiguous_result)
            self.assertEqual(
                ambiguous_result["blockers"],
                ["operation_result_artifact_ambiguous"],
            )

    def test_cancel_is_fixed_unsupported_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            before = journal.journal_path.read_bytes()

            result = operation_control.unsupported_cancel(
                root,
                journal.operation_ref,
                approve=True,
                reviewed_by="person:test",
                expected_control_digest=journal.control_digest,
            )
            after = journal.journal_path.read_bytes()
            journal.close()

            self.assertFalse(result["ok"])
            self.assertEqual(result["blockers"], ["operation_cancel_not_supported"])
            self.assertFalse(result["control"]["cancel_supported"])
            self.assertFalse(result["control"]["cancel_requested"])
            self.assertFalse(result["control"]["resume_supported"])
            self.assertFalse(result["privacy_guards"]["writes"])
            self.assertEqual(before, after)

    def test_invalid_operation_ref_is_not_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            secret_like = "C:/private/secret-token"

            result = operation_control.inspect_operation(root, secret_like)

            self.assertIsNone(result["operation_ref"])
            self.assertNotIn(secret_like, json.dumps(result))

    def test_cli_has_one_canonical_surface_and_status_json(self) -> None:
        parser = archive_cli.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        operation_parser = subparsers.choices["operation-control"]
        self.assertEqual(
            sum(value is operation_parser for value in subparsers.choices.values()),
            1,
        )
        project_parser = subparsers.choices["project-version-update"]
        self.assertTrue(
            any("--output" in action.option_strings for action in project_parser._actions)
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            journal, _output = self.start_journal(root)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = archive_cli.main(
                    [
                        "operation-control",
                        str(root),
                        "--operation-ref",
                        journal.operation_ref,
                        "--action",
                        "status",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            journal.close()

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["state"], "running_observed")

    def test_index_and_project_update_output_embed_roundtrip_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            archive_root.mkdir()

            def fake_index(_root: Path, *, progress_callback=None):
                if progress_callback is not None:
                    progress_callback("index-lock-and-schema", "start", None, None)
                    progress_callback("index-commit", "done", None, None)
                return {
                    "ok": True,
                    "state": "rebuilt",
                    "index_rebuilt": True,
                    "index_complete": True,
                    "warnings": [],
                }

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    archive_cli.archive_services,
                    "require_existing_archive_root",
                    return_value=archive_root,
                ),
                patch.object(
                    archive_cli.archive_services,
                    "index_archive",
                    side_effect=fake_index,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                index_exit = archive_cli.main(
                    [
                        "index",
                        str(archive_root),
                        "--output",
                        ".wom-scratch/diagnostics/index-result.json",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(index_exit, 0, stderr.getvalue())
            index_payload = json.loads(
                (
                    archive_root
                    / ".wom-scratch"
                    / "diagnostics"
                    / "index-result.json"
                ).read_text(encoding="utf-8")
            )
            index_operation = index_payload["cli_output_artifact"]["operation"]
            self.assertEqual(
                operation_control.inspect_operation(
                    archive_root, index_operation["operation_ref"]
                )["state"],
                "completed_result_available",
            )

            project_root = Path(tmp) / "project"
            project_root.mkdir()

            def fake_update(
                _root: Path,
                *,
                progress_callback=None,
                **_kwargs,
            ):
                if progress_callback is not None:
                    progress_callback("project-preflight", "start", None, None)
                    progress_callback("project-preflight", "done", None, None)
                return {
                    "ok": True,
                    "status": "dry_run_ready",
                    "target": {},
                    "source_mirror": {},
                    "runtime": {},
                    "blockers": [],
                    "next_safe_actions": [],
                }

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    archive_cli.archive_services,
                    "wom_kit_project_version_update",
                    side_effect=fake_update,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                update_exit = archive_cli.main(
                    [
                        "project-version-update",
                        str(project_root),
                        "--target",
                        "v0.3.313",
                        "--dry-run",
                        "--output",
                        ".zettel-kasten/diagnostics/update-result.json",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(update_exit, 0, stderr.getvalue())
            project_payload = json.loads(
                (
                    project_root
                    / ".zettel-kasten"
                    / "diagnostics"
                    / "update-result.json"
                ).read_text(encoding="utf-8")
            )
            project_operation = project_payload["cli_output_artifact"]["operation"]
            project_status = operation_control.inspect_operation(
                project_root, project_operation["operation_ref"]
            )
            self.assertTrue(project_status["ok"], project_status)
            self.assertEqual(project_status["state"], "completed_result_available")


if __name__ == "__main__":
    unittest.main()
