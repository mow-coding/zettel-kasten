from __future__ import annotations

import tempfile
import unittest
import shutil
from pathlib import Path

from wom_kit import archive_services
from wom_kit.agent_instruction_policy import (
    AgentInstructionPolicyError,
    inspect_agent_instruction_policies,
)


def _policy(
    *,
    role: str,
    policy_id: str,
    status: str = "active",
    directives: dict[str, str] | None = None,
) -> str:
    rows = [
        "<!-- wom-agent-policy",
        "schema_version: wom-kit/agent-instruction-policy/v0.1",
        f"policy_id: {policy_id}",
        "policy_version: 1",
        f"status: {status}",
        f"scope_role: {role}",
        "directives:",
    ]
    for key, value in sorted((directives or {}).items()):
        rows.append(f"  {key}: {value}")
    rows.extend(["-->", "", "# Local instructions", "private prose is never echoed"])
    return "\n".join(rows) + "\n"


class AgentInstructionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.archive = self.project / "archive"
        self.archive.mkdir(parents=True)
        (self.archive / "archive.yml").write_text(
            "archive_id: archive:test\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_matching_active_policies_resolve_with_fixed_precedence(self) -> None:
        (self.project / "AGENTS.md").write_text(
            _policy(
                role="project_current",
                policy_id="project_current",
                directives={"collaboration_harness": "retired"},
            ),
            encoding="utf-8",
        )
        (self.archive / "AGENTS.md").write_text(
            _policy(
                role="archive_local",
                policy_id="archive_local",
                directives={"collaboration_harness": "retired"},
            ),
            encoding="utf-8",
        )
        result = inspect_agent_instruction_policies(self.archive)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "resolved")
        self.assertFalse(result["write_actions_blocked"])
        row = next(
            item
            for item in result["resolved_directives"]
            if item["directive"] == "collaboration_harness"
        )
        self.assertEqual(row["selected_source_role"], "project_current")
        self.assertFalse(row["conflict"])

    def test_opposing_active_harness_policies_block_without_echo(self) -> None:
        (self.project / "AGENTS.md").write_text(
            _policy(
                role="project_current",
                policy_id="project_current",
                directives={"collaboration_harness": "retired"},
            ),
            encoding="utf-8",
        )
        (self.archive / "AGENTS.md").write_text(
            _policy(
                role="archive_local",
                policy_id="archive_local",
                directives={"collaboration_harness": "enabled"},
            ).replace("private prose", "secret_private_instruction"),
            encoding="utf-8",
        )
        result = inspect_agent_instruction_policies(self.archive)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "conflict")
        self.assertTrue(result["write_actions_blocked"])
        self.assertIn("active_agent_instruction_policy_conflict", result["blockers"])
        rendered = repr(result)
        self.assertNotIn("secret_private_instruction", rendered)
        self.assertNotIn(str(self.project), rendered)

    def test_runtime_policy_cannot_be_overridden_by_lower_source(self) -> None:
        (self.project / "AGENTS.md").write_text(
            _policy(
                role="project_current",
                policy_id="project_current",
                directives={"direct_archive_write": "enabled"},
            ),
            encoding="utf-8",
        )
        result = inspect_agent_instruction_policies(self.archive)
        self.assertFalse(result["ok"])
        row = next(
            item
            for item in result["resolved_directives"]
            if item["directive"] == "direct_archive_write"
        )
        self.assertEqual(row["selected_source_role"], "wom_runtime")
        self.assertEqual(row["selected_value"], "forbidden")
        self.assertTrue(row["conflict"])

    def test_retired_policy_is_evidence_not_active_authority(self) -> None:
        (self.project / "AGENTS.md").write_text(
            _policy(
                role="project_current",
                policy_id="old_harness",
                status="retired",
                directives={"collaboration_harness": "enabled"},
            ),
            encoding="utf-8",
        )
        result = inspect_agent_instruction_policies(self.archive)
        self.assertTrue(result["ok"])
        self.assertIn(
            "retired_or_historical_instruction_policy_present", result["warnings"]
        )
        self.assertFalse(
            any(
                row["directive"] == "collaboration_harness"
                for row in result["resolved_directives"]
            )
        )

    def test_unmarked_multiple_sources_are_unverified_and_block_writes(self) -> None:
        (self.project / "AGENTS.md").write_text("# project prose\n", encoding="utf-8")
        (self.archive / "AGENTS.md").write_text("# archive prose\n", encoding="utf-8")
        result = inspect_agent_instruction_policies(self.archive)
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["unverified_source_count"], 2)
        self.assertTrue(result["write_actions_blocked"])
        self.assertIn(
            "multiple_unverified_agent_instruction_sources", result["blockers"]
        )

    def test_arbitrary_project_root_is_rejected_before_read(self) -> None:
        other = Path(self.temporary.name) / "other"
        other.mkdir()
        (other / "AGENTS.md").write_text("private", encoding="utf-8")
        with self.assertRaises(AgentInstructionPolicyError) as captured:
            inspect_agent_instruction_policies(
                self.archive, project_root=other
            )
        self.assertEqual(
            captured.exception.code, "agent_instruction_project_root_not_bound"
        )

    def test_runtime_context_and_start_here_surface_conflict_as_write_blocker(self) -> None:
        project = Path(self.temporary.name) / "runtime-project"
        archive = project / "archive"
        shutil.copytree(
            Path(__file__).resolve().parents[1]
            / "examples"
            / "fake-life-archive",
            archive,
        )
        project_policy = _policy(
            role="project_current",
            policy_id="project_current",
            directives={"exact_human_approval": "forbidden"},
        ).replace("private prose", "PRIVATE INSTRUCTION SENTINEL")
        archive_policy = _policy(
            role="archive_local",
            policy_id="archive_local",
            directives={"exact_human_approval": "required"},
        )
        (project / "AGENTS.md").write_text(project_policy, encoding="utf-8")
        (archive / "AGENTS.md").write_text(archive_policy, encoding="utf-8")

        runtime = archive_services.runtime_context(archive)
        start = archive_services.ai_start_here(archive)

        self.assertFalse(runtime["ok"])
        self.assertTrue(
            runtime["agent_instruction_policy"]["write_actions_blocked"]
        )
        self.assertIn(
            "active_agent_instruction_policy_conflict", runtime["blockers"]
        )
        self.assertEqual(start["agent_instruction_policy"]["status"], "conflict")
        serialized = str((runtime, start))
        self.assertNotIn("PRIVATE INSTRUCTION SENTINEL", serialized)
        self.assertNotIn(str(project), serialized)


if __name__ == "__main__":
    unittest.main()
