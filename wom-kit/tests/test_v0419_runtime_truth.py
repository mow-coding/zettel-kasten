import argparse
import json
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

from wom_kit import archive_cli, archive_services


class V0419RuntimeTruthTests(unittest.TestCase):
    @unittest.skipUnless(
        sys.platform == "win32",
        "the approved exact publisher is Windows-only",
    )
    def test_exact_component_write_preserves_concurrent_absent_preimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            target = metadata_root / "installed-version.txt"
            drift = b"v9.9.9\n"
            desired = b"v0.4.19\n"
            component = (
                archive_services.project_update_transaction
                .ProjectUpdateComponent(
                    component_ref="active-pin",
                    role="active_pin",
                    sequence=1,
                    logical_target=(
                        ".zettel-kasten/installed-version.txt"
                    ),
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

            class Guard:
                def held_observation(self, _path):
                    return {"state": "passed", "reason_code": "verified"}

                def hold(self, _path):
                    return True

                def ensure_directory(self, _parent, _child):
                    return True

            state = SimpleNamespace(
                project_root=project_root,
                component_paths={"active-pin": target},
                directory_guard=Guard(),
                transaction=SimpleNamespace(
                    transaction_ref="update_" + "b" * 32,
                ),
            )
            original_publish = (
                archive_services
                ._project_update_windows_publish_bytes_no_replace
            )
            injected = False

            def inject_external_create(destination, raw):
                nonlocal injected
                destination_path = Path(destination)
                if not injected and destination_path == target:
                    injected = True
                    target.write_bytes(drift)
                return original_publish(destination, raw)

            with mock.patch.object(
                archive_services,
                "_project_update_windows_publish_bytes_no_replace",
                side_effect=inject_external_create,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "project_version_update_component_compare_and_swap_failed",
                ):
                    archive_services._project_update_exact_write_bytes(
                        state,
                        component,
                        desired,
                    )

            self.assertEqual(target.read_bytes(), drift)
            self.assertTrue(injected)
            self.assertEqual(list(metadata_root.glob(".*.wom-publish")), [])

    def test_durable_state_blocks_unavailable_receipt_preimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            runtime_candidate = object.__new__(
                archive_services.project_runtime.PreparedRuntimeCandidate
            )
            bootstrap = object.__new__(
                archive_services.project_runtime.BootstrapWheel
            )
            supply = object.__new__(
                archive_services.project_runtime.RuntimeSupplyLock
            )
            reservation = SimpleNamespace(transaction_ref="update_" + "a" * 32)
            unavailable = {"state": "unavailable", "kind": "unknown"}
            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value=unavailable,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    (
                        "project_version_update_transaction_receipt_"
                        "observation_unavailable"
                    ),
                ):
                    archive_services._project_update_prepare_durable_state(
                        inspection_root=project_root,
                        project_root=project_root,
                        mirror_path=project_root / ".zettel-kasten" / "source",
                        mirror_logical=".zettel-kasten/source",
                        target_tag="v0.4.19",
                        target_version="0.4.19",
                        target_commit="a" * 40,
                        reviewer="person:test",
                        expected_approval_root=project_root,
                        expected_archive_id="archive:test",
                        reservation=reservation,
                        expected_lock_bytes=b"lock",
                        runner=mock.Mock(),
                        runtime_candidate=runtime_candidate,
                        runtime_bootstrap=bootstrap,
                        runtime_supply=supply,
                        runtime_policy={},
                        runtime_plan={},
                        directory_guard=mock.Mock(),
                        preflight_git_snapshot={},
                        preflight_git_config_digest="a" * 64,
                        target_ref_snapshot={},
                        target_evidence={},
                        materialization_preflight={},
                        head_before="a" * 40,
                        pin_specs=[],
                        launcher_snapshot={},
                        prepared_preview_base={},
                    )

    @unittest.skipUnless(
        sys.platform == "win32",
        "the approved exact publisher is Windows-only",
    )
    def test_exact_component_write_preserves_raced_existing_bytes(self) -> None:
        for race_kind in ("replace", "in_place"):
            with self.subTest(race=race_kind), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp) / "project"
                metadata_root = project_root / ".zettel-kasten"
                metadata_root.mkdir(parents=True)
                target = metadata_root / "installed-version.txt"
                expected = b"v0.4.18\n"
                external = b"v9.9.9\n"
                desired = b"v0.4.19\n"
                target.write_bytes(expected)
                component = (
                    archive_services.project_update_transaction
                    .ProjectUpdateComponent(
                        component_ref="active-pin",
                        role="active_pin",
                        sequence=1,
                        logical_target=(
                            ".zettel-kasten/installed-version.txt"
                        ),
                        pre_sha256=(
                            archive_services.project_update_transaction
                            .digest_component(expected)
                        ),
                        post_sha256=(
                            archive_services.project_update_transaction
                            .digest_component(desired)
                        ),
                        preimage_key="active-pin-preimage",
                    )
                )

                class Guard:
                    def held_observation(self, _path):
                        return {"state": "passed", "reason_code": "verified"}

                    def hold(self, _path):
                        return True

                    def ensure_directory(self, _parent, _child):
                        return True

                state = SimpleNamespace(
                    project_root=project_root,
                    component_paths={"active-pin": target},
                    directory_guard=Guard(),
                    transaction=SimpleNamespace(
                        transaction_ref="update_" + "c" * 32,
                    ),
                )
                swap = archive_services._project_update_component_swap_path(
                    state,
                    component,
                )
                original_rename = archive_services.os.rename
                injected = False

                def inject_race(source, destination):
                    nonlocal injected
                    if (
                        not injected
                        and Path(source) == target
                        and Path(destination) == swap
                    ):
                        injected = True
                        if race_kind == "replace":
                            replacement = target.with_name("external.tmp")
                            replacement.write_bytes(external)
                            archive_services.os.replace(replacement, target)
                        else:
                            target.write_bytes(external)
                    return original_rename(source, destination)

                with mock.patch.object(
                    archive_services.os,
                    "rename",
                    side_effect=inject_race,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "project_version_update_component_compare_and_swap_failed",
                    ):
                        archive_services._project_update_exact_write_bytes(
                            state,
                            component,
                            desired,
                        )

                self.assertTrue(injected)
                self.assertEqual(target.read_bytes(), external)
                self.assertFalse(swap.exists())

    @unittest.skipUnless(
        sys.platform == "win32",
        "the approved exact publisher is Windows-only",
    )
    def test_exact_component_write_resumes_each_swap_boundary(self) -> None:
        for boundary in ("preimage_moved", "postimage_published"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                project_root = Path(tmp) / "project"
                metadata_root = project_root / ".zettel-kasten"
                metadata_root.mkdir(parents=True)
                target = metadata_root / "installed-version.txt"
                expected = b"v0.4.18\n"
                desired = b"v0.4.19\n"
                component = (
                    archive_services.project_update_transaction
                    .ProjectUpdateComponent(
                        component_ref="active-pin",
                        role="active_pin",
                        sequence=1,
                        logical_target=(
                            ".zettel-kasten/installed-version.txt"
                        ),
                        pre_sha256=(
                            archive_services.project_update_transaction
                            .digest_component(expected)
                        ),
                        post_sha256=(
                            archive_services.project_update_transaction
                            .digest_component(desired)
                        ),
                        preimage_key="active-pin-preimage",
                    )
                )

                class Guard:
                    def held_observation(self, _path):
                        return {"state": "passed", "reason_code": "verified"}

                    def hold(self, _path):
                        return True

                    def ensure_directory(self, _parent, _child):
                        return True

                state = SimpleNamespace(
                    project_root=project_root,
                    component_paths={"active-pin": target},
                    directory_guard=Guard(),
                    transaction=SimpleNamespace(
                        transaction_ref="update_" + "d" * 32,
                    ),
                )
                swap = archive_services._project_update_component_swap_path(
                    state,
                    component,
                )
                swap.write_bytes(expected)
                if boundary == "postimage_published":
                    target.write_bytes(desired)

                archive_services._project_update_exact_write_bytes(
                    state,
                    component,
                    desired,
                )

                self.assertEqual(target.read_bytes(), desired)
                self.assertFalse(swap.exists())

    @unittest.skipUnless(
        sys.platform == "win32",
        "the approved exact publisher is Windows-only",
    )
    def test_exact_component_write_never_deletes_a_writable_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            target = metadata_root / "installed-version.txt"
            expected = b"v0.4.18\n"
            desired = b"v0.4.19\n"
            target.write_bytes(desired)
            component = (
                archive_services.project_update_transaction
                .ProjectUpdateComponent(
                    component_ref="active-pin",
                    role="active_pin",
                    sequence=1,
                    logical_target=(
                        ".zettel-kasten/installed-version.txt"
                    ),
                    pre_sha256=(
                        archive_services.project_update_transaction
                        .digest_component(expected)
                    ),
                    post_sha256=(
                        archive_services.project_update_transaction
                        .digest_component(desired)
                    ),
                    preimage_key="active-pin-preimage",
                )
            )

            class Guard:
                def held_observation(self, _path):
                    return {"state": "passed", "reason_code": "verified"}

            state = SimpleNamespace(
                project_root=project_root,
                component_paths={"active-pin": target},
                directory_guard=Guard(),
                transaction=SimpleNamespace(
                    transaction_ref="update_" + "f" * 32,
                ),
            )
            swap = archive_services._project_update_component_swap_path(
                state,
                component,
            )
            swap.write_bytes(expected)

            # A writable handle that survives a name move represents the exact
            # post-verification race a plain unlink cannot make safe.  The
            # retained-handle cleanup must refuse deletion and preserve both
            # the published target and the recoverable preimage.
            with swap.open("r+b") as external_writer:
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "project_version_update_component_swap_cleanup_failed",
                ):
                    archive_services._project_update_exact_write_bytes(
                        state,
                        component,
                        desired,
                    )
                external_writer.seek(0)
                self.assertEqual(external_writer.read(), expected)
                self.assertEqual(target.read_bytes(), desired)
                self.assertEqual(swap.read_bytes(), expected)

            archive_services._project_update_exact_write_bytes(
                state,
                component,
                desired,
            )
            self.assertEqual(target.read_bytes(), desired)
            self.assertFalse(swap.exists())

    def _create_project_update_preflight_fixture(self, parent: Path) -> Path:
        project_root = parent / "project"
        mirror = project_root / ".zettel-kasten" / "source"
        files = {
            mirror / "wom-kit" / "src" / "wom_kit" / "__init__.py": (
                b'__version__ = "0.4.18"\n'
            ),
            mirror / "wom-kit" / "pyproject.toml": (
                b'[project]\nname = "wom-kit"\nversion = "0.4.18"\n'
            ),
            mirror / "wom_kit" / "__init__.py": (
                b'__version__ = "0.4.18"\n'
            ),
        }
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(
            ["git", "init", "--quiet", str(mirror)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for key, value in (
            ("user.name", "WOM Test"),
            ("user.email", "wom-test@example.invalid"),
            ("core.autocrlf", "false"),
        ):
            subprocess.run(
                ["git", "-C", str(mirror), "config", key, value],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        subprocess.run(
            [
                "git",
                "-C",
                str(mirror),
                "remote",
                "add",
                "origin",
                "https://example.invalid/wom-test.git",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "-C", str(mirror), "add", "--all"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "-C", str(mirror), "commit", "--quiet", "-m", "fixture"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (project_root / ".zettel-kasten" / "installed-version.txt").write_text(
            "v0.4.18\n",
            encoding="utf-8",
        )
        (mirror / "installed-version.txt").write_text(
            "v0.4.18\n",
            encoding="utf-8",
        )
        return project_root

    def test_update_preflight_git_unavailable_stops_later_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            original_git_observation = (
                archive_services._wom_kit_project_update_git_observation
            )
            original_metadata = (
                archive_services.wom_kit_project_update_git_metadata_evidence
            )
            original_snapshot = (
                archive_services._wom_kit_project_update_git_snapshot
            )
            cases = (
                (
                    "git_inside_worktree",
                    ["rev-parse", "--is-inside-work-tree"],
                    "git_worktree_root_exact",
                    "git_repo_verified",
                ),
                (
                    "git_worktree_root_exact",
                    ["rev-parse", "--show-toplevel"],
                    "git_metadata_local_real",
                    "git_repo_verified",
                ),
                (
                    "git_metadata_local_real",
                    None,
                    "git_head",
                    "git_repo_verified",
                ),
                (
                    "git_head",
                    ["rev-parse", "--verify", "HEAD"],
                    "git_snapshot",
                    "worktree_clean_except_untracked_local_pin",
                ),
                (
                    "git_snapshot",
                    None,
                    "source_mirror_pin_tracking",
                    "worktree_clean_except_untracked_local_pin",
                ),
                (
                    "source_mirror_pin_tracking",
                    [
                        "ls-files",
                        "--error-unmatch",
                        "--",
                        "installed-version.txt",
                    ],
                    "origin_configuration",
                    "source_mirror_pin_git_tracked",
                ),
                (
                    "origin_configuration",
                    [
                        "config",
                        "--local",
                        "--no-includes",
                        "--name-only",
                        "--get-regexp",
                        r"^remote\.origin\.url$",
                    ],
                    None,
                    "origin_configured",
                ),
            )
            for check_name, target_arguments, later_check, compatibility in cases:
                with self.subTest(check=check_name):
                    def observe_git(root, arguments, **kwargs):
                        if arguments == target_arguments:
                            return False, None, ""
                        return original_git_observation(
                            root,
                            arguments,
                            **kwargs,
                        )

                    patches = []
                    if check_name == "git_metadata_local_real":
                        patches.append(
                            mock.patch.object(
                                archive_services,
                                "wom_kit_project_update_git_metadata_evidence",
                                return_value={
                                    "state": "unavailable",
                                    "reason_code": (
                                        "project_git_metadata_observation_unavailable"
                                    ),
                                },
                            )
                        )
                    else:
                        patches.append(
                            mock.patch.object(
                                archive_services,
                                "_wom_kit_project_update_git_observation",
                                side_effect=observe_git,
                            )
                        )
                    if check_name == "git_snapshot":
                        patches.append(
                            mock.patch.object(
                                archive_services,
                                "_wom_kit_project_update_git_snapshot",
                                return_value=None,
                            )
                        )
                    with archive_services.ExitStack() as stack:
                        for patcher in patches:
                            stack.enter_context(patcher)
                        result = archive_services.wom_kit_project_version_update(
                            project_root,
                            target="v0.4.19",
                            dry_run=True,
                        )

                    self.assertEqual(result["status"], "blocked")
                    self.assertEqual(result["preflight"]["state"], "unavailable")
                    self.assertEqual(
                        result["preflight"]["checks"][check_name]["state"],
                        "unavailable",
                    )
                    if later_check is not None:
                        self.assertEqual(
                            result["preflight"]["checks"][later_check]["state"],
                            "not_reached",
                        )
                    self.assertIsNone(result["source_mirror"][compatibility])

    def test_update_preflight_path_unavailable_stops_git_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            metadata_root = project_root / ".zettel-kasten"
            cases = (
                ("inspection_root", project_root, 1),
                ("project_root", project_root, 2),
                ("metadata_root", metadata_root, None),
                ("source_mirror", metadata_root / "source", 1),
                (
                    "update_lock",
                    project_root
                    / archive_services.WOM_KIT_PROJECT_UPDATE_LOCK_RELATIVE,
                    1,
                ),
            )
            original_observer = (
                archive_services.wom_kit_real_path_kind_observation
            )
            for check_name, target_path, unavailable_occurrence in cases:
                with self.subTest(check=check_name):
                    target_calls = 0

                    def observe(root, path):
                        nonlocal target_calls
                        if path == target_path:
                            target_calls += 1
                            if (
                                unavailable_occurrence is None
                                or target_calls == unavailable_occurrence
                            ):
                                return {
                                    "state": "unavailable",
                                    "kind": "unknown",
                                }
                        return original_observer(root, path)

                    with mock.patch.object(
                        archive_services,
                        "wom_kit_real_path_kind_observation",
                        side_effect=observe,
                    ):
                        result = archive_services.wom_kit_project_version_update(
                            project_root,
                            target="v0.4.19",
                            dry_run=True,
                        )

                    self.assertEqual(result["status"], "blocked")
                    self.assertEqual(
                        result["preflight"]["checks"][check_name]["state"],
                        "unavailable",
                    )
                    self.assertEqual(
                        result["preflight"]["checks"][
                            "git_inside_worktree"
                        ]["state"],
                        "not_reached",
                    )
                    self.assertIsNone(
                        result["source_mirror"]["git_repo_verified"]
                    )

    def test_update_preflight_distinguishes_pin_and_origin_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            original_git_observation = (
                archive_services._wom_kit_project_update_git_observation
            )
            pin_arguments = [
                "ls-files",
                "--error-unmatch",
                "--",
                "installed-version.txt",
            ]
            origin_arguments = [
                "config",
                "--local",
                "--no-includes",
                "--name-only",
                "--get-regexp",
                r"^remote\.origin\.url$",
            ]

            def observe_absent_origin(root, arguments, **kwargs):
                if arguments == origin_arguments:
                    return True, 1, ""
                return original_git_observation(root, arguments, **kwargs)

            with mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=observe_absent_origin,
            ):
                absent_origin = archive_services.wom_kit_project_version_update(
                    project_root,
                    target="v0.4.19",
                    dry_run=True,
                )
            self.assertEqual(
                absent_origin["preflight"]["checks"]["origin_configuration"][
                    "state"
                ],
                "failed",
            )
            self.assertFalse(
                absent_origin["source_mirror"]["origin_configured"]
            )

            def observe_unexpected_pin(root, arguments, **kwargs):
                if arguments == pin_arguments:
                    return True, 2, ""
                return original_git_observation(root, arguments, **kwargs)

            with mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=observe_unexpected_pin,
            ):
                unknown_pin = archive_services.wom_kit_project_version_update(
                    project_root,
                    target="v0.4.19",
                    dry_run=True,
                )
            self.assertEqual(
                unknown_pin["preflight"]["checks"][
                    "source_mirror_pin_tracking"
                ]["state"],
                "unavailable",
            )
            self.assertIsNone(
                unknown_pin["source_mirror"][
                    "source_mirror_pin_git_tracked"
                ]
            )
            self.assertEqual(
                unknown_pin["preflight"]["checks"]["origin_configuration"][
                    "state"
                ],
                "not_reached",
            )

    def test_update_preflight_unavailable_active_pin_row_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            active_pin = (
                project_root / ".zettel-kasten" / "installed-version.txt"
            )
            original_observer = (
                archive_services.wom_kit_real_path_kind_observation
            )
            active_pin_calls = 0

            def observe(root, path):
                nonlocal active_pin_calls
                if path == active_pin:
                    active_pin_calls += 1
                    if active_pin_calls == 1:
                        return {"state": "unavailable", "kind": "unknown"}
                return original_observer(root, path)

            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                side_effect=observe,
            ):
                result = archive_services.wom_kit_project_version_update(
                    project_root,
                    target="v0.4.19",
                    dry_run=True,
                )

        active_rows = [
            item
            for item in result["pins"]["planned"]
            if item["role"] == "project_pin"
        ]
        self.assertEqual(len(active_rows), 1)
        self.assertIsNone(active_rows[0]["existed_before"])
        self.assertEqual(result["status"], "blocked")

    def test_source_version_metadata_observation_is_four_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            mirror = project_root / ".zettel-kasten" / "source"
            pyproject = mirror / "wom-kit" / "pyproject.toml"
            pyproject.write_text(
                '[project]\nname = "wom-kit"\nversion = "not-stable"\n',
                encoding="utf-8",
            )
            invalid = (
                archive_services
                .wom_kit_project_update_source_versions_observation(mirror)
            )
            self.assertEqual(invalid["state"], "failed")
            self.assertEqual(
                invalid["reason_code"],
                "project_source_version_metadata_invalid",
            )

            original_observer = (
                archive_services.wom_kit_real_path_kind_observation
            )
            package_init = (
                mirror / "wom-kit" / "src" / "wom_kit" / "__init__.py"
            )

            def observe(root, path):
                if path == package_init:
                    return {"state": "unavailable", "kind": "unknown"}
                return original_observer(root, path)

            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                side_effect=observe,
            ):
                unavailable = (
                    archive_services
                    .wom_kit_project_update_source_versions_observation(mirror)
                )
            self.assertEqual(unavailable["state"], "unavailable")
            self.assertEqual(
                unavailable["reason_code"],
                "project_source_version_metadata_unavailable",
            )

            package_init.write_bytes(b"\xff\xfe")
            invalid_encoding = (
                archive_services
                .wom_kit_project_update_source_versions_observation(mirror)
            )
            self.assertEqual(invalid_encoding["state"], "failed")
            self.assertEqual(
                invalid_encoding["reason_code"],
                "project_source_version_metadata_invalid",
            )

            package_init.write_bytes(
                b"x"
                * (
                    archive_services.WOM_KIT_VERSION_METADATA_MAX_BYTES
                    + 1
                )
            )
            too_large = (
                archive_services
                .wom_kit_project_update_source_versions_observation(mirror)
            )
            self.assertEqual(too_large["state"], "failed")
            self.assertEqual(
                too_large["reason_code"],
                "project_source_version_metadata_invalid",
            )

    def test_source_mirror_metadata_reads_preserve_failed_vs_unavailable(
        self,
    ) -> None:
        for role, relative, maximum in (
            (
                "source",
                Path("wom-kit/src/wom_kit/__init__.py"),
                archive_services.WOM_KIT_VERSION_METADATA_MAX_BYTES,
            ),
            (
                "pyproject",
                Path("wom-kit/pyproject.toml"),
                archive_services.WOM_KIT_VERSION_METADATA_MAX_BYTES,
            ),
            (
                "pin",
                Path("installed-version.txt"),
                archive_services.WOM_KIT_VERSION_PIN_MAX_BYTES,
            ),
        ):
            for failure_kind, expected_state in (
                ("too_large", "failed"),
                ("invalid_utf8", "failed"),
                ("io_unavailable", "unavailable"),
            ):
                with self.subTest(role=role, failure_kind=failure_kind):
                    with tempfile.TemporaryDirectory() as tmp:
                        project_root = Path(tmp) / "project"
                        mirror = project_root / ".zettel-kasten" / "source"
                        valid_files = {
                            mirror
                            / "wom-kit"
                            / "src"
                            / "wom_kit"
                            / "__init__.py": b'__version__ = "0.4.19"\n',
                            mirror / "wom-kit" / "pyproject.toml": (
                                b'[project]\nname = "wom-kit"\nversion = "0.4.19"\n'
                            ),
                            mirror / "installed-version.txt": b"v0.4.19\n",
                        }
                        for path, payload in valid_files.items():
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(payload)
                        target_path = mirror / relative
                        if failure_kind == "too_large":
                            target_path.write_bytes(b"x" * (maximum + 1))
                        elif failure_kind == "invalid_utf8":
                            target_path.write_bytes(b"\xff\xfe")

                        original_reader = (
                            archive_services._wom_kit_read_bounded_real_bytes
                        )

                        def read(root, path, **kwargs):
                            if (
                                failure_kind == "io_unavailable"
                                and path == target_path
                            ):
                                return None
                            return original_reader(root, path, **kwargs)

                        warnings: list[str] = []
                        with mock.patch.object(
                            archive_services,
                            "_wom_kit_read_bounded_real_bytes",
                            side_effect=read,
                        ):
                            result = (
                                archive_services
                                .wom_kit_project_source_mirror_info(
                                    project_root,
                                    normalized_package="0.4.19",
                                    warnings=warnings,
                                )
                            )

                    self.assertEqual(
                        result["observation_state"],
                        expected_state,
                    )
                    self.assertEqual(
                        result["status"],
                        "metadata_invalid"
                        if expected_state == "failed"
                        else "unavailable",
                    )
                    self.assertTrue(warnings)

    def test_git_output_lines_resolver_failure_is_private_unavailable(self) -> None:
        private_marker = "PRIVATE_EXECUTABLE_PATH_MARKER"
        with mock.patch.object(
            archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner,
            "resolve_preapproval",
            side_effect=OSError(private_marker),
        ):
            result = archive_services.git_output_lines_observation(
                Path("ignored"),
                ["tag", "--list", "v*"],
            )

        self.assertEqual(result["state"], "unavailable")
        self.assertEqual(
            result["reason_code"],
            "project_source_git_observation_unavailable",
        )
        self.assertEqual(result["lines"], [])
        self.assertNotIn(private_marker, json.dumps(result, sort_keys=True))

        with mock.patch.object(
            archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner,
            "resolve_preapproval",
            side_effect=OSError(private_marker),
        ):
            metadata = (
                archive_services
                .wom_kit_project_update_git_metadata_evidence_legacy_read_only(
                    Path("ignored"),
                    Path("ignored/source"),
                )
            )
            integrity = archive_services.wom_kit_runtime_mirror_integrity(
                Path("ignored"),
                Path("ignored/source"),
                None,
                Path("ignored/source/archive.py"),
                source_version="0.4.19",
            )
        self.assertEqual(metadata["state"], "unavailable")
        self.assertEqual(metadata["reason_code"], "project_git_metadata_unavailable")
        self.assertFalse(integrity["verified"])
        self.assertEqual(
            integrity["reason_code"],
            "project_git_runner_observation_unavailable",
        )
        self.assertEqual(
            integrity["checks"]["git_worktree_root_exact"]["state"],
            "unavailable",
        )
        serialized = json.dumps(
            {"metadata": metadata, "integrity": integrity},
            sort_keys=True,
        )
        self.assertNotIn(private_marker, serialized)

    def test_completed_git_invalid_output_is_failed_not_unavailable(self) -> None:
        with (
            mock.patch.object(
                archive_services,
                "wom_kit_project_update_git_command",
                return_value=["trusted-git"],
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_project_update_git_environment",
                return_value={},
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_run_capped",
                return_value=(0, b"\xff"),
            ),
        ):
            available, return_code, output = (
                archive_services._wom_kit_project_update_git_observation(
                    Path("ignored"),
                    ["rev-parse", "--verify", "HEAD"],
                    runner=object(),
                )
            )
        self.assertTrue(available)
        self.assertEqual(
            return_code,
            archive_services.WOM_KIT_PROJECT_UPDATE_GIT_OUTPUT_INVALID_RETURN_CODE,
        )
        self.assertEqual(output, "")

        runner = mock.Mock()
        with (
            mock.patch.object(
                archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner,
                "resolve_preapproval",
                return_value=runner,
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                return_value=(True, 2, "private-output-must-not-escape"),
            ),
        ):
            lines = archive_services.git_output_lines_observation(
                Path("ignored"),
                ["tag", "--list", "v*"],
            )
        self.assertEqual(lines["state"], "failed")
        self.assertEqual(lines["lines"], [])
        self.assertNotIn("private-output", json.dumps(lines, sort_keys=True))

    def test_git_metadata_completed_invalid_probe_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror = project_root / "source"
            (mirror / ".git").mkdir(parents=True)
            with mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                return_value=(True, 2, "private-output-must-not-escape"),
            ):
                result = (
                    archive_services.wom_kit_project_update_git_metadata_evidence(
                        project_root,
                        mirror,
                        runner=object(),
                    )
                )
        self.assertEqual(result["state"], "failed")
        self.assertEqual(
            result["reason_code"],
            "project_git_metadata_not_local_real",
        )
        self.assertNotIn("private-output", json.dumps(result, sort_keys=True))

    def test_version_info_pin_read_preserves_failed_vs_unavailable(self) -> None:
        for failure_kind, expected_state in (
            ("too_large", "failed"),
            ("invalid_utf8", "failed"),
            ("io_unavailable", "unavailable"),
        ):
            with self.subTest(failure_kind=failure_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    project_root = Path(tmp) / "project"
                    metadata_root = project_root / ".zettel-kasten"
                    metadata_root.mkdir(parents=True)
                    pin = metadata_root / "installed-version.txt"
                    pin.write_bytes(b"v0.4.19\n")
                    if failure_kind == "too_large":
                        pin.write_bytes(
                            b"x"
                            * (
                                archive_services.WOM_KIT_VERSION_PIN_MAX_BYTES
                                + 1
                            )
                        )
                    elif failure_kind == "invalid_utf8":
                        pin.write_bytes(b"\xff\xfe")
                    original_reader = (
                        archive_services._wom_kit_read_bounded_real_bytes
                    )

                    def read(root, path, **kwargs):
                        if failure_kind == "io_unavailable" and path == pin:
                            return None
                        return original_reader(root, path, **kwargs)

                    with mock.patch.object(
                        archive_services,
                        "_wom_kit_read_bounded_real_bytes",
                        side_effect=read,
                    ):
                        result = archive_services.wom_kit_version_info(
                            project_root
                        )

                pin_result = result["project_pin"]
                self.assertEqual(pin_result["observation_state"], expected_state)
                self.assertEqual(
                    pin_result["status"],
                    "invalid" if expected_state == "failed" else "unavailable",
                )
                self.assertEqual(
                    pin_result["observation_reason_code"],
                    "project_pin_invalid"
                    if expected_state == "failed"
                    else "project_pin_observation_unavailable",
                )

    def test_version_consistency_prioritizes_deterministic_pin_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            (metadata_root / "installed-version.txt").write_text(
                "not-a-version\n",
                encoding="utf-8",
            )
            source_summary = {
                "checked": True,
                "status": "present",
                "source_version": archive_services.WOM_KIT_VERSION,
                "source_matches_running_version": True,
                "mirror_behind_latest_fetched_tag": False,
                "observation_state": "passed",
                "observation_reason_code": "verified",
            }
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_project_source_mirror_info",
                    return_value=source_summary,
                ),
                mock.patch.object(
                    archive_services,
                    "wom_kit_runtime_alignment",
                    return_value=(
                        {
                            "status": "project_source_update_required",
                            "reason_code": "project_pin_missing_or_invalid",
                        },
                        [],
                    ),
                ),
            ):
                result = archive_services.wom_kit_version_info(project_root)
        self.assertEqual(result["consistency_state"], "project_pin_mismatch")
        self.assertFalse(result["ok"])

    def test_target_evidence_distinguishes_failed_git_content_from_unavailable(
        self,
    ) -> None:
        head = "a" * 40
        tag_ref = "refs/tags/v0.4.19"
        base_observations = {
            ("show-ref", "--verify", "--quiet", tag_ref): (True, 0, ""),
            ("cat-file", "-t", tag_ref): (True, 0, "tag"),
            ("rev-parse", "--verify", f"{tag_ref}^{{commit}}"): (
                True,
                0,
                head,
            ),
            (
                "show-ref",
                "--verify",
                "--quiet",
                "refs/remotes/origin/main",
            ): (True, 0, ""),
            (
                "merge-base",
                "--is-ancestor",
                head,
                "refs/remotes/origin/main",
            ): (True, 0, ""),
        }

        def valid_blob(_root, object_spec, _size, **_kwargs):
            content = (
                b'[project]\nname = "wom-kit"\nversion = "0.4.19"\n'
                if object_spec.endswith("wom-kit/pyproject.toml")
                else b'__version__ = "0.4.19"\n'
            )
            return {"state": "passed", "reason_code": "verified", "blob": content}

        cases = (
            (
                ("show-ref", "--verify", "--quiet", tag_ref),
                (True, 2, ""),
                "project_target_tag_probe_failed",
            ),
            (
                ("cat-file", "-t", tag_ref),
                (True, 2, ""),
                "project_target_tag_object_invalid",
            ),
            (
                ("rev-parse", "--verify", f"{tag_ref}^{{commit}}"),
                (True, 2, ""),
                "project_target_commit_unresolvable",
            ),
            (
                ("cat-file", "-s", f"{head}:wom-kit/src/wom_kit/__init__.py"),
                (True, 2, ""),
                "project_target_source_metadata_missing",
            ),
            (
                ("cat-file", "-s", f"{head}:wom-kit/src/wom_kit/__init__.py"),
                (True, 0, "not-a-size"),
                "project_target_source_metadata_invalid",
            ),
            (
                (
                    "show-ref",
                    "--verify",
                    "--quiet",
                    "refs/remotes/origin/main",
                ),
                (True, 2, ""),
                "project_origin_main_probe_failed",
            ),
            (
                (
                    "merge-base",
                    "--is-ancestor",
                    head,
                    "refs/remotes/origin/main",
                ),
                (True, 2, ""),
                "project_target_ancestry_probe_failed",
            ),
        )
        for failing_args, failing_result, reason_code in cases:
            with self.subTest(reason_code=reason_code):
                def observe(_root, arguments, **_kwargs):
                    arguments_key = tuple(arguments)
                    if arguments_key == failing_args:
                        return failing_result
                    if arguments_key[:2] == ("cat-file", "-s"):
                        object_spec = arguments_key[2]
                        content_size = (
                            len(b'[project]\nname = "wom-kit"\nversion = "0.4.19"\n')
                            if object_spec.endswith("wom-kit/pyproject.toml")
                            else len(b'__version__ = "0.4.19"\n')
                        )
                        return True, 0, str(content_size)
                    return base_observations[arguments_key]

                with (
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_observation",
                        side_effect=observe,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_wom_kit_project_update_git_blob_observation",
                        side_effect=valid_blob,
                    ),
                ):
                    result = archive_services.wom_kit_project_update_target_evidence(
                        Path("ignored"),
                        "v0.4.19",
                        runner=object(),
                    )
                self.assertEqual(result["observation_state"], "failed")
                self.assertEqual(result["observation_reason_code"], reason_code)

        with (
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=lambda _root, arguments, **_kwargs: (
                    (True, 0, "25")
                    if tuple(arguments)[:2] == ("cat-file", "-s")
                    else base_observations[tuple(arguments)]
                ),
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_blob_observation",
                return_value={
                    "state": "passed",
                    "reason_code": "verified",
                    "blob": b"\xff",
                },
            ),
        ):
            invalid_utf8 = archive_services.wom_kit_project_update_target_evidence(
                Path("ignored"),
                "v0.4.19",
                runner=object(),
            )
        self.assertEqual(invalid_utf8["observation_state"], "failed")
        self.assertEqual(
            invalid_utf8["observation_reason_code"],
            "project_target_source_metadata_invalid",
        )

        with (
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=lambda _root, arguments, **_kwargs: (
                    (True, 0, "25")
                    if tuple(arguments)[:2] == ("cat-file", "-s")
                    else base_observations[tuple(arguments)]
                ),
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_blob_observation",
                return_value={
                    "state": "unavailable",
                    "reason_code": "project_git_blob_observation_unavailable",
                    "blob": None,
                },
            ),
        ):
            unavailable_blob = (
                archive_services.wom_kit_project_update_target_evidence(
                    Path("ignored"),
                    "v0.4.19",
                    runner=object(),
                )
            )
        self.assertEqual(unavailable_blob["observation_state"], "unavailable")
        self.assertEqual(
            unavailable_blob["observation_reason_code"],
            "project_target_evidence_unavailable",
        )

    def test_runtime_git_helpers_distinguish_malformed_from_unavailable(
        self,
    ) -> None:
        for observed, expected_state in (
            ((False, None, ""), "unavailable"),
            ((True, 2, ""), "failed"),
            ((True, 0, "malformed-tree-record"), "failed"),
        ):
            with self.subTest(helper="head-python", observed=observed):
                with mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_git_observation",
                    return_value=observed,
                ):
                    result = (
                        archive_services
                        .wom_kit_runtime_head_python_entries_observation(
                            Path("ignored"),
                            runner=object(),
                        )
                    )
                self.assertEqual(result["state"], expected_state)

        for observed, expected_state in (
            ((False, None, ""), "unavailable"),
            ((True, 2, ""), "failed"),
            ((True, 0, "bad"), "failed"),
        ):
            with self.subTest(helper="all-index-flags", observed=observed):
                with mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_git_observation",
                    return_value=observed,
                ):
                    result = (
                        archive_services
                        .wom_kit_runtime_all_tracked_index_flags_evidence(
                            Path("ignored"),
                            runner=object(),
                        )
                    )
                self.assertEqual(result["state"], expected_state)

        tag = "v0.4.19"
        for available, return_code, expected_state in (
            (False, None, "unavailable"),
            (True, 2, "failed"),
        ):
            with self.subTest(helper="target-refs", return_code=return_code):
                with mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_git_observation",
                    return_value=(available, return_code, ""),
                ):
                    result = (
                        archive_services
                        .wom_kit_project_update_target_ref_snapshot_observation(
                            Path("ignored"),
                            tag,
                            runner=object(),
                        )
                    )
                self.assertEqual(result["state"], expected_state)

        def branch_observe(_root, arguments, **_kwargs):
            if arguments[0] == "check-ref-format":
                return True, 0, "main"
            return True, 2, ""

        with mock.patch.object(
            archive_services,
            "_wom_kit_project_update_git_observation",
            side_effect=branch_observe,
        ):
            branch = archive_services.wom_kit_project_update_branch_observation(
                Path("ignored"),
                "main",
                "a" * 40,
                runner=object(),
            )
        self.assertEqual(branch["state"], "failed")
        self.assertEqual(
            branch["reason_code"],
            "project_source_branch_binding_invalid",
        )

        for size_observation, expected_state in (
            ((False, None, ""), "unavailable"),
            ((True, 2, ""), "failed"),
            ((True, 0, "not-a-size"), "failed"),
        ):
            with self.subTest(helper="resource-blob", size=size_observation):
                observations = iter(
                    [
                        (
                            True,
                            0,
                            "100644 blob " + "a" * 40 + "\tmanifest.json\0",
                        ),
                        size_observation,
                    ]
                )
                with mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_git_observation",
                    side_effect=lambda *_args, **_kwargs: next(observations),
                ):
                    resource = archive_services.wom_kit_runtime_git_blob_at_ref_observation(
                        Path("ignored"),
                        "HEAD",
                        "manifest.json",
                        max_bytes=1024,
                        runner=object(),
                    )
                self.assertEqual(resource["state"], expected_state)

    def test_bounded_bytes_and_source_inventory_preserve_invalid_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            oversized = root / "oversized.bin"
            oversized.write_bytes(b"xx")
            observation = (
                archive_services._wom_kit_read_bounded_real_bytes_observation(
                    root,
                    oversized,
                    max_bytes=1,
                )
            )
            self.assertEqual(observation["state"], "failed")
            self.assertEqual(
                observation["reason_code"],
                "bounded_bytes_size_policy_exceeded",
            )

            mirror = root / "mirror"
            package_root = mirror / "wom-kit" / "src" / "wom_kit"
            package_root.mkdir(parents=True)
            (package_root / "one.py").write_text("pass\n", encoding="utf-8")
            (package_root / "two.py").write_text("pass\n", encoding="utf-8")
            with mock.patch.object(
                archive_services,
                "WOM_KIT_RUNTIME_MAX_SOURCE_TREE_ENTRIES",
                1,
            ):
                inventory = archive_services.wom_kit_runtime_source_tree_inventory(
                    root,
                    mirror,
                    {
                        "wom-kit/src/wom_kit/one.py",
                        "wom-kit/src/wom_kit/two.py",
                    },
                )
        self.assertEqual(
            inventory["reason_code"],
            "project_runtime_source_tree_entry_limit_exceeded",
        )

    def test_git_snapshot_distinguishes_process_loss_from_invalid_result(self) -> None:
        symbolic = {
            "state": "passed",
            "reason_code": "verified",
            "head_state": "detached",
            "branch": None,
        }
        for observed, expected_state in (
            ((False, None, ""), "unavailable"),
            ((True, 2, ""), "failed"),
        ):
            with self.subTest(expected_state=expected_state), mock.patch.object(
                archive_services,
                "wom_kit_project_update_symbolic_head_observation",
                return_value=symbolic,
            ), mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                return_value=observed,
            ):
                result = (
                    archive_services
                    ._wom_kit_project_update_git_snapshot_observation(
                        Path("ignored"),
                        runner=object(),
                    )
                )
            self.assertEqual(result["state"], expected_state)
            self.assertIsNone(result["snapshot"])

    def test_update_preflight_source_version_truth_stops_transaction_checks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            for state, reason in (
                (
                    "unavailable",
                    "project_source_version_metadata_unavailable",
                ),
                ("failed", "project_source_version_metadata_invalid"),
            ):
                with self.subTest(state=state):
                    with mock.patch.object(
                        archive_services,
                        "wom_kit_project_update_source_versions_observation",
                        return_value={
                            "state": state,
                            "reason_code": reason,
                            "versions": {
                                "package": None,
                                "pyproject": None,
                                "root_shim": None,
                            },
                        },
                    ):
                        result = (
                            archive_services.wom_kit_project_version_update(
                                project_root,
                                target="v0.4.19",
                                dry_run=True,
                            )
                        )

                    checks = result["preflight"]["checks"]
                    self.assertEqual(
                        checks["source_version_metadata"]["state"],
                        state,
                    )
                    self.assertEqual(
                        checks["git_transaction_snapshot"]["state"],
                        "not_reached",
                    )
                    self.assertEqual(
                        checks["git_config_trust"]["state"],
                        "not_reached",
                    )
                    self.assertEqual(
                        result["target"]["observation_state"],
                        "not_reached",
                    )
                    self.assertEqual(result["status"], "blocked")

    def test_update_preflight_second_git_observations_are_authoritative(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            original_snapshot = (
                archive_services._wom_kit_project_update_git_snapshot
            )
            snapshot_calls = 0

            def unavailable_second_snapshot(root, **kwargs):
                nonlocal snapshot_calls
                snapshot_calls += 1
                if snapshot_calls == 2:
                    return None
                return original_snapshot(root, **kwargs)

            with mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_snapshot",
                side_effect=unavailable_second_snapshot,
            ):
                snapshot_result = (
                    archive_services.wom_kit_project_version_update(
                        project_root,
                        target="v0.4.19",
                        dry_run=True,
                    )
                )
            snapshot_checks = snapshot_result["preflight"]["checks"]
            self.assertEqual(snapshot_checks["git_snapshot"]["state"], "passed")
            self.assertEqual(
                snapshot_checks["git_transaction_snapshot"]["state"],
                "unavailable",
            )
            self.assertEqual(
                snapshot_checks["git_config_trust"]["state"],
                "not_reached",
            )
            self.assertEqual(
                snapshot_result["target"]["observation_state"],
                "not_reached",
            )

            with mock.patch.object(
                archive_services,
                "wom_kit_project_update_git_config_trust_digest",
                return_value=None,
            ):
                config_result = archive_services.wom_kit_project_version_update(
                    project_root,
                    target="v0.4.19",
                    dry_run=True,
                )
            config_checks = config_result["preflight"]["checks"]
            self.assertEqual(
                config_checks["git_transaction_snapshot"]["state"],
                "passed",
            )
            self.assertEqual(
                config_checks["git_config_trust"]["state"],
                "unavailable",
            )
            self.assertEqual(
                config_result["target"]["observation_state"],
                "not_reached",
            )

    def test_update_preflight_invalid_target_evidence_is_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = self._create_project_update_preflight_fixture(
                Path(tmp)
            )
            result = archive_services.wom_kit_project_version_update(
                project_root,
                target="invalid-target",
                dry_run=True,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["target"]["observation_state"], "not_reached")
        self.assertEqual(
            result["target"]["observation_reason_code"],
            "project_target_evidence_not_reached",
        )

    def test_source_mirror_unsafe_paths_have_failed_observation_reason(self) -> None:
        cases = (
            (
                "mirror",
                lambda root: root / ".zettel-kasten" / "source",
                "project_source_mirror_path_unsafe",
            ),
            (
                "source_init",
                lambda root: (
                    root
                    / ".zettel-kasten"
                    / "source"
                    / "wom-kit"
                    / "src"
                    / "wom_kit"
                    / "__init__.py"
                ),
                "project_source_init_path_unsafe",
            ),
            (
                "pyproject",
                lambda root: (
                    root
                    / ".zettel-kasten"
                    / "source"
                    / "wom-kit"
                    / "pyproject.toml"
                ),
                "project_source_pyproject_path_unsafe",
            ),
            (
                "mirror_pin",
                lambda root: (
                    root
                    / ".zettel-kasten"
                    / "source"
                    / "installed-version.txt"
                ),
                "project_source_pin_path_unsafe",
            ),
        )
        for label, unsafe_path_for, expected_reason in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                mirror = root / ".zettel-kasten" / "source"
                root.mkdir()
                if label != "mirror":
                    mirror.mkdir(parents=True)
                unsafe_path = unsafe_path_for(root)
                original_observer = (
                    archive_services.wom_kit_real_path_kind_observation
                )

                def observe(observation_root, path):
                    if path == unsafe_path:
                        return {"state": "failed", "kind": "unsafe"}
                    return original_observer(observation_root, path)

                warnings = []
                with mock.patch.object(
                    archive_services,
                    "wom_kit_real_path_kind_observation",
                    side_effect=observe,
                ):
                    result = archive_services.wom_kit_project_source_mirror_info(
                        root,
                        normalized_package="0.4.19",
                        warnings=warnings,
                    )

                self.assertEqual(result["status"], "unsafe_path")
                self.assertEqual(result["observation_state"], "failed")
                self.assertEqual(
                    result["observation_reason_code"],
                    expected_reason,
                )
                self.assertTrue(warnings)

    def test_version_pin_root_binding_failure_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            with mock.patch.object(
                archive_services,
                "wom_kit_version_pin_search_roots_observation",
                return_value={
                    "state": "failed",
                    "reason_code": "project_archive_root_binding_unsafe",
                    "roots": [("inspection_root", root)],
                },
            ):
                result = archive_services.wom_kit_version_info(root)

        self.assertEqual(result["project_pin"]["status"], "unsafe_path")
        self.assertEqual(
            result["project_pin"]["observation_state"],
            "failed",
        )
        self.assertEqual(
            result["project_pin"]["observation_reason_code"],
            "project_archive_root_binding_unsafe",
        )
        self.assertEqual(result["project_pin"]["checked_locations"], [])

    def test_runtime_alignment_consumes_failed_search_root_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            failed = {
                "state": "failed",
                "reason_code": "project_archive_root_binding_unsafe",
                "roots": [("inspection_root", root)],
            }
            passed = {
                "state": "passed",
                "reason_code": "verified",
                "roots": [("inspection_root", root)],
            }
            project_pin = {
                "status": "present",
                "path": ".zettel-kasten/installed-version.txt",
                "installed_version": "v0.4.19",
            }
            source_mirror = {
                "status": "present",
                "source_version": "0.4.19",
                "pyproject_version": "0.4.19",
            }
            for observations, expected_calls in (
                ([failed], 1),
                ([passed, failed], 2),
            ):
                with self.subTest(expected_calls=expected_calls):
                    with mock.patch.object(
                        archive_services,
                        "wom_kit_version_pin_search_roots_observation",
                        side_effect=observations,
                    ) as search:
                        alignment, _ = archive_services.wom_kit_runtime_alignment(
                            root,
                            package_version="0.4.19",
                            project_pin=project_pin,
                            project_source_mirror=source_mirror,
                            redact_local_paths=True,
                        )

                    self.assertEqual(search.call_count, expected_calls)
                    self.assertEqual(
                        alignment["status"],
                        "project_source_update_required",
                    )
                    self.assertEqual(
                        alignment["reason_code"],
                        "project_archive_root_binding_unsafe",
                    )
                    self.assertEqual(
                        alignment["integrity"]["reason_code"],
                        "project_archive_root_binding_unsafe",
                    )

    def test_source_observation_unavailable_makes_version_info_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            unavailable_source = {
                "checked": True,
                "status": "unavailable",
                "source_version": None,
                "pyproject_version": None,
                "observation_state": "unavailable",
                "observation_reason_code": "project_source_probe_unavailable",
            }
            with (
                mock.patch.object(
                    archive_services,
                    "wom_kit_project_source_mirror_info",
                    return_value=unavailable_source,
                ),
                mock.patch.object(
                    archive_services,
                    "wom_kit_windows_path_shadow_info",
                    return_value={"reason_codes": []},
                ),
            ):
                result = archive_services.wom_kit_version_info(root)

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["runtime_alignment"]["status"],
            "project_source_observation_unavailable",
        )
        self.assertTrue(
            any(
                "project source observation is unavailable" in warning
                for warning in result["warnings"]
            )
        )

    def test_tracked_python_real_git_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror = project_root / ".zettel-kasten" / "source"
            files = {
                mirror / "wom-kit" / "cli" / "archive.py": b"pass\n",
                mirror / "wom-kit" / "src" / "wom_kit" / "__init__.py": (
                    b'__version__ = "0.4.19"\n'
                ),
                mirror / "wom-kit" / "src" / "wom_kit" / "archive_cli.py": (
                    b"pass\n"
                ),
            }
            for path, content in files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            subprocess.run(
                ["git", "init", "--quiet", str(mirror)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for key, value in (
                ("user.name", "WOM Test"),
                ("user.email", "wom-test@example.invalid"),
            ):
                subprocess.run(
                    ["git", "-C", str(mirror), "config", key, value],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            subprocess.run(
                ["git", "-C", str(mirror), "add", "--all"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "-C", str(mirror), "commit", "--quiet", "-m", "fixture"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            runner = (
                archive_services.project_update_git_runner
                .TrustedProjectUpdateGitRunner.resolve_preapproval()
            )
            try:
                runner.close_transport_boundary()
                result = archive_services.wom_kit_runtime_tracked_python_integrity(
                    project_root,
                    mirror,
                    runner=runner,
                )
            finally:
                runner.close()

        self.assertEqual(result["reason_code"], "verified")
        self.assertTrue(result["tracked_python_sources_verified"])
        self.assertTrue(result["checks"])
        self.assertTrue(
            all(
                check["state"] == "passed"
                for check in result["checks"].values()
            )
        )

    def test_tracked_python_unavailable_does_not_fail_later_checks(self) -> None:
        with mock.patch.object(
            archive_services,
            "wom_kit_runtime_head_python_entries_observation",
            return_value={
                "state": "unavailable",
                "reason_code": "project_tracked_python_source_set_unavailable",
                "entries": None,
            },
        ):
            result = archive_services.wom_kit_runtime_tracked_python_integrity(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["wrapper_tracked_at_head"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["tracked_python_source_set_complete"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["tracked_python_index_flags_safe"]["state"],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["tracked_python_worktree_bytes_match_head"][
                "state"
            ],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["tracked_python_sources_verified"]["state"],
            "unavailable",
        )

    def test_tracked_python_known_incomplete_is_failed_not_unavailable(self) -> None:
        wrapper = archive_services.WOM_KIT_RUNTIME_WRAPPER_GIT_PATH
        with mock.patch.object(
            archive_services,
            "wom_kit_runtime_head_python_entries_observation",
            return_value={
                "state": "passed",
                "reason_code": "verified",
                "entries": {wrapper: ("100644", "a" * 40)},
            },
        ):
            result = archive_services.wom_kit_runtime_tracked_python_integrity(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["wrapper_tracked_at_head"]["state"],
            "passed",
        )
        self.assertEqual(
            result["checks"]["tracked_python_source_set_complete"]["state"],
            "failed",
        )
        self.assertEqual(
            result["checks"]["tracked_python_index_flags_safe"]["state"],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["tracked_python_sources_verified"]["state"],
            "failed",
        )

    def test_source_tree_access_failure_is_unavailable(self) -> None:
        with mock.patch.object(
            archive_services,
            "wom_kit_real_path_kind_observation",
            return_value={"state": "unavailable", "kind": "unknown"},
        ):
            result = archive_services.wom_kit_runtime_source_tree_inventory(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                {
                    "wom-kit/src/wom_kit/__init__.py",
                    "wom-kit/src/wom_kit/archive_cli.py",
                },
            )

        self.assertEqual(
            result["reason_code"],
            "project_runtime_python_inventory_unavailable",
        )
        self.assertFalse(result["runtime_source_tree_path_components_real"])

    def test_tracked_python_path_access_failure_is_unavailable(self) -> None:
        tracked_paths = sorted(
            archive_services.WOM_KIT_RUNTIME_REQUIRED_PYTHON_PATHS
        )
        head_entries = {
            path: ("100644", format(index + 1, "040x"))
            for index, path in enumerate(tracked_paths)
        }
        flags_text = "".join(f"H {path}\0" for path in tracked_paths)
        index_text = "".join(
            f"100644 {head_entries[path][1]} 0\t{path}\0"
            for path in tracked_paths
        )

        def fake_git(_root, arguments, **_kwargs):
            if arguments[0:3] == ["ls-files", "-v", "-z"]:
                return True, 0, flags_text
            if arguments[0:3] == ["ls-files", "--stage", "-z"]:
                return True, 0, index_text
            raise AssertionError(arguments)

        with (
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_head_python_entries_observation",
                return_value={
                    "state": "passed",
                    "reason_code": "verified",
                    "entries": head_entries,
                },
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=fake_git,
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value={"state": "unavailable", "kind": "unknown"},
            ),
        ):
            result = archive_services.wom_kit_runtime_tracked_python_integrity(
                Path("synthetic-project"),
                Path("synthetic-project") / "source",
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["tracked_python_path_components_real"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["tracked_python_sources_verified"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["runtime_source_tree_path_components_real"][
                "state"
            ],
            "not_reached",
        )

    def test_resource_probe_unavailable_does_not_fail_unreached_checks(self) -> None:
        with mock.patch.object(
            archive_services,
            "wom_kit_runtime_all_tracked_index_flags_evidence",
            return_value={
                "safe": False,
                "entry_count": 0,
                "state": "unavailable",
                "reason_code": "project_tracked_index_flags_unavailable",
            },
        ):
            result = archive_services.wom_kit_runtime_resource_integrity(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["all_tracked_index_flags_safe"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["runtime_resource_manifest_verified"]["state"],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["runtime_resources_verified"]["state"],
            "unavailable",
        )

    def test_resource_manifest_probe_unavailable_preserves_passed_flags(self) -> None:
        with (
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_all_tracked_index_flags_evidence",
                return_value={
                    "safe": True,
                    "entry_count": 12,
                    "state": "passed",
                    "reason_code": "verified",
                },
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_git_blob_at_ref_observation",
                return_value={
                    "state": "unavailable",
                    "reason_code": (
                        "project_runtime_resource_manifest_unavailable"
                    ),
                    "blob": None,
                },
            ),
        ):
            result = archive_services.wom_kit_runtime_resource_integrity(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["all_tracked_index_flags_safe"]["state"],
            "passed",
        )
        self.assertEqual(
            result["checks"]["runtime_resource_manifest_verified"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["runtime_resource_index_matches_head"]["state"],
            "not_reached",
        )

    def test_resource_manifest_confirmed_missing_is_failed(self) -> None:
        with (
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_all_tracked_index_flags_evidence",
                return_value={
                    "safe": True,
                    "entry_count": 12,
                    "state": "passed",
                    "reason_code": "verified",
                },
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_git_blob_at_ref_observation",
                return_value={
                    "state": "failed",
                    "reason_code": "project_runtime_resource_manifest_missing",
                    "blob": None,
                },
            ),
        ):
            result = archive_services.wom_kit_runtime_resource_integrity(
                Path("synthetic-project"),
                Path("synthetic-mirror"),
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["runtime_resource_manifest_verified"]["state"],
            "failed",
        )
        self.assertEqual(
            result["reason_code"],
            "project_runtime_resource_manifest_missing",
        )

    def test_resource_path_access_failure_is_unavailable(self) -> None:
        resource_bytes = b""
        manifest_bytes = json.dumps(
            {
                "schema": "wom-kit/package-resource-manifest/v0.1",
                "file_count": 1,
                "files": [
                    {
                        "source": "docs/example.txt",
                        "packaged": "docs/example.txt",
                        "bytes": len(resource_bytes),
                        "sha256": archive_services.hashlib.sha256(
                            resource_bytes
                        ).hexdigest(),
                    }
                ],
            },
            sort_keys=True,
        ).encode("utf-8")
        manifest_path = archive_services.WOM_KIT_RUNTIME_RESOURCE_MANIFEST_GIT_PATH
        source_path = "wom-kit/docs/example.txt"
        packaged_path = "wom-kit/src/wom_kit/_resources/docs/example.txt"
        entries = {
            manifest_path: "1" * 40,
            source_path: "2" * 40,
            packaged_path: "3" * 40,
        }
        tree_text = "".join(
            f"100644 blob {object_id}\t{path}\0"
            for path, object_id in sorted(entries.items())
        )
        index_text = "".join(
            f"100644 {object_id} 0\t{path}\0"
            for path, object_id in sorted(entries.items())
        )

        def fake_git(_root, arguments, **_kwargs):
            if arguments[0:2] == ["ls-tree", "-z"]:
                return True, 0, tree_text
            if arguments[0:3] == ["ls-files", "--stage", "-z"]:
                return True, 0, index_text
            raise AssertionError(arguments)

        with (
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_all_tracked_index_flags_evidence",
                return_value={
                    "safe": True,
                    "entry_count": 3,
                    "state": "passed",
                    "reason_code": "verified",
                },
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_runtime_git_blob_at_ref_observation",
                return_value={
                    "state": "passed",
                    "reason_code": "verified",
                    "blob": (entries[manifest_path], manifest_bytes),
                },
            ),
            mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                side_effect=fake_git,
            ),
            mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                return_value={"state": "unavailable", "kind": "unknown"},
            ),
        ):
            result = archive_services.wom_kit_runtime_resource_integrity(
                Path("synthetic-project"),
                Path("synthetic-project") / "source",
                runner=object(),
            )

        self.assertEqual(
            result["checks"]["runtime_resource_path_components_real"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["runtime_resources_verified"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["checks"]["runtime_resource_worktree_bytes_match_head"][
                "state"
            ],
            "not_reached",
        )

    def test_integrity_evidence_keeps_later_checks_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            missing_mirror = project_root / ".zettel-kasten" / "source"
            result = archive_services._wom_kit_runtime_mirror_integrity_with_runner(
                project_root,
                missing_mirror,
                None,
                missing_mirror / "wom-kit" / "cli" / "archive.py",
                source_version="0.4.19",
                runner=object(),
            )

        self.assertFalse(result["verified"])
        self.assertEqual(
            result["checks"]["mirror_real_directory_inside_project"]["state"],
            "failed",
        )
        self.assertFalse(result["origin_configured"])
        self.assertEqual(
            result["checks"]["origin_configured"]["state"],
            "not_reached",
        )
        self.assertEqual(
            result["checks"]["source_tag_at_head"]["state"],
            "not_reached",
        )

    def test_mirror_path_resolution_error_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror = project_root / ".zettel-kasten" / "source"
            wrapper = mirror / "wom-kit" / "cli" / "archive.py"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("pass\n", encoding="utf-8")
            pin = mirror / "installed-version.txt"
            pin.write_text("0.4.19\n", encoding="utf-8")

            def fake_git(_root, arguments, **_kwargs):
                if arguments == ["rev-parse", "--is-inside-work-tree"]:
                    return True, 0, "true"
                if arguments == ["rev-parse", "--show-toplevel"]:
                    return True, 0, str(mirror)
                raise AssertionError(arguments)

            original_resolve = Path.resolve

            def failing_resolve(path, *args, **kwargs):
                if path == mirror:
                    raise OSError("synthetic access failure")
                return original_resolve(path, *args, **kwargs)

            with (
                mock.patch.object(
                    archive_services,
                    "_wom_kit_project_update_git_observation",
                    side_effect=fake_git,
                ),
                mock.patch.object(Path, "resolve", failing_resolve),
            ):
                result = (
                    archive_services
                    ._wom_kit_runtime_mirror_integrity_with_runner(
                        project_root,
                        mirror,
                        pin,
                        wrapper,
                        source_version="0.4.19",
                        runner=object(),
                    )
                )

        self.assertEqual(
            result["checks"]["git_worktree_root_exact"]["state"],
            "unavailable",
        )
        self.assertEqual(
            result["reason_code"],
            "project_git_worktree_root_unavailable",
        )
        self.assertEqual(
            result["checks"]["git_metadata_local_real"]["state"],
            "not_reached",
        )

    def test_mirror_completed_invalid_git_probe_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror = project_root / ".zettel-kasten" / "source"
            wrapper = mirror / "wom-kit" / "cli" / "archive.py"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("pass\n", encoding="utf-8")
            pin = mirror / "installed-version.txt"
            pin.write_text("0.4.19\n", encoding="utf-8")
            with mock.patch.object(
                archive_services,
                "_wom_kit_project_update_git_observation",
                return_value=(True, 2, "private-output-must-not-escape"),
            ):
                result = (
                    archive_services
                    ._wom_kit_runtime_mirror_integrity_with_runner(
                        project_root,
                        mirror,
                        pin,
                        wrapper,
                        source_version="0.4.19",
                        runner=object(),
                    )
                )
        self.assertEqual(
            result["checks"]["git_worktree_root_exact"]["state"],
            "failed",
        )
        self.assertEqual(
            result["reason_code"],
            "project_git_worktree_root_unverified",
        )
        self.assertNotIn("private-output", json.dumps(result, sort_keys=True))

    def test_target_evidence_unavailable_stops_at_first_unresolved_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            mirror = project_root / ".zettel-kasten" / "source"
            wrapper = mirror / "wom-kit" / "cli" / "archive.py"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("pass\n", encoding="utf-8")
            pin = mirror / "installed-version.txt"
            pin.write_text("0.4.19\n", encoding="utf-8")
            head = "a" * 40
            passed_children = archive_services.wom_kit_runtime_integrity_evidence()
            for field_name in (
                "wrapper_tracked_at_head",
                "tracked_python_source_set_complete",
                "tracked_python_index_flags_safe",
                "tracked_python_index_matches_head",
                "tracked_python_path_components_real",
                "tracked_python_worktree_bytes_match_head",
                "runtime_source_root_top_level_isolated",
                "runtime_source_tree_path_components_real",
                "runtime_python_filesystem_source_set_exact",
                "runtime_python_bytecode_absent",
                "runtime_python_extension_modules_absent",
                "runtime_python_filesystem_closed_world",
                "tracked_python_sources_verified",
                "all_tracked_index_flags_safe",
                "runtime_resource_manifest_verified",
                "runtime_resource_index_matches_head",
                "runtime_resource_path_components_real",
                "runtime_resource_worktree_bytes_match_head",
                "runtime_resources_verified",
            ):
                archive_services._wom_kit_runtime_integrity_record_check(
                    passed_children,
                    field_name,
                    True,
                )
            passed_children.update(
                {
                    "reason_code": "verified",
                    "tracked_python_source_count": 3,
                    "runtime_source_tree_entry_count": 4,
                    "runtime_python_filesystem_source_count": 2,
                    "all_tracked_index_entry_count": 4,
                    "runtime_resource_entry_count": 1,
                    "_wrapper_blob_oid": "b" * 40,
                }
            )

            def fake_git(_root, arguments, **_kwargs):
                if arguments == ["rev-parse", "--is-inside-work-tree"]:
                    return True, 0, "true"
                if arguments == ["rev-parse", "--show-toplevel"]:
                    return True, 0, str(mirror)
                if arguments == ["ls-files", "-z", "--", "installed-version.txt"]:
                    return True, 0, ""
                if arguments == ["rev-parse", "--verify", "HEAD"]:
                    return True, 0, head
                if arguments[0:5] == [
                    "config",
                    "--local",
                    "--no-includes",
                    "--name-only",
                    "--get-regexp",
                ]:
                    return True, 0, "remote.origin.url"
                raise AssertionError(arguments)

            stages = (
                ({}, "source_tag_available_locally", "source_tag_annotated"),
                (
                    {"tag_available_locally": True},
                    "source_tag_annotated",
                    "source_tag_at_head",
                ),
                (
                    {
                        "tag_available_locally": True,
                        "annotated_tag_verified": True,
                    },
                    "source_tag_at_head",
                    "tag_source_versions_match",
                ),
                (
                    {
                        "tag_available_locally": True,
                        "annotated_tag_verified": True,
                        "target_commit": head,
                    },
                    "tag_source_versions_match",
                    "origin_main_available_locally",
                ),
                (
                    {
                        "tag_available_locally": True,
                        "annotated_tag_verified": True,
                        "target_commit": head,
                        "all_source_versions_match_target": True,
                    },
                    "origin_main_available_locally",
                    "source_tag_reachable_from_origin_main",
                ),
                (
                    {
                        "tag_available_locally": True,
                        "annotated_tag_verified": True,
                        "target_commit": head,
                        "all_source_versions_match_target": True,
                        "origin_main_available_locally": True,
                    },
                    "source_tag_reachable_from_origin_main",
                    None,
                ),
            )
            target_check_order = (
                "source_tag_available_locally",
                "source_tag_annotated",
                "source_tag_at_head",
                "tag_source_versions_match",
                "origin_main_available_locally",
                "source_tag_reachable_from_origin_main",
            )
            for partial, unresolved, later in stages:
                target = {
                    "tag_available_locally": False,
                    "annotated_tag_verified": False,
                    "target_commit": None,
                    "all_source_versions_match_target": False,
                    "origin_main_available_locally": False,
                    "target_reachable_from_origin_main": False,
                    "observation_state": "unavailable",
                    "observation_reason_code": "project_target_probe_unavailable",
                    **partial,
                }
                with self.subTest(unresolved=unresolved):
                    with (
                        mock.patch.object(
                            archive_services,
                            "_wom_kit_project_update_git_observation",
                            side_effect=fake_git,
                        ),
                        mock.patch.object(
                            archive_services,
                            "wom_kit_project_update_git_metadata_evidence",
                            return_value={
                                "state": "passed",
                                "reason_code": "verified",
                            },
                        ),
                        mock.patch.object(
                            archive_services,
                            "_wom_kit_project_update_git_snapshot_observation",
                            return_value={
                                "state": "passed",
                                "reason_code": "verified",
                                "snapshot": {
                                    "index_matches_head": True,
                                    "flags_safe": True,
                                    "raw_bytes_match_head": True,
                                    "untracked_paths": [],
                                },
                            },
                        ),
                        mock.patch.object(
                            archive_services,
                            "wom_kit_runtime_tracked_python_integrity",
                            return_value=passed_children,
                        ),
                        mock.patch.object(
                            archive_services,
                            "wom_kit_runtime_resource_integrity",
                            return_value=passed_children,
                        ),
                        mock.patch.object(
                            archive_services,
                            "wom_kit_project_update_target_evidence",
                            return_value=target,
                        ),
                    ):
                        result = (
                            archive_services
                            ._wom_kit_runtime_mirror_integrity_with_runner(
                                project_root,
                                mirror,
                                pin,
                                wrapper,
                                source_version="0.4.19",
                                runner=object(),
                            )
                        )

                self.assertEqual(
                    result["checks"][unresolved]["state"],
                    "unavailable",
                )
                self.assertEqual(
                    result["checks"][unresolved]["reason_code"],
                    "project_target_probe_unavailable",
                )
                self.assertEqual(
                    result["reason_code"],
                    "project_target_probe_unavailable",
                )
                unresolved_index = target_check_order.index(unresolved)
                for earlier in target_check_order[:unresolved_index]:
                    self.assertEqual(
                        result["checks"][earlier]["state"],
                        "passed",
                    )
                if later is not None:
                    self.assertEqual(
                        result["checks"][later]["state"],
                        "not_reached",
                    )

    def test_runtime_preparation_revalidation_reports_dimensions_not_values(self) -> None:
        observations = {
            name: ("passed", f"runtime_preparation_{name}_verified")
            for name in (
                archive_services
                .WOM_KIT_PROJECT_UPDATE_RUNTIME_PREPARATION_CHECKS
            )
        }
        observations["target_refs"] = (
            "failed",
            "runtime_preparation_target_refs_changed",
        )
        observations["prepared_runtime_payload"] = (
            "unavailable",
            "runtime_preparation_prepared_runtime_payload_unavailable",
        )

        result = (
            archive_services
            .wom_kit_project_update_runtime_preparation_revalidation(
                observations
            )
        )

        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["changed_dimensions"], ["target_refs"])
        self.assertEqual(
            result["unavailable_dimensions"],
            ["prepared_runtime_payload"],
        )
        self.assertIn(
            "version_update_lock",
            result["expected_transaction_changes_excluded"],
        )
        self.assertFalse(result["compared_values_echoed"])
        self.assertFalse(result["private_values_echoed"])
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("refs/tags/", serialized)
        self.assertNotIn("installed-version.txt", serialized)

    def test_runtime_plan_preserves_unavailable_prerequisite_over_blocker_wording(
        self,
    ) -> None:
        state, reason = (
            archive_services
            ._wom_kit_project_update_runtime_plan_observation_state(
                ["project_runtime_exact_public_wheel_required"],
                prerequisite_states=("passed", "unavailable"),
            )
        )

        self.assertEqual(state, "unavailable")
        self.assertEqual(
            reason,
            "runtime_preparation_runtime_plan_unavailable",
        )

    def test_runtime_plan_missing_install_is_actionable_not_blocked(self) -> None:
        inspection_truth = {
            "state": "failed",
            "reason_code": "project_runtime_missing",
        }
        prerequisites = (
            archive_services
            ._wom_kit_project_update_runtime_plan_prerequisite_states(
                policy_state="passed",
                supply_state="passed",
                bootstrap_available=True,
                launcher_state="passed",
            )
        )
        state, reason = (
            archive_services
            ._wom_kit_project_update_runtime_plan_observation_state(
                [],
                prerequisite_states=prerequisites,
            )
        )

        self.assertEqual(inspection_truth["reason_code"], "project_runtime_missing")
        self.assertEqual(prerequisites, ("passed",) * 4)
        self.assertEqual(state, "passed")
        self.assertEqual(reason, "verified")

    def test_legacy_required_policy_projection_is_still_observable(self) -> None:
        state, reason = (
            archive_services._wom_kit_project_update_policy_observation(
                {"state": "required", "required": True}
            )
        )

        self.assertEqual(state, "passed")
        self.assertEqual(reason, "verified_legacy_policy_projection")

    def test_write_runtime_guard_uses_parent_when_cli_root_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_file = root / "archive.yml"
            archive_file.write_text("archive_id: test\n", encoding="utf-8")
            args = argparse.Namespace(
                archive_root=archive_file,
                _wom_project_runtime_effect="project_write",
                approve=False,
            )
            guard_result = {
                "blocked": True,
                "reason_code": "project_runtime_mismatch",
                "project_runtime_argv": ["launcher"],
            }
            with mock.patch.object(
                archive_cli.project_runtime,
                "project_write_guard",
                return_value=guard_result,
            ) as guard:
                result = archive_cli._project_write_runtime_guard(
                    args,
                    ["synthetic-writer"],
                )

        self.assertEqual(result["reason_codes"], ["project_runtime_mismatch"])
        self.assertEqual(guard.call_args.args[0], root)

    def test_update_preflight_blocks_unavailable_optional_pin_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            metadata_root = project_root / ".zettel-kasten"
            metadata_root.mkdir(parents=True)
            (metadata_root / "installed-version.txt").write_text(
                "v0.4.18\n",
                encoding="utf-8",
            )
            inaccessible_pin = (
                metadata_root / "source" / "installed-version.txt"
            )
            original_observer = (
                archive_services.wom_kit_real_path_kind_observation
            )

            def observe(root, path):
                if path == inaccessible_pin:
                    return {"state": "unavailable", "kind": "unknown"}
                return original_observer(root, path)

            with mock.patch.object(
                archive_services,
                "wom_kit_real_path_kind_observation",
                side_effect=observe,
            ):
                result = archive_services.wom_kit_project_version_update(
                    project_root,
                    target="v0.4.19",
                    dry_run=True,
                )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "A recognized installed-version pin location could not be observed safely.",
            result["blockers"],
        )
        self.assertNotIn(
            "source_mirror_pin",
            {item["role"] for item in result["pins"]["planned"]},
        )


if __name__ == "__main__":
    unittest.main()
