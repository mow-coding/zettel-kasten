from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, runtime_guidance
from wom_kit import runtime_skill_install


KIT_ROOT = Path(__file__).resolve().parents[1]
FAKE_ARCHIVE = KIT_ROOT / "examples" / "fake-life-archive"


class RuntimeGuidanceReadinessTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = archive_cli.main(args)
        return code, output.getvalue()

    def make_repo(self, root: Path, *, complete_agents: bool = True) -> tuple[Path, Path]:
        repo = root / "repo"
        archive_root = repo / "archive"
        repo.mkdir()
        shutil.copytree(FAKE_ARCHIVE, archive_root)
        agents_lines = [
            "# Repository Guidance",
            (
                "Run `archive ai-start-here <archive-root> --dry-run "
                "--progress --format json`."
            ),
            "Read the returned `action_routing`.",
            (
                "Use `archive search <archive-root> <query> --count-total "
                "--format json`."
            ),
        ]
        if complete_agents:
            agents_lines.append(
                "Raw grep and raw SQL are not authoritative WOM search results."
            )
        else:
            agents_lines.append("PRIVATE_AGENTS_BODY_CANARY")
        (repo / "AGENTS.md").write_text(
            "\n".join(agents_lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return repo, archive_root

    def install_repo_skill(self, repo: Path) -> None:
        kwargs = {
            "host": "codex",
            "scope": "repo",
            "repo_root": repo,
        }
        preview = runtime_skill_install.runtime_skill_install(
            dry_run=True,
            approve=False,
            **kwargs,
        )
        self.assertTrue(preview["ok"], preview)
        installed = runtime_skill_install.runtime_skill_install(
            dry_run=False,
            approve=True,
            reviewed_by="person:test",
            expected_plan_sha256=str(preview["operation_plan_sha256"]),
            **kwargs,
        )
        self.assertTrue(installed["ok"], installed)

    def rewrite_repo_skill_manifest_version(
        self,
        repo: Path,
        value: str,
    ) -> None:
        manifest_path = (
            repo
            / ".agents"
            / "skills"
            / runtime_skill_install.SKILL_NAME
            / runtime_skill_install.INSTALL_MANIFEST_NAME
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["package_version"] = value
        payload = {
            key: item
            for key, item in manifest.items()
            if key != "manifest_payload_sha256"
        }
        manifest["manifest_payload_sha256"] = (
            runtime_skill_install.canonical_sha256(payload)
        )
        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def tree_digest(self, root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_explicit_codex_repo_readiness_inspects_skill_and_agents_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, archive_root = self.make_repo(Path(tmp))
            self.install_repo_skill(repo)
            before = self.tree_digest(repo)

            code, output = self.run_cli(
                [
                    "runtime-guidance-readiness",
                    str(archive_root),
                    "--host",
                    "codex",
                    "--scope",
                    "repo",
                    "--repo-root",
                    str(repo),
                    "--format",
                    "json",
                ]
            )

            after = self.tree_digest(repo)
            self.assertEqual(before, after)

        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(result["ok"])
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            result["schema"],
            "wom-kit/runtime-guidance-readiness/v0.1",
        )
        self.assertEqual(result["runtime_skill"]["status"], "managed_current")
        self.assertEqual(
            result["runtime_skill"]["installation"]["installed_version"],
            "0.3.293",
        )
        self.assertEqual(
            result["runtime_skill"]["installation"][
                "installed_version_status"
            ],
            "valid",
        )
        self.assertEqual(result["agents_routing"]["status"], "current")
        self.assertEqual(result["agents_routing"]["missing_routes"], [])
        self.assertEqual(
            result["host_guidance_consumption"]["status"],
            "not_proven",
        )
        self.assertFalse(result["host_guidance_consumption"]["claim_supported"])
        self.assertFalse(result["closed_actions"]["files_written"])
        self.assertFalse(result["closed_actions"]["agents_file_modified"])
        self.assertFalse(
            result["closed_actions"]["runtime_skill_installation_changed"]
        )
        self.assertFalse(result["closed_actions"]["network_checked"])
        self.assertTrue(result["privacy"]["local_paths_redacted"])
        self.assertFalse(result["privacy"]["agents_body_exposed"])
        self.assertNotIn(str(repo), output)
        self.assertNotIn(str(archive_root), output)

    def test_untrusted_manifest_versions_never_echo_and_fail_closed_without_writes(
        self,
    ) -> None:
        unsafe_versions = (
            r"C:\private\version.txt",
            "../private/version.txt",
            "0.3",
            "0.3.293-dev",
            "PRIVATE_VERSION_CANARY",
        )
        for unsafe_version in unsafe_versions:
            with self.subTest(unsafe_version=unsafe_version):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, archive_root = self.make_repo(Path(tmp))
                    self.install_repo_skill(repo)
                    self.rewrite_repo_skill_manifest_version(
                        repo,
                        unsafe_version,
                    )
                    before = self.tree_digest(repo)

                    readiness_code, readiness_output = self.run_cli(
                        [
                            "runtime-guidance-readiness",
                            str(archive_root),
                            "--host",
                            "codex",
                            "--scope",
                            "repo",
                            "--repo-root",
                            str(repo),
                            "--format",
                            "json",
                        ]
                    )
                    status_json_code, status_json_output = self.run_cli(
                        [
                            "runtime-skill-status",
                            "--host",
                            "codex",
                            "--scope",
                            "repo",
                            "--repo-root",
                            str(repo),
                            "--format",
                            "json",
                        ]
                    )
                    status_text_code, status_text_output = self.run_cli(
                        [
                            "runtime-skill-status",
                            "--host",
                            "codex",
                            "--scope",
                            "repo",
                            "--repo-root",
                            str(repo),
                            "--format",
                            "text",
                        ]
                    )
                    after = self.tree_digest(repo)

                self.assertEqual(before, after)
                self.assertEqual(readiness_code, 1, readiness_output)
                self.assertEqual(status_json_code, 1, status_json_output)
                self.assertEqual(status_text_code, 1, status_text_output)
                readiness = json.loads(readiness_output)
                status = json.loads(status_json_output)
                self.assertFalse(readiness["ok"])
                self.assertEqual(readiness["status"], "blocked")
                self.assertIn(
                    "runtime_skill_manifest_version_invalid",
                    readiness["diagnostic_codes"],
                )
                self.assertEqual(
                    readiness["runtime_skill"]["status"],
                    "managed_invalid",
                )
                readiness_installation = readiness["runtime_skill"][
                    "installation"
                ]
                self.assertIsNone(
                    readiness_installation["installed_version"]
                )
                self.assertEqual(
                    readiness_installation["installed_version_status"],
                    "invalid_or_untrusted",
                )
                self.assertFalse(
                    readiness_installation[
                        "untrusted_manifest_values_exposed"
                    ]
                )
                self.assertFalse(
                    readiness["privacy"][
                        "untrusted_manifest_values_exposed"
                    ]
                )
                self.assertEqual(
                    status["installation"]["state"],
                    "managed_invalid",
                )
                self.assertIsNone(
                    status["installation"]["installed_version"]
                )
                self.assertEqual(
                    status["installation"]["installed_version_status"],
                    "invalid_or_untrusted",
                )
                combined_output = (
                    readiness_output
                    + status_json_output
                    + status_text_output
                )
                self.assertNotIn(
                    json.dumps(unsafe_version, ensure_ascii=True),
                    readiness_output + status_json_output,
                )
                self.assertNotIn(
                    f"Installed version: {unsafe_version}",
                    status_text_output,
                )
                self.assertNotIn(str(repo), combined_output)
                self.assertNotIn("Traceback", combined_output)

    def test_existing_non_archive_root_returns_content_free_blocked_json(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, archive_root = self.make_repo(Path(tmp))
            (archive_root / "archive.yml").unlink()
            before = self.tree_digest(repo)

            code, output = self.run_cli(
                [
                    "runtime-guidance-readiness",
                    str(archive_root),
                    "--host",
                    "codex",
                    "--scope",
                    "repo",
                    "--repo-root",
                    str(repo),
                    "--format",
                    "json",
                ]
            )
            after = self.tree_digest(repo)

        self.assertEqual(code, 1, output)
        self.assertEqual(before, after)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["archive_id"])
        self.assertEqual(result["diagnostic_codes"], ["invalid_archive"])
        self.assertFalse(result["closed_actions"]["files_written"])
        self.assertTrue(result["privacy"]["local_paths_redacted"])
        self.assertNotIn(str(repo), output)
        self.assertNotIn(str(archive_root), output)
        self.assertNotIn("Traceback", output)

    def test_absent_skill_and_incomplete_agents_have_distinct_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, archive_root = self.make_repo(
                Path(tmp),
                complete_agents=False,
            )
            result = runtime_guidance.runtime_guidance_readiness(
                archive_root,
                host="codex",
                scope="repo",
                repo_root=repo,
            )
            serialized = json.dumps(result, ensure_ascii=False)

        self.assertTrue(result["ok"], result)
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["runtime_skill"]["status"], "absent")
        self.assertEqual(result["agents_routing"]["status"], "incomplete")
        self.assertIn("runtime_skill_absent", result["diagnostic_codes"])
        self.assertIn(
            "legacy_agents_routing_absent",
            result["diagnostic_codes"],
        )
        self.assertEqual(
            result["next_safe_commands"],
            [
                "archive runtime-skill-install --host codex --scope repo "
                "--repo-root <repo-root> --dry-run --format json"
            ],
        )
        self.assertNotIn("PRIVATE_AGENTS_BODY_CANARY", serialized)

    def test_unreadable_agents_and_unsupported_scope_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, archive_root = self.make_repo(Path(tmp))
            (repo / "AGENTS.md").write_bytes(b"\xff\xfePRIVATE_PATH_CANARY")

            unreadable = runtime_guidance.runtime_guidance_readiness(
                archive_root,
                host="codex",
                scope="repo",
                repo_root=repo,
            )
            unsupported = runtime_guidance.runtime_guidance_readiness(
                archive_root,
                host="codex",
                scope="user",
                repo_root=repo,
            )
            serialized = json.dumps(
                {"unreadable": unreadable, "unsupported": unsupported},
                ensure_ascii=False,
            )

        self.assertFalse(unreadable["ok"])
        self.assertEqual(unreadable["status"], "blocked")
        self.assertIn(
            "agents_routing_unreadable",
            unreadable["diagnostic_codes"],
        )
        self.assertFalse(unsupported["ok"])
        self.assertEqual(unsupported["status"], "blocked")
        self.assertEqual(
            unsupported["diagnostic_codes"],
            ["unsupported_host_scope"],
        )
        self.assertNotIn("PRIVATE_PATH_CANARY", serialized)
        self.assertNotIn(str(repo), serialized)

    def test_cli_requires_explicit_host_scope_and_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, archive_root = self.make_repo(Path(tmp))
            missing_host_code, missing_host_output = self.run_cli(
                [
                    "runtime-guidance-readiness",
                    str(archive_root),
                    "--scope",
                    "repo",
                ]
            )
            missing_root_code, missing_root_output = self.run_cli(
                [
                    "runtime-guidance-readiness",
                    str(archive_root),
                    "--host",
                    "codex",
                    "--scope",
                    "repo",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(missing_host_code, 2)
        self.assertIn("--host", missing_host_output)
        self.assertEqual(missing_root_code, 1)
        missing_root = json.loads(missing_root_output)
        self.assertEqual(
            missing_root["diagnostic_codes"],
            ["repo_root_required"],
        )

    def test_start_surfaces_do_not_run_host_inspection_and_return_not_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, archive_root = self.make_repo(Path(tmp))
            with mock.patch.object(
                runtime_guidance,
                "runtime_guidance_readiness",
                side_effect=AssertionError("ordinary start invoked host inspection"),
            ):
                context_code, context_output = self.run_cli(
                    ["runtime-context", str(archive_root), "--format", "json"]
                )
                start_code, start_output = self.run_cli(
                    [
                        "ai-start-here",
                        str(archive_root),
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )

        self.assertEqual(context_code, 0, context_output)
        self.assertEqual(start_code, 0, start_output)
        expected_command = (
            "archive runtime-guidance-readiness <archive-root> "
            "--host codex --scope repo --repo-root <repo-root> --format json"
        )
        for result in (json.loads(context_output), json.loads(start_output)):
            readiness = result["runtime_guidance_readiness"]
            self.assertEqual(readiness["status"], "not_checked")
            self.assertFalse(readiness["checked"])
            self.assertFalse(readiness["automatic_check_performed"])
            self.assertEqual(readiness["check_command"], expected_command)
            self.assertEqual(
                readiness["host_guidance_consumption"],
                "not_proven",
            )

    def test_runtime_feedback_route_requires_plan_ledger_human_preview_approve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _repo, archive_root = self.make_repo(Path(tmp))
            context = archive_services.runtime_context(archive_root)
            plan = archive_services.operator_feedback_plan(
                archive_root,
                dry_run=True,
            )

        route = context["action_routing"]["operator_feedback_routing"]
        self.assertEqual(
            [item["action"] for item in route["sequence"]],
            [
                "read_feedback_policy",
                "inspect_feedback_ledger",
                "human_review",
                "preview_feedback_record",
                "approve_feedback_record",
            ],
        )
        self.assertIn(
            "operator-feedback-plan",
            route["sequence"][0]["command"],
        )
        self.assertIn(
            "operator-feedback-ledger",
            route["sequence"][1]["command"],
        )
        self.assertTrue(route["sequence"][2]["required_gate"])
        self.assertIsNone(route["sequence"][2]["command"])
        self.assertIn("--dry-run", route["sequence"][3]["command"])
        self.assertNotIn("--approve", route["sequence"][3]["command"])
        self.assertIn("--approve", route["sequence"][4]["command"])
        self.assertIn("--reviewed-by", route["sequence"][4]["command"])
        self.assertFalse(
            route["user_knowledge_objets_are_canonical_feedback_tracker"]
        )
        self.assertFalse(
            route["truth_boundaries"]["external_submission_performed"]
        )
        self.assertFalse(
            route["truth_boundaries"][
                "delivered_status_proves_human_receipt"
            ]
        )
        self.assertEqual(plan["data"]["runtime_routing"], route)
        self.assertFalse(plan["privacy_guards"]["feedback_body_read"])
        self.assertFalse(plan["privacy_guards"]["writes"])


if __name__ == "__main__":
    unittest.main()
