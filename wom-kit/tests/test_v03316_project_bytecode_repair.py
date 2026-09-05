from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import completion_workflows, project_runtime

from . import test_completion_workflows as _completion_tests
from . import test_letter129_project_update_collision_batch_core as _batch_core
from . import test_project_runtime as _project_runtime_tests


class Letter129ProjectBytecodeRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = _completion_tests.CompletionWorkflowTests(
            "runTest"
        )
        self.fixture_case.setUp()

    def tearDown(self) -> None:
        self.fixture_case.doCleanups()

    def fixture(self, root: Path) -> tuple[Path, Path, bytes]:
        return self.fixture_case.project_mirror_fixture(root)

    def test_approval_requires_external_writer_quiescence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            original = bytecode.read_bytes()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )

            result = completion_workflows._project_bytecode_repair_legacy_core(
                project_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-test",
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_external_writers_not_quiescent",
                result["blockers"],
            )
            self.assertEqual(bytecode.read_bytes(), original)

    def test_hardlinked_bytecode_is_not_a_cleanup_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            alias = bytecode.with_name("alias.cpython-312.pyc")
            try:
                os.link(bytecode, alias)
            except OSError as error:
                self.skipTest(f"hardlinks unavailable: {error}")

            result = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_hardlink_refused",
                result["blockers"],
            )
            self.assertTrue(bytecode.is_file())
            self.assertTrue(alias.is_file())

    def test_per_file_cap_is_enforced_by_stable_reader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            self.assertGreater(bytecode.stat().st_size, 4)

            with patch.object(
                completion_workflows,
                "PROJECT_BYTECODE_REPAIR_MAX_FILE_BYTES",
                4,
            ):
                result = completion_workflows.project_bytecode_repair_plan(
                    project_root,
                    max_files=100,
                )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_file_too_large",
                result["blockers"],
            )
            self.assertTrue(bytecode.is_file())

    def test_same_bytes_replacement_invalidates_approved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            original = bytecode.read_bytes()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            bytecode.unlink()
            bytecode.write_bytes(original)

            result = completion_workflows._project_bytecode_repair_legacy_core(
                project_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-test",
                affirm_external_writers_quiescent=True,
            )

            self.assertFalse(result["ok"])
            self.assertIn("project_bytecode_plan_changed", result["blockers"])
            self.assertEqual(bytecode.read_bytes(), original)

    def test_version_update_lock_blocks_repair_without_deleting_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            original = bytecode.read_bytes()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            lock_path = (
                project_root
                / completion_workflows.archive_services
                .WOM_KIT_PROJECT_UPDATE_LOCK_RELATIVE
            )
            lock_path.write_bytes(
                completion_workflows.archive_services
                .WOM_KIT_PROJECT_UPDATE_LOCK_BYTES
            )

            result = completion_workflows._project_bytecode_repair_legacy_core(
                project_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-test",
                affirm_external_writers_quiescent=True,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "blocked")
            self.assertIn("project_version_update_lock_active", result["blockers"])
            self.assertEqual(bytecode.read_bytes(), original)

    def test_name_swap_before_handle_delete_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            reviewed = bytecode.read_bytes()
            replacement = b"NEW UNREVIEWED BYTECODE"
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            original_delete = (
                completion_workflows.archive_services
                ._delete_activity_group_evidence_exact
            )
            swapped = False

            def swap_then_delete(root, path, **kwargs):
                nonlocal swapped
                if not swapped:
                    moved = path.with_name(path.name + ".reviewed")
                    path.replace(moved)
                    path.write_bytes(replacement)
                    swapped = True
                return original_delete(root, path, **kwargs)

            with patch.object(
                completion_workflows.archive_services,
                "_delete_activity_group_evidence_exact",
                side_effect=swap_then_delete,
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "partial")
            self.assertEqual(bytecode.read_bytes(), replacement)
            self.assertEqual(
                bytecode.with_name(bytecode.name + ".reviewed").read_bytes(),
                reviewed,
            )

    def test_same_bytes_new_inode_before_handle_delete_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            reviewed = bytecode.read_bytes()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            original_delete = (
                completion_workflows.archive_services
                ._delete_activity_group_evidence_exact
            )
            swapped = False

            def swap_then_delete(root, path, **kwargs):
                nonlocal swapped
                if not swapped:
                    path.replace(path.with_name(path.name + ".reviewed"))
                    path.write_bytes(reviewed)
                    swapped = True
                return original_delete(root, path, **kwargs)

            with patch.object(
                completion_workflows.archive_services,
                "_delete_activity_group_evidence_exact",
                side_effect=swap_then_delete,
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "partial")
            self.assertEqual(bytecode.read_bytes(), reviewed)
            self.assertEqual(
                bytecode.with_name(bytecode.name + ".reviewed").read_bytes(),
                reviewed,
            )

    def test_late_hardlink_before_handle_delete_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            alias = bytecode.with_name("late-alias.cpython-312.pyc")
            original_delete = (
                completion_workflows.archive_services
                ._delete_activity_group_evidence_exact
            )
            linked = False

            def link_then_delete(root, path, **kwargs):
                nonlocal linked
                if not linked:
                    os.link(path, alias)
                    linked = True
                return original_delete(root, path, **kwargs)

            with patch.object(
                completion_workflows.archive_services,
                "_delete_activity_group_evidence_exact",
                side_effect=link_then_delete,
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "partial")
            self.assertTrue(bytecode.is_file())
            self.assertTrue(alias.is_file())

    def test_post_delete_fsync_failure_reports_removed_byte_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            original_delete = (
                completion_workflows.archive_services
                ._delete_activity_group_evidence_exact
            )

            def delete_then_report_durability_failure(*args, **kwargs):
                original_delete(*args, **kwargs)
                raise OSError("injected post-delete durability failure")

            with patch.object(
                completion_workflows.archive_services,
                "_delete_activity_group_evidence_exact",
                side_effect=delete_then_report_durability_failure,
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "partial")
            self.assertFalse(bytecode.exists())
            self.assertEqual(result["summary"]["removed_count"], 1)
            self.assertTrue(result["writes_may_have_occurred"])
            self.assertIn(
                "project_bytecode_removal_durability_unverified",
                result["blockers"],
            )

    def test_cache_directory_removal_failure_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            cache_directory = bytecode.parent
            bytecode.unlink()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )

            with patch.object(
                Path,
                "rmdir",
                side_effect=OSError("injected rmdir failure"),
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "partial")
            self.assertTrue(cache_directory.is_dir())
            self.assertIn(
                "project_bytecode_cache_directory_removal_failed",
                result["blockers"],
            )

    def test_cache_directory_with_non_bytecode_child_blocks_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            note = bytecode.parent / "notes.txt"
            note.write_bytes(b"KEEP THIS USER FILE")
            original_bytecode = bytecode.read_bytes()

            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )

            self.assertFalse(plan["ok"])
            self.assertEqual(plan["state"], "blocked")
            self.assertIn(
                "project_bytecode_cache_directory_contains_unsupported_entry",
                plan["blockers"],
            )
            self.assertEqual(bytecode.read_bytes(), original_bytecode)
            self.assertEqual(note.read_bytes(), b"KEEP THIS USER FILE")

    def test_receipt_parent_junction_is_rejected_before_external_write(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction regression")
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            outside = Path(tmp) / "outside-receipts"
            outside.mkdir()
            junction = project_root / ".zettel-kasten" / "receipts"
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True,
                text=True,
            )
            if created.returncode != 0:
                self.skipTest("junction creation unavailable")
            try:
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

                self.assertFalse(result["ok"])
                self.assertEqual(result["state"], "blocked")
                self.assertTrue(bytecode.is_file())
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse(result["privacy_guards"]["writes"])
            finally:
                subprocess.run(
                    ["cmd", "/c", "rmdir", str(junction)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

    def test_mounted_archive_root_resolves_parent_project_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            archive_root = project_root / "archive"
            archive_root.mkdir()
            (archive_root / "archive.yml").write_text(
                "archive_id: mounted-letter-129\n",
                encoding="utf-8",
            )

            plan = completion_workflows.project_bytecode_repair_plan(
                archive_root,
                max_files=100,
            )
            self.assertTrue(plan["ok"], plan)
            repaired = completion_workflows._project_bytecode_repair_legacy_core(
                archive_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-test",
                affirm_external_writers_quiescent=True,
            )

            self.assertTrue(repaired["ok"], repaired)
            self.assertFalse(bytecode.exists())
            self.assertTrue(
                (project_root / repaired["summary"]["receipt_path"]).is_file()
            )

    def test_empty_cache_directory_inventory_obeys_entry_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror, bytecode, _source = self.fixture(project_root)
            bytecode.unlink()
            runtime_root = mirror / "wom-kit" / "src" / "wom_kit"
            for index in range(4):
                package = runtime_root / f"package_{index}" / "__pycache__"
                package.mkdir(parents=True)
            (mirror / ".git" / "info" / "exclude").write_text(
                "**/__pycache__/\n",
                encoding="utf-8",
            )

            result = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=1,
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_inventory_bound_exceeded",
                result["blockers"],
            )

    def test_unignored_untracked_bytecode_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror, bytecode, _source = self.fixture(project_root)
            (mirror / ".gitignore").write_text("", encoding="utf-8")

            result = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_not_ignored_refused",
                result["blockers"],
            )
            self.assertTrue(bytecode.is_file())

    def test_empty_bytecode_cache_directory_has_approved_cleanup_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            cache_directory = bytecode.parent
            bytecode.unlink()
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "ready")
            self.assertEqual(plan["summary"]["bytecode_file_count"], 0)
            self.assertEqual(plan["summary"]["pycache_directory_count"], 1)

            result = completion_workflows._project_bytecode_repair_legacy_core(
                project_root,
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-test",
                affirm_external_writers_quiescent=True,
            )

            self.assertTrue(result["ok"], result)
            self.assertFalse(cache_directory.exists())
            self.assertEqual(
                result["summary"][
                    "removed_empty_pycache_directory_count"
                ],
                1,
            )

    def test_receipt_failure_reports_removed_bytes_as_evidence_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            _mirror, bytecode, _source = self.fixture(project_root)
            plan = completion_workflows.project_bytecode_repair_plan(
                project_root,
                max_files=100,
            )
            original_write = (
                completion_workflows.archive_services
                ._write_bytes_create_if_absent
            )

            def fail_completion_receipt(path, value):
                if path.name.endswith(".json") and ".intent." not in path.name:
                    raise OSError("injected completion receipt failure")
                return original_write(path, value)

            with patch.object(
                completion_workflows.archive_services,
                "_write_bytes_create_if_absent",
                side_effect=fail_completion_receipt,
            ):
                result = completion_workflows._project_bytecode_repair_legacy_core(
                    project_root,
                    max_files=100,
                    expected_plan_sha256=plan["summary"]["plan_sha256"],
                    reviewed_by="person:letter-129-test",
                    affirm_external_writers_quiescent=True,
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["state"], "evidence_incomplete")
            self.assertFalse(bytecode.exists())
            self.assertEqual(result["summary"]["removed_count"], 1)
            self.assertIsNone(result["summary"]["receipt_path"])
            self.assertTrue(result["privacy_guards"]["writes"])
            self.assertIn(
                "project_bytecode_receipt_evidence_incomplete",
                result["blockers"],
            )


class Letter129BoundRepairCanaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = (
            _batch_core.Letter129ProjectUpdateCollisionBatchCoreTests(
                "runTest"
            )
        )
        self.fixture_case.setUp()

    def tearDown(self) -> None:
        self.fixture_case.tearDown()

    def test_historical_repair_preserves_planner_but_public_update_requires_durable_runtime_supply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _private_markers = self.fixture_case.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=24,
            )
            preview = self.fixture_case.update_preview(fixture)
            materialization_plan_sha256 = preview[
                "materialization_preflight"
            ]["materialization_plan_sha256"]
            target = str(fixture["target_tag"])

            plan = completion_workflows.project_bytecode_repair_plan(
                fixture["project_root"],
                max_files=100,
                target=target,
                expected_materialization_plan_sha256=(
                    materialization_plan_sha256
                ),
            )
            self.assertTrue(plan["ok"], plan)
            self.assertTrue(
                plan["summary"]["collision_binding_verified"]
            )
            self.assertEqual(plan["summary"]["collision_entry_count"], 25)

            repaired = completion_workflows._project_bytecode_repair_legacy_core(
                fixture["project_root"],
                max_files=100,
                expected_plan_sha256=plan["summary"]["plan_sha256"],
                reviewed_by="person:letter-129-canary",
                affirm_external_writers_quiescent=True,
                target=target,
                expected_materialization_plan_sha256=(
                    materialization_plan_sha256
                ),
            )
            self.assertTrue(repaired["ok"], repaired)
            self.assertEqual(repaired["summary"]["removed_count"], 24)
            self.assertEqual(
                repaired["summary"][
                    "removed_empty_pycache_directory_count"
                ],
                1,
            )

            fresh_preview = self.fixture_case.update_preview(fixture)
            self.assertTrue(fresh_preview["ok"], fresh_preview)
            self.assertEqual(
                fresh_preview["status"],
                "ready_for_approval",
            )
            self.assertEqual(
                fresh_preview["materialization_preflight"][
                    "conflict_count"
                ],
                0,
            )

            if os.name != "nt":
                # The historical repair planner remains portable, but the
                # approved project update is intentionally Windows-only in
                # v0.4.16.  Exercise the real POSIX contract without the
                # legacy test harness's approval-capability injection.
                with patch.object(
                    completion_workflows.archive_services,
                    "WOM_KIT_PROJECT_UPDATE_APPROVAL_PLATFORM_SUPPORTED",
                    False,
                ):
                    unsupported_preview = self.fixture_case.update_preview(
                        fixture
                    )
                self.assertTrue(unsupported_preview["ok"], unsupported_preview)
                self.assertEqual(
                    unsupported_preview["status"],
                    "preview_only_platform_unsupported",
                )
                self.assertFalse(
                    unsupported_preview["write_boundary"][
                        "approval_platform_supported"
                    ]
                )
                self.assertEqual(unsupported_preview["files_written"], [])
                return

            (
                update_code,
                update_output,
                _update_stderr,
            ) = self.fixture_case.fixture_case.run_cli_split(
                [
                    "project-version-update",
                    str(fixture["project_root"]),
                    "--target",
                    target,
                    "--approve",
                    "--reviewed-by",
                    "person:letter-129-canary",
                    "--affirm-external-writers-quiescent",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(update_code, 1, update_output)
            updated = json.loads(update_output)
            self.assertFalse(updated["ok"], updated)
            self.assertEqual(updated["status"], "blocked")
            self.assertIn(
                "project_version_update_durable_transaction_inputs_invalid",
                updated["blockers"],
            )
            self.assertEqual(updated["files_written"], [])
            self.assertEqual(
                (fixture["metadata_root"] / "installed-version.txt").read_text(
                    encoding="utf-8"
                ).strip(),
                fixture["old_tag"],
            )

    def test_collision_set_name_drift_blocks_bound_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _private_markers = self.fixture_case.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=2,
            )
            preview = self.fixture_case.update_preview(fixture)
            materialization_plan_sha256 = preview[
                "materialization_preflight"
            ]["materialization_plan_sha256"]
            runtime_root = (
                fixture["mirror"]
                / "wom-kit"
                / "src"
                / "wom_kit"
                / "__pycache__"
            )
            original = next(runtime_root.glob("*.pyc"))
            original.rename(
                runtime_root / "DIFFERENT_IGNORED_NAME.cpython-312.pyc"
            )

            result = completion_workflows.project_bytecode_repair_plan(
                fixture["project_root"],
                max_files=100,
                target=str(fixture["target_tag"]),
                expected_materialization_plan_sha256=(
                    materialization_plan_sha256
                ),
            )

            self.assertFalse(result["ok"])
            self.assertIn(
                "project_bytecode_collision_set_mismatch",
                result["blockers"],
            )

    def test_head_drift_after_collision_snapshot_blocks_bound_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _private_markers = self.fixture_case.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=2,
            )
            preview = self.fixture_case.update_preview(fixture)
            materialization_plan_sha256 = preview[
                "materialization_preflight"
            ]["materialization_plan_sha256"]
            original_batch = (
                completion_workflows.archive_services
                ._wom_kit_project_version_update_collision_inspect_batch_core
            )
            drifted = False

            def batch_then_commit(*args, **kwargs):
                nonlocal drifted
                result = original_batch(*args, **kwargs)
                if not drifted:
                    self.fixture_case.fixture_case.git_fixture_command(
                        fixture["mirror"],
                        "commit",
                        "--allow-empty",
                        "-m",
                        "injected authority drift",
                    )
                    drifted = True
                return result

            with patch.object(
                completion_workflows.archive_services,
                "_wom_kit_project_version_update_collision_inspect_batch_core",
                side_effect=batch_then_commit,
            ):
                result = completion_workflows.project_bytecode_repair_plan(
                    fixture["project_root"],
                    max_files=100,
                    target=str(fixture["target_tag"]),
                    expected_materialization_plan_sha256=(
                        materialization_plan_sha256
                    ),
                )

            self.assertFalse(result["ok"])
            self.assertFalse(
                result["summary"]["collision_binding_verified"]
            )
            self.assertIn(
                "project_bytecode_collision_authority_drifted",
                result["blockers"],
            )

    def test_cli_repair_approve_fails_closed_and_preview_remains_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, private_markers = self.fixture_case.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=3,
            )
            preview = self.fixture_case.update_preview(fixture)
            materialization_plan_sha256 = preview[
                "materialization_preflight"
            ]["materialization_plan_sha256"]
            target = str(fixture["target_tag"])
            project_root = str(fixture["project_root"])
            run_cli = self.fixture_case.fixture_case.run_cli
            (
                fixture["metadata_root"] / "installed-version.txt"
            ).write_text(target + "\n", encoding="utf-8")
            _project_runtime_tests._write_receipt_bound_runtime(
                fixture["project_root"],
                version=target.removeprefix("v"),
            )
            launcher = (
                fixture["project_root"]
                / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            )
            launcher.parent.mkdir(parents=True, exist_ok=True)
            launcher.write_bytes(project_runtime.launcher_bytes(target))
            runtime_inspection = project_runtime.inspect_runtime(
                fixture["project_root"],
                target,
            )
            self.assertTrue(
                runtime_inspection["receipt_candidate_valid"],
                runtime_inspection,
            )
            self.assertTrue(
                runtime_inspection["live_payload_aligned"],
                runtime_inspection,
            )

            inspect_code, inspect_output = run_cli(
                [
                    "project-version-update-collision",
                    project_root,
                    "--target",
                    target,
                    "--expected-plan-sha256",
                    materialization_plan_sha256,
                    "--action",
                    "inspect-all",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(inspect_code, 0, inspect_output)
            inspected = json.loads(inspect_output)
            self.assertTrue(inspected["remediation"]["route_eligible"])
            self.assertEqual(
                inspected["summary"]["inspected_entry_count"],
                4,
            )

            plan_code, plan_output = run_cli(
                [
                    "project-bytecode-repair-plan",
                    project_root,
                    "--target",
                    target,
                    "--expected-materialization-plan-sha256",
                    materialization_plan_sha256,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(plan_code, 0, plan_output)
            plan = json.loads(plan_output)
            self.assertTrue(plan["summary"]["collision_binding_verified"])

            # A parser-known closed writer must not inspect the runtime at all.
            # Keep the real receipt/payload checks in the read-only plan above.
            with patch.object(
                project_runtime,
                "current_project_runtime_binding",
                return_value={
                    "bound": True,
                    "reason_code": "current_project_runtime_bound",
                },
            ) as runtime_binding:
                repair_code, repair_output = run_cli(
                    [
                        "project-bytecode-repair",
                        project_root,
                        "--target",
                        target,
                        "--expected-materialization-plan-sha256",
                        materialization_plan_sha256,
                        "--expected-plan-sha256",
                        plan["summary"]["plan_sha256"],
                        "--approve",
                        "--reviewed-by",
                        "person:letter-129-cli-canary",
                        "--affirm-external-writers-quiescent",
                        "--format",
                        "json",
                    ]
                )
            runtime_binding.assert_not_called()
            self.assertEqual(repair_code, 1, repair_output)
            repaired = json.loads(repair_output)
            self.assertEqual(repaired["state"], "blocked")
            self.assertEqual(
                repaired["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertFalse(repaired["private_values_echoed"])

            fresh_code, fresh_output = run_cli(
                [
                    "project-version-update",
                    project_root,
                    "--target",
                    target,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(fresh_code, 1, fresh_output)
            fresh = json.loads(fresh_output)
            self.assertEqual(fresh["status"], "blocked")
            self.assertEqual(
                fresh["materialization_preflight"]["conflict_count"],
                4,
            )
            all_output = inspect_output + plan_output + repair_output
            for marker in private_markers:
                self.assertNotIn(marker, all_output)


if __name__ == "__main__":
    unittest.main()
