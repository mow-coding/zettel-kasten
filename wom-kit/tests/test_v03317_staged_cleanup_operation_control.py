from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import operation_control


class StagedCleanupOperationControlTests(unittest.TestCase):
    def _completed_operation(
        self,
        root: Path,
        *,
        suffix: str,
        run_id: str,
        payload_fields: dict[str, object],
        exit_code: int,
        result_ok: bool,
    ) -> tuple[dict[str, object], dict[str, object]]:
        output_relative = f".wom-scratch/diagnostics/{suffix}.json"
        journal = operation_control.OperationRunJournal.prepare(
            root,
            output_relative=output_relative,
            command="staged-cleanup-check",
            run_id=run_id,
        )
        output_path = root.joinpath(*output_relative.split("/"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **payload_fields,
            "cli_execution": {
                "status": "completed",
                "run_id": journal.run_id,
                "command": journal.command,
                "exit_code": exit_code,
            },
            "cli_output_artifact": {
                "command": journal.command,
                "operation": journal.metadata(),
            },
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.assertTrue(
            journal.complete(
                exit_code=exit_code,
                result_available=True,
                result_ok=result_ok,
                result_path=output_path,
            )
        )
        return (
            operation_control.inspect_operation(root, journal.operation_ref),
            operation_control.recovery_plan(root, journal.operation_ref),
        )

    def test_command_kind_and_all_content_free_progress_stages_are_registered(
        self,
    ) -> None:
        self.assertEqual(
            operation_control.COMMAND_KINDS["staged-cleanup-check"],
            "staged_cleanup_check",
        )
        self.assertEqual(
            operation_control.KIND_COMMANDS["staged_cleanup_check"],
            "staged-cleanup-check",
        )
        self.assertEqual(
            operation_control.COMMAND_STAGES["staged-cleanup-check"],
            frozenset(
                {
                    "starting",
                    "manifest",
                    "zettel-references",
                    "staged-walk",
                    "verify",
                    "source-hash",
                    "store-hash",
                    "unknown",
                }
            ),
        )

    def test_projection_is_exact_bounded_and_drops_private_result_fields(
        self,
    ) -> None:
        private_marker = "C:/private-owner/staging/never-echo-this.txt"
        private_object_id = "sha256:" + "f" * 64
        payload = {
            "ok": True,
            "safe_to_cleanup": False,
            "state": "not_safe_to_cleanup",
            "summary": {
                "preserved": 2,
                "deferred": 1,
                "not_preserved": 1,
                "unsafe": 0,
                "private_count_label": private_marker,
            },
            "reason_codes": ["staged_entries_not_preserved"],
            "files": [
                {
                    "path": private_marker,
                    "object_id": private_object_id,
                    "raw_message": private_marker,
                }
            ],
            "archive_id": private_marker,
        }

        projected = operation_control._safe_domain_projection(
            payload,
            command="staged-cleanup-check",
        )

        self.assertEqual(
            projected,
            {
                "command": "staged-cleanup-check",
                "inspection_ok": True,
                "safe_to_cleanup": False,
                "state": "not_safe_to_cleanup",
                "attention_required": True,
                "summary": {
                    "preserved": 2,
                    "deferred": 1,
                    "not_preserved": 1,
                    "unsafe": 0,
                },
                "reason_codes": ["staged_entries_not_preserved"],
                "local_paths_echoed": False,
                "object_ids_echoed": False,
                "private_values_echoed": False,
                "raw_messages_copied": False,
            },
        )
        rendered = json.dumps(projected)
        self.assertNotIn(private_marker, rendered)
        self.assertNotIn(private_object_id, rendered)

    def test_projection_rejects_unallowlisted_or_inconsistent_truth(self) -> None:
        base = {
            "ok": True,
            "safe_to_cleanup": False,
            "state": "not_safe_to_cleanup",
            "summary": {
                "preserved": 0,
                "deferred": 0,
                "not_preserved": 1,
                "unsafe": 0,
            },
            "reason_codes": ["staged_entries_not_preserved"],
        }
        invalid_payloads = [
            {**base, "state": "future_private_state"},
            {**base, "reason_codes": ["private_filename_as_reason"]},
            {**base, "summary": {**base["summary"], "preserved": True}},
            {**base, "summary": {**base["summary"], "preserved": -1}},
            {
                **base,
                "summary": {
                    **base["summary"],
                    "preserved": operation_control.MAX_STAGED_CLEANUP_SUMMARY_COUNT,
                },
            },
            {
                **base,
                "summary": {
                    "preserved": 0,
                    "deferred": 0,
                    "not_preserved": 0,
                    "unsafe": 0,
                },
            },
            {**base, "reason_codes": []},
            {
                **base,
                "ok": True,
                "safe_to_cleanup": True,
                "state": "safe_to_cleanup",
            },
            {
                **base,
                "ok": False,
                "safe_to_cleanup": True,
                "state": "inspection_blocked",
                "reason_codes": ["unsafe_staged_folder"],
            },
            {
                **base,
                "ok": False,
                "safe_to_cleanup": False,
                "state": "inspection_blocked",
                "reason_codes": [],
            },
            {
                "ok": True,
                "safe_to_cleanup": True,
                "state": "safe_to_cleanup",
                "summary": {
                    "preserved": 1,
                    "deferred": 1,
                    "not_preserved": 0,
                    "unsafe": 0,
                },
                "reason_codes": [],
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    operation_control._safe_domain_projection(
                        payload,
                        command="staged-cleanup-check",
                    )
                )

        deferred_projection = operation_control._safe_domain_projection(
            {
                "ok": True,
                "safe_to_cleanup": False,
                "state": "not_safe_to_cleanup",
                "summary": {
                    "preserved": 1,
                    "deferred": 1,
                    "not_preserved": 0,
                    "unsafe": 0,
                },
                "reason_codes": ["staged_entry_explicitly_deferred"],
            },
            command="staged-cleanup-check",
        )
        self.assertIsNotNone(deferred_projection)
        self.assertEqual(
            deferred_projection["reason_codes"],
            ["staged_entry_explicitly_deferred"],
        )

    def test_frozen_evidence_failure_reasons_are_allowlisted(self) -> None:
        reason_codes = (
            "derived_text_source_bytes_changed_by_normalization",
            "derived_text_manifest_missing",
            "derived_text_manifest_invalid",
            "derived_text_store_missing",
            "derived_text_store_sha256_mismatch",
            "derived_text_capture_receipt_missing",
            "derived_text_capture_receipt_invalid",
        )
        for reason_code in reason_codes:
            with self.subTest(reason_code=reason_code):
                projected = operation_control._safe_domain_projection(
                    {
                        "ok": True,
                        "safe_to_cleanup": False,
                        "state": "not_safe_to_cleanup",
                        "summary": {
                            "preserved": 1,
                            "deferred": 0,
                            "not_preserved": 1,
                            "unsafe": 0,
                        },
                        "reason_codes": [reason_code],
                    },
                    command="staged-cleanup-check",
                )
                self.assertIsNotNone(projected)
                self.assertEqual(projected["reason_codes"], [reason_code])

    def test_scan_blockers_and_unsafe_path_project_without_private_details(
        self,
    ) -> None:
        private_marker = "C:/private/staging/entry-name-must-not-appear"
        for reason_code in (
            "derived_text_manifest_scan_incomplete",
            "derived_text_receipt_scan_incomplete",
            "objet_manifest_path_unsafe",
            "objet_manifest_scan_incomplete",
            "staged_tree_changed_during_inspection",
            "staged_evidence_changed_during_inspection",
        ):
            with self.subTest(reason_code=reason_code):
                projected = operation_control._safe_domain_projection(
                    {
                        "ok": False,
                        "safe_to_cleanup": False,
                        "state": "inspection_blocked",
                        "summary": {
                            "preserved": 0,
                            "deferred": 0,
                            "not_preserved": 0,
                            "unsafe": 0,
                        },
                        "reason_codes": [reason_code],
                        "raw_message": private_marker,
                    },
                    command="staged-cleanup-check",
                )
                self.assertIsNotNone(projected)
                self.assertEqual(projected["state"], "inspection_blocked")
                self.assertEqual(projected["reason_codes"], [reason_code])
                self.assertNotIn(private_marker, json.dumps(projected))

        unsafe_projection = operation_control._safe_domain_projection(
            {
                "ok": True,
                "safe_to_cleanup": False,
                "state": "not_safe_to_cleanup",
                "summary": {
                    "preserved": 0,
                    "deferred": 0,
                    "not_preserved": 0,
                    "unsafe": 1,
                },
                "reason_codes": ["staged_entry_path_unsafe"],
                "files": [{"path": private_marker}],
            },
            command="staged-cleanup-check",
        )
        self.assertIsNotNone(unsafe_projection)
        self.assertEqual(unsafe_projection["state"], "not_safe_to_cleanup")
        self.assertEqual(
            unsafe_projection["reason_codes"],
            ["staged_entry_path_unsafe"],
        )
        self.assertNotIn(private_marker, json.dumps(unsafe_projection))

    def test_completed_safe_not_safe_and_blocked_results_route_exactly(self) -> None:
        private_marker = "PRIVATE_STAGED_FILENAME_MUST_NOT_REACH_CONTROL"
        cases = [
            {
                "suffix": "safe",
                "run_id": "a" * 32,
                "exit_code": 0,
                "result_ok": True,
                "payload": {
                    "ok": True,
                    "safe_to_cleanup": True,
                    "state": "safe_to_cleanup",
                    "summary": {
                        "preserved": 1,
                        "deferred": 0,
                        "not_preserved": 0,
                        "unsafe": 0,
                    },
                    "reason_codes": [],
                },
            },
            {
                "suffix": "not-safe",
                "run_id": "b" * 32,
                "exit_code": 1,
                "result_ok": False,
                "payload": {
                    "ok": True,
                    "safe_to_cleanup": False,
                    "state": "not_safe_to_cleanup",
                    "summary": {
                        "preserved": 1,
                        "deferred": 0,
                        "not_preserved": 1,
                        "unsafe": 0,
                    },
                    "reason_codes": ["staged_entries_not_preserved"],
                },
            },
            {
                "suffix": "blocked",
                "run_id": "c" * 32,
                "exit_code": 1,
                "result_ok": False,
                "payload": {
                    "ok": False,
                    "safe_to_cleanup": False,
                    "state": "inspection_blocked",
                    "summary": {
                        "preserved": 0,
                        "deferred": 0,
                        "not_preserved": 0,
                        "unsafe": 0,
                    },
                    "reason_codes": ["unsafe_staged_folder"],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            for index, case in enumerate(cases):
                with self.subTest(state=case["payload"]["state"]):
                    root = Path(tmp) / f"archive-{index}"
                    root.mkdir()
                    payload = {
                        **case["payload"],
                        "files": [
                            {
                                "path": private_marker,
                                "object_id": "sha256:" + "e" * 64,
                            }
                        ],
                        "raw_message": private_marker,
                    }
                    status, recovery = self._completed_operation(
                        root,
                        suffix=str(case["suffix"]),
                        run_id=str(case["run_id"]),
                        payload_fields=payload,
                        exit_code=int(case["exit_code"]),
                        result_ok=bool(case["result_ok"]),
                    )

                    domain = status["result"]["domain"]
                    self.assertEqual(status["state"], "completed_result_available")
                    self.assertEqual(status["operation_kind"], "staged_cleanup_check")
                    self.assertEqual(
                        domain["inspection_ok"],
                        case["payload"]["ok"],
                    )
                    self.assertEqual(
                        domain["safe_to_cleanup"],
                        case["payload"]["safe_to_cleanup"],
                    )
                    self.assertEqual(
                        domain["attention_required"],
                        case["payload"]["state"] != "safe_to_cleanup",
                    )
                    expected_actions = list(
                        operation_control._STAGED_CLEANUP_COMPLETED_ACTIONS[
                            str(case["payload"]["state"])
                        ]
                    )
                    self.assertEqual(status["next_safe_actions"], expected_actions)
                    self.assertEqual(recovery["next_safe_actions"], expected_actions)
                    self.assertNotIn(private_marker, json.dumps(status))
                    self.assertNotIn(private_marker, json.dumps(recovery))

    def test_not_safe_exit_binding_uses_cleanup_verdict_not_inspection_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            status, _recovery = self._completed_operation(
                root,
                suffix="not-safe-binding",
                run_id="d" * 32,
                payload_fields={
                    "ok": True,
                    "safe_to_cleanup": False,
                    "state": "not_safe_to_cleanup",
                    "summary": {
                        "preserved": 0,
                        "deferred": 0,
                        "not_preserved": 1,
                        "unsafe": 0,
                    },
                    "reason_codes": ["staged_entries_not_preserved"],
                },
                exit_code=1,
                result_ok=False,
            )

        self.assertFalse(status["result"]["ok"])
        self.assertTrue(status["result"]["domain"]["inspection_ok"])
        self.assertFalse(status["result"]["domain"]["safe_to_cleanup"])
        self.assertTrue(status["result"]["binding_verified"])


if __name__ == "__main__":
    unittest.main()
