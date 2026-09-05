import os
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

from wom_kit import archive_services


class V0419LockObservationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows retained handle only")
    def test_directory_guard_borrows_only_active_exact_handle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            guard = archive_services._WomKitProjectUpdateDirectoryGuard(
                project_root
            )
            self.assertIsNone(guard.retained_windows_handle(project_root))
            self.assertTrue(guard.hold(project_root))

            borrowed = guard.retained_windows_handle(project_root)

            self.assertIsInstance(borrowed, int)
            self.assertTrue(guard.is_held(project_root))
            guard.release(project_root)
            self.assertIsNone(guard.retained_windows_handle(project_root))
            guard.close()

    def test_lock_receipt_cleanup_requires_confirmed_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            with mock.patch.object(
                archive_services.os,
                "lstat",
                side_effect=PermissionError("private lock access failure"),
            ):
                self.assertFalse(
                    archive_services
                    ._wom_kit_project_update_remove_exclusive_receipt_if_owned(
                        project_root,
                        lock_path,
                        None,
                    )
                )

            lock_path.write_bytes(
                archive_services.WOM_KIT_PROJECT_UPDATE_LOCK_BYTES
            )
            lock_stat = os.lstat(lock_path)
            identity = (int(lock_stat.st_dev), int(lock_stat.st_ino))
            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value={"state": "unavailable", "kind": "unknown"},
            ):
                self.assertFalse(
                    archive_services
                    ._wom_kit_project_update_remove_exclusive_receipt_if_owned(
                        project_root,
                        lock_path,
                        identity,
                    )
                )
            self.assertFalse(lock_path.exists())

    def test_interrupted_lock_cleanup_preserves_unavailable_truth(self) -> None:
        unavailable = {
            "state": "unavailable",
            "kind": "unknown",
            "reason_code": "project_update_lock_observation_unavailable",
        }
        owned = {
            "state": "passed",
            "kind": "owned",
            "reason_code": "verified",
        }
        missing = {
            "state": "failed",
            "kind": "missing",
            "reason_code": "project_update_lock_missing",
        }
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            with (
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_lock_after_failure_observation",
                    return_value=unavailable,
                ),
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_release_owned_lock",
                ) as release,
            ):
                result = (
                    archive_services
                    ._wom_kit_project_update_reconcile_lock_after_acquire_failure(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                        release_owned=True,
                    )
                )
            release.assert_not_called()
            self.assertIsNone(result["lock_removed"])
            self.assertTrue(result["preserve_lock"])
            self.assertFalse(result["release_attempted"])

            with (
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_lock_after_failure_observation",
                    side_effect=[owned, unavailable],
                ),
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_release_owned_lock",
                    return_value=False,
                ) as release,
            ):
                raced = (
                    archive_services
                    ._wom_kit_project_update_reconcile_lock_after_acquire_failure(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                        release_owned=True,
                    )
                )
            release.assert_called_once()
            self.assertIsNone(raced["lock_removed"])
            self.assertTrue(raced["preserve_lock"])
            self.assertTrue(raced["release_attempted"])

            with (
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_lock_after_failure_observation",
                    side_effect=[owned, missing],
                ),
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_release_owned_lock",
                    return_value=True,
                ),
            ):
                removed = (
                    archive_services
                    ._wom_kit_project_update_reconcile_lock_after_acquire_failure(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                        release_owned=True,
                    )
                )
            self.assertTrue(removed["lock_removed"])
            self.assertFalse(removed["preserve_lock"])

    def test_component_read_separates_missing_unsafe_and_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            component = project_root / "installed-version.txt"
            self.assertIsNone(
                archive_services._project_update_safe_read_component(
                    project_root,
                    component,
                    maximum=4096,
                )
            )

            component.write_bytes(b"v0.4.18\n")
            self.assertEqual(
                archive_services._project_update_safe_read_component(
                    project_root,
                    component,
                    maximum=4096,
                ),
                b"v0.4.18\n",
            )
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "unavailable", "kind": "unknown"},
                ),
                mock.patch.object(
                    archive_services,
                    "_wom_kit_read_bounded_real_bytes",
                ) as read_bytes,
            ):
                unavailable = (
                    archive_services._project_update_safe_read_component(
                        project_root,
                        component,
                        maximum=4096,
                    )
                )
            read_bytes.assert_not_called()
            self.assertIs(
                unavailable,
                archive_services._PROJECT_UPDATE_UNAVAILABLE_LIVE_COMPONENT,
            )

            with mock.patch.object(
                archive_services.os,
                "read",
                side_effect=PermissionError("private read failure"),
            ):
                read_unavailable = (
                    archive_services._project_update_safe_read_component(
                        project_root,
                        component,
                        maximum=4096,
                    )
                )
            self.assertIs(
                read_unavailable,
                archive_services._PROJECT_UPDATE_UNAVAILABLE_LIVE_COMPONENT,
            )

            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value={"state": "failed", "kind": "unsafe"},
            ):
                unsafe = archive_services._project_update_safe_read_component(
                    project_root,
                    component,
                    maximum=4096,
                )
            self.assertIs(
                unsafe,
                archive_services._PROJECT_UPDATE_UNSAFE_LIVE_COMPONENT,
            )

    def test_component_bytes_observation_separates_drift_and_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            component = project_root / "installed-version.txt"
            component.write_bytes(b"v0.4.18\n")

            passed = (
                archive_services._project_update_component_bytes_observation(
                    project_root,
                    component,
                    maximum=4096,
                )
            )
            self.assertEqual(passed["state"], "passed")
            self.assertEqual(passed["value"], b"v0.4.18\n")

            oversized = (
                archive_services._project_update_component_bytes_observation(
                    project_root,
                    component,
                    maximum=4,
                )
            )
            self.assertEqual(oversized["state"], "failed")
            self.assertEqual(
                oversized["reason_code"],
                "project_update_component_too_large",
            )

            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "passed", "kind": "file"},
                ),
                mock.patch.object(
                    archive_services.os,
                    "lstat",
                    side_effect=PermissionError("private lstat failure"),
                ),
            ):
                lstat_unavailable = (
                    archive_services
                    ._project_update_component_bytes_observation(
                        project_root,
                        component,
                        maximum=4096,
                    )
                )
            self.assertEqual(lstat_unavailable["state"], "unavailable")
            self.assertNotIn("private", str(lstat_unavailable))

            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "passed", "kind": "file"},
                ),
                mock.patch.object(
                    archive_services.os,
                    "lstat",
                    side_effect=FileNotFoundError,
                ),
            ):
                raced_missing = (
                    archive_services
                    ._project_update_component_bytes_observation(
                        project_root,
                        component,
                        maximum=4096,
                    )
                )
            self.assertEqual(raced_missing["state"], "failed")
            self.assertEqual(
                raced_missing["reason_code"],
                "project_update_component_changed",
            )

            with mock.patch.object(
                archive_services.os,
                "fstat",
                side_effect=PermissionError("private fstat failure"),
            ):
                fstat_unavailable = (
                    archive_services
                    ._project_update_component_bytes_observation(
                        project_root,
                        component,
                        maximum=4096,
                    )
                )
            self.assertEqual(fstat_unavailable["state"], "unavailable")
            self.assertNotIn("private", str(fstat_unavailable))

            component_stat = os.stat(component)
            base_fields = {
                "st_mode": component_stat.st_mode,
                "st_size": component_stat.st_size,
                "st_mtime_ns": component_stat.st_mtime_ns,
                "st_dev": component_stat.st_dev,
                "st_ino": component_stat.st_ino,
                "st_file_attributes": getattr(
                    component_stat,
                    "st_file_attributes",
                    0,
                ),
            }
            for field, replacement in (
                ("st_size", component_stat.st_size + 1),
                ("st_mtime_ns", component_stat.st_mtime_ns + 1),
                ("st_ino", component_stat.st_ino + 1),
            ):
                drift_fields = dict(base_fields)
                drift_fields[field] = replacement
                with self.subTest(field=field), mock.patch.object(
                    archive_services.os,
                    "fstat",
                    return_value=SimpleNamespace(**drift_fields),
                ):
                    drift = (
                        archive_services
                        ._project_update_component_bytes_observation(
                            project_root,
                            component,
                            maximum=4096,
                        )
                    )
                self.assertEqual(drift["state"], "failed")
                self.assertEqual(
                    drift["reason_code"],
                    "project_update_component_changed",
                )

    def test_runtime_candidate_wrapper_preserves_observation_state(self) -> None:
        state = SimpleNamespace(
            project_root=Path("project"),
            runtime_candidate=object(),
        )
        for observation, expected in (
            (
                {
                    "state": "passed",
                    "reason_code": "verified",
                    "matches": True,
                },
                "passed",
            ),
            (
                {
                    "state": "failed",
                    "reason_code": "confirmed_drift",
                    "matches": False,
                },
                "failed",
            ),
            (
                {
                    "state": "unavailable",
                    "reason_code": "observation_unavailable",
                    "matches": False,
                },
                "unavailable",
            ),
        ):
            with self.subTest(expected=expected), mock.patch.object(
                archive_services.project_runtime,
                "_existing_runtime_candidate_observation",
                return_value=observation,
            ):
                result = (
                    archive_services
                    ._project_update_runtime_candidate_observation(state)
                )
            self.assertEqual(result["state"], expected)

        with mock.patch.object(
            archive_services.project_runtime,
            "_existing_runtime_candidate_observation",
            side_effect=PermissionError("private runtime access failure"),
        ):
            unavailable = (
                archive_services
                ._project_update_runtime_candidate_observation(state)
            )
        self.assertEqual(unavailable["state"], "unavailable")
        self.assertNotIn("private", str(unavailable))

    def test_runtime_live_sha_does_not_invent_preimage_on_io_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            candidate = SimpleNamespace(
                existing_runtime_repair_required=False,
            )
            state = SimpleNamespace(
                project_root=project_root,
                runtime_candidate=candidate,
                runtime_pre_sha256=(
                    archive_services.project_update_transaction
                    .ABSENT_COMPONENT_SHA256
                ),
                runtime_post_sha256="sha256:" + "a" * 64,
                source_pre_sha256="sha256:" + "b" * 64,
                target_version="0.4.19",
                transaction=SimpleNamespace(
                    intent=SimpleNamespace(components=()),
                ),
                component_paths={},
            )
            unknown = archive_services._project_update_unknown_component_sha256(
                "runtime"
            )
            with (
                mock.patch.object(
                    archive_services,
                    "_project_update_source_live_sha256",
                    return_value=state.source_pre_sha256,
                ),
                mock.patch.object(
                    archive_services,
                    "_project_update_runtime_candidate_observation",
                    return_value={
                        "state": "unavailable",
                        "reason_code": "synthetic_unavailable",
                    },
                ),
                mock.patch.object(
                    archive_services.project_runtime,
                    "_runtime_path_presence_observation",
                ) as presence,
            ):
                unavailable = (
                    archive_services._project_update_live_component_sha256(
                        state
                    )
                )
            presence.assert_not_called()
            self.assertEqual(unavailable["runtime"], unknown)

            with (
                mock.patch.object(
                    archive_services,
                    "_project_update_source_live_sha256",
                    return_value=state.source_pre_sha256,
                ),
                mock.patch.object(
                    archive_services,
                    "_project_update_runtime_candidate_observation",
                    return_value={
                        "state": "failed",
                        "reason_code": "confirmed_not_postimage",
                    },
                ),
                mock.patch.object(
                    archive_services.project_runtime,
                    "_runtime_path_presence_observation",
                    return_value={"state": "unavailable", "present": None},
                ),
            ):
                absent_unavailable = (
                    archive_services._project_update_live_component_sha256(
                        state
                    )
                )
            self.assertEqual(absent_unavailable["runtime"], unknown)

            candidate.existing_runtime_repair_required = True
            with (
                mock.patch.object(
                    archive_services,
                    "_project_update_source_live_sha256",
                    return_value=state.source_pre_sha256,
                ),
                mock.patch.object(
                    archive_services,
                    "_project_update_runtime_candidate_observation",
                    return_value={
                        "state": "failed",
                        "reason_code": "confirmed_not_postimage",
                    },
                ),
                mock.patch.object(
                    archive_services.project_runtime,
                    "runtime_repair_state_observation",
                    return_value={
                        "state": "unavailable",
                        "repair_state": "unknown",
                    },
                ),
            ):
                repair_unavailable = (
                    archive_services._project_update_live_component_sha256(
                        state
                    )
                )
            self.assertEqual(repair_unavailable["runtime"], unknown)

    def test_exact_component_write_stops_on_unavailable_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            path = project_root / "installed-version.txt"
            before = b"v0.4.18\n"
            after = b"v0.4.19\n"
            component = SimpleNamespace(
                component_ref="active-pin:0001",
                role="active_pin",
                pre_sha256=(
                    archive_services._project_update_raw_component_sha256(
                        before
                    )
                ),
                post_sha256=(
                    archive_services._project_update_raw_component_sha256(
                        after
                    )
                ),
            )
            guard = mock.Mock()
            guard.held_observation.return_value = {
                "state": "passed",
                "reason_code": "verified",
            }
            state = SimpleNamespace(
                project_root=project_root,
                component_paths={component.component_ref: path},
                directory_guard=guard,
                transaction=SimpleNamespace(
                    transaction_ref="update_" + "e" * 32,
                ),
            )
            with mock.patch.object(
                archive_services,
                "_project_update_safe_read_component",
                return_value=(
                    archive_services
                    ._PROJECT_UPDATE_UNAVAILABLE_LIVE_COMPONENT
                ),
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "component_observation_unavailable",
                ):
                    archive_services._project_update_exact_write_bytes(
                        state,
                        component,
                        after,
                    )

            path.write_bytes(before)
            with mock.patch.object(
                archive_services,
                "_project_update_safe_read_component",
                side_effect=[
                    before,
                    before,
                    archive_services
                    ._PROJECT_UPDATE_UNAVAILABLE_LIVE_COMPONENT,
                ],
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "component_verification_unavailable",
                ):
                    archive_services._project_update_exact_write_bytes(
                        state,
                        component,
                        after,
                    )
            self.assertEqual(path.read_bytes(), after)

    def test_owned_lock_observation_distinguishes_exact_and_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            lock_path = metadata_root / "version-update.lock"
            expected = archive_services.WOM_KIT_PROJECT_UPDATE_LOCK_BYTES
            lock_path.write_bytes(expected)
            lock_stat = os.lstat(lock_path)
            identity = (int(lock_stat.st_dev), int(lock_stat.st_ino))

            exact = (
                archive_services.wom_kit_project_update_owned_lock_observation(
                    project_root,
                    lock_path,
                    identity,
                )
            )
            self.assertEqual(
                exact,
                {"state": "passed", "reason_code": "verified"},
            )
            self.assertNotIn(str(lock_path), str(exact))

            lock_path.write_bytes(b"X" * len(expected))
            changed = (
                archive_services.wom_kit_project_update_owned_lock_observation(
                    project_root,
                    lock_path,
                    identity,
                )
            )
            self.assertEqual(changed["state"], "failed")
            self.assertFalse(
                archive_services.wom_kit_project_update_owned_lock_present(
                    project_root,
                    lock_path,
                    identity,
                )
            )

            lock_path.unlink()
            missing = (
                archive_services.wom_kit_project_update_owned_lock_observation(
                    project_root,
                    lock_path,
                    identity,
                )
            )
            self.assertEqual(missing["state"], "failed")

    def test_owned_lock_lstat_failure_is_unavailable_not_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "passed", "kind": "file"},
                ),
                mock.patch.object(
                    archive_services.os,
                    "lstat",
                    side_effect=PermissionError("private access failure"),
                ),
            ):
                result = (
                    archive_services
                    .wom_kit_project_update_owned_lock_observation(
                        project_root,
                        lock_path,
                        (1, 2),
                    )
                )
            self.assertEqual(result["state"], "unavailable")
            self.assertNotIn("private", str(result))

    def test_owned_lock_fstat_and_read_failures_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            lock_path.write_bytes(
                archive_services.WOM_KIT_PROJECT_UPDATE_LOCK_BYTES
            )
            lock_stat = os.lstat(lock_path)
            identity = (int(lock_stat.st_dev), int(lock_stat.st_ino))

            with mock.patch.object(
                archive_services.os,
                "fstat",
                side_effect=PermissionError("private fstat failure"),
            ):
                fstat_result = (
                    archive_services
                    .wom_kit_project_update_owned_lock_observation(
                        project_root,
                        lock_path,
                        identity,
                    )
                )
            self.assertEqual(fstat_result["state"], "unavailable")

            with mock.patch.object(
                archive_services.os,
                "read",
                side_effect=PermissionError("private read failure"),
            ):
                read_result = (
                    archive_services
                    .wom_kit_project_update_owned_lock_observation(
                        project_root,
                        lock_path,
                        identity,
                    )
                )
            self.assertEqual(read_result["state"], "unavailable")
            self.assertNotIn("private", str(read_result))

    def test_directory_guard_lstat_failure_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            guard = archive_services._WomKitProjectUpdateDirectoryGuard(
                project_root
            )
            self.assertTrue(guard.hold(project_root))
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "passed", "kind": "directory"},
                ),
                mock.patch.object(
                    archive_services.os,
                    "lstat",
                    side_effect=PermissionError("private access failure"),
                ),
            ):
                result = guard.held_observation(project_root)
            self.assertEqual(result["state"], "unavailable")
            self.assertNotIn(str(project_root), str(result))
            guard.close()

    def test_directory_guard_identity_drift_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            guard = archive_services._WomKitProjectUpdateDirectoryGuard(
                project_root
            )
            self.assertTrue(guard.hold(project_root))
            key = guard._key(project_root)
            device, inode = guard._identities[key]
            guard._identities[key] = (device, inode + 1)
            result = guard.held_observation(project_root)
            self.assertEqual(result["state"], "failed")
            guard.close()

    @unittest.skipUnless(os.name == "nt", "Windows handle observation only")
    def test_get_file_information_failure_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            guard = archive_services._WomKitProjectUpdateDirectoryGuard(
                project_root
            )
            self.assertTrue(guard.hold(project_root))
            with mock.patch.object(
                guard,
                "_windows_handle_information_observation",
                return_value={
                    "state": "unavailable",
                    "reason_code": (
                        "project_update_directory_guard_handle_observation_unavailable"
                    ),
                },
            ):
                result = guard.held_observation(project_root)
            self.assertEqual(result["state"], "unavailable")
            guard.close()

    def test_lock_failure_code_preserves_unavailable(self) -> None:
        failure_code = (
            archive_services._wom_kit_project_update_approved_lock_failure_code
        )
        self.assertIsNone(failure_code(({"state": "passed"},)))
        self.assertEqual(
            failure_code(({"state": "failed"},)),
            "project_version_update_approved_snapshot_changed",
        )
        self.assertEqual(
            failure_code(({"state": "unavailable"},)),
            "project_version_update_approved_snapshot_unavailable",
        )

    def test_rollback_lock_observation_never_turns_unavailable_into_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "unavailable", "kind": "unknown"},
                ),
                mock.patch.object(
                    archive_services,
                    "wom_kit_project_update_owned_lock_observation",
                ) as ownership,
            ):
                result = (
                    archive_services
                    ._wom_kit_project_update_lock_after_failure_observation(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                    )
                )
            ownership.assert_not_called()
            self.assertEqual(
                result,
                {
                    "state": "unavailable",
                    "kind": "unknown",
                    "reason_code": "project_update_lock_observation_unavailable",
                },
            )
            self.assertNotIn("missing", str(result))

    def test_rollback_lock_observation_distinguishes_missing_and_changed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            lock_path = project_root / "version-update.lock"
            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value={"state": "passed", "kind": "missing"},
            ):
                missing = (
                    archive_services
                    ._wom_kit_project_update_lock_after_failure_observation(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                    )
                )
            self.assertEqual(missing["state"], "failed")
            self.assertEqual(missing["kind"], "missing")

            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    return_value={"state": "passed", "kind": "file"},
                ),
                mock.patch.object(
                    archive_services,
                    "wom_kit_project_update_owned_lock_observation",
                    return_value={
                        "state": "failed",
                        "reason_code": "project_update_owned_lock_changed",
                    },
                ),
            ):
                changed = (
                    archive_services
                    ._wom_kit_project_update_lock_after_failure_observation(
                        project_root,
                        lock_path,
                        (1, 2),
                        expected_lock_bytes=b"lock\n",
                    )
                )
            self.assertEqual(changed["state"], "failed")
            self.assertEqual(changed["kind"], "changed")


if __name__ == "__main__":
    unittest.main()
