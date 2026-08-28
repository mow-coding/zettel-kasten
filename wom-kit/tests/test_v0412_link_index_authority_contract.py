from __future__ import annotations

import copy
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Mapping

from wom_kit import archive_services, completion_workflows, operation_approval_binding
from wom_kit.exact_human_approval import (
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ROLE = "evidence"
REVIEWER = "person:v0412-link-index-contract"

# v0.4.12 introduces one opaque, generation-bound accelerator.  This test names
# the smallest expected internal API explicitly so implementation does not add a
# second public command or weaken the existing zettel_objet_link_plan surface:
#
#   build_zettel_objet_link_authority_projection(archive_root) -> Mapping
#   zettel_objet_link_plan(..., authority_projection=<that Mapping>) -> Mapping
#
# The projection must expose only the stable schema/generation bindings needed
# for validation.  It remains an accelerator; final descriptor, duplicate-ID,
# reparse-point, manifest, and Windows stable-point proofs stay authoritative.
PROJECTION_BUILDER_API = "build_zettel_objet_link_authority_projection"
PROJECTION_PLAN_ARGUMENT = "authority_projection"


class V0412LinkIndexAuthorityContractTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        return root

    @staticmethod
    def zettel_path(root: Path) -> Path:
        return root / "zettels" / f"{ZETTEL_ID}.md"

    @staticmethod
    def manifest_path(root: Path) -> Path:
        return root / "objects" / "manifests" / "files.jsonl"

    def index(self, root: Path) -> dict[str, Any]:
        result = archive_services.index_archive(root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["index_state"], archive_services.INDEX_STATE_CURRENT)
        return result

    def projection_builder(self) -> Callable[[Path], Mapping[str, Any]]:
        builder = getattr(completion_workflows, PROJECTION_BUILDER_API, None)
        self.assertTrue(
            callable(builder),
            (
                "v0.4.12 requires completion_workflows."
                f"{PROJECTION_BUILDER_API}(archive_root); the projection API "
                "does not exist yet"
            ),
        )
        return builder

    def build_projection(self, root: Path) -> dict[str, Any]:
        builder = self.projection_builder()
        projection = builder(root)
        self.assertIsInstance(projection, Mapping)
        projected = dict(projection)
        self.assertEqual(
            projected.get("schema"),
            "wom-kit/zettel-objet-link-authority-projection/v0.1",
        )
        self.assertRegex(str(projected.get("generation") or ""), r"^gen:[0-9a-f]{32}$")
        self.assertRegex(
            str(projected.get("manifest_sha256") or ""),
            r"^sha256:[0-9a-f]{64}$",
        )
        return projected

    def projected_plan(
        self,
        root: Path,
        projection: Mapping[str, Any],
    ) -> dict[str, Any]:
        signature = inspect.signature(completion_workflows.zettel_objet_link_plan)
        self.assertIn(
            PROJECTION_PLAN_ARGUMENT,
            signature.parameters,
            (
                "v0.4.12 requires zettel_objet_link_plan(..., "
                f"{PROJECTION_PLAN_ARGUMENT}=projection); the bounded plan "
                "entrypoint is not wired yet"
            ),
        )
        return completion_workflows.zettel_objet_link_plan(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
            authority_projection=projection,
        )

    @staticmethod
    def public_plan_identity(result: Mapping[str, Any]) -> tuple[Any, ...]:
        summary = result.get("summary")
        summary_mapping = summary if isinstance(summary, Mapping) else {}
        return (
            result.get("ok"),
            result.get("state"),
            tuple(result.get("reason_codes") or ()),
            tuple(result.get("blockers") or ()),
            summary_mapping.get("plan_sha256"),
        )

    def seed_existing_link(self, root: Path) -> None:
        path = self.zettel_path(root)
        text = path.read_text(encoding="utf-8")
        replacement = (
            "assets:\n"
            f"  - object_id: {OBJECT_ID}\n"
            f"    role: {ROLE}"
        )
        self.assertEqual(text.count("assets: []"), 1)
        path.write_text(text.replace("assets: []", replacement), encoding="utf-8")

    def seed_private_sentinels(self, root: Path) -> tuple[str, str]:
        title = "PRIVATE_V0412_TITLE_MUST_NOT_ESCAPE"
        body = "PRIVATE_V0412_BODY_MUST_NOT_ESCAPE"
        path = self.zettel_path(root)
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "title: Fake thought while eating alone",
            f"title: {title}",
        ).replace(
            "This zettel represents a private personal reflection.",
            body,
        )
        path.write_text(text, encoding="utf-8")
        return title, body

    def assert_content_free_failure(
        self,
        result: Mapping[str, Any],
        expected_code: str,
        *,
        root: Path,
        private_values: tuple[str, ...],
    ) -> None:
        self.assertFalse(result.get("ok"), result)
        self.assertEqual(result.get("state"), "blocked", result)
        self.assertEqual(result.get("reason_codes"), [expected_code], result)
        self.assertIn(expected_code, result.get("blockers") or (), result)
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            ZETTEL_ID,
            OBJECT_ID,
            str(root),
            root.as_posix(),
            *private_values,
        ):
            self.assertNotIn(forbidden, rendered)

    def test_twenty_unchanged_projection_plans_are_digest_and_status_stable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            self.index(root)
            projection = self.build_projection(root)

            plans = [self.projected_plan(root, projection) for _ in range(20)]

        identities = [self.public_plan_identity(plan) for plan in plans]
        self.assertEqual(len(set(identities)), 1, identities)
        self.assertTrue(plans[0]["ok"], plans[0])
        self.assertEqual(plans[0]["state"], "ready")
        self.assertRegex(
            str(plans[0]["summary"]["plan_sha256"]),
            r"^[0-9a-f]{64}$",
        )
        self.assertEqual(
            plans[0]["summary"].get("index_generation"),
            projection["generation"],
        )
        self.assertEqual(
            plans[0]["summary"].get("manifest_sha256"),
            projection["manifest_sha256"],
        )

    def test_twenty_existing_link_plans_are_stable_already_present(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            self.seed_existing_link(root)
            self.index(root)
            projection = self.build_projection(root)

            plans = [self.projected_plan(root, projection) for _ in range(20)]

        rendered = [json.dumps(plan, ensure_ascii=False, sort_keys=True) for plan in plans]
        self.assertEqual(len(set(rendered)), 1, plans)
        for plan in plans:
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(plan["state"], "already_present", plan)
            self.assertEqual(plan.get("reason_codes"), [], plan)
            self.assertEqual(plan["blockers"], [], plan)
            self.assertEqual(plan["would_change"], [], plan)
            summary = plan.get("summary") or {}
            self.assertEqual(
                summary.get("index_generation"),
                projection["generation"],
            )
            self.assertEqual(
                summary.get("manifest_sha256"),
                projection["manifest_sha256"],
            )
            self.assertNotIn("receipt_path", summary)
            self.assertNotIn("receipt_generation", summary)
            self.assertNotIn("zettel_unavailable", rendered[0])
            self.assertNotIn("plan_changed", rendered[0])

    def test_projection_duplicate_tree_drift_and_manifest_drift_have_distinct_codes(
        self,
    ) -> None:
        cases = (
            ("projection_stale", "zettel_identity_projection_stale"),
            ("duplicate_id", "zettel_identity_duplicate"),
            ("canonical_drift", "zettel_tree_changed_during_plan"),
            ("manifest_drift", "manifest_changed"),
        )
        for mutation, expected_code in cases:
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = self.archive(Path(temp_dir))
                    title, body = self.seed_private_sentinels(root)
                    self.index(root)
                    projection = self.build_projection(root)

                    if mutation == "projection_stale":
                        projection = copy.deepcopy(projection)
                        projection["generation"] = "gen:" + "f" * 32
                    elif mutation == "duplicate_id":
                        shutil.copyfile(
                            self.zettel_path(root),
                            root / "zettels" / "PRIVATE_DUPLICATE_TARGET.md",
                        )
                    elif mutation == "canonical_drift":
                        with self.zettel_path(root).open("a", encoding="utf-8") as handle:
                            handle.write("\nPRIVATE_CANONICAL_DRIFT\n")
                    elif mutation == "manifest_drift":
                        with self.manifest_path(root).open("ab") as handle:
                            handle.write(b"\n")
                    else:  # pragma: no cover - guards the test table itself
                        self.fail(f"unknown mutation: {mutation}")

                    result = self.projected_plan(root, projection)
                    self.assert_content_free_failure(
                        result,
                        expected_code,
                        root=root,
                        private_values=(
                            title,
                            body,
                            "PRIVATE_DUPLICATE_TARGET.md",
                            "PRIVATE_CANONICAL_DRIFT",
                        ),
                    )

    def test_successful_link_writer_seals_index_delta_or_leaves_durable_dirty_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            index_result = self.index(root)
            expected_generation = str(index_result["index_generation"])
            plan = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertTrue(plan["ok"], plan)
            binding = operation_approval_binding.zettel_objet_link_approval_binding(plan)
            context = binding.context(
                archive_id=archive_services.read_archive_id(root),
                reviewer_claim=REVIEWER,
            )
            claim = claim_exact_human_approval(
                root,
                context,
                ExactHumanApprovalDecision(
                    approved=True,
                    synthetic_acknowledged=False,
                    reason_code="exact_human_approval_approved",
                    plan_sha256=context.plan_sha256,
                    target_binding_sha256=context.target_binding_sha256,
                ),
                bytearray(b"I" * 32),
            )
            try:
                result = completion_workflows.zettel_objet_link_apply(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                    expected_plan_sha256=str(plan["summary"]["plan_sha256"]),
                    reviewed_by=REVIEWER,
                    expected_exact_approval_plan_sha256=binding.plan_sha256,
                    expected_exact_approval_target_binding_sha256=(
                        binding.target_binding_sha256
                    ),
                    exact_human_approval_claim=claim,
                )
                self.assertTrue(result["ok"], result)
                if claim.status == "started":
                    claim.finalize_succeeded()
            finally:
                if claim.status == "started":
                    claim.finalize_failed("operation_blocked")
                claim.close()

            db_path = root / archive_services.INDEX_RELATIVE_PATH
            conn = archive_services.connect_archive_index(db_path, row_factory=True)
            try:
                metadata = archive_services.read_archive_index_metadata(conn)
                indexed = conn.execute(
                    "SELECT frontmatter_json FROM zettels WHERE zettel_id = ?",
                    (ZETTEL_ID,),
                ).fetchone()
            finally:
                conn.close()

            durable_dirty = (
                metadata.get("state") == archive_services.INDEX_STATE_DIRTY
                and metadata.get("generation") == expected_generation
            )
            sealed_delta = False
            if metadata.get("state") == archive_services.INDEX_STATE_CURRENT and indexed:
                frontmatter = json.loads(str(indexed["frontmatter_json"]))
                raw_assets = frontmatter.get("assets")
                assets = raw_assets if isinstance(raw_assets, list) else []
                sealed_delta = (
                    metadata.get("generation") == expected_generation
                    and any(
                        isinstance(item, Mapping)
                        and item.get("object_id") == OBJECT_ID
                        and item.get("role") == ROLE
                        for item in assets
                    )
                    and archive_services.require_current_zettel_index(root).get("ok")
                    is True
                )

            self.assertTrue(
                durable_dirty or sealed_delta,
                (
                    "zettel_objet_link_apply changed a canonical zet without "
                    "sealing its exact index delta or durably marking the same "
                    "index generation dirty"
                ),
            )


if __name__ == "__main__":
    unittest.main()
