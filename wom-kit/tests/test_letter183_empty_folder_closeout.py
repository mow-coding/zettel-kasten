"""Beta letter 183: files finished, folders left behind.

After v0.4.63 removed every selected file (five PDFs under ten paths), the
run still ended "partial": the listed folders held empty subfolders, the
recovery text read as if file items were unfinished, a request without items
was refused, and a .git that the earlier cleanup had emptied blocked every
later plan (activity_cleanup_git_inventory_unavailable). Since v0.4.64:

- a request may select no files and name remove_empty_directory_trees; every
  folder of the tree is bound at plan time and removed deepest first only if
  it is unchanged and empty; a folder holding a file, link or reparse point
  stays with its parents, and that is not a failure;
- a .git with no file at any depth is not a repository;
- the result reports folder removal apart from the file items, and the
  recovery guidance no longer says items are incomplete when only folders are;
- a preview says whether this process carries the conversation's session refs.

Synthetic files only.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup
from wom_kit import operation_control

from . import test_activity_cleanup as fixture
from . import test_letter180_activity_cleanup_recovery as letter180


class _Base(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp
    plan = fixture.ActivityCleanupTests.plan
    execute = fixture.ActivityCleanupTests.execute

    def write_request(self):
        self.request.write_text(json.dumps(self.document), encoding="utf-8")

    def empty_tree(self, root, names=("a/b/c", "a/d", "e")):
        for name in names:
            (root / name).mkdir(parents=True, exist_ok=True)

    def folders_only(self, trees, *, roots=None, activity="synthetic-folders"):
        self.document.update(activity_id=activity, roots=[str(r) for r in (roots or trees)], items=[],
                             remove_empty_directories=[], remove_empty_directory_trees=[str(t) for t in trees])
        self.write_request()


class PlanTests(_Base):
    def test_a_request_without_items_needs_a_folder_part(self):
        self.source.unlink()
        self.document.update(items=[], remove_empty_directories=[])
        self.write_request()
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_request_invalid")

    def test_tree_preview_counts_without_paths(self):
        self.source.unlink()
        self.empty_tree(self.external)
        (self.external / "a" / "d" / ".env.PRIVATE_KEEP").write_bytes(b"synthetic")
        self.folders_only([self.external])
        public = self.plan()["public"]
        self.assertTrue(public["ok"], public["blockers"])
        self.assertEqual(public["item_count"], 0)
        tree = public["directory_trees"][0]
        # folders: root, a, a/b, a/b/c, a/d, e -> a/d, a and the root hold the file
        self.assertEqual(tree["directory_count"], 6)
        self.assertEqual(tree["directory_count_kept_because_it_holds_a_file"], 3)
        self.assertEqual(tree["empty_directory_count_to_remove"], 3)
        self.assertEqual(tree["file_or_link_count_inside"], 1)
        self.assertEqual(tree["possible_secret_config_count_inside"], 1)
        self.assertTrue(tree["tree_is_a_selected_root"])
        self.assertFalse(tree["tree_root_would_be_removed"])
        dumped = json.dumps(public)
        self.assertNotIn(str(self.base), dumped)
        self.assertNotIn("PRIVATE_KEEP", dumped)

    def test_tree_outside_the_roots_or_overlapping_is_refused(self):
        self.source.unlink()
        self.empty_tree(self.external)
        outside = self.base / "elsewhere"
        outside.mkdir()
        self.folders_only([outside], roots=[self.external])
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_directory_outside_selection")
        self.folders_only([self.external, self.external / "a"], roots=[self.external])
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_directory_tree_overlap")

    def test_git_folder_without_any_file_is_not_a_repository(self):
        self.source.unlink()
        self.empty_tree(self.external, (".git/objects/info", ".git/refs/heads", "src"))
        self.folders_only([self.external])
        public = self.plan()["public"]
        self.assertTrue(public["ok"], public["blockers"])
        self.assertEqual(public["git"], [{"repository": False, "empty_git_residue": True}])
        self.assertEqual(public["empty_git_residue_root_count"], 1)

    def test_git_folder_with_any_file_keeps_the_git_checks(self):
        self.source.unlink()
        self.empty_tree(self.external, (".git/objects/info", ".git/refs/heads"))
        (self.external / ".git" / "objects" / "leftover").write_bytes(b"synthetic content")
        self.folders_only([self.external])
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_git_inventory_unavailable")

    def test_real_repository_is_still_a_repository(self):
        self.source.unlink()
        run = subprocess.run(["git", "init", "-q", str(self.external)], capture_output=True, check=False)
        if run.returncode:
            self.skipTest("git unavailable")
        self.empty_tree(self.external, ("src",))
        self.folders_only([self.external])
        public = self.plan()["public"]
        self.assertTrue(public["git"][0]["repository"])
        self.assertNotIn("empty_git_residue", public["git"][0])

    def test_file_request_binding_is_unchanged_and_folder_request_binds_its_folders(self):
        first = self.plan()
        self.assertEqual(cleanup.approval_binding(first).target_binding_sha256,
                         cleanup.digest(first["material"]["items"]))
        self.source.unlink()
        self.empty_tree(self.external)
        self.folders_only([self.external])
        one = cleanup.approval_binding(self.plan()).target_binding_sha256
        self.folders_only([self.external / "a"], roots=[self.external])
        two = cleanup.approval_binding(self.plan()).target_binding_sha256
        self.assertNotEqual(one, two)


@unittest.skipUnless(os.name == "nt", "native bound directory deletion")
class EmptyFolderCloseoutTests(_Base):
    def two_roots_with_linked_file(self):
        """The customer's shape: one file linked into two folders, each with an empty subtree."""
        self.source.unlink()
        self.root_a, self.root_b = self.base / "materials", self.base / "webapp"
        for root in (self.root_a, self.root_b):
            root.mkdir()
            self.empty_tree(root)
        (self.root_a / "doc.pdf").write_bytes(b"%PDF-1.4 synthetic")
        os.link(self.root_a / "doc.pdf", self.root_b / "doc.pdf")
        self.document.update(roots=[str(self.root_a), str(self.root_b)],
            items=[{"path": str(root / "doc.pdf"), "role": "source", "reason": "Synthetic linked PDF",
                    "disposition": "preserve"} for root in (self.root_a, self.root_b)],
            remove_empty_directories=[str(self.root_a), str(self.root_b)])
        self.write_request()

    def test_files_done_but_listed_folders_kept_is_reported_as_folder_only(self):
        self.two_roots_with_linked_file()
        result = self.execute(self.plan())
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["state_detail"], "selected_items_complete_folder_removal_unfinished")
        self.assertTrue(result["selected_items_complete"])
        self.assertTrue(result["folders_empty"])           # no files
        self.assertFalse(result["folders_removed"])        # but the folders exist
        self.assertEqual({row["code"] for row in result["directories"]}, {"contains_subdirectory"})
        self.assertEqual(result["folder_outcome"]["listed_directories"],
                         {"requested": 2, "removed": 0, "already_absent": 0, "kept": 2})
        text = " ".join(result["plain_summary"])
        self.assertIn("Selected items: 2 of 2 completed.", text)
        self.assertIn("Only folder removal is unfinished", text)
        self.assertIn("remove_empty_directory_trees", text)
        self.assertEqual(result["remaining"]["remaining_subfolder_count"], 10)
        self.assertEqual(result["measurements"]["directory_unfinished_count"], 2)
        # recovery guidance: not "ended without completing every selected item"
        domain = operation_control._safe_activity_cleanup_domain_projection(result)
        actions = operation_control._activity_cleanup_completed_next_actions(domain)
        self.assertIn("Every selected file item is finished (2 of 2)", actions[0])
        self.assertNotIn("without completing every selected item", " ".join(actions))
        self.assertTrue(any("time" in line or "ended" in line for line in result["measurements"]["plain_time_summary"]))

    def test_follow_up_request_without_items_removes_the_empty_trees(self):
        self.two_roots_with_linked_file()
        self.execute(self.plan())
        # what the earlier cleanup left in the web app: an emptied .git and a kept secret file
        self.empty_tree(self.root_b, (".git/objects/pack", ".git/refs"))
        secret = self.root_b / "a" / "PRIVATE.env"
        secret.write_bytes(b"synthetic secret")
        self.folders_only([self.root_a, self.root_b], activity="synthetic-folders-2")
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["blockers"])
        result = self.execute(candidate)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "completed")
        self.assertFalse(self.root_a.exists())
        self.assertTrue(secret.read_bytes() == b"synthetic secret")
        self.assertEqual(sorted(p.name for p in self.root_b.iterdir()), ["a"])
        self.assertEqual(sorted(p.name for p in (self.root_b / "a").iterdir()), ["PRIVATE.env"])
        first, second = result["directory_trees"]
        self.assertEqual((first["state"], first["removed_empty"], first["tree_root_removed"]),
                         ("empty_directories_removed", 6, True))
        self.assertEqual(second["state"], "empty_directories_removed")
        self.assertEqual(second["kept_not_empty"], 2)       # the root and a
        self.assertEqual(second["codes"], {"contains_file_or_link": 1, "contains_subdirectory": 1})
        self.assertFalse(second["tree_root_removed"])
        self.assertFalse(result["folders_removed"])
        self.assertIn("This request selected no files", result["plain_summary"][0])
        status = cleanup.status(self.plan(resume=True))
        self.assertTrue(status["selected_items_complete"])
        self.assertFalse(status["folders_removed"])

    def test_folder_replaced_after_the_plan_is_held(self):
        self.source.unlink()
        self.empty_tree(self.external)
        self.folders_only([self.external])
        candidate = self.plan()
        (self.external / "e").rmdir()
        (self.external / "e").mkdir()                      # same name, another folder
        result = self.execute(candidate)
        self.assertFalse(result["ok"])
        tree = result["directory_trees"][0]
        self.assertEqual(tree["state"], "some_held")
        self.assertEqual(tree["codes"].get("directory_changed_since_plan"), 1)
        self.assertTrue((self.external / "e").is_dir())
        self.assertFalse((self.external / "a").exists())

    def test_file_added_after_the_plan_keeps_its_folders_and_is_untouched(self):
        self.source.unlink()
        self.empty_tree(self.external)
        self.folders_only([self.external])
        candidate = self.plan()
        late = self.external / "a" / "b" / "late.txt"
        late.write_bytes(b"new synthetic work")
        result = self.execute(candidate)
        self.assertTrue(result["ok"], result)
        self.assertEqual(late.read_bytes(), b"new synthetic work")
        self.assertFalse((self.external / "a" / "b" / "c").exists())
        self.assertFalse((self.external / "e").exists())
        self.assertEqual(result["directory_trees"][0]["kept_not_empty"], 3)
        self.assertFalse(result["folders_empty"])

    def test_folder_created_after_the_plan_is_not_removed(self):
        self.source.unlink()
        self.empty_tree(self.external)
        self.folders_only([self.external])
        candidate = self.plan()
        (self.external / "e" / "unplanned").mkdir()
        result = self.execute(candidate)
        self.assertTrue((self.external / "e" / "unplanned").is_dir())
        self.assertEqual(result["directory_trees"][0]["codes"].get("contains_subdirectory"), 2)

    def test_junction_inside_the_tree_is_never_followed_or_removed(self):
        self.source.unlink()
        self.empty_tree(self.external)
        outside = self.base / "other-activity"
        outside.mkdir()
        (outside / "theirs.txt").write_bytes(b"another activity")
        link = self.external / "e" / "shared"
        run = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, check=False)
        if run.returncode:
            self.skipTest("junction unavailable")
        self.addCleanup(lambda: os.path.lexists(link) and os.rmdir(link))
        self.folders_only([self.external])
        candidate = self.plan()
        tree = candidate["public"]["directory_trees"][0]
        self.assertEqual(tree["link_or_reparse_point_count_inside"], 1)
        result = self.execute(candidate)
        self.assertTrue(os.path.lexists(link))
        self.assertEqual((outside / "theirs.txt").read_bytes(), b"another activity")
        self.assertTrue((self.external / "e").is_dir())
        self.assertFalse((self.external / "a").exists())
        self.assertTrue(result["ok"], result)


class RecoveryWordingTests(unittest.TestCase):
    def domain(self, **counts):
        return {"command": "activity-cleanup", "ok": False, "state": "partial", "cause_code": None,
                "counts": counts, "item_codes": []}

    def test_unfinished_items_keep_the_reconcile_guidance(self):
        actions = operation_control._activity_cleanup_completed_next_actions(self.domain(
            selected_item_count=10, completed_item_count=9, retained_item_count=1, unprocessed_item_count=0,
            interrupted_item_count=0, unknown_local_outcome_count=0, directory_unfinished_count=4))
        self.assertIn("without completing every selected item", actions[0])

    def test_results_from_older_versions_keep_the_old_guidance(self):
        actions = operation_control._activity_cleanup_completed_next_actions(self.domain(
            completed_item_count=10, retained_item_count=0, unprocessed_item_count=0,
            interrupted_item_count=0, unknown_local_outcome_count=0))
        self.assertIn("without completing every selected item", actions[0])

    def test_folder_only_remainder_says_so(self):
        actions = operation_control._activity_cleanup_completed_next_actions(self.domain(
            selected_item_count=10, completed_item_count=10, retained_item_count=0, unprocessed_item_count=0,
            interrupted_item_count=0, unknown_local_outcome_count=0, directory_unfinished_count=4,
            directory_removed_count=1))
        self.assertIn("Every selected file item is finished (10 of 10)", actions[0])
        self.assertIn("4 folder(s)", actions[1])


class SessionContextNoticeTests(unittest.TestCase):
    def attach(self, env):
        from wom_kit import exact_human_approval_workflow as workflow
        from wom_kit import work_session_permission as permission
        cleared = {name: "" for name in permission.CONTEXT_ENV}
        with patch.dict(os.environ, {**cleared, **env}):
            for name in permission.CONTEXT_ENV:
                if not os.environ.get(name):
                    os.environ.pop(name, None)
            return workflow._attach_session_permission_evidence(
                {"ok": True, "exact_human_approval": {"approval_id": "synthetic"}},
                session_presenter=None, grant_refusal=None)

    def test_dialog_without_session_refs_is_named(self):
        result = self.attach({})
        context = result["caller_session_context"]
        self.assertEqual(context["state"], "missing")
        self.assertTrue(context["dialog_shown_without_session_refs"])
        self.assertFalse(context["missing_context_proves_grant_expired"])
        self.assertFalse(context["values_echoed"])

    def test_one_missing_ref_is_incomplete(self):
        result = self.attach({"WOM_CLIENT_APP_REF": "synthetic-app"})
        self.assertEqual(result["caller_session_context"]["state"], "incomplete")
        self.assertNotIn("synthetic-app", json.dumps(result))

    def test_refusal_reason_keeps_precedence(self):
        from wom_kit import exact_human_approval_workflow as workflow
        result = workflow._attach_session_permission_evidence(
            {"ok": True, "exact_human_approval": {"approval_id": "synthetic"}},
            session_presenter=None, grant_refusal="work_session_grant_expired")
        self.assertNotIn("caller_session_context", result)


@unittest.skipUnless(os.name == "nt", "native bound directory deletion")
class Letter183RealCliTests(letter180.Letter180ReconcileTests):
    """Through the real CLI: a request without items closes out the empty folders."""

    def test_items_empty_request_previews_and_removes_empty_folders(self):
        root = self.base / "webapp"
        for name in ("src/app", ".git/objects/pack", ".git/refs/heads"):
            (root / name).mkdir(parents=True)
        kept = root / "src" / "PRIVATE.env"
        kept.write_bytes(b"synthetic secret")
        self.document.update(activity_id="synthetic-folders-cli", roots=[str(root)], items=[],
                             remove_empty_directories=[], remove_empty_directory_trees=[str(root)])
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        code, preview = self.run_cli("--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["git"], [{"repository": False, "empty_git_residue": True}])
        self.assertEqual(preview["directory_trees"][0]["empty_directory_count_to_remove"], 6)
        self.assertIn(preview["caller_session_context"]["state"], {"missing", "incomplete", "valid_shape", "invalid_shape"})
        self.assertNotIn(str(self.base), json.dumps(preview))
        puts = []
        original_put = self.transport.put_object

        def counting_put(**kwargs):
            puts.append(kwargs.get("key", ""))
            return original_put(**kwargs)
        code, result = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
                                    patches=[(self.transport, "put_object", counting_put)])
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(puts, [])                          # nothing is uploaded for a folder request
        self.assertEqual(kept.read_bytes(), b"synthetic secret")
        self.assertFalse((root / ".git").exists())
        self.assertFalse((root / "src" / "app").exists())
        self.assertTrue((root / "src").is_dir())


for _name in [name for name in dir(Letter183RealCliTests) if name.startswith("test_") and "items_empty" not in name]:
    setattr(Letter183RealCliTests, _name, None)


if __name__ == "__main__":
    unittest.main()
