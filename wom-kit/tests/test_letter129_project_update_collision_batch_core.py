from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_services

from . import test_cli as _test_cli


class Letter129ProjectUpdateCollisionBatchCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_case = _test_cli.ArchiveCliTests("runTest")
        self.fixture_case.setUp()

    def tearDown(self) -> None:
        self.fixture_case.doCleanups()

    def runtime_shadow_fixture(
        self,
        root: Path,
        *,
        bytecode_count: int,
        include_other_shadow: bool = False,
        hardlink_pair: bool = False,
    ) -> tuple[dict[str, object], list[str]]:
        fixture = self.fixture_case.create_project_version_update_fixture(root)
        mirror = fixture["mirror"]
        target_tag = str(fixture["target_tag"])
        self.fixture_case.git_fixture_command(
            mirror,
            "fetch",
            "--quiet",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
            f"+refs/tags/{target_tag}:refs/tags/{target_tag}",
        )
        runtime_root = mirror / "wom-kit" / "src" / "wom_kit"
        cache = runtime_root / "__pycache__"
        cache.mkdir()
        private_markers: list[str] = []
        if hardlink_pair:
            first = cache / "PRIVATE_LETTER129_A.cpython-312.pyc"
            second = cache / "PRIVATE_LETTER129_B.cpython-312.pyc"
            first.write_bytes(b"PRIVATE LETTER129 HARDLINK BYTECODE\n")
            second.hardlink_to(first)
            private_markers.extend([first.name, second.name])
        else:
            for index in range(bytecode_count):
                name = f"PRIVATE_LETTER129_{index:02d}.cpython-312.pyc"
                (cache / name).write_bytes(
                    f"PRIVATE LETTER129 BYTECODE {index}\n".encode("ascii")
                )
                private_markers.append(name)
        exclude_lines = ["wom-kit/src/wom_kit/__pycache__/\n"]
        if include_other_shadow:
            other_name = "PRIVATE_LETTER129_RUNTIME_SHADOW.py"
            (runtime_root / other_name).write_text(
                "PRIVATE LETTER129 NON-BYTECODE SHADOW\n",
                encoding="utf-8",
            )
            exclude_lines.append(f"wom-kit/src/wom_kit/{other_name}\n")
            private_markers.append(other_name)
        (mirror / ".git" / "info" / "exclude").write_text(
            "".join(exclude_lines),
            encoding="utf-8",
        )
        return fixture, private_markers

    @staticmethod
    def update_preview(fixture: dict[str, object]) -> dict[str, object]:
        return archive_services._wom_kit_project_version_update_legacy_core(
            fixture["project_root"],
            target=str(fixture["target_tag"]),
            dry_run=True,
        )

    @staticmethod
    def inspect_all(
        fixture: dict[str, object],
        preview: dict[str, object],
    ) -> dict[str, object]:
        preflight = preview["materialization_preflight"]
        return archive_services.wom_kit_project_version_update_collision_inspect_batch(
            fixture["project_root"],
            target=str(fixture["target_tag"]),
            expected_plan_sha256=preflight[
                "materialization_plan_sha256"
            ],
        )

    def test_twenty_four_bytecode_files_and_cache_directory_route_as_one_set(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, private_markers = self.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=24,
            )
            preview = self.update_preview(fixture)
            preflight = preview["materialization_preflight"]
            self.assertEqual(preflight["conflict_count"], 25, preview)
            self.assertTrue(preflight["conflict_count_complete"])
            self.assertFalse(preflight["conflicts_truncated"])
            self.assertTrue(
                all(
                    item["reason_codes"]
                    == ["ignored_or_untracked_runtime_source_shadow"]
                    for item in preflight["conflicts"]
                )
            )

            original_planner = (
                archive_services._wom_kit_project_update_materialization_plan_details_internal
            )
            original_git_batch = (
                archive_services._wom_kit_project_update_collision_git_eligibility_batch
            )
            with patch.object(
                archive_services,
                "_wom_kit_project_update_materialization_plan_details_internal",
                wraps=original_planner,
            ) as planner, patch.object(
                archive_services,
                "_wom_kit_project_update_collision_git_eligibility_batch",
                wraps=original_git_batch,
            ) as git_batch:
                result, private = (
                    archive_services._wom_kit_project_version_update_collision_inspect_batch_core(
                        fixture["project_root"],
                        target=str(fixture["target_tag"]),
                        expected_plan_sha256=preflight[
                            "materialization_plan_sha256"
                        ],
                        runner=(
                            self.fixture_case
                            .trusted_project_update_git_runner()
                        ),
                    )
                )

            self.assertEqual(planner.call_count, 1)
            self.assertEqual(git_batch.call_count, 1)
            self.assertTrue(result["ok"], result)
            self.assertEqual(
                result["schema"],
                "wom-kit/project-version-update-collision/v0.2",
            )
            self.assertEqual(result["action"], "inspect-all")
            self.assertTrue(result["project_bytecode_repair_route_eligible"])
            remediation = result["remediation"]
            self.assertTrue(remediation["route_eligible"])
            self.assertTrue(remediation["exact_collision_set_covered"])
            self.assertEqual(remediation["route"], "project_bytecode_repair")
            self.assertEqual(
                remediation["next_action_hint"],
                "project_bytecode_repair_plan",
            )
            self.assertEqual(remediation["derived_bytecode_file_count"], 24)
            self.assertEqual(
                remediation["bytecode_cache_directory_count"],
                1,
            )
            self.assertEqual(remediation["unsupported_entry_count"], 0)
            self.assertFalse(remediation["repair_performed"])
            self.assertFalse(result["write_boundary"]["writes"])
            self.assertFalse(result["write_boundary"]["deletes"])
            self.assertFalse(result["write_boundary"]["overwrites"])
            self.assertEqual(
                result["summary"]["entry_kind_counts"],
                {"plain_directory": 1, "regular_file": 24},
            )
            self.assertEqual(
                result["summary"]["runtime_shadow_kind_counts"],
                {
                    "bytecode_cache_directory": 1,
                    "derived_bytecode_file": 24,
                },
            )
            self.assertEqual(len(private["derived_bytecode_file_paths"]), 24)
            self.assertEqual(
                len(private["bytecode_cache_directory_paths"]),
                1,
            )
            self.assertTrue(
                all(
                    entry["ignored_verified"]
                    and entry["index_untracked_verified"]
                    and entry["current_tree_untracked_verified"]
                    and entry["authority_matches_plan"]
                    for entry in result["entries"]
                )
            )
            rendered = json.dumps(result, ensure_ascii=False)
            for marker in private_markers:
                self.assertNotIn(marker, rendered)
            self.assertNotIn(str(fixture["project_root"]), rendered)
            self.assertFalse(result["privacy_guards"]["private_bytes_read"])

            directory_entry = next(
                entry
                for entry in result["entries"]
                if entry["entry_kind"] == "plain_directory"
            )
            single = archive_services.wom_kit_project_version_update_collision(
                fixture["project_root"],
                target=str(fixture["target_tag"]),
                entry_ref=directory_entry["entry_ref"],
                expected_plan_sha256=preflight[
                    "materialization_plan_sha256"
                ],
                action="inspect",
                dry_run=True,
            )
            self.assertTrue(single["ok"], single)
            self.assertEqual(single["entry"]["entry_kind"], "plain_directory")
            self.assertEqual(
                single["entry"]["runtime_shadow_kind"],
                "bytecode_cache_directory",
            )
            self.assertTrue(
                single["entry"][
                    "eligible_for_project_bytecode_repair_route"
                ]
            )
            self.assertFalse(
                single["entry"]["eligible_for_preserve_relocate"]
            )

    def test_mixed_runtime_shadow_is_inspected_but_remediation_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, private_markers = self.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=2,
                include_other_shadow=True,
            )
            preview = self.update_preview(fixture)
            result = self.inspect_all(fixture, preview)

            self.assertTrue(result["ok"], result)
            self.assertEqual(
                result["status"],
                "inspected_remediation_unavailable",
            )
            self.assertFalse(result["remediation_available"])
            self.assertFalse(result["project_bytecode_repair_route_eligible"])
            self.assertIsNone(result["remediation"]["route"])
            self.assertEqual(
                result["remediation"]["blocker_codes"],
                ["project_update_collision_remediation_unavailable"],
            )
            unsupported = [
                entry
                for entry in result["entries"]
                if entry["runtime_shadow_kind"] == "other_runtime_shadow"
            ]
            self.assertEqual(len(unsupported), 1)
            self.assertEqual(
                unsupported[0]["remediation_blocker_codes"],
                ["project_update_collision_remediation_unavailable"],
            )
            self.assertFalse(result["write_boundary"]["writes"])
            rendered = json.dumps(result, ensure_ascii=False)
            for marker in private_markers:
                self.assertNotIn(marker, rendered)

    def test_hardlinked_bytecode_never_routes_to_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, private_markers = self.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=0,
                hardlink_pair=True,
            )
            preview = self.update_preview(fixture)
            result = self.inspect_all(fixture, preview)

            self.assertTrue(result["ok"], result)
            bytecode_entries = [
                entry
                for entry in result["entries"]
                if entry["runtime_shadow_kind"] == "derived_bytecode_file"
            ]
            self.assertEqual(len(bytecode_entries), 2)
            self.assertTrue(
                all(not entry["single_link_verified"] for entry in bytecode_entries)
            )
            self.assertTrue(
                all(
                    not entry[
                        "eligible_for_project_bytecode_repair_route"
                    ]
                    for entry in bytecode_entries
                )
            )
            self.assertFalse(result["project_bytecode_repair_route_eligible"])
            self.assertFalse(result["write_boundary"]["deletes"])
            rendered = json.dumps(result, ensure_ascii=False)
            for marker in private_markers:
                self.assertNotIn(marker, rendered)

    def test_partial_ref_set_and_plan_drift_do_not_authorize_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _ = self.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=2,
            )
            preview = self.update_preview(fixture)
            preflight = preview["materialization_preflight"]
            refs = [item["entry_ref"] for item in preflight["conflicts"]]
            partial = archive_services.wom_kit_project_version_update_collision_inspect_batch(
                fixture["project_root"],
                target=str(fixture["target_tag"]),
                entry_refs=refs[:-1],
                expected_plan_sha256=preflight[
                    "materialization_plan_sha256"
                ],
            )
            self.assertFalse(partial["ok"], partial)
            self.assertIn(
                "project_update_collision_batch_entry_set_incomplete",
                partial["blocker_codes"],
            )
            self.assertFalse(
                partial["remediation"]["exact_collision_set_covered"]
            )
            self.assertFalse(partial["project_bytecode_repair_route_eligible"])

            stale = archive_services.wom_kit_project_version_update_collision_inspect_batch(
                fixture["project_root"],
                target=str(fixture["target_tag"]),
                expected_plan_sha256="sha256:" + "0" * 64,
            )
            self.assertFalse(stale["ok"])
            self.assertEqual(stale["status"], "blocked")
            self.assertIn(
                "project_update_collision_plan_drifted",
                stale["blocker_codes"],
            )
            self.assertEqual(stale["entries"], [])
            self.assertFalse(stale["write_boundary"]["writes"])

    def test_internal_revalidation_accepts_only_the_callers_owned_update_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture, _ = self.runtime_shadow_fixture(
                Path(tmp),
                bytecode_count=2,
            )
            preview = self.update_preview(fixture)
            preflight = preview["materialization_preflight"]
            project_root = fixture["project_root"]
            metadata_root = fixture["metadata_root"]
            lock_path = (
                project_root
                / archive_services.WOM_KIT_PROJECT_UPDATE_LOCK_RELATIVE
            )
            identity = (
                archive_services._wom_kit_project_update_acquire_lock_exclusive(
                    project_root,
                    metadata_root,
                    lock_path,
                    reservation_callback=lambda _identity: None,
                )
            )
            try:
                public = self.inspect_all(fixture, preview)
                self.assertFalse(public["ok"])
                self.assertIn(
                    "project_update_collision_concurrent_operation",
                    public["blocker_codes"],
                )

                result, private = (
                    archive_services._wom_kit_project_version_update_collision_inspect_batch_core(
                        project_root,
                        target=str(fixture["target_tag"]),
                        expected_plan_sha256=preflight[
                            "materialization_plan_sha256"
                        ],
                        owned_lock_identity=identity,
                        runner=(
                            self.fixture_case
                            .trusted_project_update_git_runner()
                        ),
                    )
                )
                self.assertTrue(result["ok"], result)
                self.assertTrue(private["owned_lock_identity_verified"])
                self.assertRegex(private["head_before"], r"^[0-9a-f]{40,64}$")
                self.assertEqual(
                    private["target_ref_snapshot"]["target_commit"],
                    fixture["target_commit"],
                )

                wrong, wrong_private = (
                    archive_services._wom_kit_project_version_update_collision_inspect_batch_core(
                        project_root,
                        target=str(fixture["target_tag"]),
                        expected_plan_sha256=preflight[
                            "materialization_plan_sha256"
                        ],
                        owned_lock_identity=(identity[0], identity[1] + 1),
                        runner=(
                            self.fixture_case
                            .trusted_project_update_git_runner()
                        ),
                    )
                )
                self.assertFalse(wrong["ok"])
                self.assertIn(
                    "project_update_collision_concurrent_operation",
                    wrong["blocker_codes"],
                )
                self.assertFalse(
                    wrong_private["owned_lock_identity_verified"]
                )
            finally:
                self.assertTrue(
                    archive_services._wom_kit_project_update_release_owned_lock(
                        project_root,
                        lock_path,
                        identity,
                    )
                )


if __name__ == "__main__":
    unittest.main()
