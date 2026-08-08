from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import legacy_coordination_cleanup as cleanup_module
from wom_kit.legacy_coordination_cleanup import (
    legacy_coordination_cleanup,
    legacy_coordination_cleanup_plan,
)


MAX_FILES = 100
MAX_BYTES = 1024 * 1024


class LegacyCoordinationCleanupTests(unittest.TestCase):
    def make_workspace(self, root: Path, *, target: bool = True) -> Path:
        workspace = root / "workspace"
        archive = workspace / "archive"
        archive.mkdir(parents=True)
        (archive / "archive.yml").write_text(
            "archive_id: archive:personal:test\nname: Test\ntype: personal\n",
            encoding="utf-8",
        )
        (archive / "archive-identity.yml").write_text(
            "identity:\n  archive_id: archive:personal:test\n"
            "  identity_id: identity:archive:personal:test\n",
            encoding="utf-8",
        )
        if target:
            (workspace / ".mow-harness").mkdir()
        return workspace

    def plan(self, workspace: Path, **overrides: int) -> dict[str, object]:
        return legacy_coordination_cleanup_plan(
            workspace,
            max_files=overrides.get("max_files", MAX_FILES),
            max_bytes=overrides.get("max_bytes", MAX_BYTES),
        )

    def apply(
        self,
        workspace: Path,
        plan: dict[str, object],
        **overrides: object,
    ) -> dict[str, object]:
        arguments: dict[str, object] = {
            "dry_run": False,
            "approve": True,
            "reviewed_by": "person:test-owner",
            "expected_plan_sha256": plan["plan_sha256"],
            "affirm_workspace_owner_authorized": True,
            "affirm_external_writers_quiescent": True,
            "affirm_retired_state_disposable": True,
            "affirm_backups_and_receipts_disposable": False,
            "max_files": MAX_FILES,
            "max_bytes": MAX_BYTES,
        }
        arguments.update(overrides)
        return legacy_coordination_cleanup(workspace, **arguments)

    def test_absent_target_is_safe_idempotent_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp), target=False)
            plan = self.plan(workspace)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["status"], "target_absent")
            result = self.apply(workspace, plan)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "target_absent")
            self.assertFalse(result["changed"])

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_valid_cleanup_preserves_everything_outside_exact_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target = workspace / ".mow-harness"
            (target / "source" / "nested").mkdir(parents=True)
            (target / "source" / "nested" / "state.bin").write_bytes(b"legacy-state")
            (target / "installed-version.txt").write_bytes(b"1.2.3\n")
            collab = workspace / "collab"
            collab.mkdir()
            collab_file = collab / "STATE.md"
            collab_file.write_bytes(b"outside-collab-must-survive")
            outside = workspace / "ordinary.txt"
            outside.write_bytes(b"ordinary-must-survive")
            before = {
                collab_file: collab_file.read_bytes(),
                outside: outside.read_bytes(),
                workspace / "archive" / "archive.yml": (
                    workspace / "archive" / "archive.yml"
                ).read_bytes(),
            }

            plan = self.plan(workspace)
            self.assertTrue(plan["safe_to_cleanup"], plan)
            self.assertRegex(str(plan["plan_sha256"]), r"^[0-9a-f]{64}$")
            result = self.apply(workspace, plan)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "cleanup_completed")
            self.assertFalse(target.exists())
            self.assertEqual(
                result["residue"],
                {
                    "target_present": False,
                    "tombstone_present": False,
                    "lock_present": False,
                },
            )
            for path, raw in before.items():
                self.assertEqual(path.read_bytes(), raw)
            leftovers = [
                child.name
                for child in workspace.iterdir()
                if "legacy-coordination-cleanup" in child.name
            ]
            self.assertEqual(leftovers, [])

    def test_dry_run_is_read_only_and_rejects_apply_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"unchanged")
            before = target_file.read_bytes()
            result = legacy_coordination_cleanup(
                workspace,
                dry_run=True,
                approve=False,
                reviewed_by=None,
                expected_plan_sha256=None,
                affirm_workspace_owner_authorized=False,
                affirm_external_writers_quiescent=False,
                affirm_retired_state_disposable=False,
                affirm_backups_and_receipts_disposable=False,
                max_files=MAX_FILES,
                max_bytes=MAX_BYTES,
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "dry_run_ready")
            self.assertEqual(target_file.read_bytes(), before)

            rejected = legacy_coordination_cleanup(
                workspace,
                dry_run=True,
                approve=True,
                reviewed_by=None,
                expected_plan_sha256=None,
                affirm_workspace_owner_authorized=False,
                affirm_external_writers_quiescent=False,
                affirm_retired_state_disposable=False,
                affirm_backups_and_receipts_disposable=False,
                max_files=MAX_FILES,
                max_bytes=MAX_BYTES,
            )
            self.assertFalse(rejected["ok"])
            self.assertIn("approval_fields_only_valid_for_apply", rejected["blockers"])
            self.assertEqual(target_file.read_bytes(), before)

    def test_preview_discloses_when_approval_platform_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            with patch.object(
                cleanup_module,
                "LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED",
                False,
            ):
                plan = self.plan(workspace)

            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["status"], "ready")
            self.assertFalse(plan["approval_platform_supported"])
            self.assertEqual(plan["approval_supported_platforms"], ["windows"])
            self.assertFalse(plan["safe_to_cleanup"])

    def test_stale_digest_and_each_required_gate_block_without_mutation(self) -> None:
        cases = {
            "approve": False,
            "reviewed_by": "unsafe actor with spaces",
            "expected_plan_sha256": "0" * 64,
            "affirm_workspace_owner_authorized": False,
            "affirm_external_writers_quiescent": False,
            "affirm_retired_state_disposable": False,
        }
        for key, value in cases.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                workspace = self.make_workspace(Path(tmp))
                target_file = workspace / ".mow-harness" / "update.log"
                target_file.write_bytes(b"must-remain")
                plan = self.plan(workspace)
                result = self.apply(workspace, plan, **{key: value})
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(target_file.read_bytes(), b"must-remain")

    def test_unsupported_apply_platform_blocks_before_lock_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"must-remain")
            plan = self.plan(workspace)

            with patch.object(
                cleanup_module,
                "LEGACY_COORDINATION_CLEANUP_APPLY_SUPPORTED",
                False,
            ), patch.object(
                cleanup_module,
                "_acquire_lock",
                side_effect=AssertionError("lock creation must not run"),
            ):
                result = self.apply(workspace, plan)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertIn(
                "cleanup_apply_platform_unsupported",
                result["blockers"],
            )
            self.assertEqual(target_file.read_bytes(), b"must-remain")
            self.assertFalse(
                (workspace / cleanup_module.LOCK_NAME).exists()
            )

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_preexisting_lock_race_is_never_unlinked_without_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"must-remain")
            plan = self.plan(workspace)
            lock = workspace / cleanup_module.LOCK_NAME

            def foreign_lock_wins(_workspace: object, _path: Path):
                lock.write_bytes(b"FOREIGN_LOCK_SENTINEL")
                raise FileExistsError("foreign lock won the race")

            with patch.object(
                cleanup_module,
                "_acquire_lock",
                side_effect=foreign_lock_wins,
            ):
                result = self.apply(workspace, plan)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("cleanup_lock_occupied_or_unsafe", result["blockers"])
            self.assertEqual(lock.read_bytes(), b"FOREIGN_LOCK_SENTINEL")
            self.assertEqual(target_file.read_bytes(), b"must-remain")
            self.assertTrue(result["residue"]["lock_present"])

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_failed_lock_initialization_leaves_uncertain_entry_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            lock = workspace / cleanup_module.LOCK_NAME

            with cleanup_module.bind_workspace_root(
                workspace.resolve(strict=True)
            ) as bound_root:
                with patch.object(cleanup_module.os, "write", return_value=0):
                    with self.assertRaises(OSError):
                        cleanup_module._acquire_lock(bound_root, lock)

            self.assertTrue(lock.is_file())
            self.assertEqual(lock.read_bytes(), b"")

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_owned_lock_replacement_is_not_ignored_or_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            lock = workspace / cleanup_module.LOCK_NAME
            escaped = workspace / "escaped-owned-lock"
            with cleanup_module.bind_workspace_root(
                workspace.resolve(strict=True)
            ) as bound_root:
                descriptor, record = cleanup_module._acquire_lock(
                    bound_root,
                    lock,
                )
                os.close(descriptor)
                lock.replace(escaped)
                lock.write_bytes(b"FOREIGN_LOCK_SENTINEL")

                _target, blockers, _present = (
                    cleanup_module._workspace_target_name_state(
                        workspace.resolve(strict=True),
                        owned_lock_record=record,
                    )
                )

            self.assertIn("cleanup_lock_present", blockers)
            self.assertEqual(lock.read_bytes(), b"FOREIGN_LOCK_SENTINEL")
            self.assertTrue(escaped.is_file())

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_lock_release_never_deletes_a_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            lock = workspace / cleanup_module.LOCK_NAME
            escaped = workspace / "escaped-owned-lock"
            real_delete = cleanup_module.delete_exact_approved_file

            def replace_before_bound_delete(
                root: Path,
                path: Path,
                expected: dict[str, object],
            ) -> None:
                path.replace(escaped)
                path.write_bytes(b"FOREIGN_LOCK_SENTINEL")
                real_delete(root, path, expected)

            with cleanup_module.bind_workspace_root(
                workspace.resolve(strict=True)
            ) as bound_root:
                descriptor, record = cleanup_module._acquire_lock(
                    bound_root,
                    lock,
                )
                with patch.object(
                    cleanup_module,
                    "delete_exact_approved_file",
                    side_effect=replace_before_bound_delete,
                ):
                    released = cleanup_module._release_lock(
                        workspace.resolve(strict=True),
                        lock,
                        descriptor,
                        record,
                    )

            self.assertFalse(released)
            self.assertEqual(lock.read_bytes(), b"FOREIGN_LOCK_SENTINEL")
            self.assertTrue(escaped.is_file())

    def test_prior_tombstone_blocks_new_or_absent_target_without_false_success(self) -> None:
        for target_present in (False, True):
            with self.subTest(target_present=target_present), tempfile.TemporaryDirectory() as tmp:
                workspace = self.make_workspace(Path(tmp), target=target_present)
                tombstone = workspace / f"{cleanup_module.TOMBSTONE_PREFIX}old"
                tombstone.mkdir()
                (tombstone / "private.bin").write_bytes(b"partial-state")

                plan = self.plan(workspace)

                self.assertFalse(plan["ok"], plan)
                self.assertEqual(plan["status"], "blocked")
                self.assertIn(
                    "prior_cleanup_tombstone_present",
                    plan["blockers"],
                )
                self.assertEqual(
                    (tombstone / "private.bin").read_bytes(),
                    b"partial-state",
                )

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_backups_and_receipts_require_extra_affirmation(self) -> None:
        for evidence_name in ("backups", "receipts"):
            with self.subTest(evidence=evidence_name), tempfile.TemporaryDirectory() as tmp:
                workspace = self.make_workspace(Path(tmp))
                evidence = workspace / ".mow-harness" / evidence_name
                evidence.mkdir()
                (evidence / "evidence.bin").write_bytes(b"reviewed-evidence")
                plan = self.plan(workspace)
                self.assertTrue(plan["summary"]["backups_or_receipts_present"])
                blocked = self.apply(workspace, plan)
                self.assertFalse(blocked["ok"])
                self.assertIn(
                    "backups_and_receipts_disposable_affirmation_required",
                    blocked["blockers"],
                )
                completed = self.apply(
                    workspace,
                    plan,
                    affirm_backups_and_receipts_disposable=True,
                )
                self.assertTrue(completed["ok"], completed)

    def test_collab_unknown_and_case_variants_fail_closed(self) -> None:
        cases = (
            ("collab", "collab_present_in_target"),
            ("unknown", "unknown_top_level_entry"),
            ("Source", "top_level_name_case_mismatch"),
        )
        for name, blocker in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                workspace = self.make_workspace(Path(tmp))
                candidate = workspace / ".mow-harness" / name
                candidate.mkdir()
                private_file = candidate / "private.bin"
                private_file.write_bytes(b"must-not-be-read-in-output")
                listed_paths: list[Path] = []
                read_paths: list[Path] = []
                original_list = cleanup_module._list_directory_bound
                original_read = cleanup_module._stream_regular_file_bound

                def track_list(*args: object, **kwargs: object):
                    path = args[1]
                    if isinstance(path, Path):
                        listed_paths.append(path)
                    return original_list(*args, **kwargs)

                def track_read(*args: object, **kwargs: object):
                    path = args[1]
                    if isinstance(path, Path):
                        read_paths.append(path)
                    return original_read(*args, **kwargs)

                with patch.object(
                    cleanup_module,
                    "_list_directory_bound",
                    side_effect=track_list,
                ), patch.object(
                    cleanup_module,
                    "_stream_regular_file_bound",
                    side_effect=track_read,
                ):
                    plan = self.plan(workspace)
                self.assertFalse(plan["ok"])
                self.assertIn(blocker, plan["blockers"])
                self.assertTrue(candidate.exists())
                self.assertNotIn(candidate, listed_paths)
                self.assertNotIn(private_file, read_paths)

    def test_target_case_variant_blocks_instead_of_becoming_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp), target=False)
            (workspace / ".MOW-HARNESS").mkdir()
            plan = self.plan(workspace)
            self.assertFalse(plan["ok"])
            self.assertIn("target_name_case_mismatch", plan["blockers"])

    def test_relative_drive_and_profile_roots_are_rejected_before_cleanup(self) -> None:
        relative = self.plan(Path("relative-workspace"))
        self.assertFalse(relative["ok"], relative)
        self.assertIn("workspace_root_must_be_absolute", relative["blockers"])

        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            direct_target = self.plan(workspace / ".mow-harness")
            self.assertFalse(direct_target["ok"], direct_target)
            self.assertIn(
                "workspace_root_cannot_be_legacy_target",
                direct_target["blockers"],
            )
            with patch.object(
                cleanup_module,
                "_account_profile_roots",
                return_value=(
                    {
                        cleanup_module._normalized_path_key(
                            workspace.resolve(strict=True)
                        )
                    },
                    True,
                ),
            ):
                protected = self.plan(workspace)
            self.assertFalse(protected["ok"], protected)
            self.assertIn(
                "workspace_root_broad_or_protected",
                protected["blockers"],
            )

        drive_or_filesystem_root = Path(Path.cwd().anchor)
        broad = self.plan(drive_or_filesystem_root)
        self.assertFalse(broad["ok"], broad)
        self.assertIn("workspace_root_broad_or_protected", broad["blockers"])

    def test_ancestor_link_or_junction_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            actual_parent = temp_root / "actual"
            workspace = self.make_workspace(actual_parent)
            alias = temp_root / "alias"
            if os.name == "nt":
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(alias), str(actual_parent)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if created.returncode != 0:
                    self.skipTest("junction creation unavailable")
            else:
                os.symlink(actual_parent, alias, target_is_directory=True)

            plan = self.plan(alias / "workspace")

            self.assertFalse(plan["ok"], plan)
            self.assertIn(
                "workspace_root_path_component_unsafe",
                plan["blockers"],
            )
            self.assertTrue((workspace / ".mow-harness").exists())

    def test_real_hardlink_with_link_count_above_one_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            source = workspace / "outside.bin"
            source.write_bytes(b"outside")
            linked = workspace / ".mow-harness" / "update.log"
            os.link(source, linked)
            plan = self.plan(workspace)
            self.assertFalse(plan["ok"])
            self.assertIn("hardlink_entry", plan["blockers"])
            self.assertEqual(source.read_bytes(), b"outside")

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-only")
    def test_named_alternate_data_stream_is_blocked_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"visible")
            stream_path = Path(f"{target_file}:private")
            try:
                stream_path.write_bytes(b"hidden-private-state")
            except OSError as exc:
                self.skipTest(f"named stream creation unavailable: {exc}")

            plan = self.plan(workspace)
            self.assertFalse(plan["ok"], plan)
            self.assertIn("alternate_data_stream_entry", plan["blockers"])
            result = self.apply(workspace, plan)
            self.assertFalse(result["ok"], result)
            self.assertEqual(target_file.read_bytes(), b"visible")
            self.assertEqual(stream_path.read_bytes(), b"hidden-private-state")

    def test_symlink_or_reparse_is_blocked_when_creation_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            outside = workspace / "outside-dir"
            outside.mkdir()
            try:
                os.symlink(
                    outside,
                    workspace / ".mow-harness" / "source",
                    target_is_directory=True,
                )
            except (OSError, NotImplementedError) as exc:
                if os.name != "nt":
                    self.skipTest(f"symlink creation unavailable: {exc}")
                junction = subprocess.run(
                    [
                        "cmd",
                        "/c",
                        "mklink",
                        "/J",
                        str(workspace / ".mow-harness" / "source"),
                        str(outside),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if junction.returncode != 0:
                    self.skipTest(
                        f"symlink and junction creation unavailable: {exc}"
                    )
            plan = self.plan(workspace)
            self.assertFalse(plan["ok"])
            self.assertIn("symlink_or_reparse_entry", plan["blockers"])

    def test_unreadable_file_fails_closed_without_private_error_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"private-unreadable-sentinel")
            original = cleanup_module._stream_regular_file_bound

            def refuse_target(*args: object, **kwargs: object):
                path = args[1]
                if isinstance(path, Path) and path.name == "update.log":
                    raise PermissionError("PRIVATE_UNREADABLE_DETAIL")
                return original(*args, **kwargs)

            with patch.object(
                cleanup_module,
                "_stream_regular_file_bound",
                side_effect=refuse_target,
            ):
                plan = self.plan(workspace)
            self.assertFalse(plan["ok"])
            self.assertIn("unsafe_modified_or_unreadable_file", plan["blockers"])
            rendered = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn("update.log", rendered)
            self.assertNotIn("PRIVATE_UNREADABLE_DETAIL", rendered)

    def test_git_tracked_target_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"tracked")
            subprocess.run(
                ["git", "init", "-q", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(workspace), "add", "-f", ".mow-harness/update.log"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            plan = self.plan(workspace)
            self.assertFalse(plan["ok"])
            self.assertIn("git_tracked_target", plan["blockers"])

    def test_nested_repository_inside_target_is_blocked_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            nested_repository = workspace / ".mow-harness" / "source"
            nested_repository.mkdir()
            tracked = nested_repository / "keep.txt"
            tracked.write_bytes(b"nested-tracked-state")
            subprocess.run(
                ["git", "init", "-q", str(nested_repository)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(nested_repository), "add", "keep.txt"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            plan = self.plan(workspace)

            self.assertFalse(plan["ok"], plan)
            self.assertIn("nested_git_repository_present", plan["blockers"])
            self.assertEqual(tracked.read_bytes(), b"nested-tracked-state")

    def test_every_ancestor_repository_index_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            subprocess.run(
                ["git", "init", "-q", str(outer)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            workspace = self.make_workspace(outer)
            tracked = workspace / ".mow-harness" / "update.log"
            tracked.write_bytes(b"outer-index-tracked")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(outer),
                    "add",
                    "-f",
                    "workspace/.mow-harness/update.log",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # The nearest repository is intentionally untracked.  A check that
            # asks only this inner index would miss the outer tracked file.
            subprocess.run(
                ["git", "init", "-q", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            plan = self.plan(workspace)

            self.assertFalse(plan["ok"], plan)
            self.assertIn("git_tracked_target", plan["blockers"])
            self.assertEqual(tracked.read_bytes(), b"outer-index-tracked")

    def test_inherited_git_environment_cannot_redirect_tracking_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            workspace = self.make_workspace(temp_root)
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"tracked")
            unrelated = temp_root / "unrelated"
            subprocess.run(
                ["git", "init", "-q", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "init", "-q", str(unrelated)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(workspace), "add", "-f", ".mow-harness/update.log"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            with patch.dict(
                os.environ,
                {"GIT_DIR": str(unrelated / ".git")},
                clear=False,
            ):
                plan = self.plan(workspace)

            self.assertFalse(plan["ok"], plan)
            self.assertIn("git_tracking_environment_unsafe", plan["blockers"])
            self.assertEqual(target_file.read_bytes(), b"tracked")

    def test_broken_git_repository_state_blocks_instead_of_failing_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"tracked")
            subprocess.run(
                ["git", "init", "-q", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(workspace), "add", "-f", ".mow-harness/update.log"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            (workspace / ".git" / "config").write_bytes(b"[broken\n")

            plan = self.plan(workspace)

            self.assertFalse(plan["ok"], plan)
            self.assertIn("git_tracking_check_failed", plan["blockers"])
            self.assertEqual(target_file.read_bytes(), b"tracked")

    def test_scan_file_and_byte_bounds_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            source = workspace / ".mow-harness" / "source"
            source.mkdir()
            (source / "one.bin").write_bytes(b"1")
            (source / "two.bin").write_bytes(b"2")
            file_plan = self.plan(workspace, max_files=1)
            self.assertFalse(file_plan["ok"])
            self.assertIn("max_files_exceeded", file_plan["blockers"])
            byte_plan = self.plan(workspace, max_bytes=1)
            self.assertFalse(byte_plan["ok"])
            self.assertIn("max_bytes_exceeded", byte_plan["blockers"])

    def test_cross_mount_boundary_maps_to_explicit_plan_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            original = cleanup_module._list_directory_bound

            def refuse_target_mount(
                root: Path,
                directory: Path,
                **kwargs: object,
            ):
                if directory.name == cleanup_module.TARGET_NAME:
                    raise cleanup_module._MountBoundaryError(
                        "mount_boundary_entry"
                    )
                return original(root, directory, **kwargs)

            with patch.object(
                cleanup_module,
                "_list_directory_bound",
                side_effect=refuse_target_mount,
            ):
                plan = self.plan(workspace)

            self.assertFalse(plan["ok"], plan)
            self.assertIn("cross_mount_entry", plan["blockers"])

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_full_replan_drift_blocks_before_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"before")
            approved = self.plan(workspace)
            original = cleanup_module._build_private_plan
            call_count = 0

            def drift_on_locked_replan(*args: object, **kwargs: object):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    target_file.write_bytes(b"after")
                return original(*args, **kwargs)

            with patch.object(
                cleanup_module,
                "_build_private_plan",
                side_effect=drift_on_locked_replan,
            ):
                result = self.apply(workspace, approved)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("full_replan_drift", result["blockers"])
            self.assertEqual(target_file.read_bytes(), b"after")

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_git_tracking_change_after_locked_replan_blocks_before_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"becomes-tracked")
            subprocess.run(
                ["git", "init", "-q", str(workspace)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            approved = self.plan(workspace)
            self.assertTrue(approved["ok"], approved)
            original = cleanup_module._build_private_plan
            call_count = 0

            def track_after_locked_replan(*args: object, **kwargs: object):
                nonlocal call_count
                call_count += 1
                result = original(*args, **kwargs)
                if call_count == 2:
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(workspace),
                            "add",
                            "-f",
                            ".mow-harness/update.log",
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                return result

            with patch.object(
                cleanup_module,
                "_build_private_plan",
                side_effect=track_after_locked_replan,
            ):
                result = self.apply(workspace, approved)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("git_tracked_target", result["blockers"])
            self.assertEqual(target_file.read_bytes(), b"becomes-tracked")

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_partial_failure_is_non_ok_and_echoes_no_private_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            private_name = "very-private-filename.txt"
            private_value = "PRIVATE_SENTINEL_VALUE"
            target_file = workspace / ".mow-harness" / "source" / private_name
            target_file.parent.mkdir()
            target_file.write_text(private_value, encoding="utf-8")
            plan = self.plan(workspace)
            with patch.object(
                cleanup_module,
                "_remove_verified_empty_directory",
                side_effect=OSError("private failure detail"),
            ):
                result = self.apply(workspace, plan)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "partial_cleanup_pending")
            self.assertTrue(result["changed"])
            self.assertIsNone(result["remaining_tombstone_id"])
            rendered = json.dumps(result, ensure_ascii=False)
            self.assertNotIn(str(workspace), rendered)
            self.assertNotIn(private_name, rendered)
            self.assertNotIn(private_value, rendered)
            self.assertNotIn("private failure detail", rendered)
            self.assertTrue((workspace / ".mow-harness").is_dir())
            self.assertFalse(target_file.exists())
            tombstones = [
                child
                for child in workspace.iterdir()
                if child.name.startswith(".wom-legacy-coordination-cleanup-tombstone-")
            ]
            self.assertEqual(tombstones, [])

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_first_delete_uncertainty_is_reported_as_possible_partial_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"uncertain-but-preserved-by-test-double")
            plan = self.plan(workspace)

            with patch.object(
                cleanup_module,
                "_unlink_verified_file",
                side_effect=OSError("post-disposition state unknown"),
            ):
                result = self.apply(workspace, plan)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "partial_cleanup_pending")
            self.assertTrue(result["changed"])
            self.assertEqual(
                target_file.read_bytes(),
                b"uncertain-but-preserved-by-test-double",
            )

    @unittest.skipUnless(os.name == "nt", "approved apply is Windows-only")
    def test_ctrl_c_during_delete_returns_partial_result_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            target_file = workspace / ".mow-harness" / "update.log"
            target_file.write_bytes(b"interrupt-test-sentinel")
            outside_file = workspace / "outside-interrupt-sentinel.txt"
            outside_file.write_bytes(b"must-survive")
            plan = self.plan(workspace)
            real_unlink = cleanup_module._unlink_verified_file

            def delete_then_interrupt(*args: object) -> None:
                real_unlink(*args)
                raise KeyboardInterrupt

            with patch.object(
                cleanup_module,
                "_unlink_verified_file",
                side_effect=delete_then_interrupt,
            ):
                result = self.apply(workspace, plan)

            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "partial_cleanup_pending")
            self.assertTrue(result["changed"])
            self.assertIn("cleanup_execution_interrupted", result["blockers"])
            self.assertFalse((workspace / cleanup_module.LOCK_NAME).exists())
            self.assertFalse(target_file.exists())
            self.assertTrue(result["residue"]["target_present"])
            self.assertFalse(result["residue"]["lock_present"])
            self.assertEqual(outside_file.read_bytes(), b"must-survive")

    def test_public_plan_does_not_echo_paths_names_or_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.make_workspace(Path(tmp))
            private_name = "secret-account-name.txt"
            private_value = "PRIVATE_TOKEN_SENTINEL"
            source = workspace / ".mow-harness" / "source"
            source.mkdir()
            (source / private_name).write_text(private_value, encoding="utf-8")
            plan = self.plan(workspace)
            rendered = json.dumps(plan, ensure_ascii=False)
            self.assertNotIn(str(workspace), rendered)
            self.assertNotIn(private_name, rendered)
            self.assertNotIn(private_value, rendered)
            self.assertEqual(
                plan["privacy"],
                {
                    "absolute_paths_echoed": False,
                    "filenames_echoed": False,
                    "file_contents_echoed": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
