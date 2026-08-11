from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli, archive_services, operation_control

from . import test_cli as _test_cli


ENTRY_REF = "update-entry:0001"
PLAN_SHA256 = "sha256:" + "b" * 64
TARGET = "v0.3.315"


class ProjectUpdateCollisionCliTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_command_is_alias_free_and_exposes_one_action_surface(self) -> None:
        commands = archive_cli.parser_command_manifest(
            archive_cli.build_parser()
        )
        command = next(
            item
            for item in commands
            if item["name"] == "project-version-update-collision"
        )

        self.assertEqual(command["aliases"], [])
        self.assertEqual(command["required_positionals"], ["inspection_root"])
        self.assertIn("--entry-ref", command["options"])
        self.assertIn("--expected-plan-sha256", command["options"])
        self.assertIn("--reveal-target-relative-path", command["options"])

    def test_collision_receipt_trust_boundary_is_explicit(self) -> None:
        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "project-version-update.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "unauthenticated_private_state_internal_consistency",
            text,
        )
        self.assertIn("only single-artifact drift detection", text)
        self.assertIn("coherently rewrite the", text)
        self.assertIn("payload plus both private receipts", text)
        self.assertIn("outside the v0.3.315 trust", text)
        self.assertIn("boundary. Result fields", text)

    def test_missing_service_fails_closed_without_reflecting_local_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "PRIVATE_PROJECT_ROOT_315"
            root.mkdir()
            with patch.object(
                archive_cli.archive_services,
                "wom_kit_project_version_update_collision",
                None,
                create=True,
            ):
                code, stdout, stderr = self.run_cli(
                    [
                        "project-version-update-collision",
                        str(root),
                        "--target",
                        TARGET,
                        "--entry-ref",
                        ENTRY_REF,
                        "--expected-plan-sha256",
                        PLAN_SHA256,
                        "--action",
                        "inspect",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )

        result = json.loads(stdout)
        rendered = stdout + stderr
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "deferred_not_available")
        self.assertEqual(
            result["blocker_codes"],
            ["project_update_collision_service_unavailable"],
        )
        self.assertFalse(result["write_boundary"]["writes"])
        self.assertFalse(result["write_boundary"]["deletes"])
        self.assertFalse(result["write_boundary"]["update_retried"])
        self.assertNotIn(str(root), rendered)
        self.assertNotIn("PRIVATE_PROJECT_ROOT_315", rendered)

    def test_inspect_wires_only_the_opaque_contract_to_service(self) -> None:
        captured: dict[str, object] = {}

        def fake_service(root: Path, **kwargs: object) -> dict[str, object]:
            captured["root"] = root
            captured.update(kwargs)
            return {
                "ok": True,
                "schema": "wom-kit/project-version-update-collision/v0.1",
                "status": "inspected",
                "action": "inspect",
                "entry": {"entry_ref": ENTRY_REF},
                "inspection": {
                    "target_relative_path": "public/release-file.txt",
                    "path_source": "verified_target_tree",
                },
                "write_boundary": {"writes": False},
                "blockers": [],
                "next_safe_actions": [],
            }

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision",
            side_effect=fake_service,
            create=True,
        ):
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, _ = self.run_cli(
                [
                    "project-version-update-collision",
                    str(root),
                    "--target",
                    TARGET,
                    "--entry-ref",
                    ENTRY_REF,
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--action",
                    "inspect",
                    "--dry-run",
                    "--reveal-target-relative-path",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertEqual(captured["target"], TARGET)
        self.assertEqual(captured["entry_ref"], ENTRY_REF)
        self.assertEqual(captured["action"], "inspect")
        self.assertTrue(captured["dry_run"])
        self.assertFalse(captured["approve"])
        self.assertEqual(captured["expected_plan_sha256"], PLAN_SHA256)
        self.assertTrue(captured["reveal_target_relative_path"])

    def test_inspect_requires_the_exact_materialization_plan_digest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, _ = self.run_cli(
                [
                    "project-version-update-collision",
                    str(root),
                    "--target",
                    TARGET,
                    "--entry-ref",
                    ENTRY_REF,
                    "--action",
                    "inspect",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        result = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertEqual(
            result["blocker_codes"],
            ["project_update_collision_requires_expected_plan"],
        )
        self.assertFalse(result["write_boundary"]["writes"])

    def test_path_hash_or_bare_ordinal_is_not_an_entry_reference(self) -> None:
        invalid_values = [
            "0001",
            "collision:sha256:" + "c" * 64,
            "update-entry:0000",
            "update-entry:1",
            "update-entry:00001",
        ]
        for invalid in invalid_values:
            with self.subTest(entry_ref=invalid), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                root.mkdir()
                code, stdout, _ = self.run_cli(
                    [
                        "project-version-update-collision",
                        str(root),
                        "--target",
                        TARGET,
                        "--entry-ref",
                        invalid,
                        "--expected-plan-sha256",
                        PLAN_SHA256,
                        "--action",
                        "inspect",
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
                result = json.loads(stdout)
                self.assertEqual(code, 1)
                self.assertIn(
                    "project_update_collision_entry_ref_invalid",
                    result["blocker_codes"],
                )
                self.assertIsNone(result["entry"]["entry_ref"])

    def test_parser_error_does_not_reflect_private_argument_text(self) -> None:
        private_canary = "--PRIVATE_LOCAL_COLLISION_PATH_315"
        code, stdout, stderr = self.run_cli(
            ["project-version-update-collision", private_canary]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertNotIn(private_canary, stderr)
        self.assertIn("private argument values were not echoed", stderr)

    def test_approved_relocation_requires_plan_reviewer_and_quiescence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, _ = self.run_cli(
                [
                    "project-version-update-collision",
                    str(root),
                    "--target",
                    TARGET,
                    "--entry-ref",
                    ENTRY_REF,
                    "--action",
                    "preserve-relocate",
                    "--approve",
                    "--format",
                    "json",
                ]
            )

        result = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertEqual(
            result["blocker_codes"],
            [
                "project_update_collision_requires_expected_plan",
                "project_update_collision_approve_requires_reviewer",
                "project_update_collision_approve_requires_quiescence",
            ],
        )
        self.assertFalse(result["write_boundary"]["writes"])
        self.assertFalse(result["write_boundary"]["deletes"])

    def test_approved_relocation_passes_exact_approval_inputs(self) -> None:
        captured: dict[str, object] = {}

        def fake_service(root: Path, **kwargs: object) -> dict[str, object]:
            captured["root"] = root
            captured.update(kwargs)
            return {
                "ok": True,
                "schema": "wom-kit/project-version-update-collision/v0.1",
                "status": "preserved_relocated",
                "action": "preserve-relocate",
                "entry": {"entry_ref": ENTRY_REF},
                "write_boundary": {
                    "writes": True,
                    "deletes": False,
                    "overwrites": False,
                    "update_retried": False,
                },
                "blockers": [],
                "next_safe_actions": [
                    "Run a fresh project-version-update --dry-run."
                ],
            }

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision",
            side_effect=fake_service,
            create=True,
        ):
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, _ = self.run_cli(
                [
                    "project-version-update-collision",
                    str(root),
                    "--target",
                    TARGET,
                    "--entry-ref",
                    ENTRY_REF,
                    "--action",
                    "preserve-relocate",
                    "--approve",
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--reviewed-by",
                    "person:beta-reviewer",
                    "--affirm-external-writers-quiescent",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(code, 0, stdout)
        self.assertTrue(captured["approve"])
        self.assertFalse(captured["dry_run"])
        self.assertEqual(captured["expected_plan_sha256"], PLAN_SHA256)
        self.assertEqual(captured["reviewed_by"], "person:beta-reviewer")
        self.assertTrue(captured["affirm_external_writers_quiescent"])
        self.assertFalse(captured["reveal_target_relative_path"])

    def test_text_reveal_uses_only_verified_target_result(self) -> None:
        def fake_service(root: Path, **kwargs: object) -> dict[str, object]:
            return {
                "ok": True,
                "status": "inspected",
                "action": "inspect",
                "entry": {"entry_ref": ENTRY_REF},
                "target": {
                    "target_relative_path": "public/Foo.txt",
                    "target_relative_path_echoed": True,
                    "target_tree_exact_key_verified": True,
                },
                "inspection": {
                    "target_relative_path": "PRIVATE-DECOY.txt",
                },
                "write_boundary": {"writes": False},
                "blockers": [],
                "next_safe_actions": [],
            }

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision",
            side_effect=fake_service,
        ):
            root = Path(tmp) / "project"
            root.mkdir()
            code, stdout, stderr = self.run_cli(
                [
                    "project-version-update-collision",
                    str(root),
                    "--target",
                    TARGET,
                    "--entry-ref",
                    ENTRY_REF,
                    "--expected-plan-sha256",
                    PLAN_SHA256,
                    "--action",
                    "inspect",
                    "--dry-run",
                    "--reveal-target-relative-path",
                    "--format",
                    "text",
                ]
            )
        self.assertEqual(code, 0, stdout + stderr)
        self.assertIn("Verified target-relative path: public/Foo.txt", stdout)
        self.assertNotIn("PRIVATE-DECOY", stdout + stderr)

    def test_service_exception_is_uncertain_only_for_approved_write_mode(self) -> None:
        base = [
            "project-version-update-collision",
            "PRIVATE-ROOT",
            "--target",
            TARGET,
            "--entry-ref",
            ENTRY_REF,
            "--expected-plan-sha256",
            PLAN_SHA256,
            "--action",
            "preserve-relocate",
            "--format",
            "json",
        ]
        with patch.object(
            archive_cli.archive_services,
            "wom_kit_project_version_update_collision",
            side_effect=KeyboardInterrupt(),
        ):
            dry_code, dry_stdout, _ = self.run_cli([*base, "--dry-run"])
            approved_code, approved_stdout, _ = self.run_cli(
                [
                    *base,
                    "--approve",
                    "--reviewed-by",
                    "human:letter-127-test",
                    "--affirm-external-writers-quiescent",
                ]
            )
        dry_result = json.loads(dry_stdout)
        approved_result = json.loads(approved_stdout)
        self.assertEqual(dry_code, 1)
        self.assertEqual(dry_result["status"], "failed_safely")
        self.assertFalse(dry_result["write_boundary"]["writes"])
        self.assertFalse(
            dry_result["write_boundary"]["writes_may_have_occurred"]
        )
        self.assertFalse(
            dry_result["write_boundary"]["preservation_relocation_attempted"]
        )
        self.assertFalse(
            dry_result["write_boundary"]["preservation_relocation_succeeded"]
        )
        self.assertFalse(
            dry_result["write_boundary"]["relocation_may_have_been_attempted"]
        )
        self.assertEqual(approved_code, 1)
        self.assertEqual(
            approved_result["status"],
            "collision_outcome_unverified_recovery_required",
        )
        self.assertIsNone(approved_result["write_boundary"]["writes"])
        self.assertFalse(approved_result["write_boundary"]["writes_verified"])
        self.assertTrue(
            approved_result["write_boundary"]["writes_may_have_occurred"]
        )
        self.assertIsNone(
            approved_result["write_boundary"][
                "preservation_relocation_attempted"
            ]
        )
        self.assertIsNone(
            approved_result["write_boundary"][
                "preservation_relocation_succeeded"
            ]
        )
        self.assertTrue(
            approved_result["write_boundary"][
                "relocation_may_have_been_attempted"
            ]
        )
        self.assertIn(
            "project_update_collision_outcome_unverified",
            approved_result["blocker_codes"],
        )
        self.assertNotIn("PRIVATE-ROOT", approved_stdout)


class ProjectUpdateCollisionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = _test_cli.ArchiveCliTests("runTest")
        self.fixture_case.setUp()

    def tearDown(self) -> None:
        self.fixture_case.doCleanups()

    def collision_fixture(
        self,
        root: Path,
    ) -> tuple[dict[str, object], Path, bytes, str, str]:
        fixture = self.fixture_case.create_project_version_update_fixture(
            root,
            ignored_checkout_collision=True,
        )
        collision_path = fixture["mirror"] / fixture["collision_name"]
        private_bytes = b"PRIVATE COLLISION BYTES MUST BE PRESERVED\n"
        collision_path.write_bytes(private_bytes)
        failed_update = archive_services.wom_kit_project_version_update(
            fixture["project_root"],
            target=fixture["target_tag"],
            approve=True,
            reviewed_by="human:letter-127-test",
            affirm_external_writers_quiescent=True,
        )
        self.assertEqual(failed_update["status"], "blocked")
        preflight = failed_update["materialization_preflight"]
        return (
            fixture,
            collision_path,
            private_bytes,
            preflight["conflicts"][0]["entry_ref"],
            preflight["materialization_plan_sha256"],
        )

    @staticmethod
    def collision_call(
        fixture: dict[str, object],
        entry_ref: str,
        plan_sha256: str,
        *,
        action: str,
        dry_run: bool = False,
        approve: bool = False,
        reveal: bool = False,
    ) -> dict[str, object]:
        return archive_services.wom_kit_project_version_update_collision(
            fixture["project_root"],
            target=fixture["target_tag"],
            entry_ref=entry_ref,
            expected_plan_sha256=plan_sha256,
            action=action,
            dry_run=dry_run,
            approve=approve,
            reviewed_by=("human:letter-127-test" if approve else None),
            affirm_external_writers_quiescent=approve,
            reveal_target_relative_path=reveal,
        )

    def test_actual_windows_preserve_then_fresh_update_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))

            inspected = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="inspect",
                dry_run=True,
            )
            disclosed = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="inspect",
                dry_run=True,
                reveal=True,
            )
            preview = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                dry_run=True,
            )
            approved = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )

            self.assertEqual(inspected["status"], "inspected")
            self.assertTrue(inspected["plan"]["current_plan_evaluated"])
            self.assertTrue(inspected["plan"]["fresh_preview_required"])
            self.assertTrue(
                inspected["entry"]["eligible_for_preserve_relocate"]
            )
            self.assertFalse(inspected["entry"]["private_bytes_read"])
            self.assertEqual(
                inspected["entry"]["private_content_read_stages"],
                [],
            )
            self.assertFalse(
                inspected["target"]["target_relative_path_echoed"]
            )
            self.assertEqual(
                disclosed["target"]["target_relative_path"],
                fixture["collision_name"],
            )
            self.assertTrue(
                disclosed["target"]["target_tree_exact_key_verified"]
            )
            disclosed_rendered = json.dumps(disclosed, ensure_ascii=False)
            self.assertNotIn(str(fixture["project_root"]), disclosed_rendered)
            self.assertNotIn(private_bytes.decode().strip(), disclosed_rendered)
            self.assertEqual(
                preview["status"],
                "ready_to_preserve_relocate",
            )
            self.assertFalse(preview["entry"]["private_bytes_read"])
            self.assertEqual(
                preview["entry"]["private_content_read_stages"],
                [],
            )
            self.assertEqual(approved["status"], "preserved_relocated")
            self.assertTrue(approved["ok"], approved)
            self.assertTrue(approved["plan"]["current_plan_evaluated"])
            self.assertTrue(approved["plan"]["fresh_preview_required"])
            self.assertTrue(
                approved["coordination"]["project_update_lock_released"]
            )
            self.assertTrue(
                approved["coordination"][
                    "project_update_lock_absent_verified"
                ]
            )
            self.assertTrue(
                approved["write_boundary"][
                    "preservation_relocation_succeeded"
                ]
            )
            self.assertFalse(approved["write_boundary"]["deletes"])
            self.assertEqual(
                approved["write_boundary"]["delete_semantics"],
                "no_collision_payload_byte_deletion_or_unlink_cleanup; "
                "successful_atomic_relocation_vacates_source_name; "
                "owned_temporary_and_coordination_artifact_cleanup_is_separate",
            )
            self.assertFalse(approved["write_boundary"]["overwrites"])
            self.assertFalse(approved["write_boundary"]["update_retried"])
            self.assertTrue(approved["entry"]["private_bytes_read"])
            self.assertEqual(
                approved["entry"]["private_content_read_stages"],
                ["source_pre_move", "destination_post_move"],
            )
            self.assertEqual(
                approved["receipt"]["terminal_binding_verification_scope"],
                "unauthenticated_private_state_internal_consistency",
            )
            self.assertFalse(
                approved["receipt"]["authenticated_binding_verified"]
            )
            self.assertEqual(
                approved["trust_boundary"]["private_receipt_authentication"],
                "none",
            )
            self.assertTrue(
                approved["trust_boundary"]["single_artifact_drift_detection"]
            )
            self.assertFalse(
                approved["trust_boundary"][
                    "coordinated_same_user_private_state_rewrite_detection"
                ]
            )
            self.assertFalse(collision_path.exists())
            case_suffix = approved["quarantine"]["case_ref"].split(":", 1)[1]
            case_directory = (
                fixture["metadata_root"]
                / "private"
                / "version-update-collisions"
                / f"case-{case_suffix}"
            )
            self.assertEqual(
                (case_directory / "payload").read_bytes(),
                private_bytes,
            )
            self.assertTrue((case_directory / "intent.json").is_file())
            self.assertTrue((case_directory / "completed.json").is_file())
            intent_payload = json.loads(
                (case_directory / "intent.json").read_text(encoding="utf-8")
            )
            completion_payload = json.loads(
                (case_directory / "completed.json").read_text(
                    encoding="utf-8"
                )
            )
            private_content_sha256 = intent_payload["source_content_sha256"]
            self.assertEqual(
                intent_payload["schema"],
                "wom-kit/project-version-update-collision-private-intent/v0.2",
            )
            self.assertEqual(
                completion_payload["schema"],
                "wom-kit/project-version-update-collision-private-completion/v0.2",
            )
            self.assertEqual(
                completion_payload["payload_content_sha256"],
                private_content_sha256,
            )
            self.assertEqual(
                completion_payload["payload_file_index"],
                intent_payload["source_file_index"],
            )
            self.assertEqual(
                completion_payload["payload_volume_serial"],
                intent_payload["source_volume_serial"],
            )
            self.assertFalse(
                (fixture["metadata_root"] / "version-update.lock").exists()
            )
            rendered = json.dumps(approved, ensure_ascii=False)
            self.assertNotIn(fixture["collision_name"], rendered)
            self.assertNotIn(private_bytes.decode().strip(), rendered)
            self.assertNotIn(private_content_sha256, rendered)
            self.assertNotIn(str(fixture["project_root"]), rendered)

            fresh_preview_before_observation = (
                archive_services.wom_kit_project_version_update(
                    fixture["project_root"],
                    target=fixture["target_tag"],
                    dry_run=True,
                )
            )
            self.assertTrue(
                fresh_preview_before_observation["ok"],
                fresh_preview_before_observation,
            )
            self.assertEqual(
                fresh_preview_before_observation["status"],
                "ready_for_approval",
            )

            observed_inspect = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="inspect",
                dry_run=True,
            )
            self.assertTrue(observed_inspect["ok"], observed_inspect)
            self.assertEqual(observed_inspect["status"], "preserved_relocated")
            self.assertTrue(
                observed_inspect["quarantine"]["already_completed"]
            )
            self.assertTrue(observed_inspect["entry"]["private_bytes_read"])
            self.assertEqual(
                observed_inspect["entry"]["private_content_read_stages"],
                ["preserved_payload_terminal_reobserve"],
            )
            self.assertFalse(observed_inspect["write_boundary"]["writes"])
            self.assertTrue(
                observed_inspect["write_boundary"]["terminal_observation_only"]
            )
            self.assertFalse(
                observed_inspect["plan"]["current_plan_evaluated"]
            )
            self.assertIsNone(
                observed_inspect["plan"]["materialization_plan_sha256"]
            )
            self.assertTrue(
                observed_inspect["plan"]["fresh_preview_required"]
            )

            observed_completion = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )
            self.assertTrue(observed_completion["ok"], observed_completion)
            self.assertEqual(
                observed_completion["status"],
                "preserved_relocated",
            )
            self.assertTrue(
                observed_completion["quarantine"]["already_completed"]
            )
            self.assertTrue(
                observed_completion["receipt"]["terminal_binding_verified"]
            )
            self.assertTrue(
                observed_completion["receipt"][
                    "terminal_internal_consistency_verified"
                ]
            )
            self.assertFalse(
                observed_completion["receipt"][
                    "authenticated_binding_verified"
                ]
            )
            self.assertTrue(
                observed_completion["entry"]["private_bytes_read"]
            )
            self.assertEqual(
                observed_completion["entry"][
                    "private_content_read_stages"
                ],
                ["preserved_payload_terminal_reobserve"],
            )
            self.assertFalse(
                observed_completion["coordination"][
                    "project_update_lock_absent_verified"
                ]
            )
            self.assertTrue(
                observed_completion["coordination"][
                    "project_update_lock_absent_at_start_verified"
                ]
            )
            self.assertFalse(
                observed_completion["plan"]["current_plan_evaluated"]
            )
            self.assertTrue(
                observed_completion["plan"]["fresh_preview_required"]
            )
            self.assertFalse(observed_completion["write_boundary"]["writes"])
            self.assertFalse(
                observed_completion["write_boundary"][
                    "preservation_relocation_attempted"
                ]
            )
            self.assertTrue(
                observed_completion["write_boundary"][
                    "preservation_relocation_already_completed"
                ]
            )
            self.assertTrue(
                observed_completion["write_boundary"][
                    "terminal_observation_only"
                ]
            )
            self.assertFalse(
                observed_completion["write_boundary"]["update_retried"]
            )
            self.assertFalse(collision_path.exists())
            self.assertEqual(
                (case_directory / "payload").read_bytes(),
                private_bytes,
            )
            observed_rendered = json.dumps(
                observed_completion,
                ensure_ascii=False,
            )
            self.assertNotIn(fixture["collision_name"], observed_rendered)
            self.assertNotIn(private_bytes.decode().strip(), observed_rendered)
            self.assertNotIn(private_content_sha256, observed_rendered)
            self.assertNotIn(str(fixture["project_root"]), observed_rendered)

            fresh_preview = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                dry_run=True,
            )
            self.assertTrue(fresh_preview["ok"], fresh_preview)
            self.assertEqual(fresh_preview["status"], "ready_for_approval")
            self.assertEqual(
                fresh_preview["materialization_preflight"],
                fresh_preview_before_observation["materialization_preflight"],
            )

            payload_path = case_directory / "payload"
            same_length_tamper = b"X" * len(private_bytes)
            self.assertNotEqual(same_length_tamper, private_bytes)
            payload_path.write_bytes(same_length_tamper)
            payload_tampered = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="inspect",
                dry_run=True,
            )
            self.assertEqual(
                payload_tampered["status"],
                "collision_state_recovery_required",
            )
            self.assertIn(
                "project_update_collision_recovery_required",
                payload_tampered["blocker_codes"],
            )
            self.assertFalse(payload_tampered["write_boundary"]["writes"])
            self.assertTrue(payload_tampered["entry"]["private_bytes_read"])
            self.assertEqual(
                payload_tampered["entry"]["private_content_read_stages"],
                ["preserved_payload_terminal_reobserve"],
            )
            self.assertNotIn(
                private_content_sha256,
                json.dumps(payload_tampered, ensure_ascii=False),
            )
            self.assertEqual(payload_path.read_bytes(), same_length_tamper)
            payload_path.write_bytes(private_bytes)

            original_payload_backup = case_directory / "payload-original-test"
            replacement_payload = case_directory / "payload-replacement-test"
            payload_path.rename(original_payload_backup)
            replacement_payload.write_bytes(private_bytes)
            replacement_payload.rename(payload_path)
            identity_replaced = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )
            self.assertEqual(
                identity_replaced["status"],
                "collision_state_recovery_required",
            )
            self.assertIn(
                "project_update_collision_recovery_required",
                identity_replaced["blocker_codes"],
            )
            self.assertFalse(identity_replaced["write_boundary"]["writes"])
            self.assertTrue(identity_replaced["entry"]["private_bytes_read"])
            self.assertEqual(
                identity_replaced["entry"]["private_content_read_stages"],
                ["preserved_payload_terminal_reobserve"],
            )
            self.assertEqual(payload_path.read_bytes(), private_bytes)
            payload_path.unlink()
            original_payload_backup.rename(payload_path)

            completion_path = case_directory / "completed.json"
            completion_bytes = completion_path.read_bytes()
            completion_path.write_bytes(completion_bytes + b"\nTAMPERED")
            tampered = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )
            self.assertEqual(
                tampered["status"],
                "collision_state_recovery_required",
            )
            self.assertIn(
                "project_update_collision_recovery_required",
                tampered["blocker_codes"],
            )
            self.assertFalse(tampered["write_boundary"]["writes"])
            self.assertFalse(collision_path.exists())
            self.assertEqual(
                (case_directory / "payload").read_bytes(),
                private_bytes,
            )
            completion_path.write_bytes(completion_bytes)

            final_update = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                approve=True,
                reviewed_by="human:letter-127-test",
                affirm_external_writers_quiescent=True,
            )
            self.assertTrue(final_update["ok"], final_update)
            self.assertEqual(
                final_update["status"],
                "updated_restart_required",
            )

    def test_private_read_observer_and_zero_byte_windows_preservation(
        self,
    ) -> None:
        observed: list[str] = []

        def zero_read_failure(
            _handle: object,
            _buffer: object,
            _requested: int,
            read_count: object,
            _overlapped: object,
        ) -> bool:
            read_count._obj.value = 0
            return False

        failed_digest = (
            archive_services._wom_kit_project_update_collision_hash_open_windows_handle(
                object(),
                zero_read_failure,
                1,
                content_read_observer=lambda: observed.append("read"),
            )
        )
        self.assertIsNone(failed_digest)
        self.assertEqual(observed, [])

        partial_calls = 0

        def partial_then_fail(
            _handle: object,
            buffer: object,
            _requested: int,
            read_count: object,
            _overlapped: object,
        ) -> bool:
            nonlocal partial_calls
            partial_calls += 1
            if partial_calls == 1:
                buffer[0] = b"A"
                read_count._obj.value = 1
                return True
            read_count._obj.value = 0
            return False

        partial_digest = (
            archive_services._wom_kit_project_update_collision_hash_open_windows_handle(
                object(),
                partial_then_fail,
                2,
                content_read_observer=lambda: observed.append("read"),
            )
        )
        self.assertIsNone(partial_digest)
        self.assertEqual(observed, ["read"])

        observed.clear()

        def valid_empty_read(
            _handle: object,
            _buffer: object,
            _requested: int,
            read_count: object,
            _overlapped: object,
        ) -> bool:
            read_count._obj.value = 0
            return True

        empty_digest = (
            archive_services._wom_kit_project_update_collision_hash_open_windows_handle(
                object(),
                valid_empty_read,
                0,
                content_read_observer=lambda: observed.append("read"),
            )
        )
        self.assertEqual(
            empty_digest,
            "sha256:e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855",
        )
        self.assertEqual(observed, [])

        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                _,
                _,
                _,
            ) = self.collision_fixture(Path(tmp))
            collision_path.write_bytes(b"")
            refreshed = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                dry_run=True,
            )
            preflight = refreshed["materialization_preflight"]
            entry_ref = next(
                conflict["entry_ref"]
                for conflict in preflight["conflicts"]
                if "untracked_entry_overlaps_target_file"
                in conflict["reason_codes"]
            )
            plan_sha256 = preflight["materialization_plan_sha256"]
            approved = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )
            self.assertTrue(approved["ok"], approved)
            self.assertEqual(approved["status"], "preserved_relocated")
            self.assertFalse(approved["entry"]["private_bytes_read"])
            self.assertEqual(
                approved["entry"]["private_content_read_stages"],
                [],
            )
            observed_terminal = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="inspect",
                dry_run=True,
            )
            self.assertTrue(observed_terminal["ok"], observed_terminal)
            self.assertTrue(
                observed_terminal["receipt"][
                    "terminal_internal_consistency_verified"
                ]
            )
            self.assertFalse(
                observed_terminal["entry"]["private_bytes_read"]
            )
            self.assertEqual(
                observed_terminal["entry"]["private_content_read_stages"],
                [],
            )

    def test_plan_drift_and_hardlink_fail_without_moving_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            with patch.object(
                archive_services,
                "_wom_kit_project_update_collision_git_eligibility",
                return_value=(False, True),
            ):
                not_ignored = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    dry_run=True,
                )
            self.assertIn(
                "project_update_collision_entry_not_relocatable",
                not_ignored["blocker_codes"],
            )
            self.assertFalse(not_ignored["entry"]["ignored_verified"])
            self.assertEqual(collision_path.read_bytes(), private_bytes)

            self.fixture_case.git_fixture_command(
                fixture["mirror"],
                "add",
                "-f",
                fixture["collision_name"],
            )
            index_tracked = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                dry_run=True,
            )
            self.assertEqual(
                index_tracked["blocker_codes"],
                ["project_update_collision_git_state_unsafe"],
            )
            self.fixture_case.git_fixture_command(
                fixture["mirror"],
                "reset",
                "--quiet",
                "--",
                fixture["collision_name"],
            )
            collision_path.write_bytes(private_bytes + b"DRIFT\n")
            drifted = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                dry_run=True,
            )
            self.assertEqual(
                drifted["blocker_codes"],
                ["project_update_collision_plan_drifted"],
            )
            self.assertEqual(
                collision_path.read_bytes(),
                private_bytes + b"DRIFT\n",
            )

        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                _,
            ) = self.collision_fixture(Path(tmp))
            hardlink = fixture["mirror"] / "private-hardlink-alias.bin"
            hardlink.hardlink_to(collision_path)
            with (fixture["mirror"] / ".git" / "info" / "exclude").open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write("private-hardlink-alias.bin\n")
            refreshed = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                dry_run=True,
            )
            hardlink_plan = refreshed["materialization_preflight"]
            hardlink_ref = next(
                conflict["entry_ref"]
                for conflict in hardlink_plan["conflicts"]
                if "untracked_entry_overlaps_target_file"
                in conflict["reason_codes"]
            )
            blocked = self.collision_call(
                fixture,
                hardlink_ref,
                hardlink_plan["materialization_plan_sha256"],
                action="preserve-relocate",
                dry_run=True,
            )
            self.assertIn(
                "project_update_collision_entry_not_relocatable",
                blocked["blocker_codes"],
            )
            self.assertFalse(blocked["entry"]["single_link_verified"])
            self.assertEqual(collision_path.read_bytes(), private_bytes)
            self.assertEqual(hardlink.read_bytes(), private_bytes)

    def test_completion_failure_preserves_payload_and_owned_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            original_writer = (
                archive_services._wom_kit_project_update_collision_write_private_receipt
            )
            calls = 0

            def fail_completion(*args: object, **kwargs: object) -> bool:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return original_writer(*args, **kwargs)
                return False

            with patch.object(
                archive_services,
                "_wom_kit_project_update_collision_write_private_receipt",
                side_effect=fail_completion,
            ):
                result = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    approve=True,
                )

            self.assertEqual(
                result["status"],
                "preserved_relocated_recovery_required",
            )
            self.assertFalse(result["ok"])
            self.assertFalse(collision_path.exists())
            case_suffix = result["quarantine"]["case_ref"].split(":", 1)[1]
            payload = (
                fixture["metadata_root"]
                / "private"
                / "version-update-collisions"
                / f"case-{case_suffix}"
                / "payload"
            )
            self.assertEqual(payload.read_bytes(), private_bytes)
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )
            self.assertFalse(
                result["coordination"]["project_update_lock_released"]
            )
            self.assertFalse(result["write_boundary"]["rollback_move_attempted"])

    def test_existing_destination_and_uncertain_lock_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            preview = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                dry_run=True,
            )
            case_suffix = preview["quarantine"]["case_ref"].split(":", 1)[1]
            existing_case = (
                fixture["metadata_root"]
                / "private"
                / "version-update-collisions"
                / f"case-{case_suffix}"
            )
            existing_case.mkdir(parents=True)
            marker = existing_case / "PRIVATE-DO-NOT-OVERWRITE.bin"
            marker_bytes = b"PRIVATE EXISTING CASE\n"
            marker.write_bytes(marker_bytes)

            blocked = self.collision_call(
                fixture,
                entry_ref,
                plan_sha256,
                action="preserve-relocate",
                approve=True,
            )
            self.assertEqual(
                blocked["status"],
                "collision_state_recovery_required",
            )
            self.assertIn(
                "project_update_collision_private_case_exists",
                blocked["blocker_codes"],
            )
            self.assertEqual(marker.read_bytes(), marker_bytes)
            self.assertEqual(collision_path.read_bytes(), private_bytes)
            rendered = json.dumps(blocked, ensure_ascii=False)
            self.assertNotIn(marker.name, rendered)
            self.assertNotIn(marker_bytes.decode().strip(), rendered)

        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            original_acquire = (
                archive_services.wom_kit_project_update_acquire_lock_exclusive
            )

            def acquire_then_uncertain(*args: object, **kwargs: object) -> object:
                original_acquire(*args, **kwargs)
                raise archive_services.WomKitProjectUpdateReceiptUncertainError(
                    "content_free_test_failure"
                )

            with patch.object(
                archive_services,
                "wom_kit_project_update_acquire_lock_exclusive",
                side_effect=acquire_then_uncertain,
            ):
                uncertain = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    approve=True,
                )
            self.assertEqual(
                uncertain["status"],
                "collision_state_recovery_required",
            )
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )
            self.assertFalse(
                uncertain["coordination"]["project_update_lock_released"]
            )
            self.assertEqual(collision_path.read_bytes(), private_bytes)

    def test_approved_catch_all_reports_unverified_and_retains_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            with patch.object(
                archive_services,
                "_wom_kit_project_update_collision_move_windows",
                side_effect=KeyboardInterrupt(),
            ):
                result = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    approve=True,
                )

            self.assertEqual(
                result["status"],
                "collision_outcome_unverified_recovery_required",
            )
            self.assertFalse(result["outcome_verified"])
            self.assertIsNone(result["write_boundary"]["writes"])
            self.assertFalse(result["write_boundary"]["writes_verified"])
            self.assertTrue(
                result["write_boundary"]["writes_may_have_occurred"]
            )
            self.assertIsNone(
                result["write_boundary"][
                    "preservation_relocation_attempted"
                ]
            )
            self.assertIsNone(
                result["write_boundary"][
                    "preservation_relocation_succeeded"
                ]
            )
            self.assertTrue(
                result["write_boundary"][
                    "relocation_may_have_been_attempted"
                ]
            )
            self.assertIn(
                "project_update_collision_outcome_unverified",
                result["blocker_codes"],
            )
            self.assertFalse(
                result["coordination"]["project_update_lock_released"]
            )
            self.assertFalse(
                result["coordination"][
                    "project_update_lock_absent_verified"
                ]
            )
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )
            self.assertEqual(collision_path.read_bytes(), private_bytes)
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(fixture["collision_name"], rendered)
            self.assertNotIn(private_bytes.decode().strip(), rendered)

    def test_post_rename_verifier_interruption_keeps_unknown_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            with patch.object(
                archive_services,
                "_wom_kit_project_update_collision_private_file_binding_windows",
                side_effect=KeyboardInterrupt(),
            ):
                result = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    approve=True,
                )

            self.assertEqual(
                result["status"],
                "collision_outcome_unverified_recovery_required",
            )
            self.assertFalse(result["outcome_verified"])
            self.assertIsNone(result["write_boundary"]["writes"])
            self.assertIsNone(
                result["write_boundary"][
                    "preservation_relocation_attempted"
                ]
            )
            self.assertIsNone(
                result["write_boundary"][
                    "preservation_relocation_succeeded"
                ]
            )
            self.assertTrue(
                result["write_boundary"][
                    "relocation_may_have_been_attempted"
                ]
            )
            self.assertFalse(collision_path.exists())
            case_suffix = result["quarantine"]["case_ref"].split(":", 1)[1]
            case_directory = (
                fixture["metadata_root"]
                / "private"
                / "version-update-collisions"
                / f"case-{case_suffix}"
            )
            self.assertEqual(
                (case_directory / "payload").read_bytes(),
                private_bytes,
            )
            self.assertTrue((case_directory / "intent.json").is_file())
            self.assertFalse((case_directory / "completed.json").exists())
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )
            self.assertFalse(
                result["coordination"]["project_update_lock_released"]
            )
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(fixture["collision_name"], rendered)
            self.assertNotIn(private_bytes.decode().strip(), rendered)

    def test_reported_lock_release_requires_verified_safe_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (
                fixture,
                collision_path,
                private_bytes,
                entry_ref,
                plan_sha256,
            ) = self.collision_fixture(Path(tmp))
            with patch.object(
                archive_services,
                "wom_kit_project_update_release_owned_lock",
                return_value=True,
            ):
                result = self.collision_call(
                    fixture,
                    entry_ref,
                    plan_sha256,
                    action="preserve-relocate",
                    approve=True,
                )

            self.assertEqual(
                result["status"],
                "collision_state_recovery_required",
            )
            self.assertFalse(
                result["coordination"][
                    "project_update_lock_absent_verified"
                ]
            )
            self.assertFalse(
                result["coordination"]["project_update_lock_released"]
            )
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )
            self.assertFalse(collision_path.exists())
            self.assertTrue(result["write_boundary"]["writes"])

    def test_runtime_shadow_cannot_use_target_path_disclosure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture_case.create_project_version_update_fixture(
                Path(tmp)
            )
            shadow_relative = "wom-kit/src/private-shadow.py"
            with (fixture["mirror"] / ".git" / "info" / "exclude").open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(shadow_relative + "\n")
            shadow_path = fixture["mirror"] / "wom-kit" / "src" / "private-shadow.py"
            shadow_bytes = b"PRIVATE RUNTIME SHADOW\n"
            shadow_path.write_bytes(shadow_bytes)
            failed = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                approve=True,
                reviewed_by="human:letter-127-test",
                affirm_external_writers_quiescent=True,
            )
            preflight = failed["materialization_preflight"]
            conflict = next(
                item
                for item in preflight["conflicts"]
                if "ignored_or_untracked_runtime_source_shadow"
                in item["reason_codes"]
            )
            inspected = self.collision_call(
                fixture,
                conflict["entry_ref"],
                preflight["materialization_plan_sha256"],
                action="inspect",
                dry_run=True,
                reveal=True,
            )
            self.assertTrue(inspected["ok"], inspected)
            self.assertIsNone(inspected["target"]["target_relative_path"])
            self.assertFalse(
                inspected["target"]["target_relative_path_available"]
            )
            rendered = json.dumps(inspected, ensure_ascii=False)
            self.assertNotIn(shadow_relative, rendered)
            self.assertNotIn(shadow_bytes.decode().strip(), rendered)


class ProjectUpdateOperationControlProjectionTests(unittest.TestCase):
    def write_failed_update_result(
        self,
        root: Path,
        *,
        private_canary: str,
    ) -> tuple[operation_control.OperationRunJournal, Path]:
        output = root / ".zettel-kasten" / "diagnostics" / "update.json"
        journal = operation_control.OperationRunJournal.prepare(
            root,
            output_relative=".zettel-kasten/diagnostics/update.json",
            command="project-version-update",
            run_id="1" * 32,
        )
        payload = {
            "ok": False,
            "status": "blocked",
            "target": {"tag": TARGET},
            "blocker_codes": [
                "project_update_materialization_collision"
            ],
            "blockers": [private_canary],
            "materialization_preflight": {
                "materialization_plan_sha256": PLAN_SHA256,
                "conflicts": [
                    {
                        "reason_codes": ["ignored_target_path_collision"],
                        "entry_ref": ENTRY_REF,
                        "private_local_path": private_canary,
                    }
                ]
            },
            "cli_execution": {
                "status": "completed",
                "run_id": journal.run_id,
                "command": "project-version-update",
                "exit_code": 1,
            },
            "cli_output_artifact": {
                "command": "project-version-update",
                "operation": journal.metadata(),
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.assertTrue(
            journal.complete(
                exit_code=1,
                result_available=True,
                result_ok=False,
                result_path=output,
            )
        )
        return journal, output

    def test_failed_bound_update_gets_path_free_collision_next_action(
        self,
    ) -> None:
        private_canary = "PRIVATE_IGNORED_LOCAL_PATH_315"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            journal, _ = self.write_failed_update_result(
                root,
                private_canary=private_canary,
            )
            try:
                status = operation_control.inspect_operation(
                    root,
                    journal.operation_ref,
                )
                recovery = operation_control.recovery_plan(
                    root,
                    journal.operation_ref,
                )
            finally:
                journal.close()

        for result in (status, recovery):
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "completed_result_available")
            self.assertFalse(result["control"]["recovery_required"])
            self.assertFalse(result["result"]["ok"])
            domain = result["result"]["domain"]
            self.assertFalse(domain["completion_ok"])
            self.assertTrue(domain["attention_required"])
            self.assertEqual(domain["collision_refs"], [ENTRY_REF])
            self.assertEqual(
                domain["materialization_plan_sha256"], PLAN_SHA256
            )
            self.assertIn(
                "project-version-update-collision",
                result["next_safe_actions"][0],
            )
            self.assertIn(ENTRY_REF, result["next_safe_actions"][0])
            self.assertIn(PLAN_SHA256, result["next_safe_actions"][0])
            self.assertNotIn(private_canary, rendered)
            self.assertNotIn(str(root), rendered)


if __name__ == "__main__":
    unittest.main()
