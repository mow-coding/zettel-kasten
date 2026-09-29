"""S2 verification and authoring checks (S2-U09, U10, U12, U13, U15, U16, U17).

Every scenario runs through official ``archive`` commands on a private copy of
the example archive. Results are content-free: no temp path, private title or
body text is asserted on or printed. Where the current behaviour differs from
the S2 expectation the test fails with a clear message and carries an
``# S2-Uxx gap:`` comment; nothing is skipped or faked.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wom_kit import archive_cli, archive_services as services

KIT = Path(__file__).resolve().parents[1]
FIXTURE = KIT / "examples" / "fake-life-archive"
SKILL_ROOT = KIT / "templates" / "ai-runtime" / "wom-archive"
REFERENCES = SKILL_ROOT / "references"
PROMOTION_CHECKLIST_IDS = (
    "one_clear_purpose", "understandable_title", "future_self_contained", "source_clarity",
    "object_id_only", "stable_facets", "allowed_edges", "explicit_visibility",
    "provenance_present", "sensitive_content_reviewed",
)
LOCATOR_COUNT_STATES = {
    "exact", "body_marker_count_exceeds_frontmatter", "frontmatter_count_exceeds_body",
}
CONVENTIONS = {
    "schema": "wom-kit/authoring-conventions/v0.1",
    "language": "ko-KR",
    "title_rules": ["제목은 사람에게 바로 이해되어야 한다."],
    "body_rules": ["본문에는 미래의 인간 독자에게 필요한 정보만 쓴다."],
    "required_sections": ["결론"],
    "forbidden_body_content": ["도구 실행 상태"],
    "examples": ["결론부터 쓰고 근거를 이어 쓴다."],
}


def _parser_commands() -> set[str]:
    parser = archive_cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


def _skill_texts() -> dict[str, str]:
    files = [SKILL_ROOT / "SKILL.md", *sorted(REFERENCES.glob("*.md"))]
    return {path.name: path.read_text(encoding="utf-8") for path in files}


def _fenced_lines(text: str, prefix: str) -> list[str]:
    lines: list[str] = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", text, re.S):
        lines.extend(line.strip() for line in block.splitlines() if line.strip().startswith(prefix))
    return lines


class _ArchiveFixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "archive"
        shutil.copytree(FIXTURE, self.root)
        self.parser = archive_cli.build_parser()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def fresh_root(self, name: str) -> Path:
        root = Path(self._tmp.name) / name
        shutil.copytree(FIXTURE, root)
        return root

    def invoke(self, argv: list[str], *, root: Path | None = None) -> tuple[int, str, str]:
        root = root or self.root
        args = self.parser.parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = args.func(args)
        for stream in (out.getvalue(), err.getvalue()):
            self.assertNotIn(str(root), stream, "command output echoed the private root")
            self.assertNotIn(root.as_posix(), stream, "command output echoed the private root")
        return code, out.getvalue(), err.getvalue()

    def invoke_json(self, argv: list[str], *, root: Path | None = None) -> tuple[int, dict]:
        code, out, err = self.invoke(argv, root=root)
        self.assertTrue(out.strip(), f"no JSON on stdout (exit {code}); stderr: {err[:200]!r}")
        return code, json.loads(out)

    def write_zet(self, relative: str, frontmatter: str, body: str, *, root: Path | None = None) -> Path:
        path = (root or self.root).joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
        return path


class LocatorLossAuditCountStateTests(_ArchiveFixtureCase):
    def _write_locator_zet(self, name: str, markers: int, declared: int) -> Path:
        return self.write_zet(
            f"inbox/{name}.md",
            f"id: {name}\nstatus: draft\nfacets:\n  source_system: notion_db3\n"
            f"  source_page_id: private-page-{name}\n  source_locator_omitted_count: {declared}\n",
            "\n".join(["[source locator omitted]"] * markers) + "\n",
        )

    def _audit(self) -> dict:
        code, result = self.invoke_json(
            ["notion-import-locator-loss-audit", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, result.get("blockers"))
        self.assertFalse(result["privacy_guards"]["zettel_paths_echoed"])
        return result

    def test_s2_u09_every_locator_count_difference_maps_to_a_named_state(self) -> None:
        """S2-U09: body markers (6) over frontmatter count (4) is a named mismatch state."""
        excess = self._write_locator_zet("zet_locator_probe_excess", markers=6, declared=4)
        result = self._audit()
        summary = result["summary"]
        self.assertEqual(summary["affected_zettel_count"], 1)
        self.assertEqual(summary["body_marker_count"], 6)
        self.assertEqual(summary["frontmatter_omitted_count"], 4)
        self.assertEqual(summary["marker_frontmatter_count_delta"], 2)
        self.assertEqual(summary["count_mismatch_zettel_count"], 1)
        self.assertEqual(summary["exact_count_zettel_count"], 0)
        self.assertEqual(result["items"][0]["count_state"], "body_marker_count_exceeds_frontmatter")
        self.assertEqual(result["items"][0]["body_marker_count"], 6)
        self.assertEqual(result["items"][0]["frontmatter_omitted_count"], 4)
        self.assertEqual(summary["counts_by_state"], {"body_marker_count_exceeds_frontmatter": 1})

        excess.unlink()
        self._write_locator_zet("zet_locator_probe_exact", markers=4, declared=4)
        self._write_locator_zet("zet_locator_probe_short", markers=1, declared=2)
        result = self._audit()
        states = {item["count_state"] for item in result["items"]}
        self.assertEqual(states, {"exact", "frontmatter_count_exceeds_body"})
        self.assertEqual(result["summary"]["exact_count_zettel_count"], 1)
        self.assertEqual(result["summary"]["count_mismatch_zettel_count"], 1)
        self.assertTrue(set(result["summary"]["counts_by_state"]) <= LOCATOR_COUNT_STATES)
        for marker_count, declared in ((0, 0), (3, 1), (1, 3), (7, 7)):
            self.assertIn(services.notion_import_locator_count_state(marker_count, declared),
                          LOCATOR_COUNT_STATES, (marker_count, declared))


class DocumentedCreateDraftExampleTests(unittest.TestCase):
    # S2-U10 gap: doc example fix pending at S2 intake -- the fenced ai_assisted
    # create-draft examples omitted --abstract, --facet and --source-fidelity,
    # which the CLI contract requires for AI-assisted drafts. The references were
    # corrected in the same worktree while this test was written; the test keeps
    # failing loudly if an example regresses. Do not weaken it.
    def test_s2_u10_documented_ai_assisted_examples_carry_the_required_flags(self) -> None:
        """S2-U10: every fenced ai_assisted create-draft example names abstract, facet, fidelity."""
        docs = ("capture-draft-and-publication.md", "operator-contract.md")
        examples: list[tuple[str, str]] = []
        for name in docs:
            text = (REFERENCES / name).read_text(encoding="utf-8")
            examples.extend((name, line) for line in _fenced_lines(text, "archive create-draft"))
        self.assertTrue(examples, "no fenced create-draft examples found in the references")
        ai_examples = [(name, line) for name, line in examples if "--creation-mode ai_assisted" in line]
        self.assertTrue(ai_examples, "no fenced ai_assisted create-draft example found")
        required = ("--abstract", "--facet", "--source-fidelity")
        offending = [
            f"{name}: missing {[flag for flag in required if flag not in line]}: {line}"
            for name, line in ai_examples
            if any(flag not in line for flag in required)
        ]
        self.assertEqual(
            offending, [],
            "documented ai_assisted create-draft examples contradict the CLI contract:\n"
            + "\n".join(offending),
        )


class DeclaredConventionsThroughDraftAndMintTests(_ArchiveFixtureCase):
    def test_s2_u12_declared_conventions_flow_through_draft_and_mint_previews(self) -> None:
        """S2-U12: a declared authoring convention is read; draft and mint previews honour it."""
        conventions = self.root / "zettel-kasten" / "authoring-conventions.yml"
        conventions.write_text(archive_cli.dump_yaml(CONVENTIONS), encoding="utf-8")
        self.assertTrue(services.index_archive(self.root)["ok"])
        code, declared = self.invoke_json(
            ["authoring-conventions", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(declared["state"], "declared")
        self.assertEqual(declared["summary"]["rule_counts"]["required_sections"], 1)

        body = ("# 합성 결론 노트\n\n## 결론\n\n결론부터 쓰고 근거를 이어 쓴다.\n\n"
                "## 근거\n\n미래의 인간 독자에게 필요한 정보만 담았다.\n")
        code, preview = self.invoke_json([
            "create-draft", str(self.root), "--title", "합성 결론 노트", "--body", body,
            "--kind", "permanent_note", "--facet", "domain=synthetic",
            "--abstract", "합성 결론 노트의 짧은 요약", "--creation-mode", "human_written",
            "--created-by", "person:synthetic-author", "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, preview.get("blockers"))
        self.assertTrue(preview["ok"], preview.get("blockers"))
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["blockers"], [])
        self.assertEqual(preview["quality_check"]["warning_explanations"], [])

        frontmatter = dict(preview["frontmatter_preview"])
        frontmatter["promotion"] = {
            "stage": "promotion_candidate", "ready_for_promotion": True,
            "checklist": {item: True for item in PROMOTION_CHECKLIST_IDS}}
        draft_path = self.root.joinpath(*preview["proposed_path"].split("/"))
        self.assertFalse(draft_path.exists(), "dry-run must not have written the draft")
        draft_path.write_text(
            "---\n" + archive_cli.dump_yaml(frontmatter) + "---\n\n" + body, encoding="utf-8")
        self.assertTrue(services.index_archive(self.root)["ok"])

        code, mint = self.invoke_json(
            ["mint-zet", str(self.root), "--path", preview["proposed_path"], "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, mint.get("blockers"))
        self.assertTrue(mint["ok"], mint.get("blockers"))
        self.assertTrue(mint["dry_run"])
        self.assertTrue(str(mint["proposed_canonical_path"]).startswith("zettels/"))
        convention_blockers = [
            item for item in [*mint["blockers"], *mint["warnings"]]
            if str(item).startswith("authoring_conventions_")]
        self.assertEqual(convention_blockers, [])
        canonical_path = self.root.joinpath(*str(mint["proposed_canonical_path"]).split("/"))
        self.assertFalse(canonical_path.exists(), "mint-zet dry-run must not write the canonical zet")


class TitleRemapDefaultCapTests(_ArchiveFixtureCase):
    PROPOSAL = ".wom-scratch/title-remap/reviewed.jsonl"

    def _write_proposal(self, root: Path, count: int, *, materialize: bool) -> None:
        # A row whose zet is absent falls back to a full scan of zettels/, so
        # every count gets its own fresh fixture copy to keep the run linear.
        rows = []
        for index in range(count):
            name = f"zet_title_remap_probe_{index:04d}"
            sha = "sha256:" + "0" * 64
            if materialize:
                path = self.write_zet(
                    f"zettels/{name}.md",
                    f"id: {name}\ntitle: 32634f642e1b80b68144d468b8{index:06x}\n"
                    "status: canonical\nkind: note\n",
                    "body text\n", root=root)
                sha = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append({"schema": "wom-kit/zet-title-remap-proposal/v0.1", "zettel_id": name,
                         "expected_file_sha256": sha, "basis": "source_export_property",
                         "title": f"Reviewed source title number {index}"})
        proposal = root.joinpath(*self.PROPOSAL.split("/"))
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def _plan(self, root: Path) -> tuple[int, dict]:
        return self.invoke_json(["zet-title-remap-plan", str(root), "--proposal", self.PROPOSAL,
                                 "--dry-run", "--format", "json"], root=root)

    def test_s2_u13_default_max_items_returns_every_row_up_to_the_ceiling(self) -> None:
        """S2-U13: 101 and 1001 rows return whole without --max-items; 5001 names the ceiling."""
        parsed = self.parser.parse_args(
            ["zet-title-remap-plan", "archive", "--proposal", self.PROPOSAL, "--dry-run"])
        self.assertEqual(parsed.max_items, services.ZET_TITLE_REMAP_MAX_ITEMS)
        self.assertEqual(services.ZET_TITLE_REMAP_MAX_ITEMS, 5000)

        for count in (101, 1001):
            with self.subTest(rows=count):
                root = self.fresh_root(f"archive-{count}")
                self._write_proposal(root, count, materialize=True)
                code, result = self._plan(root)
                self.assertEqual(code, 0, result.get("blockers"))
                self.assertTrue(result["ok"], result.get("blockers"))
                self.assertFalse(result["summary"]["truncated_due_to_max_items"])
                self.assertEqual(result["summary"]["proposal_line_count"], count)
                self.assertEqual(result["summary"]["candidate_count"], count)
                self.assertEqual(result["summary"]["ready_for_review_count"], count)
                self.assertEqual(len(result["items"]), count)
                self.assertNotIn("proposal_exceeds_max_items", result["blockers"])

        root = self.fresh_root("archive-5001")
        self._write_proposal(root, 5001, materialize=False)
        code, result = self._plan(root)
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertIn("proposal_exceeds_max_items", result["blockers"])
        self.assertTrue(result["summary"]["truncated_due_to_max_items"])
        self.assertEqual(result["summary"]["proposal_line_count"], 5001)
        self.assertEqual(result["summary"]["candidate_count"], 5000)


class UnpublishedDraftReportingTests(_ArchiveFixtureCase):
    def test_s2_u15_unpublished_draft_is_never_reported_complete(self) -> None:
        """S2-U15: one inbox draft beside minted zets surfaces as attention with a mint-zet preview."""
        self.assertEqual(len(list((self.root / "inbox").glob("*.md"))), 1)
        self.assertGreaterEqual(len(list((self.root / "zettels").glob("*.md"))), 1)
        self.assertTrue(services.index_archive(self.root)["ok"])

        code, start = self.invoke_json(["ai-start-here", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, start.get("blockers"))
        attention = start["inbox_attention"]
        self.assertTrue(attention["complete"])
        self.assertGreaterEqual(attention["unpublished_draft_count"], 1)
        self.assertEqual(attention["status"], "attention")
        self.assertTrue(attention["review_recommended"])
        self.assertIn("unpublished draft", attention["human_summary"])
        self.assertFalse(attention["paths_titles_or_body_echoed"])
        routes = json.dumps(start["action_routing"], ensure_ascii=False)
        self.assertRegex(routes, r"archive mint-zet [^\"]*--dry-run")

        code, handoff = self.invoke_json(
            ["session-handoff-checkpoint", str(self.root), "--dry-run", "--format", "json"])
        self.assertEqual(code, 0, handoff.get("blockers"))
        self.assertFalse(handoff["ready_for_context_reset"])
        # The checkpoint carries the same content-free inbox block and says in
        # its next safe actions that it does not publish the remaining drafts.
        self.assertGreaterEqual(handoff["inbox_attention"]["unpublished_draft_count"], 1)
        self.assertFalse(handoff["inbox_attention"]["paths_titles_or_body_echoed"])
        actions = "\n".join(str(action) for action in handoff["next_safe_actions"])
        self.assertIn("unpublished inbox draft", actions)
        self.assertIn("mint-zet --dry-run", actions)


class RuntimeSkillGuidanceTests(unittest.TestCase):
    # S2-U16 gap: skill omits zet-quality-check -- at S2 intake the runtime skill
    # named create-draft and mint-zet but no quality gate between them. The
    # skill was amended in the same worktree while this test was written; the
    # test keeps failing loudly if the chain or any named command disappears.
    def test_s2_u16_skill_names_the_create_quality_mint_chain_with_real_commands(self) -> None:
        """S2-U16: the skill names create-draft, zet-quality-check, mint-zet; every archive command exists."""
        texts = _skill_texts()
        commands = _parser_commands()
        joined = "\n".join(texts.values())
        missing = [
            name for name in ("create-draft", "zet-quality-check", "mint-zet")
            if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", joined)]
        self.assertEqual(missing, [], f"runtime skill text never names {missing}; parser has them: "
                                      f"{[name in commands for name in missing]}")

        named: dict[str, set[str]] = {}
        for file_name, text in texts.items():
            spans = re.findall(r"`([^`\n]*)`", text) + re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
            for span in spans:
                for match in re.finditer(r"(?<![\w./-])archive ([a-z][a-z0-9-]*)(?![\w-])", span):
                    named.setdefault(match.group(1), set()).add(file_name)
        self.assertGreaterEqual(len(named), 20)
        unknown = {name: sorted(files) for name, files in named.items() if name not in commands}
        self.assertEqual(unknown, {}, f"skill names commands the parser lacks: {unknown}")


class ScratchRootMatrixTests(_ArchiveFixtureCase):
    ROWS = (
        ("zet-title-remap-plan", "--proposal", ".wom-scratch/title-remap/reviewed.jsonl",
         "elsewhere/reviewed.jsonl", "proposal_path_outside_private_scratch"),
        ("activity-group-membership-plan", "--request", ".wom-scratch/private/activity-groups/req.json",
         "elsewhere/req.json", "request_path_outside_private_activity_group_scratch"),
        ("notion-import-locator-evidence-plan", "--evidence",
         ".wom-scratch/notion-locator-evidence/evidence.jsonl", "elsewhere/evidence.jsonl",
         "evidence_path_outside_private_scratch"),
        ("operator-feedback-compose", "--request", "profiles/local/operator-feedback/requests/req.json",
         "elsewhere/req.json", "feedback_body_request_path_invalid"),
    )
    PATH_CODES = {row[4] for row in ROWS}

    def _codes(self, command: str, flag: str, relative: str) -> list[str]:
        code, out, err = self.invoke([command, str(self.root), flag, relative, "--dry-run", "--format", "json"])
        if not out.strip():
            self.assertEqual(code, 1)
            return re.findall(r"blocked \[([a-z_]+)\]", err)
        result = json.loads(out)
        return list(result.get("blockers") or result.get("blocker_codes") or [])

    def test_s2_u17_request_outside_documented_root_yields_only_the_path_code(self) -> None:
        """S2-U17: in-root requests reach schema checks; out-of-root requests name the path code only."""
        for command, flag, inside, outside, path_code in self.ROWS:
            with self.subTest(command=command):
                for relative in (inside, outside):
                    path = self.root.joinpath(*relative.split("/"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}\n", encoding="utf-8")
                inside_codes = self._codes(command, flag, inside)
                self.assertTrue(inside_codes, "an empty request should reach schema/metadata checks")
                self.assertFalse(set(inside_codes) & self.PATH_CODES, inside_codes)
                self.assertFalse([c for c in inside_codes if "path" in c or "root" in c], inside_codes)
                outside_codes = self._codes(command, flag, outside)
                self.assertEqual(outside_codes, [path_code])


if __name__ == "__main__":
    unittest.main()
