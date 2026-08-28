from __future__ import annotations

import builtins
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

from wom_kit import (
    archive_services,
    completion_workflows,
    operation_approval_binding,
)
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
REVIEWER = "person:letter140-bound-read-privacy-test"


class Letter140BoundReadPrivacyTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        self.reindex(root)
        return root

    def reindex(self, root: Path) -> dict[str, object]:
        indexed = archive_services.index_archive(root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        return indexed

    def plan(self, root: Path) -> dict[str, object]:
        result = completion_workflows.zettel_objet_link_plan(
            root,
            zettel_id=ZETTEL_ID,
            object_id=OBJECT_ID,
            role=ROLE,
        )
        self.assertTrue(result["ok"], result)
        return result

    def apply(self, root: Path, plan: dict[str, object]) -> dict[str, object]:
        claim, binding = self.claim(root, plan)
        succeeded = False
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
            succeeded = True
            return result
        finally:
            try:
                if claim.status == "started":
                    if succeeded:
                        claim.finalize_succeeded()
                    else:
                        claim.finalize_failed("operation_blocked")
            finally:
                claim.close()

    def claim(self, root: Path, plan: dict[str, object]):
        binding = operation_approval_binding.zettel_objet_link_approval_binding(
            plan
        )
        context = binding.context(
            archive_id=archive_services.read_archive_id(root),
            reviewer_claim=REVIEWER,
        )
        return claim_exact_human_approval(
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
        ), binding

    @staticmethod
    def create_directory_junction(link: Path, target: Path) -> None:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise OSError("Windows junction creation failed")

    @staticmethod
    def remove_directory_junction(link: Path) -> None:
        os.rmdir(link)

    def require_directory_junctions(self, parent: Path) -> None:
        target = parent / "junction-probe-target"
        link = parent / "junction-probe-link"
        target.mkdir()
        try:
            self.create_directory_junction(link, target)
        except OSError:
            self.skipTest("Windows directory junctions are unavailable")
        finally:
            if link.exists():
                self.remove_directory_junction(link)

    @contextmanager
    def track_outside_access(self, outside: Path):
        outside_root = outside.resolve()
        counts = {
            "file_open_or_read": 0,
            "directory_scan": 0,
        }

        def is_outside(value: object) -> bool:
            if isinstance(value, int):
                return False
            try:
                candidate = Path(value)  # type: ignore[arg-type]
                return candidate.resolve().is_relative_to(outside_root)
            except (OSError, RuntimeError, TypeError, ValueError):
                return False

        real_builtin_open = builtins.open
        real_path_open = Path.open
        real_scandir = os.scandir
        real_stable_read = archive_services._bounded_stable_regular_file_read
        real_hold_file = archive_services._hold_activity_group_evidence_file

        def tracked_builtin_open(file, *args, **kwargs):
            if is_outside(file):
                counts["file_open_or_read"] += 1
            return real_builtin_open(file, *args, **kwargs)

        def tracked_path_open(path: Path, *args, **kwargs):
            if is_outside(path):
                counts["file_open_or_read"] += 1
            return real_path_open(path, *args, **kwargs)

        def tracked_scandir(path):
            if is_outside(path):
                counts["directory_scan"] += 1
            return real_scandir(path)

        def tracked_stable_read(path: Path, *, max_bytes: int):
            if is_outside(path):
                counts["file_open_or_read"] += 1
            return real_stable_read(path, max_bytes=max_bytes)

        @contextmanager
        def tracked_hold_file(
            archive_root: Path,
            path: Path,
            *,
            max_bytes: int,
        ):
            if is_outside(path):
                counts["file_open_or_read"] += 1
            with real_hold_file(
                archive_root,
                path,
                max_bytes=max_bytes,
            ) as held:
                yield held

        with (
            mock.patch.object(builtins, "open", new=tracked_builtin_open),
            mock.patch.object(Path, "open", new=tracked_path_open),
            mock.patch.object(os, "scandir", new=tracked_scandir),
            mock.patch.object(
                archive_services,
                "_bounded_stable_regular_file_read",
                new=tracked_stable_read,
            ),
            mock.patch.object(
                archive_services,
                "_hold_activity_group_evidence_file",
                new=tracked_hold_file,
            ),
        ):
            yield counts

    def test_normal_plan_apply_and_receipt_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            plan = self.plan(root)
            applied = self.apply(root, plan)
            self.assertTrue(applied["ok"], applied)

            found = completion_workflows.zettel_objet_link_receipts(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )

            self.assertTrue(found["ok"], found)
            self.assertEqual(found["summary"]["validated_receipt_count"], 1)
            self.assertEqual(
                found["summary"]["selected_receipt_path"],
                plan["summary"]["receipt_path"],
            )

    def test_id_lookup_scans_both_roots_and_never_uses_first_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            direct = root / "zettels" / f"{ZETTEL_ID}.md"
            nested = root / "zettels" / "nested" / "renamed.md"
            nested.parent.mkdir()
            direct.rename(nested)
            self.reindex(root)

            renamed = self.plan(root)
            self.assertEqual(
                renamed["summary"]["zettel_path"],
                "zettels/nested/renamed.md",
            )

            duplicate = root / "inbox" / "duplicate-target.md"
            shutil.copyfile(nested, duplicate)
            self.reindex(root)
            ambiguous = completion_workflows.zettel_objet_link_plan(
                root,
                zettel_id=ZETTEL_ID,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertFalse(ambiguous["ok"], ambiguous)
            self.assertIn(
                "zettel_identity_duplicate",
                ambiguous["blockers"],
            )

    def test_path_lookup_scans_both_roots_and_rejects_duplicate_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            direct = root / "zettels" / f"{ZETTEL_ID}.md"
            relative = f"zettels/{ZETTEL_ID}.md"

            unique = completion_workflows.zettel_objet_link_plan(
                root,
                relative_path=relative,
                object_id=OBJECT_ID,
                role=ROLE,
            )
            self.assertTrue(unique["ok"], unique)

            duplicate = root / "inbox" / "duplicate-target.md"
            shutil.copyfile(direct, duplicate)
            self.reindex(root)
            ambiguous = completion_workflows.zettel_objet_link_plan(
                root,
                relative_path=relative,
                object_id=OBJECT_ID,
                role=ROLE,
            )

            self.assertFalse(ambiguous["ok"], ambiguous)
            self.assertIn(
                "zettel_identity_duplicate",
                ambiguous["blockers"],
            )

    def test_path_lookup_rejects_same_bytes_after_leaf_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            direct = (root / "zettels" / f"{ZETTEL_ID}.md").resolve()
            hidden = direct.with_suffix(".hidden")
            relative = f"zettels/{ZETTEL_ID}.md"
            real_lookup = (
                archive_services.lookup_zettel_objet_link_authority_projection
            )
            swapped = False

            def swap_then_lookup(*args, **kwargs):
                nonlocal swapped
                if not swapped:
                    direct.rename(hidden)
                    shutil.copyfile(hidden, direct)
                    swapped = True
                return real_lookup(*args, **kwargs)

            with mock.patch.object(
                archive_services,
                "lookup_zettel_objet_link_authority_projection",
                side_effect=swap_then_lookup,
            ):
                changed = completion_workflows.zettel_objet_link_plan(
                    root,
                    relative_path=relative,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

            self.assertTrue(swapped)
            self.assertFalse(changed["ok"], changed)
            self.assertIn(
                "zettel_tree_changed_during_plan",
                changed["blockers"],
            )

    def test_cross_root_rename_during_scan_blocks_id_and_path_lookup(
        self,
    ) -> None:
        lookups = (
            {"zettel_id": ZETTEL_ID},
            {"relative_path": f"zettels/{ZETTEL_ID}.md"},
        )
        for lookup in lookups:
            with (
                self.subTest(lookup=lookup),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = self.archive(Path(temporary)).resolve()
                zettels = root / "zettels"
                source = root / "inbox" / "moving-duplicate.md"
                destination = zettels / "moving-duplicate.md"
                shutil.copyfile(
                    zettels / f"{ZETTEL_ID}.md",
                    source,
                )
                self.reindex(root)
                real_scandir = os.scandir
                scan_exit_count = 0
                moved = False

                @contextmanager
                def move_after_zettels_snapshot(target):
                    nonlocal scan_exit_count, moved
                    with real_scandir(target) as entries:
                        yield entries
                    scan_exit_count += 1
                    target_is_zettels = False
                    if not isinstance(target, int):
                        try:
                            target_is_zettels = (
                                Path(target).resolve() == zettels
                            )
                        except (OSError, TypeError, ValueError):
                            target_is_zettels = False
                    if (
                        not moved
                        and (
                            target_is_zettels
                            or (os.name != "nt" and scan_exit_count == 2)
                        )
                    ):
                        os.replace(source, destination)
                        moved = True

                with mock.patch.object(
                    completion_workflows.os,
                    "scandir",
                    new=move_after_zettels_snapshot,
                ):
                    changed = completion_workflows.zettel_objet_link_plan(
                        root,
                        object_id=OBJECT_ID,
                        role=ROLE,
                        **lookup,
                    )

                self.assertTrue(moved)
                self.assertTrue(destination.is_file())
                self.assertFalse(source.exists())
                self.assertFalse(changed["ok"], changed)
                self.assertIn(
                    "zettel_identity_projection_stale",
                    changed["blockers"],
                )

    def test_in_place_candidate_mutation_during_scan_blocks_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary)).resolve()
            other = root / "inbox" / "other.md"
            shutil.copyfile(
                root / "zettels" / "zet_20110228_fake_school_record.md",
                other,
            )
            self.reindex(root)
            duplicate_bytes = (
                root / "zettels" / f"{ZETTEL_ID}.md"
            ).read_bytes()
            real_lookup = (
                archive_services.lookup_zettel_objet_link_authority_projection
            )
            mutated = False

            def mutate_then_lookup(*args, **kwargs):
                nonlocal mutated
                if not mutated:
                    other.write_bytes(duplicate_bytes)
                    mutated = True
                return real_lookup(*args, **kwargs)

            with mock.patch.object(
                archive_services,
                "lookup_zettel_objet_link_authority_projection",
                side_effect=mutate_then_lookup,
            ):
                changed = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

            self.assertTrue(mutated)
            self.assertFalse(changed["ok"], changed)
            self.assertIn(
                "zettel_tree_changed_during_plan",
                changed["blockers"],
            )

    def test_absent_inbox_created_after_root_snapshot_blocks_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary)).resolve()
            inbox = root / "inbox"
            inbox.rename(root / "inbox-before-test")
            self.reindex(root)
            zettels = root / "zettels"
            real_scandir = os.scandir
            created = False

            @contextmanager
            def create_inbox_after_zettels_snapshot(target):
                nonlocal created
                with real_scandir(target) as entries:
                    yield entries
                target_is_zettels = False
                if not isinstance(target, int):
                    try:
                        target_is_zettels = Path(target).resolve() == zettels
                    except (OSError, TypeError, ValueError):
                        target_is_zettels = False
                if not created and (
                    target_is_zettels
                    or (os.name != "nt" and not inbox.exists())
                ):
                    inbox.mkdir()
                    shutil.copyfile(
                        zettels / f"{ZETTEL_ID}.md",
                        inbox / "late-root-duplicate.md",
                    )
                    created = True

            with mock.patch.object(
                completion_workflows.os,
                "scandir",
                new=create_inbox_after_zettels_snapshot,
            ):
                changed = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

            self.assertTrue(created)
            self.assertFalse(changed["ok"], changed)
            self.assertIn(
                "zettel_identity_projection_stale",
                changed["blockers"],
            )

    def test_absent_inbox_created_after_missing_probe_blocks_lookup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary)).resolve()
            inbox = root / "inbox"
            inbox.rename(root / "inbox-before-test")
            self.reindex(root)
            zettels = root / "zettels"
            real_chain = (
                archive_services._activity_group_bound_directory_chain
            )
            created = False

            @contextmanager
            def create_inbox_after_absent_probe(
                archive_root: Path,
                target: Path,
            ):
                nonlocal created
                target_path = Path(target).resolve()
                try:
                    with real_chain(archive_root, target) as binding:
                        yield binding
                except FileNotFoundError:
                    if not created and target_path == inbox:
                        inbox.mkdir()
                        shutil.copyfile(
                            zettels / f"{ZETTEL_ID}.md",
                            inbox / "probe-gap-duplicate.md",
                        )
                        created = True
                    raise

            if sys.platform.startswith("linux"):
                real_optional_probe = (
                    archive_services._ArchiveIndexLinuxInotifyWatcher
                    ._watch_optional_zettel_tree
                )

                def linux_create_inbox_after_absent_probe(
                    watcher,
                    folder_root: Path,
                ) -> None:
                    nonlocal created
                    target_path = Path(folder_root).resolve()
                    existed_before = target_path.exists()
                    real_optional_probe(watcher, folder_root)
                    if (
                        not created
                        and not existed_before
                        and target_path == inbox
                    ):
                        inbox.mkdir()
                        shutil.copyfile(
                            zettels / f"{ZETTEL_ID}.md",
                            inbox / "probe-gap-duplicate.md",
                        )
                        created = True

                probe_patch = mock.patch.object(
                    archive_services._ArchiveIndexLinuxInotifyWatcher,
                    "_watch_optional_zettel_tree",
                    new=linux_create_inbox_after_absent_probe,
                )
            else:
                probe_patch = mock.patch.object(
                    archive_services,
                    "_activity_group_bound_directory_chain",
                    new=create_inbox_after_absent_probe,
                )

            with probe_patch:
                changed = completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

            self.assertTrue(created)
            self.assertFalse(changed["ok"], changed)
            self.assertIn(
                "zettel_identity_projection_stale",
                changed["blockers"],
            )

    @unittest.skipUnless(os.name == "nt", "Windows watcher linearization")
    def test_closing_guard_covers_each_initial_watcher_cancel_gap(self) -> None:
        for mode in ("absent_inbox", "zettels_after_cancel"):
            with (
                self.subTest(mode=mode),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = self.archive(Path(temporary)).resolve()
                zettels = root / "zettels"
                inbox = root / "inbox"
                if mode == "absent_inbox":
                    inbox.rename(root / "inbox-before-test")
                    self.reindex(root)
                duplicate = (
                    inbox / "closing-gap.md"
                    if mode == "absent_inbox"
                    else zettels / "closing-gap.md"
                )
                real_verify = (
                    completion_workflows
                    ._ZettelObjetLinkWindowsDirectoryWatcher
                    .verify_clean
                )
                inserted = False

                def verify_then_insert(watcher):
                    nonlocal inserted
                    result = real_verify(watcher)
                    insert_now = (
                        mode == "absent_inbox"
                        and watcher._path == root
                        and watcher._names_only
                    ) or (
                        mode == "zettels_after_cancel"
                        and watcher._path == zettels
                        and watcher._watch_subtree
                    )
                    if insert_now and not inserted:
                        duplicate.parent.mkdir(exist_ok=True)
                        shutil.copyfile(
                            zettels / f"{ZETTEL_ID}.md",
                            duplicate,
                        )
                        inserted = True
                    return result

                with mock.patch.object(
                    completion_workflows
                    ._ZettelObjetLinkWindowsDirectoryWatcher,
                    "verify_clean",
                    new=verify_then_insert,
                ):
                    changed = completion_workflows.zettel_objet_link_plan(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )

                self.assertTrue(inserted)
                self.assertTrue(duplicate.is_file())
                self.assertFalse(changed["ok"], changed)
                self.assertIn(
                    "zettel_identity_projection_stale",
                    changed["blockers"],
                )

    def test_duplicate_archive_id_blocks_every_link_core_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            plan = self.plan(root)
            claim, binding = self.claim(root, plan)
            archive_id = str(plan["archive_id"])
            config = root / "archive.yml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + f"\narchive_id: {archive_id}\n",
                encoding="utf-8",
            )

            calls = (
                lambda: completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                ),
                lambda: completion_workflows.zettel_objet_link_receipts(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                ),
                lambda: completion_workflows.zettel_objet_link_revert_plan(
                    root,
                    receipt="receipts/objects/zettel-links/link."
                    + "0" * 24
                    + ".g0001.json",
                ),
                lambda: completion_workflows.zettel_objet_link_apply(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                    expected_plan_sha256=str(
                        plan["summary"]["plan_sha256"]
                    ),
                    reviewed_by=REVIEWER,
                    expected_exact_approval_plan_sha256=(
                        binding.plan_sha256
                    ),
                    expected_exact_approval_target_binding_sha256=(
                        binding.target_binding_sha256
                    ),
                    exact_human_approval_claim=claim,
                ),
            )
            try:
                for call in calls:
                    with self.subTest(call=call), self.assertRaisesRegex(
                        archive_services.ArchiveServiceError,
                        "zettel_objet_link_archive_identity_unavailable",
                    ):
                        call()
            finally:
                try:
                    if claim.status == "started":
                        claim.finalize_failed("operation_blocked")
                finally:
                    claim.close()

    def test_archive_identity_parser_rejects_ambiguous_or_non_json_yaml(self) -> None:
        malformed_cases = {
            "nested_duplicate": "\npolicy:\n  mode: one\n  mode: two\n",
            "alias_cycle": "\ncycle: &cycle\n  self: *cycle\n",
            "non_finite": "\nunsafe_number: .nan\n",
            "custom_tag": "\nunsafe_value: !wom-unknown tagged\n",
        }
        for case, suffix in malformed_cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = self.archive(Path(temporary))
                config = root / "archive.yml"
                config.write_text(
                    config.read_text(encoding="utf-8") + suffix,
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "zettel_objet_link_archive_identity_unavailable",
                ):
                    completion_workflows.zettel_objet_link_plan(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )

        with tempfile.TemporaryDirectory() as temporary:
            root = self.archive(Path(temporary))
            config = root / "archive.yml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "archive_id: archive:personal:fake-life",
                    "archive_id: invalid archive id",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "zettel_objet_link_archive_identity_unavailable",
            ):
                completion_workflows.zettel_objet_link_plan(
                    root,
                    zettel_id=ZETTEL_ID,
                    object_id=OBJECT_ID,
                    role=ROLE,
                )

    @unittest.skipUnless(os.name == "nt", "Windows hardlink contract")
    def test_control_lock_leaf_swap_opens_nothing_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self.archive(parent).resolve()
            lock_parent = (
                root
                / "receipts"
                / "objects"
                / "zettel-links"
                / ".locks"
            )
            lock_parent.mkdir(parents=True)
            lock_path = lock_parent / "control.lock"
            lock_path.write_bytes(
                completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES
            )
            hidden = lock_parent / "control.hidden"
            outside = parent / "outside-control.lock"
            outside.write_bytes(
                completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES
            )
            real_bound_read = (
                archive_services._read_activity_group_regular_bytes_bound
            )
            real_windll = ctypes.WinDLL
            swapped = False
            native_opens_after_swap = 0

            def read_then_swap(
                archive_root: Path,
                binding: dict[str, object],
                path: Path,
                *,
                max_bytes: int,
            ) -> bytes:
                nonlocal swapped
                raw = real_bound_read(
                    archive_root,
                    binding,
                    path,
                    max_bytes=max_bytes,
                )
                if path == lock_path and not swapped:
                    lock_path.rename(hidden)
                    os.link(outside, lock_path)
                    swapped = True
                return raw

            def track_native_open(*args, **kwargs):
                nonlocal native_opens_after_swap
                if swapped:
                    native_opens_after_swap += 1
                    raise AssertionError("unsafe leaf reached native open")
                return real_windll(*args, **kwargs)

            stack = ExitStack()
            binding = stack.enter_context(
                archive_services._activity_group_bound_directory_chain(
                    root,
                    lock_parent,
                )
            )
            control_lock = completion_workflows._ZettelObjetLinkLock(
                root,
                lock_path,
                expected_state="existing_exact",
                parent_binding=binding,
                parent_stack=stack,
            )
            try:
                with (
                    self.track_outside_access(outside) as counts,
                    mock.patch.object(
                        archive_services,
                        "_read_activity_group_regular_bytes_bound",
                        new=read_then_swap,
                    ),
                    mock.patch.object(
                        ctypes,
                        "WinDLL",
                        side_effect=track_native_open,
                    ),
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "zettel_objet_link_lock_unavailable",
                    ):
                        with control_lock:
                            self.fail("unsafe lock must never be acquired")
                self.assertTrue(swapped)
                self.assertEqual(native_opens_after_swap, 0)
                self.assertEqual(counts["file_open_or_read"], 0, counts)
                self.assertEqual(counts["directory_scan"], 0, counts)
                self.assertEqual(
                    outside.read_bytes(),
                    completion_workflows.ZETTEL_OBJET_LINK_LOCK_BYTES,
                )
            finally:
                stack.close()
                if lock_path.exists():
                    lock_path.unlink()
                if hidden.exists():
                    hidden.rename(lock_path)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_zettel_root_junction_swap_reads_and_scans_nothing_outside(
        self,
    ) -> None:
        for surface in ("plan", "apply", "lookup", "revert"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                self.require_directory_junctions(parent)
                root = self.archive(parent).resolve()
                plan = self.plan(root)
                claim = None
                binding = None
                if surface in {"lookup", "revert"}:
                    self.apply(root, plan)
                elif surface == "apply":
                    claim, binding = self.claim(root, plan)

                zettel_root = root / "zettels"
                hidden_root = root / "zettels-hidden"
                outside = parent / f"outside-zettels-{surface}"
                shutil.copytree(zettel_root, outside)
                real_bound_chain = (
                    archive_services._activity_group_bound_directory_chain
                )
                injected = False

                @contextmanager
                def inject_before_zettel_root_binding(
                    archive_root: Path,
                    target: Path,
                    *,
                    create: bool = False,
                ):
                    nonlocal injected
                    if not injected and Path(target) == zettel_root:
                        zettel_root.rename(hidden_root)
                        try:
                            self.create_directory_junction(
                                zettel_root,
                                outside,
                            )
                        except BaseException:
                            hidden_root.rename(zettel_root)
                            raise
                        injected = True
                    with real_bound_chain(
                        archive_root,
                        target,
                        create=create,
                    ) as held:
                        yield held

                try:
                    with (
                        self.track_outside_access(outside) as counts,
                        mock.patch.object(
                            archive_services,
                            "_activity_group_bound_directory_chain",
                            new=inject_before_zettel_root_binding,
                        ),
                    ):
                        if surface == "plan":
                            attacked = completion_workflows.zettel_objet_link_plan(
                                root,
                                zettel_id=ZETTEL_ID,
                                object_id=OBJECT_ID,
                                role=ROLE,
                            )
                        elif surface == "apply":
                            assert claim is not None and binding is not None
                            attacked = completion_workflows.zettel_objet_link_apply(
                                root,
                                zettel_id=ZETTEL_ID,
                                object_id=OBJECT_ID,
                                role=ROLE,
                                expected_plan_sha256=str(
                                    plan["summary"]["plan_sha256"]
                                ),
                                reviewed_by=REVIEWER,
                                expected_exact_approval_plan_sha256=(
                                    binding.plan_sha256
                                ),
                                expected_exact_approval_target_binding_sha256=(
                                    binding.target_binding_sha256
                                ),
                                exact_human_approval_claim=claim,
                            )
                        elif surface == "lookup":
                            attacked = completion_workflows.zettel_objet_link_receipts(
                                root,
                                zettel_id=ZETTEL_ID,
                                object_id=OBJECT_ID,
                                role=ROLE,
                            )
                        else:
                            attacked = completion_workflows.zettel_objet_link_revert_plan(
                                root,
                                receipt=str(plan["summary"]["receipt_path"]),
                            )
                    self.assertTrue(injected, attacked)
                    self.assertFalse(attacked["ok"], attacked)
                    self.assertEqual(counts["file_open_or_read"], 0, counts)
                    self.assertEqual(counts["directory_scan"], 0, counts)
                finally:
                    if injected and zettel_root.exists():
                        self.remove_directory_junction(zettel_root)
                    if hidden_root.exists() and not zettel_root.exists():
                        hidden_root.rename(zettel_root)
                    if claim is not None:
                        try:
                            if claim.status == "started":
                                claim.finalize_failed("operation_blocked")
                        finally:
                            claim.close()

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_archive_root_junction_swap_reads_no_outside_archive_yml(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent)
            hidden_root = parent / "archive-hidden"
            outside = parent / "outside-archive"
            shutil.copytree(FIXTURE, outside)
            real_require_root = archive_services.require_existing_archive_root
            injected = False

            def inject_after_root_resolution(value: Path | str) -> Path:
                nonlocal injected
                resolved = real_require_root(value)
                if not injected:
                    root.rename(hidden_root)
                    try:
                        self.create_directory_junction(root, outside)
                    except BaseException:
                        hidden_root.rename(root)
                        raise
                    injected = True
                return resolved

            try:
                with (
                    self.track_outside_access(outside) as counts,
                    mock.patch.object(
                        archive_services,
                        "require_existing_archive_root",
                        side_effect=inject_after_root_resolution,
                    ),
                ):
                    attacked = completion_workflows.zettel_objet_link_plan(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )
                self.assertTrue(injected)
                self.assertFalse(attacked["ok"], attacked)
                self.assertIn(
                    "zettel_identity_projection_stale",
                    attacked["blockers"],
                )
                self.assertEqual(counts["file_open_or_read"], 0, counts)
                self.assertEqual(counts["directory_scan"], 0, counts)
            finally:
                if injected and root.exists():
                    self.remove_directory_junction(root)
                if hidden_root.exists() and not root.exists():
                    hidden_root.rename(root)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_receipt_root_junction_swap_plan_reads_and_scans_nothing_outside(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent)
            baseline = self.plan(root)
            receipt_root = (
                root / "receipts" / "objects" / "zettel-links"
            )
            receipt_root.mkdir(parents=True, exist_ok=True)
            receipt_root = receipt_root.resolve()
            hidden_root = receipt_root.with_name("zettel-links-hidden")
            outside = parent / "outside-receipts-plan"
            outside.mkdir()
            receipt_name = Path(str(baseline["summary"]["receipt_path"])).name
            (outside / receipt_name).write_bytes(b"PRIVATE_OUTSIDE_RECEIPT")
            real_bound_chain = (
                archive_services._activity_group_bound_directory_chain
            )
            injected = False
            seen_targets: list[Path] = []

            @contextmanager
            def inject_before_receipt_root_binding(
                archive_root: Path,
                target: Path,
                *,
                create: bool = False,
            ):
                nonlocal injected
                seen_targets.append(Path(target))
                if not injected and Path(target) == receipt_root:
                    receipt_root.rename(hidden_root)
                    try:
                        self.create_directory_junction(receipt_root, outside)
                    except BaseException:
                        hidden_root.rename(receipt_root)
                        raise
                    injected = True
                with real_bound_chain(
                    archive_root,
                    target,
                    create=create,
                ) as binding:
                    yield binding

            try:
                with (
                    self.track_outside_access(outside) as counts,
                    mock.patch.object(
                        archive_services,
                        "_activity_group_bound_directory_chain",
                        new=inject_before_receipt_root_binding,
                    ),
                ):
                    attacked = completion_workflows.zettel_objet_link_plan(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )
                self.assertTrue(injected, (seen_targets, receipt_root, attacked))
                self.assertFalse(attacked["ok"], attacked)
                self.assertEqual(counts["file_open_or_read"], 0, counts)
                self.assertEqual(counts["directory_scan"], 0, counts)
            finally:
                if injected and receipt_root.exists():
                    self.remove_directory_junction(receipt_root)
                if hidden_root.exists() and not receipt_root.exists():
                    hidden_root.rename(receipt_root)

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_receipt_root_junction_swap_lookup_reads_and_scans_nothing_outside(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.require_directory_junctions(parent)
            root = self.archive(parent)
            plan = self.plan(root)
            self.apply(root, plan)
            receipt_root = (
                root / "receipts" / "objects" / "zettel-links"
            )
            receipt_root = receipt_root.resolve()
            hidden_root = receipt_root.with_name("zettel-links-hidden")
            outside = parent / "outside-receipts-lookup"
            shutil.copytree(receipt_root, outside)
            real_bound_chain = (
                archive_services._activity_group_bound_directory_chain
            )
            injected = False
            seen_targets: list[Path] = []

            @contextmanager
            def inject_before_receipt_root_binding(
                archive_root: Path,
                target: Path,
                *,
                create: bool = False,
            ):
                nonlocal injected
                seen_targets.append(Path(target))
                if not injected and Path(target) == receipt_root:
                    receipt_root.rename(hidden_root)
                    try:
                        self.create_directory_junction(receipt_root, outside)
                    except BaseException:
                        hidden_root.rename(receipt_root)
                        raise
                    injected = True
                with real_bound_chain(
                    archive_root,
                    target,
                    create=create,
                ) as binding:
                    yield binding

            try:
                with (
                    self.track_outside_access(outside) as counts,
                    mock.patch.object(
                        archive_services,
                        "_activity_group_bound_directory_chain",
                        new=inject_before_receipt_root_binding,
                    ),
                ):
                    attacked = completion_workflows.zettel_objet_link_receipts(
                        root,
                        zettel_id=ZETTEL_ID,
                        object_id=OBJECT_ID,
                        role=ROLE,
                    )
                self.assertTrue(injected, (seen_targets, receipt_root, attacked))
                self.assertFalse(attacked["ok"], attacked)
                self.assertIn(
                    "zettel_objet_link_receipts_directory_unavailable",
                    attacked["blockers"],
                )
                self.assertEqual(counts["file_open_or_read"], 0, counts)
                self.assertEqual(counts["directory_scan"], 0, counts)
            finally:
                if injected and receipt_root.exists():
                    self.remove_directory_junction(receipt_root)
                if hidden_root.exists() and not receipt_root.exists():
                    hidden_root.rename(receipt_root)


if __name__ == "__main__":
    unittest.main()
