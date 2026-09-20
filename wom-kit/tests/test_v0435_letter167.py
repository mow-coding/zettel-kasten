"""v0.4.35 (beta letter 167): the updater names a rewritten origin main and accepts it only under
--affirm-origin-main-rewritten; a failed fetch carries a fixed rejection kind and the remote's own
tag / main observation instead of "tag missing" alone.

Synthetic upstream + mirror repositories only; the runtime candidate, bootstrap and download
seams are the same injected ones the v0.4 approve-path tests use.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from wom_kit import archive_cli, archive_services

import test_cli as _cli_fixture


class RewrittenOriginUpdateTests(unittest.TestCase):
    """Borrows the approve-path scaffolding (fixtures, injected runtime seams) without inheriting its tests."""

    # every non-test helper of the CLI suite (fixtures, injected runtime seams, git runner), no tests
    for _name, _value in vars(_cli_fixture.ArchiveCliTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def _rewrite_upstream_main(self, fixture: dict[str, Any]) -> tuple[str, str]:
        """Replace the upstream history with a new root that has the same trees (a filter-repo-like rewrite)."""

        upstream = fixture["upstream"]
        git = self.git_fixture_command
        old_tree = git(upstream, "rev-parse", f"{fixture['old_commit']}^{{tree}}")
        target_tree = git(upstream, "rev-parse", f"{fixture['target_commit']}^{{tree}}")
        new_root = git(upstream, "commit-tree", old_tree, "-m", "old release (rewritten)")
        new_target = git(upstream, "commit-tree", target_tree, "-p", new_root, "-m", "target release (rewritten)")
        git(upstream, "update-ref", "refs/heads/main", new_target)
        git(upstream, "tag", "-d", fixture["target_tag"])
        git(upstream, "tag", "-a", fixture["target_tag"], new_target, "-m", fixture["target_tag"])
        self.assertNotEqual(git(upstream, "rev-parse", "refs/heads/main"), fixture["target_commit"])
        return new_root, new_target

    def _run_approve(self, tmp_root: Path, fixture: dict[str, Any], artifacts: dict[str, Any], *extra_flags: str):
        approval_started = False
        prepared_plans: list[dict[str, Any]] = []
        original_binding = archive_cli.operation_approval_binding.project_version_update_approval_binding

        def capture_binding(plan: Any) -> Any:
            prepared_plans.append(copy.deepcopy(dict(plan)))
            return original_binding(plan)

        def execute_approval(root, context, writer, *, claim_publication_boundary=None,
                             claim_succeeded_finalizer=None, _key_provider=None):
            nonlocal approval_started
            approval_started = True
            return self.execute_test_exact_human_transaction(
                root, context, writer, claim_publication_boundary=claim_publication_boundary,
                claim_succeeded_finalizer=claim_succeeded_finalizer, _key_provider=_key_provider,
            )

        command = [
            "project-version-update", str(fixture["project_root"]), "--target", fixture["target_tag"],
            "--approve", "--affirm-external-writers-quiescent", "--reviewed-by", "person:project-version-reviewer",
            *extra_flags, "--format", "json",
        ]
        with patch.object(archive_services, "wom_kit_project_update_runtime_policy", return_value=artifacts["policy"]), \
                patch.object(archive_services, "wom_kit_project_update_runtime_supply", return_value=artifacts["supply"]), \
                patch.object(archive_services.project_runtime, "bootstrap_wheel_for_target",
                             return_value=(artifacts["bootstrap"], artifacts["bootstrap_summary"])), \
                patch.object(archive_services.project_runtime, "_download_exact_artifact", side_effect=artifacts["download"]), \
                patch.object(archive_services.project_runtime, "_initialize_runtime_payload",
                             side_effect=self.initialize_fast_runtime_candidate), \
                patch.object(archive_services.project_runtime, "_verify_retained_artifacts",
                             side_effect=self.verify_fast_retained_runtime_artifacts), \
                patch.object(archive_cli.operation_approval_binding, "project_version_update_approval_binding",
                             side_effect=capture_binding), \
                patch.object(archive_cli, "_execute_project_version_update_exact_human_approved_write",
                             side_effect=execute_approval):
            code, stdout, stderr = self.run_cli_split(command)
        return code, stdout, stderr, approval_started, prepared_plans

    @unittest.skipUnless(
        _cli_fixture.WINDOWS_PROJECT_RUNTIME,
        "the production runtime supply is Windows CPython 3.12 (the approve path is Windows-only)",
    )
    def test_rewritten_origin_main_is_named_and_accepted_only_under_the_affirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            fixture = self.create_project_version_update_fixture(tmp_root, project_runtime_policy=True)
            artifacts = self.project_runtime_candidate_artifact_fixture(tmp_root, fixture)
            new_root, new_target = self._rewrite_upstream_main(fixture)
            mirror_origin_main_before = self.git_fixture_command(fixture["mirror"], "rev-parse", "refs/remotes/origin/main")
            self.assertEqual(mirror_origin_main_before, fixture["old_commit"])

            # 1. without the affirmation: refused before any dialog, and the result says why
            code, stdout, stderr, approval_started, plans = self._run_approve(tmp_root, fixture, artifacts)
            self.assertEqual(code, 1, stdout + stderr)
            result = json.loads(stdout)
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(approval_started)
            self.assertEqual(plans, [])
            fetch = result["fetch"]
            self.assertTrue(fetch["attempted"])
            self.assertFalse(fetch["succeeded"])
            self.assertEqual(fetch["rejection_kind"], "non_fast_forward")
            self.assertTrue(fetch["remote_reachable"])
            self.assertTrue(fetch["target_tag_on_remote"])
            self.assertTrue(fetch["origin_main_rewritten"])
            self.assertEqual(fetch["origin_main_before_fetch"], fixture["old_commit"])
            self.assertEqual(fetch["origin_main_remote_sha"], new_target)
            self.assertFalse(fetch["main_ref_forced_update_affirmed"])
            self.assertFalse(fetch["raw_git_stderr_echoed"])
            self.assertIn(archive_services.WOM_KIT_PROJECT_UPDATE_ORIGIN_MAIN_REWRITTEN_BLOCKER, result["blockers"])
            self.assertTrue(any("--affirm-origin-main-rewritten" in line for line in result["next_safe_actions"]))
            # the tracking ref was not moved and no tag or probe ref remains from the diagnosis
            self.assertEqual(self.git_fixture_command(fixture["mirror"], "rev-parse", "refs/remotes/origin/main"), fixture["old_commit"])
            self.assertEqual(self.git_fixture_command(fixture["mirror"], "for-each-ref", "refs/wom-kit/"), "")
            self.assertNotIn(fixture["target_tag"], self.git_fixture_command(fixture["mirror"], "tag", "--list"))
            self.assertEqual(self.git_fixture_command(fixture["mirror"], "rev-parse", "HEAD"), fixture["old_commit"])
            self.assertFalse((fixture["metadata_root"] / "version-update.lock").exists())
            self.assertNotIn(str(fixture["upstream"]), stdout)

            # 2. the dry-run with the affirmation announces the bound warning and the forced main ref
            preview_code, preview_out, _ = self.run_cli_split([
                "project-version-update", str(fixture["project_root"]), "--target", fixture["target_tag"],
                "--dry-run", "--affirm-origin-main-rewritten", "--format", "json",
            ])
            self.assertEqual(preview_code, 0, preview_out)
            preview = json.loads(preview_out)
            self.assertIn("origin_main_rewrite_affirmed", preview["warnings"])
            self.assertTrue(preview["fetch"]["main_ref_forced_update_affirmed"])
            self.assertTrue(any("--affirm-origin-main-rewritten" in line for line in preview["next_safe_actions"]))

            # 3. with the affirmation: one forced tracking-ref update, then the ordinary verified update
            code, stdout, stderr, approval_started, plans = self._run_approve(
                tmp_root, fixture, artifacts, "--affirm-origin-main-rewritten",
            )
            self.assertEqual(code, 0, stdout + stderr)
            result = json.loads(stdout)
            self.assertEqual(result["status"], "updated_restart_required")
            self.assertTrue(approval_started)
            fetch = result["fetch"]
            self.assertTrue(fetch["succeeded"])
            self.assertTrue(fetch["main_ref_forced_update_affirmed"])
            self.assertTrue(fetch["origin_main_rewrite_accepted"])
            self.assertEqual(fetch["origin_main_before_fetch"], fixture["old_commit"])
            self.assertEqual(fetch["origin_main_after_fetch"], new_target)
            self.assertIsNone(fetch["rejection_kind"])
            self.assertIn("origin_main_rewrite_affirmed", result["warnings"])
            self.assertTrue(result["target"]["configured_origin_main_ancestry_verified"])
            self.assertEqual(self.git_fixture_command(fixture["mirror"], "rev-parse", "HEAD"), new_target)
            self.assertEqual(len(plans), 1)
            self.assertIn("origin_main_rewrite_affirmed", plans[0]["warnings"])
            self.assertTrue(plans[0]["fetch"]["main_ref_forced_update_affirmed"])
            del new_root

    def test_fetch_diagnosis_names_missing_remote_tag_and_unreachable_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            fixture = self.create_project_version_update_fixture(tmp_root, project_runtime_policy=True)
            git = self.git_fixture_command
            runner = archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner.resolve_preapproval()
            try:
                # the tag is not on the remote yet
                git(fixture["upstream"], "tag", "-d", fixture["target_tag"])
                diagnosis = archive_services._wom_kit_project_update_fetch_diagnosis(
                    fixture["mirror"], fixture["target_tag"], origin_main_local_sha=fixture["old_commit"], runner=runner,
                )
                self.assertEqual(diagnosis["rejection_kind"], "target_tag_missing_on_remote")
                self.assertTrue(diagnosis["remote_reachable"])
                self.assertFalse(diagnosis["target_tag_on_remote"])
                self.assertIsNone(diagnosis["origin_main_rewritten"])
                # a fast-forwardable remote is reported as not rewritten
                git(fixture["upstream"], "tag", "-a", fixture["target_tag"], fixture["target_commit"], "-m", fixture["target_tag"])
                diagnosis = archive_services._wom_kit_project_update_fetch_diagnosis(
                    fixture["mirror"], fixture["target_tag"], origin_main_local_sha=fixture["old_commit"], runner=runner,
                )
                self.assertEqual(diagnosis["rejection_kind"], "ref_update_rejected")
                self.assertTrue(diagnosis["target_tag_on_remote"])
                self.assertFalse(diagnosis["origin_main_rewritten"])
                # the diagnosis never leaves a tag or probe ref behind
                self.assertEqual(git(fixture["mirror"], "for-each-ref", "refs/wom-kit/"), "")
                self.assertNotIn(fixture["target_tag"], git(fixture["mirror"], "tag", "--list"))
                # an unreachable remote
                git(fixture["mirror"], "remote", "set-url", "origin", str(tmp_root / "missing-upstream"))
                diagnosis = archive_services._wom_kit_project_update_fetch_diagnosis(
                    fixture["mirror"], fixture["target_tag"], origin_main_local_sha=fixture["old_commit"], runner=runner,
                )
                self.assertEqual(diagnosis["rejection_kind"], "remote_unreachable")
                self.assertFalse(diagnosis["remote_reachable"])
                self.assertFalse(diagnosis["raw_git_stderr_echoed"])
                self.assertNotIn(str(tmp_root), json.dumps(diagnosis))
            finally:
                runner.close_transport_boundary()
            self.assertIn("non_fast_forward", archive_services.WOM_KIT_PROJECT_UPDATE_FETCH_REJECTION_KINDS)


if __name__ == "__main__":
    unittest.main()
