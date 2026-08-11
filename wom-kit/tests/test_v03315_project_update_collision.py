from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from wom_kit import archive_services, operation_control

from . import test_cli as _test_cli


class ProjectUpdateCollisionParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = _test_cli.ArchiveCliTests("runTest")
        self.fixture_case.setUp()

    def tearDown(self) -> None:
        self.fixture_case.doCleanups()

    def fixture(
        self,
        root: Path,
        *,
        ignored_checkout_collision: bool = False,
    ) -> dict[str, object]:
        return self.fixture_case.create_project_version_update_fixture(
            root,
            ignored_checkout_collision=ignored_checkout_collision,
        )

    def fetch_target(self, fixture: dict[str, object]) -> None:
        self.fixture_case.git_fixture_command(
            fixture["mirror"],
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            (
                f"refs/tags/{fixture['target_tag']}:"
                f"refs/tags/{fixture['target_tag']}"
            ),
        )

    @staticmethod
    def preview(fixture: dict[str, object]) -> dict[str, object]:
        return archive_services.wom_kit_project_version_update(
            fixture["project_root"],
            target=fixture["target_tag"],
            dry_run=True,
        )

    @staticmethod
    def approve(fixture: dict[str, object]) -> dict[str, object]:
        return archive_services.wom_kit_project_version_update(
            fixture["project_root"],
            target=fixture["target_tag"],
            approve=True,
            reviewed_by="human:letter-127-test",
            affirm_external_writers_quiescent=True,
        )

    def assert_private_projection(
        self,
        result: dict[str, object],
        *,
        forbidden: list[str],
    ) -> None:
        serialized = json.dumps(result, ensure_ascii=False)
        for value in forbidden:
            self.assertNotIn(value, serialized)
        preflight = result["materialization_preflight"]
        self.assertRegex(
            preflight["materialization_plan_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertFalse(preflight["local_paths_echoed"])
        self.assertFalse(preflight["entry_names_echoed"])
        self.assertTrue(preflight["no_write"])
        self.assertTrue(preflight["bounded"])
        for index, conflict in enumerate(preflight["conflicts"], start=1):
            self.assertEqual(
                conflict["entry_ref"],
                f"update-entry:{index:04d}",
            )
            self.assertTrue(conflict["reason_codes"])

    def test_local_ignored_target_collision_blocks_preview_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(
                Path(tmp),
                ignored_checkout_collision=True,
            )
            self.fetch_target(fixture)
            collision_path = fixture["mirror"] / fixture["collision_name"]
            private_bytes = b"PRIVATE LOCAL IGNORED CONTENT\n"
            collision_path.write_bytes(private_bytes)
            head_before = self.fixture_case.git_fixture_command(
                fixture["mirror"], "rev-parse", "HEAD"
            )
            pin_path = fixture["metadata_root"] / "installed-version.txt"
            pin_before = pin_path.read_bytes()

            preview = self.preview(fixture)
            applied = self.approve(fixture)

            for result in (preview, applied):
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(
                    result["blocker_codes"],
                    [
                        "project_version_update_materialization_conflict"
                    ],
                )
                preflight = result["materialization_preflight"]
                self.assertEqual(preflight["state"], "blocked")
                self.assertTrue(preflight["evaluated"])
                self.assertTrue(preflight["required"])
                self.assertFalse(preflight["safe"])
                self.assertGreaterEqual(preflight["conflict_count"], 1)
                self.assert_private_projection(
                    result,
                    forbidden=[
                        fixture["collision_name"],
                        private_bytes.decode().strip(),
                        str(fixture["project_root"]),
                        str(fixture["upstream"]),
                    ],
                )
            self.assertEqual(
                preview["materialization_preflight"][
                    "materialization_plan_sha256"
                ],
                applied["materialization_preflight"][
                    "materialization_plan_sha256"
                ],
            )
            self.assertTrue(applied["fetch"]["succeeded"])
            self.assertFalse(
                applied["source_mirror"]["source_checkout_change_attempted"]
            )
            self.assertEqual(
                self.fixture_case.git_fixture_command(
                    fixture["mirror"], "rev-parse", "HEAD"
                ),
                head_before,
            )
            self.assertEqual(pin_path.read_bytes(), pin_before)
            self.assertEqual(collision_path.read_bytes(), private_bytes)
            self.assertFalse(
                (fixture["metadata_root"] / "version-update.lock").exists()
            )
            self.assertFalse((fixture["metadata_root"] / "receipts").exists())

    def test_local_ignored_runtime_shadow_blocks_with_opaque_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            self.fetch_target(fixture)
            shadow_relative = "wom-kit/src/private_shadow.py"
            (fixture["mirror"] / ".git" / "info" / "exclude").write_text(
                shadow_relative + "\n",
                encoding="utf-8",
            )
            shadow_path = fixture["mirror"].joinpath(
                *PurePosixPath(shadow_relative).parts
            )
            shadow_text = "PRIVATE RUNTIME SHADOW MUST NOT ECHO"
            shadow_path.write_text(shadow_text + "\n", encoding="utf-8")

            preview = self.preview(fixture)
            applied = self.approve(fixture)

            for result in (preview, applied):
                self.assertEqual(result["status"], "blocked")
                reasons = {
                    reason
                    for conflict in result["materialization_preflight"][
                        "conflicts"
                    ]
                    for reason in conflict["reason_codes"]
                }
                self.assertIn(
                    "ignored_or_untracked_runtime_source_shadow",
                    reasons,
                )
                self.assert_private_projection(
                    result,
                    forbidden=[shadow_relative, shadow_text],
                )
            self.assertEqual(
                shadow_path.read_text(encoding="utf-8"),
                shadow_text + "\n",
            )

    def test_canonical_alias_and_win32_short_name_block_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(
                Path(tmp),
                ignored_checkout_collision=True,
            )
            self.fetch_target(fixture)
            exact_target_name = str(fixture["collision_name"])
            alias_name = exact_target_name.swapcase()
            self.assertNotEqual(alias_name, exact_target_name)
            exclude = fixture["mirror"] / ".git" / "info" / "exclude"
            exclude.write_text(alias_name + "\n", encoding="utf-8")
            alias_path = fixture["mirror"] / alias_name
            private_bytes = b"PRIVATE CANONICAL ALIAS\n"
            alias_path.write_bytes(private_bytes)
            head_before = self.fixture_case.git_fixture_command(
                fixture["mirror"], "rev-parse", "HEAD"
            )

            preview = self.preview(fixture)
            approved = self.approve(fixture)

            internal_plan = (
                archive_services._wom_kit_project_update_materialization_plan_details_internal(
                    fixture["mirror"],
                    fixture["target_commit"],
                )
            )
            authority = internal_plan[4]
            self.assertIn(
                (
                    "worktree-path-comparison-scheme",
                    archive_services.WOM_KIT_PROJECT_UPDATE_PATH_COMPARISON_SCHEME,
                ),
                authority,
            )
            self.assertTrue(
                any(
                    category == "worktree-path-canonical-map"
                    for category, _ in authority
                )
            )
            with patch.object(
                archive_services,
                "WOM_KIT_PROJECT_UPDATE_PATH_COMPARISON_SCHEME",
                "nfkc-casefold-hfs-windows-test-v2",
            ):
                changed_scheme_plan = (
                    archive_services.wom_kit_project_update_materialization_plan(
                        fixture["mirror"],
                        fixture["target_commit"],
                    )
                )
            self.assertNotEqual(
                preview["materialization_preflight"][
                    "materialization_plan_sha256"
                ],
                changed_scheme_plan["materialization_plan_sha256"],
            )

            for result in (preview, approved):
                self.assertEqual(result["status"], "blocked", result)
                reasons = {
                    reason
                    for conflict in result["materialization_preflight"][
                        "conflicts"
                    ]
                    for reason in conflict["reason_codes"]
                }
                self.assertIn(
                    "worktree_path_canonical_alias_collision",
                    reasons,
                )
                self.assert_private_projection(
                    result,
                    forbidden=[
                        alias_name,
                        exact_target_name,
                        private_bytes.decode().strip(),
                    ],
                )
            self.assertEqual(alias_path.read_bytes(), private_bytes)
            self.assertEqual(
                self.fixture_case.git_fixture_command(
                    fixture["mirror"], "rev-parse", "HEAD"
                ),
                head_before,
            )
            self.assertFalse(
                (fixture["metadata_root"] / "version-update.lock").exists()
            )

            alias_path.unlink()
            short_name = "LONGFI~1.TXT"
            exclude.write_text(short_name + "\n", encoding="utf-8")
            short_path = fixture["mirror"] / short_name
            short_path.write_bytes(b"PRIVATE SHORT NAME\n")
            short_preview = self.preview(fixture)
            short_reasons = {
                reason
                for conflict in short_preview["materialization_preflight"][
                    "conflicts"
                ]
                for reason in conflict["reason_codes"]
            }
            self.assertEqual(short_preview["status"], "blocked")
            self.assertIn("worktree_path_unsafe_cross_platform", short_reasons)
            self.assertNotIn(short_name, json.dumps(short_preview))

    def test_component_key_rejects_all_cross_platform_alias_surfaces(self) -> None:
        unsafe_paths = [
            "LONGFI~1.TXT",
            "directory/LONGFI~1.TXT",
            "con.txt",
            ".git/config",
            "trailing. ",
        ]
        for relative_path in unsafe_paths:
            with self.subTest(relative_path=relative_path):
                self.assertIsNone(
                    archive_services.wom_kit_project_update_worktree_path_canonical_key(
                        relative_path
                    )
                )
                self.assertFalse(
                    archive_services.wom_kit_project_update_safe_worktree_paths(
                        [relative_path]
                    )
                )
        self.assertFalse(
            archive_services.wom_kit_project_update_safe_worktree_paths(
                ["LongFile.txt", "LONGFI~1.TXT"]
            )
        )
        self.assertEqual(
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "Folder/Foo.txt"
            ),
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "folder/foo.txt"
            ),
        )
        self.assertEqual(
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "Ｆｏｌｄｅｒ/Foo.txt"
            ),
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "folder/foo.txt"
            ),
        )
        self.assertEqual(
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "fol\u200cder/foo.txt"
            ),
            archive_services.wom_kit_project_update_worktree_path_canonical_key(
                "folder/foo.txt"
            ),
        )

    def test_local_harmless_ignored_entry_remains_preview_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            self.fetch_target(fixture)
            ignored_name = "private-local-cache.bin"
            (fixture["mirror"] / ".git" / "info" / "exclude").write_text(
                ignored_name + "\n",
                encoding="utf-8",
            )
            ignored_path = fixture["mirror"] / ignored_name
            ignored_bytes = b"PRIVATE HARMLESS CACHE\n"
            ignored_path.write_bytes(ignored_bytes)

            preview = self.preview(fixture)

            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["status"], "ready_for_approval")
            preflight = preview["materialization_preflight"]
            self.assertEqual(preflight["state"], "ready")
            self.assertTrue(preflight["safe"])
            self.assertEqual(preflight["conflict_count"], 0)
            self.assertEqual(preview["blocker_codes"], [])
            self.assertEqual(ignored_path.read_bytes(), ignored_bytes)
            self.assertNotIn(ignored_name, json.dumps(preview))

    def test_clean_local_target_preview_and_approval_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            self.fetch_target(fixture)

            preview = self.preview(fixture)
            applied = self.approve(fixture)

            self.assertTrue(preview["ok"], preview)
            self.assertEqual(preview["status"], "ready_for_approval")
            self.assertEqual(
                preview["materialization_preflight"]["state"],
                "ready",
            )
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["status"], "updated_restart_required")
            self.assertTrue(
                applied["source_mirror"][
                    "runtime_source_rematerialization_succeeded"
                ]
            )
            self.assertEqual(applied["blocker_codes"], [])

    def test_unfetched_collision_is_deferred_then_locally_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(
                Path(tmp),
                ignored_checkout_collision=True,
            )
            collision_path = fixture["mirror"] / fixture["collision_name"]
            private_bytes = b"PRIVATE DEFERRED COLLISION\n"
            collision_path.write_bytes(private_bytes)

            first_preview = self.preview(fixture)
            applied = self.approve(fixture)
            second_preview = self.preview(fixture)

            self.assertTrue(first_preview["ok"], first_preview)
            self.assertEqual(
                first_preview["status"],
                "ready_to_fetch_on_approve",
            )
            deferred = first_preview["materialization_preflight"]
            self.assertEqual(
                deferred["state"],
                "deferred_until_approval_fetch",
            )
            self.assertFalse(deferred["evaluated"])
            self.assertIsNone(deferred["required"])
            self.assertIsNone(deferred["safe"])
            self.assertIsNone(deferred["materialization_plan_sha256"])
            self.assertFalse(first_preview["fetch"]["attempted"])
            self.assertEqual(applied["status"], "blocked")
            self.assertTrue(applied["fetch"]["succeeded"])
            self.assertEqual(second_preview["status"], "blocked")
            self.assertEqual(
                second_preview["blocker_codes"],
                ["project_version_update_materialization_conflict"],
            )
            self.assertEqual(collision_path.read_bytes(), private_bytes)

    def test_same_target_pin_only_is_not_required_but_shadow_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            applied = self.approve(fixture)
            self.assertTrue(applied["ok"], applied)
            for pin_path in (
                fixture["metadata_root"] / "installed-version.txt",
                fixture["mirror"] / "installed-version.txt",
            ):
                pin_path.write_text(
                    fixture["old_tag"] + "\n",
                    encoding="utf-8",
                )

            pin_only = self.preview(fixture)
            self.assertTrue(pin_only["ok"], pin_only)
            self.assertEqual(
                pin_only["materialization_preflight"]["state"],
                "not_required",
            )
            self.assertFalse(
                pin_only["materialization_preflight"]["required"]
            )

            shadow_relative = "wom-kit/src/runtime_tamper.py"
            with (fixture["mirror"] / ".git" / "info" / "exclude").open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(shadow_relative + "\n")
            fixture["mirror"].joinpath(
                *PurePosixPath(shadow_relative).parts
            ).write_text("PRIVATE TAMPER\n", encoding="utf-8")

            tampered = self.preview(fixture)
            self.assertFalse(tampered["ok"])
            self.assertEqual(tampered["status"], "blocked")
            self.assertTrue(
                tampered["materialization_preflight"]["required"]
            )
            self.assertEqual(
                tampered["materialization_preflight"]["state"],
                "blocked",
            )
            self.assertNotIn(shadow_relative, json.dumps(tampered))

    def test_tracked_file_directory_transitions_remain_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self.fixture_case.git_fixture_command(repo, "init", "-b", "main")
            self.fixture_case.git_fixture_command(
                repo, "config", "user.name", "archive-test"
            )
            self.fixture_case.git_fixture_command(
                repo,
                "config",
                "user.email",
                "archive-test.invalid",
            )
            (repo / "shape").mkdir()
            (repo / "shape" / "child.txt").write_text(
                "directory shape\n",
                encoding="utf-8",
            )
            self.fixture_case.git_fixture_command(repo, "add", ".")
            self.fixture_case.git_fixture_command(
                repo, "commit", "-m", "directory shape"
            )
            directory_commit = self.fixture_case.git_fixture_command(
                repo, "rev-parse", "HEAD"
            )
            shutil.rmtree(repo / "shape")
            (repo / "shape").write_text("file shape\n", encoding="utf-8")
            self.fixture_case.git_fixture_command(repo, "add", "-A")
            self.fixture_case.git_fixture_command(
                repo, "commit", "-m", "file shape"
            )
            file_commit = self.fixture_case.git_fixture_command(
                repo, "rev-parse", "HEAD"
            )

            self.fixture_case.git_fixture_command(
                repo, "checkout", "--detach", "--quiet", directory_commit
            )
            directory_to_file = (
                archive_services.wom_kit_project_update_materialization_plan(
                    repo,
                    file_commit,
                )
            )
            self.assertEqual(directory_to_file["state"], "ready")
            self.assertTrue(directory_to_file["safe"])

            ignored_empty = repo / "shape" / "private-empty"
            (repo / ".git" / "info" / "exclude").write_text(
                "shape/private-empty/\n",
                encoding="utf-8",
            )
            ignored_empty.mkdir()
            empty_directory_collision = (
                archive_services.wom_kit_project_update_materialization_plan(
                    repo,
                    file_commit,
                )
            )
            self.assertEqual(empty_directory_collision["state"], "blocked")
            empty_reasons = {
                reason
                for conflict in empty_directory_collision["conflicts"]
                for reason in conflict["reason_codes"]
            }
            self.assertIn(
                "untracked_directory_contains_untracked_entries",
                empty_reasons,
            )
            ignored_empty.rmdir()

            self.fixture_case.git_fixture_command(
                repo, "checkout", "--detach", "--quiet", file_commit
            )
            file_to_directory = (
                archive_services.wom_kit_project_update_materialization_plan(
                    repo,
                    directory_commit,
                )
            )
            self.assertEqual(file_to_directory["state"], "ready")
            self.assertTrue(file_to_directory["safe"])

    def test_final_target_snapshot_checks_name_cardinality_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp)
            target_name = "Foo.txt"
            target_bytes = b"target body\n"
            target_entries = {
                target_name: ("100644", "0" * 40, target_bytes)
            }
            target_path = mirror / target_name
            target_path.write_bytes(target_bytes)
            self.assertTrue(
                archive_services.wom_kit_project_update_target_worktree_snapshot_matches(
                    mirror,
                    target_entries,
                )
            )
            target_path.write_bytes(b"tamper body\n")
            self.assertFalse(
                archive_services.wom_kit_project_update_target_worktree_snapshot_matches(
                    mirror,
                    target_entries,
                )
            )
            target_path.write_bytes(target_bytes)
            temporary_name = mirror / "rename-intermediate"
            target_path.rename(temporary_name)
            alias_path = mirror / "foo.txt"
            temporary_name.rename(alias_path)
            self.assertFalse(
                archive_services.wom_kit_project_update_target_worktree_snapshot_matches(
                    mirror,
                    target_entries,
                )
            )
            alias_path.unlink()
            self.assertFalse(
                archive_services.wom_kit_project_update_target_worktree_snapshot_matches(
                    mirror,
                    target_entries,
                )
            )

    def test_pre_head_snapshot_failure_restores_original_and_never_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head_before = self.fixture_case.git_fixture_command(
                fixture["mirror"], "rev-parse", "HEAD"
            )
            pin_path = fixture["metadata_root"] / "installed-version.txt"
            pin_before = pin_path.read_bytes()
            snapshot_before = archive_services.wom_kit_project_update_git_snapshot(
                fixture["mirror"]
            )

            with patch.object(
                archive_services,
                "wom_kit_project_update_target_worktree_snapshot_matches",
                return_value=False,
            ):
                result = self.approve(fixture)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "failed_before_mutation")
            self.assertTrue(result["rollback"]["succeeded"])
            self.assertEqual(
                self.fixture_case.git_fixture_command(
                    fixture["mirror"], "rev-parse", "HEAD"
                ),
                head_before,
            )
            self.assertEqual(
                archive_services.wom_kit_project_update_git_snapshot(
                    fixture["mirror"]
                ),
                snapshot_before,
            )
            self.assertEqual(pin_path.read_bytes(), pin_before)
            self.assertFalse(
                (fixture["metadata_root"] / "version-update.lock").exists()
            )

    def test_tracked_change_after_progress_start_blocks_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            tracked_path = fixture["unchanged_runtime_path"]
            external_bytes = b"EXTERNAL EDIT MUST REMAIN EXACT\n"
            head_before = self.fixture_case.git_fixture_command(
                fixture["mirror"], "rev-parse", "HEAD"
            )
            pin_path = fixture["metadata_root"] / "installed-version.txt"
            pin_before = pin_path.read_bytes()
            callback_fired = False

            def change_after_progress(
                stage: str,
                message: str,
                current: int | None,
                total: int | None,
            ) -> None:
                nonlocal callback_fired
                del current, total
                if (
                    not callback_fired
                    and stage == "checkout-release"
                    and message == "start"
                ):
                    callback_fired = True
                    tracked_path.write_bytes(external_bytes)

            result = archive_services.wom_kit_project_version_update(
                fixture["project_root"],
                target=fixture["target_tag"],
                approve=True,
                reviewed_by="human:letter-127-final-cas-test",
                affirm_external_writers_quiescent=True,
                progress_callback=change_after_progress,
            )

            self.assertTrue(callback_fired)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["blocker_codes"],
                [
                    "project_version_update_source_changed_before_materialization"
                ],
            )
            self.assertFalse(
                result["source_mirror"]["source_checkout_change_attempted"]
            )
            self.assertTrue(
                result["source_mirror"][
                    "runtime_source_rematerialization_attempted"
                ]
            )
            self.assertFalse(
                result["source_mirror"][
                    "runtime_source_rematerialization_succeeded"
                ]
            )
            self.assertEqual(tracked_path.read_bytes(), external_bytes)
            self.assertEqual(
                self.fixture_case.git_fixture_command(
                    fixture["mirror"], "rev-parse", "HEAD"
                ),
                head_before,
            )
            self.assertEqual(pin_path.read_bytes(), pin_before)
            self.assertFalse(
                (fixture["metadata_root"] / "version-update.lock").exists()
            )
            self.assertFalse((fixture["metadata_root"] / "receipts").exists())
            serialized = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(external_bytes.decode().strip(), serialized)
            self.assertNotIn(str(tracked_path), serialized)

    def test_pre_head_internal_verifier_failure_retains_lock_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            head_before = self.fixture_case.git_fixture_command(
                fixture["mirror"], "rev-parse", "HEAD"
            )
            snapshot_before = archive_services.wom_kit_project_update_git_snapshot(
                fixture["mirror"]
            )

            with patch.object(
                archive_services,
                "wom_kit_project_update_target_worktree_snapshot_matches",
                return_value=False,
            ), patch.object(
                archive_services,
                "_wom_kit_project_update_target_worktree_snapshot_matches_internal",
                return_value=False,
            ):
                result = self.approve(fixture)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "failed_rollback_incomplete")
            self.assertTrue(result["rollback"]["attempted"])
            self.assertFalse(result["rollback"]["succeeded"])
            self.assertFalse(result["rollback"]["source_restored"])
            self.assertFalse(result["rollback"]["lock_removed"])
            self.assertTrue(
                result["source_mirror"]["source_checkout_change_attempted"]
            )
            self.assertEqual(
                self.fixture_case.git_fixture_command(
                    fixture["mirror"], "rev-parse", "HEAD"
                ),
                head_before,
            )
            self.assertNotEqual(
                archive_services.wom_kit_project_update_git_snapshot(
                    fixture["mirror"]
                ),
                snapshot_before,
            )
            self.assertTrue(
                (fixture["metadata_root"] / "version-update.lock").is_file()
            )

    def test_projection_is_bounded_and_output_operation_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp))
            self.fetch_target(fixture)
            shadow_paths = [
                f"wom-kit/src/private_shadow_{index}.py"
                for index in range(3)
            ]
            (fixture["mirror"] / ".git" / "info" / "exclude").write_text(
                "\n".join(shadow_paths) + "\n",
                encoding="utf-8",
            )
            for relative_path in shadow_paths:
                fixture["mirror"].joinpath(
                    *PurePosixPath(relative_path).parts
                ).write_text("PRIVATE BOUNDED SHADOW\n", encoding="utf-8")

            with patch.object(
                archive_services,
                "WOM_KIT_PROJECT_UPDATE_MAX_MATERIALIZATION_CONFLICT_REFS",
                2,
            ):
                bounded = self.preview(fixture)
            preflight = bounded["materialization_preflight"]
            self.assertGreaterEqual(preflight["conflict_count"], 3)
            self.assertEqual(len(preflight["conflicts"]), 2)
            self.assertTrue(preflight["conflicts_truncated"])
            self.assertTrue(preflight["conflict_count_complete"])

            output_relative = (
                ".zettel-kasten/diagnostics/letter-127-preview.json"
            )
            code, stdout, stderr = self.fixture_case.run_cli_split(
                [
                    "project-version-update",
                    str(fixture["project_root"]),
                    "--target",
                    fixture["target_tag"],
                    "--dry-run",
                    "--output",
                    output_relative,
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1, stdout + stderr)
            output_path = fixture["project_root"].joinpath(
                *PurePosixPath(output_relative).parts
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            operation = payload["cli_output_artifact"]["operation"]
            status = operation_control.inspect_operation(
                fixture["project_root"],
                operation["operation_ref"],
            )
            self.assertTrue(status["ok"], status)
            self.assertEqual(status["state"], "completed_result_available")
            serialized = stdout + stderr + json.dumps(payload)
            for value in shadow_paths:
                self.assertNotIn(value, serialized)
            self.assertNotRegex(
                serialized,
                re.escape(str(fixture["project_root"])),
            )


if __name__ == "__main__":
    unittest.main()
