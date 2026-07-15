from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from wom_kit import __version__, archive_cli, runtime_skill_install


class RuntimeSkillInstallTests(unittest.TestCase):
    def make_source(self, root: Path, marker: str = "one") -> Path:
        source = root / "source"
        references = source / "references"
        references.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: wom-archive\ndescription: Test WOM archive skill.\n---\n\n"
            f"# WOM Archive\n\nMarker: {marker}\n"
            "[Reference](references/guide.md)\n",
            encoding="utf-8",
            newline="\n",
        )
        (references / "guide.md").write_text(
            f"# Guide\n\nMarker: {marker}\n",
            encoding="utf-8",
            newline="\n",
        )
        return source

    def custom_kwargs(
        self,
        root: Path,
        source: Path,
        *,
        version: str = "test-v1",
    ) -> dict[str, object]:
        return {
            "host": "custom",
            "scope": "custom",
            "skills_root": root / "skills",
            "source_root": source,
            "package_version": version,
        }

    def install_from_preview(
        self,
        root: Path,
        source: Path,
        *,
        version: str = "test-v1",
    ) -> dict[str, object]:
        kwargs = self.custom_kwargs(root, source, version=version)
        preview = runtime_skill_install.runtime_skill_install(
            dry_run=True,
            approve=False,
            **kwargs,
        )
        self.assertTrue(preview["ok"], preview)
        return runtime_skill_install.runtime_skill_install(
            dry_run=False,
            approve=True,
            reviewed_by="person:test",
            expected_plan_sha256=str(preview["operation_plan_sha256"]),
            **kwargs,
        )

    def run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    def test_packaged_source_contains_progressive_skill(self) -> None:
        source = runtime_skill_install.load_source_package()
        names = {row.path for row in source.files}

        self.assertIn("SKILL.md", names)
        self.assertIn("references/operator-contract.md", names)
        self.assertEqual(len(names), 7)
        self.assertRegex(source.sha256, r"^[0-9a-f]{64}$")

    def test_absent_preview_is_read_only_and_redacts_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)

            result = runtime_skill_install.runtime_skill_install(
                dry_run=True,
                approve=False,
                **kwargs,
            )

            self.assertFalse((root / "skills").exists())
            serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "ready_to_install")
        self.assertTrue(result["would_write"])
        self.assertNotIn(str(root), serialized)
        self.assertIsNone(result["target"]["path"])

    def test_install_requires_reviewer_and_exact_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )

            missing_reviewer = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )
            stale_digest = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256="0" * 64,
                **kwargs,
            )

            self.assertFalse((root / "skills" / "wom-archive").exists())

        self.assertFalse(missing_reviewer["ok"])
        self.assertIn("reviewed_by", missing_reviewer["blockers"][0])
        self.assertFalse(stale_digest["ok"])
        self.assertIn("does not match", stale_digest["blockers"][0])

    def test_install_status_and_noop_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)

            installed = self.install_from_preview(root, source)
            status = runtime_skill_install.runtime_skill_status(**kwargs)
            repeat = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            target = root / "skills" / "wom-archive"
            manifest = json.loads(
                (target / runtime_skill_install.INSTALL_MANIFEST_NAME).read_text(encoding="utf-8")
            )

        self.assertTrue(installed["ok"], installed)
        self.assertEqual(installed["status"], "installed")
        self.assertRegex(str(installed["operation_plan_sha256"]), r"^[0-9a-f]{64}$")
        self.assertRegex(str(installed["post_write_plan_sha256"]), r"^[0-9a-f]{64}$")
        self.assertNotEqual(installed["operation_plan_sha256"], installed["post_write_plan_sha256"])
        self.assertEqual(status["status"], "managed_current")
        self.assertEqual(repeat["status"], "already_current")
        self.assertFalse(repeat["would_write"])
        self.assertEqual(manifest["reviewed_by"], "person:test")
        self.assertNotIn(str(root), json.dumps(manifest))

    def test_install_stages_outside_active_skill_discovery_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            real_write_staging = runtime_skill_install.write_staging_skill
            staging_locations: list[Path] = []

            def observe_staging(staging, *args, **call_kwargs):
                staging_locations.append(staging)
                return real_write_staging(staging, *args, **call_kwargs)

            with mock.patch.object(
                runtime_skill_install,
                "write_staging_skill",
                side_effect=observe_staging,
            ):
                result = runtime_skill_install.runtime_skill_install(
                    dry_run=False,
                    approve=True,
                    reviewed_by="person:test",
                    expected_plan_sha256=str(preview["operation_plan_sha256"]),
                    **kwargs,
                )

        self.assertTrue(result["ok"], result)
        self.assertEqual(len(staging_locations), 1)
        self.assertEqual(staging_locations[0].parent, root)
        self.assertNotEqual(staging_locations[0].parent, root / "skills")

    def test_managed_update_replaces_only_verified_old_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root, marker="one")
            installed = self.install_from_preview(root, source, version="test-v1")
            self.assertTrue(installed["ok"], installed)

            (source / "SKILL.md").write_text(
                "---\nname: wom-archive\ndescription: Test WOM archive skill.\n---\n\n"
                "# WOM Archive\n\nMarker: two\n[Reference](references/guide.md)\n",
                encoding="utf-8",
                newline="\n",
            )
            kwargs = self.custom_kwargs(root, source, version="test-v2")
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            updated = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )
            target_text = (root / "skills" / "wom-archive" / "SKILL.md").read_text(
                encoding="utf-8"
            )
            leftovers = list(root.glob(".wom-archive.backup-*"))

        self.assertEqual(preview["status"], "ready_to_update")
        self.assertTrue(updated["ok"], updated)
        self.assertEqual(updated["status"], "updated")
        self.assertIn("Marker: two", target_text)
        self.assertEqual(leftovers, [])

    def test_failed_replacement_verification_restores_verified_old_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root, marker="one")
            installed = self.install_from_preview(root, source, version="test-v1")
            self.assertTrue(installed["ok"], installed)
            target = root / "skills" / "wom-archive"

            (source / "SKILL.md").write_text(
                "---\nname: wom-archive\ndescription: Test WOM archive skill.\n---\n\n"
                "# WOM Archive\n\nMarker: two\n[Reference](references/guide.md)\n",
                encoding="utf-8",
                newline="\n",
            )
            kwargs = self.custom_kwargs(root, source, version="test-v2")
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            real_inspect = runtime_skill_install.inspect_target

            def fail_new_target_verification(*args, **call_kwargs):
                result = real_inspect(*args, **call_kwargs)
                location = args[0]
                if (
                    location.target == target
                    and result.state == "managed_current"
                    and "Marker: two" in (target / "SKILL.md").read_text(encoding="utf-8")
                ):
                    return runtime_skill_install.TargetInspection(
                        "managed_drift",
                        result.manifest,
                        result.manifest_sha256,
                        result.installed_version,
                        result.installed_source_sha256,
                        ("Injected post-promotion verification failure.",),
                        (),
                    )
                return result

            with mock.patch.object(
                runtime_skill_install,
                "inspect_target",
                side_effect=fail_new_target_verification,
            ):
                result = runtime_skill_install.runtime_skill_install(
                    dry_run=False,
                    approve=True,
                    reviewed_by="person:test",
                    expected_plan_sha256=str(preview["operation_plan_sha256"]),
                    **kwargs,
                )

            restored_text = (target / "SKILL.md").read_text(encoding="utf-8")
            failed_copies = list(root.glob(".wom-archive.failed-*"))

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "failed_before_verified_completion")
        self.assertIn("Marker: one", restored_text)
        self.assertEqual(len(failed_copies), 1)

    def test_unmanaged_target_is_never_overwritten_or_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            target = root / "skills" / "wom-archive"
            target.mkdir(parents=True)
            user_file = target / "SKILL.md"
            user_file.write_text("user-owned\n", encoding="utf-8")
            kwargs = self.custom_kwargs(root, source)

            install = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            uninstall = runtime_skill_install.runtime_skill_uninstall(
                dry_run=True, approve=False, **kwargs
            )
            preserved = user_file.read_text(encoding="utf-8")

        self.assertFalse(install["ok"])
        self.assertFalse(uninstall["ok"])
        self.assertEqual(install["installation"]["state"], "unmanaged_conflict")
        self.assertEqual(preserved, "user-owned\n")

    def test_drift_blocks_update_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            installed = self.install_from_preview(root, source)
            self.assertTrue(installed["ok"], installed)
            target_file = root / "skills" / "wom-archive" / "SKILL.md"
            target_file.write_text("human edit\n", encoding="utf-8")
            kwargs = self.custom_kwargs(root, source)

            install = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            uninstall = runtime_skill_install.runtime_skill_uninstall(
                dry_run=True, approve=False, **kwargs
            )
            preserved = target_file.read_text(encoding="utf-8")

        self.assertFalse(install["ok"])
        self.assertFalse(uninstall["ok"])
        self.assertEqual(install["installation"]["state"], "managed_drift")
        self.assertIn("human edit", preserved)

    def test_manifest_metadata_edit_blocks_update_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            installed = self.install_from_preview(root, source)
            self.assertTrue(installed["ok"], installed)
            target = root / "skills" / "wom-archive"
            manifest_path = target / runtime_skill_install.INSTALL_MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reviewed_by"] = "person:edited-by-hand"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            kwargs = self.custom_kwargs(root, source)

            status = runtime_skill_install.runtime_skill_status(**kwargs)
            update = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            uninstall = runtime_skill_install.runtime_skill_uninstall(
                dry_run=True, approve=False, **kwargs
            )

        self.assertEqual(status["installation"]["state"], "managed_invalid")
        self.assertFalse(update["ok"])
        self.assertFalse(uninstall["ok"])

    def test_relative_skill_paths_reject_cross_platform_special_names(self) -> None:
        unsafe = (
            "../SKILL.md",
            "references//guide.md",
            "references/guide.md/",
            "references/file:stream",
            "references/CON.md",
            "references/trailing. ",
            "references/control\x1f.md",
            "references\\guide.md",
        )
        for value in unsafe:
            with self.subTest(value=value):
                self.assertIsNone(runtime_skill_install.safe_relative_path(value))

        self.assertEqual(
            runtime_skill_install.safe_relative_path("references/guide.md"),
            "references/guide.md",
        )

    def test_stale_install_plan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            target = root / "skills" / "wom-archive"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("appeared later\n", encoding="utf-8")

            result = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["installation"]["state"], "unmanaged_conflict")
        self.assertIn("ownership manifest", result["blockers"][0])

    def test_source_change_invalidates_reviewed_install_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            with (source / "SKILL.md").open("a", encoding="utf-8", newline="\n") as handle:
                handle.write("Changed after review.\n")

            result = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )

        self.assertFalse(result["ok"])
        self.assertIn("does not match", result["blockers"][0])

    def test_existing_operation_lock_blocks_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_install(
                dry_run=True, approve=False, **kwargs
            )
            skills_root = root / "skills"
            skills_root.mkdir()
            lock = skills_root / runtime_skill_install.LOCK_NAME
            lock.write_text("occupied\n", encoding="utf-8")

            result = runtime_skill_install.runtime_skill_install(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )
            target_exists = (root / "skills" / "wom-archive").exists()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed_before_verified_completion")
        self.assertFalse(target_exists)

    def test_symlinked_skills_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            real_root = root / "real-skills"
            real_root.mkdir()
            linked_root = root / "linked-skills"
            try:
                os.symlink(real_root, linked_root, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink is unavailable: {exc}")

            result = runtime_skill_install.runtime_skill_status(
                host="custom",
                scope="custom",
                skills_root=linked_root,
                source_root=source,
                package_version="test-v1",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")

    def test_uninstall_removes_only_verified_managed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            installed = self.install_from_preview(root, source)
            self.assertTrue(installed["ok"], installed)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_uninstall(
                dry_run=True, approve=False, **kwargs
            )
            result = runtime_skill_install.runtime_skill_uninstall(
                dry_run=False,
                approve=True,
                reviewed_by="person:test",
                expected_plan_sha256=str(preview["operation_plan_sha256"]),
                **kwargs,
            )
            target_exists = (root / "skills" / "wom-archive").exists()

        self.assertEqual(preview["status"], "ready_to_uninstall")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "uninstalled")
        self.assertFalse(target_exists)

    def test_uninstall_rechecks_moved_target_before_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            installed = self.install_from_preview(root, source)
            self.assertTrue(installed["ok"], installed)
            kwargs = self.custom_kwargs(root, source)
            preview = runtime_skill_install.runtime_skill_uninstall(
                dry_run=True, approve=False, **kwargs
            )
            real_inspect = runtime_skill_install.inspect_target

            def fail_moved_target_verification(*args, **call_kwargs):
                result = real_inspect(*args, **call_kwargs)
                location = args[0]
                if location.target.name.startswith(".wom-archive.uninstall-"):
                    return runtime_skill_install.TargetInspection(
                        "managed_drift",
                        result.manifest,
                        result.manifest_sha256,
                        result.installed_version,
                        result.installed_source_sha256,
                        ("Injected post-move verification failure.",),
                        (),
                    )
                return result

            with mock.patch.object(
                runtime_skill_install,
                "inspect_target",
                side_effect=fail_moved_target_verification,
            ):
                result = runtime_skill_install.runtime_skill_uninstall(
                    dry_run=False,
                    approve=True,
                    reviewed_by="person:test",
                    expected_plan_sha256=str(preview["operation_plan_sha256"]),
                    **kwargs,
                )

            target_exists = (root / "skills" / "wom-archive" / "SKILL.md").is_file()
            tombstones = list(root.glob(".wom-archive.uninstall-*"))

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "failed_before_verified_removal")
        self.assertTrue(target_exists)
        self.assertEqual(tombstones, [])

    def test_repo_scope_uses_official_agents_skill_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            location = runtime_skill_install.resolve_target_location(
                host="codex", scope="repo", repo_root=repo
            )

        self.assertEqual(location.target, repo / ".agents" / "skills" / "wom-archive")
        self.assertEqual(location.path_hint, "repo/.agents/skills/wom-archive")

    def test_incompatible_target_options_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)

            result = runtime_skill_install.runtime_skill_status(
                host="codex",
                scope="user",
                skills_root=root / "skills",
                source_root=source,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")

    def test_cli_custom_preview_returns_json_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_root = root / "skills"
            code, output = self.run_cli(
                [
                    "runtime-skill-install",
                    "--host",
                    "custom",
                    "--scope",
                    "custom",
                    "--skills-root",
                    str(skills_root),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            result = json.loads(output)

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "ready_to_install")
        self.assertFalse(skills_root.exists())
        self.assertNotIn(str(root), output)

    def test_capability_manifest_lists_runtime_skill_lifecycle_commands(self) -> None:
        code, output = self.run_cli(["capabilities", "--machine"])
        result = json.loads(output)
        names = {row["name"] for row in result["data"]["commands"]}

        self.assertEqual(code, 0, result)
        self.assertTrue(
            {
                "runtime-skill-status",
                "runtime-skill-install",
                "runtime-skill-uninstall",
            }.issubset(names)
        )

    def test_source_checkout_version_is_used_for_real_package_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = runtime_skill_install.runtime_skill_install(
                dry_run=True,
                approve=False,
                host="custom",
                scope="custom",
                skills_root=root / "skills",
            )

        self.assertEqual(result["source_package"]["package_version"], __version__)
        self.assertEqual(result["source_package"]["file_count"], 7)

    def test_installer_module_has_no_network_or_provider_behavior(self) -> None:
        source = Path(runtime_skill_install.__file__).read_text(encoding="utf-8")
        banned = (
            "import subprocess",
            "import requests",
            "urllib.request",
            "http.client",
            "import socket",
            "provider_api(",
            "credential_store(",
        )
        for needle in banned:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)

    def test_public_docs_distinguish_wheel_install_from_host_activation(self) -> None:
        docs = Path(__file__).resolve().parents[1] / "docs"
        progressive = (docs / "runtime-skill-progressive-disclosure.md").read_text(
            encoding="utf-8"
        )
        install_en = (docs / "runtime-skill-install.md").read_text(encoding="utf-8")
        install_ko = (docs / "runtime-skill-install.ko.md").read_text(encoding="utf-8")

        self.assertIn("does not run as a side effect of installing the Python wheel", progressive)
        self.assertIn("$HOME/.agents/skills/wom-archive", progressive)
        self.assertIn("--expected-plan-sha256", install_en)
        self.assertIn("--expected-plan-sha256", install_ko)
        self.assertIn("unmanaged", install_en.lower())
        self.assertIn("사람이 고친", install_ko)


if __name__ == "__main__":
    unittest.main()
