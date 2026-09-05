import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services, project_runtime


class V0419TruthWriterRegressionTests(unittest.TestCase):
    @staticmethod
    def _exact_absent_component_state(
        project_root: Path,
        target: Path,
        desired: bytes,
    ) -> tuple[SimpleNamespace, object]:
        class Guard:
            def held_observation(self, _path):
                return {"state": "passed", "reason_code": "verified"}

            def hold(self, _path):
                return True

            def ensure_directory(self, _parent, _child):
                return True

        component = (
            archive_services.project_update_transaction.ProjectUpdateComponent(
                component_ref="active-pin",
                role="active_pin",
                sequence=1,
                logical_target=".zettel-kasten/installed-version.txt",
                pre_sha256=(
                    archive_services.project_update_transaction
                    .ABSENT_COMPONENT_SHA256
                ),
                post_sha256=(
                    archive_services.project_update_transaction
                    .digest_component(desired)
                ),
                preimage_key=None,
            )
        )
        state = SimpleNamespace(
            project_root=project_root,
            component_paths={"active-pin": target},
            directory_guard=Guard(),
            transaction=SimpleNamespace(
                transaction_ref="update_" + "a" * 32,
            ),
        )
        return state, component

    def test_runtime_policy_completed_git_and_blob_failures_are_failed(self) -> None:
        commit = "a" * 40
        object_id = "b" * 40
        policy_path = "wom-kit/project-runtime-policy.json"
        tree = f"100644 blob {object_id}\t{policy_path}\0"
        cases = (
            ((False, None, ""), None, "unavailable"),
            ((True, 2, "private-output"), None, "failed"),
            (
                (True, 0, tree),
                {
                    "state": "failed",
                    "reason_code": "project_git_blob_invalid",
                    "blob": None,
                },
                "failed",
            ),
            (
                (True, 0, tree),
                {
                    "state": "unavailable",
                    "reason_code": "project_git_blob_observation_unavailable",
                    "blob": None,
                },
                "unavailable",
            ),
        )
        for tree_result, blob_result, expected_state in cases:
            with self.subTest(expected_state=expected_state, blob=blob_result):
                observations = [tree_result]
                if blob_result is not None:
                    observations.append((True, 0, "64"))
                with (
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_observation",
                        side_effect=observations,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_blob_observation",
                        return_value=blob_result,
                    ),
                ):
                    result = archive_services.wom_kit_project_update_runtime_policy(
                        Path("ignored"),
                        commit,
                        runner=object(),
                    )
            self.assertEqual(result["observation_state"], expected_state)
            self.assertNotIn("private-output", json.dumps(result, sort_keys=True))

    def test_runtime_supply_completed_git_and_blob_failures_are_failed(self) -> None:
        commit = "a" * 40
        object_id = "b" * 40
        relative = "wom-kit/project-runtime-supply-lock-v0.4.19.json"
        tree = f"100644 blob {object_id}\t{relative}\0"
        policy = {
            "state": "required",
            "observation_state": "passed",
            "supply_lock_path": relative,
            "supply_lock_sha256": "sha256:" + "c" * 64,
        }
        cases = (
            ((False, None, ""), None, "unavailable"),
            ((True, 2, "private-output"), None, "failed"),
            (
                (True, 0, tree),
                {
                    "state": "failed",
                    "reason_code": "project_git_blob_invalid",
                    "blob": None,
                },
                "failed",
            ),
            (
                (True, 0, tree),
                {
                    "state": "unavailable",
                    "reason_code": "project_git_blob_observation_unavailable",
                    "blob": None,
                },
                "unavailable",
            ),
        )
        for tree_result, blob_result, expected_state in cases:
            with self.subTest(expected_state=expected_state, blob=blob_result):
                observations = [tree_result]
                if blob_result is not None:
                    observations.append((True, 0, "64"))
                with (
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_observation",
                        side_effect=observations,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_blob_observation",
                        return_value=blob_result,
                    ),
                ):
                    state, reason, supply = (
                        archive_services
                        .wom_kit_project_update_runtime_supply_observation(
                            Path("ignored"),
                            commit,
                            "0.4.19",
                            policy,
                            runner=object(),
                        )
                    )
            self.assertEqual(state, expected_state)
            self.assertIsNone(supply)
            self.assertNotIn("private-output", reason)

    def test_four_state_aggregation_preserves_priority_and_not_reached(self) -> None:
        observed = (
            archive_services._wom_kit_project_update_observed_preparation_check(
                "runtime_policy",
                "not_reached",
                "runtime_preparation_runtime_policy_not_reached",
                False,
            )
        )
        self.assertEqual(
            observed,
            (
                "not_reached",
                "runtime_preparation_runtime_policy_not_reached",
            ),
        )
        plan_state = (
            archive_services._wom_kit_project_update_runtime_plan_observation_state(
                [],
                prerequisite_states=("passed", "not_reached"),
            )
        )
        self.assertEqual(
            plan_state,
            (
                "not_reached",
                "runtime_preparation_runtime_plan_not_reached",
            ),
        )
        aggregate = archive_services.wom_kit_project_update_runtime_preparation_revalidation(
            {
                "git_snapshot": ("not_reached", "not_reached"),
                "runtime_policy": ("unavailable", "unavailable"),
                "runtime_supply": ("failed", "failed"),
            }
        )
        self.assertEqual(aggregate["state"], "failed")

    def test_runtime_plan_missing_install_is_actionable_but_other_truth_closes(
        self,
    ) -> None:
        # A clean install is expected to observe that the target runtime is
        # missing.  That observation belongs inside the approved plan; it is
        # not a prerequisite failure that can block the install plan itself.
        missing_truth = project_runtime.runtime_inspection_truth(
            {
                "status": "missing",
                "static_receipt_state": "not_reached",
                "receipt_candidate_valid": False,
            }
        )
        approved_plan = {
            "action": "install",
            "runtime_inspection": {
                "state": missing_truth["state"],
                "reason_code": missing_truth["reason_code"],
            },
        }
        live_plan = dict(approved_plan)
        passed_prerequisites = (
            archive_services
            ._wom_kit_project_update_runtime_plan_prerequisite_states(
                policy_state="passed",
                supply_state="passed",
                bootstrap_available=True,
                launcher_state="passed",
            )
        )
        state, reason = (
            archive_services._wom_kit_project_update_runtime_plan_observation_state(
                [],
                prerequisite_states=passed_prerequisites,
            )
        )
        clean_install = (
            archive_services._wom_kit_project_update_observed_preparation_check(
                "runtime_plan",
                state,
                reason,
                live_plan == approved_plan,
            )
        )
        self.assertEqual(missing_truth["reason_code"], "project_runtime_missing")
        self.assertEqual(
            clean_install,
            ("passed", "runtime_preparation_runtime_plan_verified"),
        )

        blocked_state, blocked_reason = (
            archive_services._wom_kit_project_update_runtime_plan_observation_state(
                ["project_runtime_supply_lock_target_mismatch"],
                prerequisite_states=passed_prerequisites,
            )
        )
        self.assertEqual(
            archive_services._wom_kit_project_update_observed_preparation_check(
                "runtime_plan",
                blocked_state,
                blocked_reason,
                True,
            ),
            ("failed", "runtime_preparation_runtime_plan_blocked"),
        )

        self.assertEqual(
            archive_services._wom_kit_project_update_observed_preparation_check(
                "runtime_plan",
                state,
                reason,
                {**live_plan, "action": "repair"} == approved_plan,
            ),
            ("failed", "runtime_preparation_runtime_plan_changed"),
        )

        unavailable_prerequisites = (
            archive_services
            ._wom_kit_project_update_runtime_plan_prerequisite_states(
                policy_state="passed",
                supply_state="unavailable",
                bootstrap_available=True,
                launcher_state="passed",
            )
        )
        unavailable_state, unavailable_reason = (
            archive_services._wom_kit_project_update_runtime_plan_observation_state(
                [],
                prerequisite_states=unavailable_prerequisites,
            )
        )
        self.assertEqual(
            archive_services._wom_kit_project_update_observed_preparation_check(
                "runtime_plan",
                unavailable_state,
                unavailable_reason,
                True,
            ),
            ("unavailable", "runtime_preparation_runtime_plan_unavailable"),
        )

    def test_approval_policy_compatibility_uses_expected_shape(self) -> None:
        legacy = {
            "state": "required",
            "required": True,
            "schema": "legacy",
            "policy_sha256": "sha256:" + "a" * 64,
            "source_path": "wom-kit/project-runtime-policy.json",
            "supply_lock_path": "wom-kit/supply.json",
            "supply_lock_sha256": "sha256:" + "b" * 64,
        }
        current = {
            **legacy,
            "observation_state": "passed",
            "observation_reason_code": "verified",
        }
        self.assertTrue(
            archive_services._project_update_approved_policy_uses_predecessor_shape(
                runtime_candidate_legacy=False,
                expected_policy=legacy,
            )
        )
        self.assertFalse(
            archive_services._project_update_approved_policy_uses_predecessor_shape(
                runtime_candidate_legacy=False,
                expected_policy=current,
            )
        )
        self.assertFalse(
            archive_services._project_update_approved_policy_uses_predecessor_shape(
                runtime_candidate_legacy=True,
                expected_policy=current,
            )
        )
        self.assertEqual(
            archive_services._project_update_approved_comparison_projection(
                current,
                legacy,
                predecessor_shape=True,
            ),
            legacy,
        )
        drifted = dict(current)
        drifted["state"] = "not_required"
        self.assertNotEqual(
            archive_services._project_update_approved_comparison_projection(
                drifted,
                legacy,
                predecessor_shape=True,
            ),
            legacy,
        )
        current_with_addition = {**current, "future_observation": "passed"}
        self.assertNotEqual(
            archive_services._project_update_approved_comparison_projection(
                current_with_addition,
                current,
                predecessor_shape=False,
            ),
            current,
        )

    def test_runtime_binding_known_failure_outranks_unavailable_observation(self) -> None:
        unavailable = {
            "state": "unavailable",
            "reason_code": "component_observation_unavailable",
            "snapshot": None,
        }
        inspection = {
            "status": "invalid",
            "static_receipt_state": "failed",
            "static_receipt_reason_code": "project_runtime_static_receipt_invalid",
            "receipt_candidate_valid": False,
        }
        launcher = {
            "unsafe": False,
            "already_target": False,
            "observation_state": "failed",
            "observation_reason_code": "project_runtime_launcher_mismatch",
        }
        with tempfile.TemporaryDirectory() as tmp, (
            mock.patch.object(
                project_runtime,
                "launcher_snapshot",
                return_value=launcher,
            )
        ), mock.patch.object(
            project_runtime,
            "_real_component_snapshot_observation",
            return_value=unavailable,
        ):
            result = project_runtime.current_project_runtime_binding(
                Path(tmp),
                "0.4.19",
                running_executable=Path(tmp) / "unavailable-python.exe",
                running_module_path=Path(tmp) / "unavailable-module.py",
                running_archive_cli_module_path=(
                    Path(tmp) / "unavailable-archive-cli.py"
                ),
                running_project_runtime_module_path=(
                    Path(tmp) / "unavailable-project-runtime.py"
                ),
                running_package_origin_path=(
                    Path(tmp) / "unavailable-package.py"
                ),
                running_prefix=Path(tmp) / "unavailable-prefix",
                isolated_mode=True,
                dont_write_bytecode=True,
                runtime_inspection=inspection,
            )
        self.assertEqual(result["observation_state"], "failed")
        self.assertEqual(
            result["reason_code"],
            "project_runtime_launcher_mismatch",
        )

    def test_write_guard_known_binding_failure_outranks_runtime_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            archive = project / "archive"
            metadata = project / ".zettel-kasten"
            archive.mkdir(parents=True)
            metadata.mkdir()
            (archive / "archive.yml").write_text(
                "archive_id: archive:test\n",
                encoding="utf-8",
            )
            (metadata / "installed-version.txt").write_text(
                "v0.4.19\n",
                encoding="utf-8",
            )
            unavailable = {
                "status": "invalid",
                "receipt_candidate_valid": False,
                "static_receipt_valid": True,
                "live_payload_aligned": False,
                "live_payload_state": "unavailable",
                "live_payload_reason_code": (
                    "project_runtime_live_payload_unavailable"
                ),
            }
            binding_failure = {
                "bound": False,
                "observation_state": "failed",
                "reason_code": "project_runtime_launcher_mismatch",
                "core_module_bindings": {},
            }
            with (
                mock.patch.object(
                    project_runtime,
                    "inspect_runtime",
                    return_value=unavailable,
                ),
                mock.patch.object(
                    project_runtime,
                    "current_project_runtime_binding",
                    return_value=binding_failure,
                ),
            ):
                result = project_runtime.project_write_guard(
                    archive,
                    running_version="0.4.19",
                )

        self.assertTrue(result["blocked"])
        self.assertEqual(result["reason_code"], "project_runtime_mismatch")
        self.assertEqual(result["runtime_inspection_state"], "failed")
        self.assertEqual(
            result["detail_reason_code"],
            "project_runtime_launcher_mismatch",
        )

    def test_runtime_process_identity_failures_outrank_stat_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            runtime = project_runtime.runtime_path(project, "0.4.19")
            runtime.mkdir(parents=True)
            receipt = b"{}\n"
            (runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME).write_bytes(
                receipt
            )
            expected_python = runtime / "Scripts" / "python.exe"
            expected_module = (
                runtime
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "module.py"
            )
            expected_archive_cli = expected_module.with_name("archive_cli.py")
            expected_project_runtime = expected_module.with_name(
                "project_runtime.py"
            )
            expected_package = expected_module.with_name("__init__.py")
            inspection = {
                "static_receipt_valid": True,
                "target_version": "0.4.19",
                "path": project_runtime.runtime_logical_path("0.4.19"),
                "live_payload_aligned": True,
                "live_payload_state": "passed",
                "live_payload_reason_code": "verified",
                "receipt_sha256": (
                    "sha256:" + hashlib.sha256(receipt).hexdigest()
                ),
            }
            launcher = {
                "unsafe": False,
                "already_target": True,
                "observation_state": "passed",
                "observation_reason_code": "verified",
            }
            unavailable = {
                "state": "unavailable",
                "reason_code": "component_observation_unavailable",
                "snapshot": None,
            }
            identities = {
                "executable": {
                    "running_executable": project / "wrong-python.exe",
                    "running_module_path": expected_module,
                    "running_prefix": runtime,
                },
                "module": {
                    "running_executable": expected_python,
                    "running_module_path": project / "wrong-module.py",
                    "running_prefix": runtime,
                },
                "prefix": {
                    "running_executable": expected_python,
                    "running_module_path": expected_module,
                    "running_prefix": project / "wrong-prefix",
                },
            }
            for boundary, overrides in identities.items():
                with self.subTest(boundary=boundary):
                    with (
                        mock.patch.object(
                            project_runtime,
                            "runtime_inspection_truth",
                            return_value={
                                "state": "passed",
                                "reason_code": "verified",
                                "private_values_echoed": False,
                            },
                        ),
                        mock.patch.object(
                            project_runtime,
                            "launcher_snapshot",
                            return_value=launcher,
                        ),
                        mock.patch.object(
                            project_runtime,
                            "_real_component_snapshot_observation",
                            return_value=unavailable,
                        ),
                        mock.patch.object(
                            project_runtime,
                            "_read_limited",
                            return_value=receipt,
                        ),
                    ):
                        result = (
                            project_runtime.current_project_runtime_binding(
                                project,
                                "0.4.19",
                                running_archive_cli_module_path=(
                                    expected_archive_cli
                                ),
                                running_project_runtime_module_path=(
                                    expected_project_runtime
                                ),
                                running_package_origin_path=expected_package,
                                isolated_mode=True,
                                dont_write_bytecode=True,
                                runtime_inspection=inspection,
                                **overrides,
                            )
                        )
                    self.assertEqual(result["observation_state"], "failed")
                    self.assertEqual(
                        result["reason_code"],
                        "project_runtime_process_binding_mismatch",
                    )

    def test_core_identity_failure_outranks_other_core_read_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            runtime = project_runtime.runtime_path(project, "0.4.19")
            runtime.mkdir(parents=True)
            receipt = b"{}\n"
            (runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME).write_bytes(
                receipt
            )
            expected_python = runtime / "Scripts" / "python.exe"
            expected_module = (
                runtime
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "module.py"
            )
            expected_archive_cli = expected_module.with_name("archive_cli.py")
            expected_project_runtime = expected_module.with_name(
                "project_runtime.py"
            )
            expected_package = expected_module.with_name("__init__.py")
            paths = (
                expected_python,
                expected_module,
                expected_archive_cli,
                expected_project_runtime,
                expected_package,
            )
            inventory = tuple(
                (
                    path.relative_to(runtime).as_posix(),
                    1,
                    "d" * 64,
                )
                for path in paths
            )
            inspection = {
                "static_receipt_valid": True,
                "target_version": "0.4.19",
                "path": project_runtime.runtime_logical_path("0.4.19"),
                "live_payload_aligned": True,
                "live_payload_state": "passed",
                "live_payload_reason_code": "verified",
                "receipt_sha256": (
                    "sha256:" + hashlib.sha256(receipt).hexdigest()
                ),
                "installed_payload_sha256": "sha256:" + "a" * 64,
            }
            launcher = {
                "unsafe": False,
                "already_target": True,
                "observation_state": "passed",
                "observation_reason_code": "verified",
            }
            passed = {
                "state": "passed",
                "reason_code": "verified",
                "snapshot": {},
            }

            def observed_hash(path: Path, *, ancestor_root: Path):
                _ = ancestor_root
                if Path(path) == expected_project_runtime:
                    raise project_runtime.ProjectRuntimeError(
                        "project_runtime_observation_unavailable"
                    )
                return "d" * 64, 1

            with (
                mock.patch.object(
                    project_runtime,
                    "runtime_inspection_truth",
                    return_value={
                        "state": "passed",
                        "reason_code": "verified",
                        "private_values_echoed": False,
                    },
                ),
                mock.patch.object(
                    project_runtime,
                    "launcher_snapshot",
                    return_value=launcher,
                ),
                mock.patch.object(
                    project_runtime,
                    "_real_component_snapshot_observation",
                    return_value=passed,
                ),
                mock.patch.object(
                    project_runtime,
                    "_read_limited",
                    return_value=receipt,
                ),
                mock.patch.object(
                    project_runtime,
                    "_runtime_payload_observation",
                    return_value=("a" * 64, inventory),
                ),
                mock.patch.object(
                    project_runtime,
                    "_sha256_file",
                    side_effect=observed_hash,
                ),
            ):
                result = project_runtime.current_project_runtime_binding(
                    project,
                    "0.4.19",
                    running_executable=expected_python,
                    running_module_path=expected_module,
                    running_archive_cli_module_path=(
                        project / "wrong-archive-cli.py"
                    ),
                    running_project_runtime_module_path=(
                        expected_project_runtime
                    ),
                    running_package_origin_path=expected_package,
                    running_prefix=runtime,
                    isolated_mode=True,
                    dont_write_bytecode=True,
                    runtime_inspection=inspection,
                )
                unavailable_result = (
                    project_runtime.current_project_runtime_binding(
                        project,
                        "0.4.19",
                        running_executable=expected_python,
                        running_module_path=expected_module,
                        running_archive_cli_module_path=expected_archive_cli,
                        running_project_runtime_module_path=(
                            expected_project_runtime
                        ),
                        running_package_origin_path=expected_package,
                        running_prefix=runtime,
                        isolated_mode=True,
                        dont_write_bytecode=True,
                        runtime_inspection=inspection,
                    )
                )

        self.assertEqual(result["observation_state"], "failed")
        self.assertEqual(
            result["reason_code"],
            "project_runtime_core_modules_not_receipt_bound",
        )
        self.assertEqual(
            result["core_module_bindings"]["archive_cli"]["reason_code"],
            "project_runtime_core_archive_cli_identity_mismatch",
        )
        self.assertEqual(
            result["core_module_bindings"]["project_runtime"]["reason_code"],
            "project_runtime_core_project_runtime_observation_unavailable",
        )
        self.assertEqual(
            unavailable_result["observation_state"],
            "unavailable",
        )
        self.assertEqual(
            unavailable_result["reason_code"],
            "project_runtime_process_binding_observation_unavailable",
        )
        self.assertEqual(
            unavailable_result["core_module_bindings"]["project_runtime"][
                "reason_code"
            ],
            "project_runtime_core_project_runtime_observation_unavailable",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_handle_prevents_external_temp_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed-version.txt"
            external = root / "external-replacement.tmp"
            external.write_bytes(b"external")
            stages: list[str] = []

            def contend(stage: str, temporary_path: Path) -> None:
                stages.append(stage)
                if stage != "publish_temp_flushed_and_bound":
                    return
                with self.assertRaises(OSError):
                    os.replace(external, temporary_path)

            archive_services._project_update_windows_publish_bytes_no_replace(
                target,
                b"v0.4.19\n",
                _failpoint=contend,
            )
            self.assertEqual(target.read_bytes(), b"v0.4.19\n")
            self.assertEqual(external.read_bytes(), b"external")
            self.assertIn("publish_temp_flushed_and_bound", stages)
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_power_cut_before_rename_leaves_no_named_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed-version.txt"
            script = "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "from wom_kit import archive_services",
                    "def stop(stage, _path):",
                    "    if stage == 'publish_temp_flushed_and_bound':",
                    "        os._exit(23)",
                    "archive_services._project_update_windows_publish_bytes_no_replace(",
                    "    Path(sys.argv[1]), b'v0.4.19\\n', _failpoint=stop)",
                )
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(SRC_ROOT)
            completed = subprocess.run(
                [sys.executable, "-c", script, str(target)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            self.assertEqual(completed.returncode, 23)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_power_cut_after_rename_is_cleanly_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed-version.txt"
            script = "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "from wom_kit import archive_services",
                    "def stop(stage, _path):",
                    "    if stage == 'publish_target_durable_before_delete_on_close_cancel':",
                    "        os._exit(29)",
                    "archive_services._project_update_windows_publish_bytes_no_replace(",
                    "    Path(sys.argv[1]), b'v0.4.19\\n', _failpoint=stop)",
                )
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(SRC_ROOT)
            completed = subprocess.run(
                [sys.executable, "-c", script, str(target)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            self.assertEqual(completed.returncode, 29)
            # The rename happened, but delete-on-close was still armed.  The
            # kernel removes that exact object as the process exits, leaving
            # the absent preimage safe to replay without an orphan name.
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

            archive_services._project_update_windows_publish_bytes_no_replace(
                target,
                b"v0.4.19\n",
            )
            self.assertEqual(target.read_bytes(), b"v0.4.19\n")
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_directory_barrier_failure_keeps_target_uncommitted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed-version.txt"
            with mock.patch.object(
                archive_services.project_update_transaction,
                "_require_directory_durable",
                side_effect=RuntimeError(
                    "PRIVATE_DIRECTORY_DURABILITY_DIAGNOSTIC"
                ),
            ):
                with self.assertRaises(RuntimeError):
                    archive_services._project_update_windows_publish_bytes_no_replace(
                        target,
                        b"v0.4.19\n",
                    )

            # Delete-on-close remains armed until the directory barrier has
            # succeeded, so a failed barrier cannot leave an accepted target.
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_hard_exit_after_commit_preserves_exact_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "installed-version.txt"
            script = "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "from wom_kit import archive_services",
                    "def stop(stage, _path):",
                    "    if stage == 'publish_delete_on_close_cancelled':",
                    "        os._exit(31)",
                    "archive_services._project_update_windows_publish_bytes_no_replace(",
                    "    Path(sys.argv[1]), b'v0.4.19\\n', _failpoint=stop)",
                )
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(SRC_ROOT)
            completed = subprocess.run(
                [sys.executable, "-c", script, str(target)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            self.assertEqual(completed.returncode, 31)
            self.assertEqual(target.read_bytes(), b"v0.4.19\n")
            self.assertEqual(list(root.glob(".*.wom-publish")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows retained handle")
    def test_publisher_low_level_error_is_fixed_and_path_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "PRIVATE_PROJECT_PATH"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            target = metadata_root / "PRIVATE_TARGET_NAME.txt"
            desired = b"v0.4.19\n"
            state, component = self._exact_absent_component_state(
                project_root,
                target,
                desired,
            )
            private_marker = "PRIVATE_WINERROR_AND_PATH"
            low_level = OSError(
                5,
                f"{private_marker}: {target}",
            )
            with mock.patch.object(
                archive_services,
                "_project_update_windows_publish_bytes_no_replace",
                side_effect=low_level,
            ):
                with self.assertRaises(
                    archive_services.ArchiveServiceError
                ) as captured:
                    archive_services._project_update_exact_write_bytes(
                        state,
                        component,
                        desired,
                    )
            public_error = {
                "type": type(captured.exception).__name__,
                "message": str(captured.exception),
                "args": captured.exception.args,
            }
            self.assertEqual(
                str(captured.exception),
                "project_version_update_component_compare_and_swap_failed",
            )
            serialized = json.dumps(public_error, sort_keys=True)
            self.assertNotIn(private_marker, serialized)
            self.assertNotIn(str(target), serialized)
            self.assertFalse(target.exists())
            self.assertEqual(list(metadata_root.glob(".*.wom-publish")), [])


if __name__ == "__main__":
    unittest.main()
