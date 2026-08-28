from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest import mock

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
REVIEWER = "person:v0412-link-index-lifecycle"


class V0412LinkIndexLifecycleTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        return root

    @staticmethod
    def zettel_path(root: Path) -> Path:
        return root / "zettels" / f"{ZETTEL_ID}.md"

    @staticmethod
    def metadata(root: Path) -> dict[str, str]:
        conn = archive_services.connect_archive_index(
            root / archive_services.INDEX_RELATIVE_PATH,
            row_factory=True,
        )
        try:
            return archive_services.read_archive_index_metadata(conn)
        finally:
            conn.close()

    def index(self, root: Path) -> str:
        result = archive_services.index_archive(root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["index_state"], archive_services.INDEX_STATE_CURRENT)
        generation = str(result["index_generation"])
        self.assertRegex(generation, r"^gen:[0-9a-f]{32}$")
        return generation

    def plan(self, root: Path, *, expected_generation: str) -> dict[str, Any]:
        result = completion_workflows.zettel_objet_link_plan(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "ready", result)
        self.assertEqual(
            result.get("summary", {}).get("index_generation"),
            expected_generation,
            "the service plan must bind the current index generation",
        )
        return result

    def claim(self, root: Path, plan: Mapping[str, Any]):
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
            bytearray(b"J" * 32),
        )
        return binding, claim

    @staticmethod
    def finish_claim(claim, *, succeeded: bool) -> None:
        try:
            if claim.status == "started":
                if succeeded:
                    claim.finalize_succeeded()
                else:
                    claim.finalize_failed("operation_blocked")
        finally:
            claim.close()

    @staticmethod
    def apply(
        root: Path,
        plan: Mapping[str, Any],
        binding,
        claim,
    ) -> dict[str, Any]:
        return completion_workflows.zettel_objet_link_apply(
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

    def assert_canonical_asset(self, root: Path) -> None:
        frontmatter, _body = archive_services.require_readable_zettel_content(
            self.zettel_path(root)
        )
        assets = frontmatter.get("assets")
        self.assertIsInstance(assets, list)
        self.assertTrue(
            any(
                isinstance(item, Mapping)
                and item.get("object_id") == OBJECT_ID
                and item.get("role") == ROLE
                for item in assets
            ),
            assets,
        )

    def seed_existing_link(self, root: Path) -> None:
        zettel_path = self.zettel_path(root)
        frontmatter, body = archive_services.require_readable_zettel_content(zettel_path)
        frontmatter = dict(frontmatter)
        frontmatter["assets"] = [
            *list(frontmatter.get("assets") or []),
            {"object_id": OBJECT_ID, "role": ROLE},
        ]
        zettel_path.write_text(
            "---\n" + archive_services.dump_yaml(frontmatter) + "---\n" + body,
            encoding="utf-8",
            newline="\n",
        )

    def test_success_keeps_same_generation_current_and_searchable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            succeeded = False
            index_path = root / archive_services.INDEX_RELATIVE_PATH
            index_before = hashlib.sha256(index_path.read_bytes()).hexdigest()
            try:
                result = self.apply(root, plan, binding, claim)
                self.assertTrue(result["ok"], result)
                self.assertIn(
                    archive_services.INDEX_RELATIVE_PATH,
                    result["files_written"],
                )
                self.assertTrue(result["generated_index_updated"])
                self.assertFalse(result["index_marked_dirty"])
                self.assertNotEqual(
                    hashlib.sha256(index_path.read_bytes()).hexdigest(),
                    index_before,
                )
                succeeded = True
            finally:
                self.finish_claim(claim, succeeded=succeeded)

            self.assert_canonical_asset(root)
            metadata = self.metadata(root)
            self.assertEqual(metadata["state"], archive_services.INDEX_STATE_CURRENT)
            self.assertEqual(metadata["generation"], generation)

            conn = archive_services.connect_archive_index(
                root / archive_services.INDEX_RELATIVE_PATH,
                row_factory=True,
            )
            try:
                row = conn.execute(
                    "SELECT frontmatter_json FROM zettels WHERE zettel_id = ?",
                    (ZETTEL_ID,),
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            indexed_frontmatter = json.loads(str(row["frontmatter_json"]))
            self.assertTrue(
                any(
                    isinstance(item, Mapping)
                    and item.get("object_id") == OBJECT_ID
                    and item.get("role") == ROLE
                    for item in indexed_frontmatter.get("assets", [])
                ),
                indexed_frontmatter,
            )

            search = archive_services.search_archive(root, OBJECT_ID[7:31])
            self.assertTrue(search["ok"], search)
            self.assertEqual(
                search["index_evidence"]["generation"],
                generation,
            )
            self.assertIn(
                ZETTEL_ID,
                [item.get("id") for item in search["results"]],
            )

    def test_upsert_failure_preserves_link_and_receipt_and_same_generation_dirty(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            receipt_path = root.joinpath(*str(plan["summary"]["receipt_path"]).split("/"))
            binding, claim = self.claim(root, plan)
            index_path = root / archive_services.INDEX_RELATIVE_PATH
            index_before = hashlib.sha256(index_path.read_bytes()).hexdigest()

            def fail_after_final_authority(*args, **kwargs):
                final_authority_check = kwargs.get("_final_authority_check")
                self.assertTrue(callable(final_authority_check))
                self.assertTrue(final_authority_check())
                return False

            try:
                with mock.patch.object(
                    archive_services,
                    "upsert_zettel_index_entry",
                    side_effect=fail_after_final_authority,
                ) as upsert:
                    result = self.apply(root, plan, binding, claim)

                self.assertFalse(result["ok"], result)
                self.assertEqual(
                    result["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
                self.assertIn(
                    archive_services.INDEX_RELATIVE_PATH,
                    result["files_written"],
                )
                self.assertFalse(result["generated_index_updated"])
                self.assertTrue(result["index_marked_dirty"])
                self.assertNotEqual(
                    hashlib.sha256(index_path.read_bytes()).hexdigest(),
                    index_before,
                )
                upsert.assert_called_once()
                call_args, call_kwargs = upsert.call_args
                self.assertTrue(
                    Path(call_args[1]).samefile(self.zettel_path(root))
                )
                self.assertEqual(call_kwargs.get("expected_generation"), generation)
                self.assertEqual(
                    call_kwargs.get("expected_file_sha256"),
                    hashlib.sha256(self.zettel_path(root).read_bytes()).hexdigest(),
                )

                self.assert_canonical_asset(root)
                self.assertTrue(receipt_path.is_file())
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertEqual(receipt["zettel_id"], ZETTEL_ID)
                self.assertEqual(receipt["object_id"], OBJECT_ID)

                metadata = self.metadata(root)
                self.assertEqual(metadata["state"], archive_services.INDEX_STATE_DIRTY)
                self.assertEqual(metadata["generation"], generation)
                current = archive_services.require_current_zettel_index(root)
                self.assertFalse(current["ok"], current)
                self.assertEqual(
                    current["blockers"],
                    [archive_services.INDEX_REBUILD_REQUIRED],
                )
            finally:
                self.finish_claim(claim, succeeded=False)

    def test_already_present_plan_does_not_begin_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            self.seed_existing_link(root)
            generation = self.index(root)

            with mock.patch.object(
                archive_services,
                "begin_archive_index_mutation",
                side_effect=AssertionError("already_present must not begin a mutation"),
            ) as begin, mock.patch.object(
                archive_services,
                "upsert_zettel_index_entry",
                side_effect=AssertionError("already_present must not update the index"),
            ) as upsert, mock.patch.object(
                archive_services,
                "_replace_regular_file_bytes_compare_and_swap",
                side_effect=AssertionError("already_present must not rewrite the zettel"),
            ) as replace, mock.patch.object(
                archive_services,
                "_write_activity_group_bytes_new_file_bound",
                side_effect=AssertionError("already_present must not write support files"),
            ) as create:
                result = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "already_present", result)
            self.assertEqual(result["blockers"], [], result)
            self.assertEqual(result["would_change"], [], result)
            self.assertEqual(result["summary"].get("index_generation"), generation)
            begin.assert_not_called()
            upsert.assert_not_called()
            replace.assert_not_called()
            create.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows projection fast path")
    def test_windows_apply_never_reenters_legacy_full_tree_or_manifest_parsers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            succeeded = False
            try:
                with mock.patch.object(
                    completion_workflows,
                    "_resolve_zettel_objet_link_target_bound",
                    side_effect=AssertionError(
                        "Windows apply must not re-scan every Zet body"
                    ),
                ) as resolver, mock.patch.object(
                    completion_workflows,
                    "_strict_zettel_objet_manifest_records",
                    side_effect=AssertionError(
                        "Windows apply must not reparse the full manifest"
                    ),
                ) as path_parser, mock.patch.object(
                    completion_workflows,
                    "_strict_zettel_objet_manifest_records_from_bytes",
                    side_effect=AssertionError(
                        "Windows apply must not reparse the full manifest bytes"
                    ),
                ) as bytes_parser:
                    result = self.apply(root, plan, binding, claim)

                self.assertTrue(result["ok"], result)
                succeeded = True
                resolver.assert_not_called()
                path_parser.assert_not_called()
                bytes_parser.assert_not_called()
            finally:
                self.finish_claim(claim, succeeded=succeeded)

    def test_portable_reproof_to_upsert_transient_edit_is_blocked(self) -> None:
        transient = {"occurred": False}

        class SyntheticAuthorityFence:
            def __init__(self, _root: Path) -> None:
                self.started_before_transient = not transient["occurred"]
                self.verified = False

            def arm_closing_guard(self) -> None:
                return None

            def verify_clean(self) -> None:
                if (
                    self.started_before_transient
                    and transient["occurred"]
                    and not self.verified
                ):
                    raise OSError("synthetic_transient_source_change")
                self.verified = True

            def close(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            binding, claim = self.claim(root, plan)
            before = self.zettel_path(root).read_bytes()
            unrelated = next(
                path
                for path in sorted((root / "zettels").glob("*.md"))
                if path != self.zettel_path(root)
            )
            unrelated_before = unrelated.read_bytes()
            real_resolver = (
                completion_workflows._resolve_zettel_objet_link_target_bound
            )

            def resolve_then_transient_edit(*args, **kwargs):
                resolved = real_resolver(*args, **kwargs)
                with unrelated.open("ab") as handle:
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                unrelated.write_bytes(unrelated_before)
                transient["occurred"] = True
                return resolved

            try:
                with (
                    mock.patch.object(
                        completion_workflows,
                        "_zettel_objet_link_use_windows_projection_watchers",
                        return_value=False,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_ArchiveIndexAuthorityFence",
                        SyntheticAuthorityFence,
                    ),
                    mock.patch.object(
                        completion_workflows,
                        "_resolve_zettel_objet_link_target_bound",
                        side_effect=resolve_then_transient_edit,
                    ),
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(transient["occurred"])
                self.assertEqual(unrelated.read_bytes(), unrelated_before)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                metadata = self.metadata(root)
                self.assertIn(
                    metadata["state"],
                    {
                        archive_services.INDEX_STATE_CURRENT,
                        archive_services.INDEX_STATE_DIRTY,
                    },
                )
                self.assertEqual(metadata["generation"], generation)
                if metadata["state"] == archive_services.INDEX_STATE_DIRTY:
                    health = archive_services.require_current_zettel_index(root)
                    self.assertFalse(health["ok"], health)
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows projection stable point")
    def test_windows_final_projection_rejects_late_duplicate_and_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            receipt_path = root.joinpath(
                *str(plan["summary"]["receipt_path"]).split("/")
            )
            duplicate_path = root / "inbox" / "late-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows._reprove_zettel_objet_link_dirty_projection
            )
            injected = False

            def inject_duplicate(*args, **kwargs):
                nonlocal injected
                if not injected:
                    shutil.copyfile(self.zettel_path(root), duplicate_path)
                    injected = True
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=inject_duplicate,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(injected)
                self.assertTrue(duplicate_path.is_file())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt_path.is_file())
                metadata = self.metadata(root)
                self.assertEqual(
                    metadata["state"], archive_services.INDEX_STATE_DIRTY
                )
                self.assertEqual(metadata["generation"], generation)
            finally:
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows projection lease lifetime")
    def test_transient_final_duplicate_keeps_lease_through_cas_rollback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            duplicate_path = root / "inbox" / "transient-duplicate.md"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows._reprove_zettel_objet_link_dirty_projection
            )
            real_swap = (
                archive_services._replace_regular_file_bytes_compare_and_swap
            )
            transient_injected = False
            rollback_observed_lease = False
            rebuild_blocked = False

            def inject_transient_duplicate(*args, **kwargs):
                nonlocal transient_injected
                proof = real_reprove(*args, **kwargs)
                shutil.copyfile(self.zettel_path(root), duplicate_path)
                duplicate_path.unlink()
                transient_injected = True
                return proof

            def assert_lease_then_swap(*args, **kwargs):
                nonlocal rollback_observed_lease, rebuild_blocked
                health = archive_services.require_current_zettel_index(root)
                self.assertFalse(health["ok"], health)
                self.assertIn(
                    "archive_index_mutation_in_progress",
                    health["reason_codes"],
                )
                rollback_observed_lease = True
                try:
                    archive_services.index_archive(root)
                except archive_services.ArchiveServiceError:
                    rebuild_blocked = True
                else:
                    self.fail("rebuild entered while rollback lease was active")
                return real_swap(*args, **kwargs)

            try:
                with (
                    mock.patch.object(
                        completion_workflows,
                        "_reprove_zettel_objet_link_dirty_projection",
                        side_effect=inject_transient_duplicate,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_replace_regular_file_bytes_compare_and_swap",
                        side_effect=assert_lease_then_swap,
                    ),
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_zettel_authority_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(transient_injected)
                self.assertTrue(rollback_observed_lease)
                self.assertTrue(rebuild_blocked)
                self.assertFalse(duplicate_path.exists())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                metadata = self.metadata(root)
                self.assertEqual(metadata["generation"], generation)
                self.assertIn(
                    metadata["state"],
                    {
                        archive_services.INDEX_STATE_CURRENT,
                        archive_services.INDEX_STATE_DIRTY,
                    },
                )
                if metadata["state"] == archive_services.INDEX_STATE_DIRTY:
                    health = archive_services.require_current_zettel_index(root)
                    self.assertFalse(health["ok"], health)
            finally:
                self.finish_claim(claim, succeeded=False)

    def test_keyboard_interrupt_in_final_watcher_keeps_rollback_lease(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            real_begin = archive_services.begin_archive_index_mutation
            real_commit = (
                archive_services._commit_archive_index_seal_with_fence
            )
            real_swap = (
                archive_services._replace_regular_file_bytes_compare_and_swap
            )
            token_holder = {"token": None}
            rollback_lease_proven = False
            commit_calls = 0

            def capture_begin(*args, **kwargs):
                token = real_begin(*args, **kwargs)
                token_holder["token"] = token
                return token

            def interrupt_first_final_watcher(*args, **kwargs):
                nonlocal commit_calls
                commit_calls += 1
                if commit_calls != 1:
                    return real_commit(*args, **kwargs)
                authority_fence = kwargs["authority_fence"]
                with mock.patch.object(
                    authority_fence,
                    "arm_closing_guard",
                    side_effect=KeyboardInterrupt(),
                ):
                    return real_commit(*args, **kwargs)

            def prove_lease_then_swap(*args, **kwargs):
                nonlocal rollback_lease_proven
                archive_services._require_archive_index_mutation_lease(
                    root,
                    expected_generation=generation,
                    lease_token=token_holder["token"],
                )
                rollback_lease_proven = True
                return real_swap(*args, **kwargs)

            try:
                with (
                    mock.patch.object(
                        archive_services,
                        "begin_archive_index_mutation",
                        side_effect=capture_begin,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_commit_archive_index_seal_with_fence",
                        side_effect=interrupt_first_final_watcher,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_replace_regular_file_bytes_compare_and_swap",
                        side_effect=prove_lease_then_swap,
                    ),
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(rollback_lease_proven)
                self.assertGreaterEqual(commit_calls, 2)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                metadata = self.metadata(root)
                self.assertEqual(metadata["generation"], generation)
                self.assertIn(
                    metadata["state"],
                    {
                        archive_services.INDEX_STATE_CURRENT,
                        archive_services.INDEX_STATE_DIRTY,
                    },
                )
            finally:
                token = token_holder.get("token")
                if token is not None:
                    archive_services._release_archive_index_mutation_lease(
                        root,
                        lease_token=token,
                    )
                self.finish_claim(claim, succeeded=False)

    def test_failed_rollback_upsert_retains_lease_when_dirty_is_uncertain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            binding, claim = self.claim(root, plan)
            real_begin = archive_services.begin_archive_index_mutation
            token_holder = {"token": None}
            internal_calls = 0
            dirty_call_held_lease = False

            def capture_begin(*args, **kwargs):
                token = real_begin(*args, **kwargs)
                token_holder["token"] = token
                return token

            def fail_forward_then_rollback(*args, **kwargs):
                nonlocal internal_calls
                internal_calls += 1
                if internal_calls == 1:
                    raise archive_services._ArchiveIndexFinalAuthorityChangedError(
                        "archive_index_final_authority_changed"
                    )
                return False

            def uncertain_dirty(*args, **kwargs):
                nonlocal dirty_call_held_lease
                archive_services._require_archive_index_mutation_lease(
                    root,
                    expected_generation=generation,
                    lease_token=kwargs.get("lease_token"),
                )
                dirty_call_held_lease = True
                raise archive_services._ArchiveIndexDirtyRestoreUncertainError(
                    "archive_index_dirty_restore_uncertain"
                )

            try:
                with (
                    mock.patch.object(
                        archive_services,
                        "begin_archive_index_mutation",
                        side_effect=capture_begin,
                    ),
                    mock.patch.object(
                        archive_services,
                        "_upsert_zettel_index_entry_with_lease",
                        side_effect=fail_forward_then_rollback,
                    ),
                    mock.patch.object(
                        archive_services,
                        "mark_archive_index_dirty",
                        side_effect=uncertain_dirty,
                    ),
                ):
                    with self.assertRaisesRegex(
                        archive_services._ArchiveIndexDirtyRestoreUncertainError,
                        "archive_index_dirty_restore_uncertain",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertEqual(internal_calls, 2)
                self.assertTrue(dirty_call_held_lease)
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                archive_services._require_archive_index_mutation_lease(
                    root,
                    expected_generation=generation,
                    lease_token=token_holder["token"],
                )
            finally:
                token = token_holder.get("token")
                if token is not None:
                    archive_services._release_archive_index_mutation_lease(
                        root,
                        lease_token=token,
                    )
                self.finish_claim(claim, succeeded=False)

    @unittest.skipUnless(os.name == "nt", "Windows projection stable point")
    def test_windows_final_projection_rejects_manifest_drift_and_rolls_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            plan = self.plan(root, expected_generation=generation)
            before = self.zettel_path(root).read_bytes()
            receipt_path = root.joinpath(
                *str(plan["summary"]["receipt_path"]).split("/")
            )
            manifest_path = root / "objects" / "manifests" / "files.jsonl"
            binding, claim = self.claim(root, plan)
            real_reprove = (
                completion_workflows._reprove_zettel_objet_link_dirty_projection
            )
            removed = False

            def remove_manifest(*args, **kwargs):
                nonlocal removed
                if not removed:
                    manifest_path.unlink()
                    removed = True
                return real_reprove(*args, **kwargs)

            try:
                with mock.patch.object(
                    completion_workflows,
                    "_reprove_zettel_objet_link_dirty_projection",
                    side_effect=remove_manifest,
                ):
                    with self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_manifest_changed_after_approval",
                    ):
                        self.apply(root, plan, binding, claim)

                self.assertTrue(removed)
                self.assertFalse(manifest_path.exists())
                self.assertEqual(self.zettel_path(root).read_bytes(), before)
                self.assertTrue(receipt_path.is_file())
                metadata = self.metadata(root)
                self.assertEqual(
                    metadata["state"], archive_services.INDEX_STATE_DIRTY
                )
                self.assertEqual(metadata["generation"], generation)
            finally:
                self.finish_claim(claim, succeeded=False)

    def test_unowned_dirty_call_cannot_release_active_writer_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )

            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "archive_index_mutation_in_progress",
            ):
                archive_services.index_archive(root)
            # A non-owner may truthfully observe that this exact generation is
            # already durably DIRTY, but it still cannot consume or release
            # the active writer's opaque lease.
            self.assertTrue(
                archive_services.mark_archive_index_dirty(
                    root,
                    expected_generation=generation,
                )
            )
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "archive_index_mutation_in_progress",
            ):
                archive_services.index_archive(root)

            self.assertTrue(
                archive_services.mark_archive_index_dirty(
                    root,
                    expected_generation=generation,
                    lease_token=lease_token,
                )
            )
            rebuilt = archive_services.index_archive(root)
            self.assertTrue(rebuilt["ok"], rebuilt)
            self.assertNotEqual(rebuilt["index_generation"], generation)

    def test_abandoned_dirty_intent_does_not_permanently_block_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self.archive(Path(temp_dir))
            generation = self.index(root)
            lease_token = archive_services.begin_archive_index_mutation(
                root,
                expected_generation=generation,
            )
            archive_services._release_archive_index_mutation_lease(
                root,
                lease_token=lease_token,
            )

            rebuilt = archive_services.index_archive(root)
            self.assertTrue(rebuilt["ok"], rebuilt)
            self.assertNotEqual(rebuilt["index_generation"], generation)


if __name__ == "__main__":
    unittest.main()
