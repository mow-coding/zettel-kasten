"""Beta letter 182: hard-linked files in two activity folders, secret config, plain closeout.

The customer's two activity folders each held the same five PDFs as hard
links (one file, two names). activity-cleanup refused any file with more than
one link (activity_cleanup_regular_single_link_file_required), so the folders
could never be emptied, and the result never said "selected items done" apart
from "folders empty". Since v0.4.63:

- a file with several hard links is accepted when every link is an item of
  the same request (so every link is inside the approved roots) with one role
  and disposition; the bytes are preserved once and each approved link is
  removed by the bound delete (N -> N-1 on the exact file);
- a link outside the request keeps the file held, also when it appears after
  planning;
- a real secret file (role secret_config) is never uploaded; it stays, or is
  discarded after the person's recorded confirmation;
- results say paths versus distinct files and whether the folders are empty.

Synthetic files only; mocked preservation backend except the real-CLI case.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup

from . import test_activity_cleanup as fixture
from . import test_letter180_activity_cleanup_recovery as letter180


def _body(name):
    return b"%PDF-1.4 synthetic " + name.encode()


@unittest.skipUnless(os.name == "nt", "Windows hard links, alternate data streams and native deletion")
class HardLinkGroupTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp
    plan = fixture.ActivityCleanupTests.plan
    execute = fixture.ActivityCleanupTests.execute

    def two_folders(self, names=("doc.pdf",), *, select="both", ads=False):
        """Folder A holds the files; folder B holds hard links of them."""
        self.source.unlink()
        self.root_a, self.root_b = self.base / "materials", self.base / "webapp"
        self.root_a.mkdir()
        self.root_b.mkdir()
        items = []
        for name in names:
            first, second = self.root_a / name, self.root_b / name
            first.write_bytes(_body(name))
            os.link(first, second)
            if ads:
                Path(str(first) + ":Zone.Identifier:$DATA").write_bytes(b"[ZoneTransfer]\r\nZoneId=3\r\n")
            paths = [first, second] if select == "both" else [first]
            items.extend({"path": str(path), "role": "source", "reason": "Synthetic linked PDF",
                          "disposition": "preserve"} for path in paths)
        self.document.update(roots=[str(self.root_a), str(self.root_b)], items=items, remove_empty_directories=[])
        self.write_request()

    def write_request(self):
        self.request.write_text(json.dumps(self.document), encoding="utf-8")

    def test_one_representative_path_is_held_with_counts_and_a_next_step(self):
        self.two_folders(select="one")
        candidate = self.plan()
        public = candidate["public"]
        self.assertFalse(public["ok"])
        self.assertEqual(public["blockers"], ["activity_cleanup_hardlink_not_fully_selected"])
        group = public["hardlink_groups"][0]
        self.assertEqual((group["link_count"], group["selected_link_count"]), (2, 1))
        self.assertEqual(group["unselected_links_inside_selected_roots"], 1)
        self.assertEqual(group["links_outside_selected_roots"], 0)
        self.assertIn("fsutil hardlink list", public["next_safe_actions"][0])
        self.assertNotIn(str(self.base), json.dumps(public))
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.execute(candidate)
        self.assertEqual(caught.exception.code, "activity_cleanup_plan_blocked")
        self.assertTrue((self.root_a / "doc.pdf").exists() and (self.root_b / "doc.pdf").exists())

    def test_every_link_selected_is_preserved_once_and_both_folders_end_empty(self):
        self.two_folders(names=("one.pdf", "two.pdf"))
        candidate = self.plan()
        public = candidate["public"]
        self.assertTrue(public["ok"], public["blockers"])
        self.assertEqual((public["selected_path_count"], public["distinct_selected_file_count"]), (4, 2))
        self.assertTrue(all(group["fully_selected"] for group in public["hardlink_groups"]))
        result = self.execute(candidate)
        self.assertTrue(result["ok"], result)
        self.assertEqual([row["state"] for row in result["items"]], ["deleted"] * 4)
        self.assertFalse(any(self.root_a.iterdir()) or any(self.root_b.iterdir()))
        self.assertTrue(result["selected_items_complete"] and result["folders_empty"])
        measurements = result["measurements"]
        self.assertEqual((measurements["newly_deleted_path_count"], measurements["newly_deleted_distinct_file_count"]), (4, 2))
        self.assertEqual(measurements["newly_deleted_file_payload_bytes"], len(_body("one.pdf")) + len(_body("two.pdf")))
        status = cleanup.status(self.plan(resume=True))
        self.assertTrue(status["whole_folder_cleanup_complete"])
        self.assertIn("The selected folders now contain no files.", status["plain_summary"])

    def test_a_single_link_file_is_unchanged(self):
        self.two_folders()
        lone = self.root_a / "lone.pdf"
        lone.write_bytes(_body("lone.pdf"))
        self.document["items"].append({"path": str(lone), "role": "source", "reason": "Synthetic single PDF",
                                       "disposition": "preserve"})
        self.write_request()
        candidate = self.plan()
        self.assertNotIn("link_count", candidate["material"]["items"][-1]["state"])
        self.assertTrue(self.execute(candidate)["ok"])

    def test_a_link_outside_the_selected_folders_keeps_the_file(self):
        self.two_folders()
        outside = self.base / "other-activity"
        outside.mkdir()
        os.link(self.root_a / "doc.pdf", outside / "doc.pdf")
        public = self.plan()["public"]
        self.assertEqual(public["blockers"], ["activity_cleanup_hardlink_not_fully_selected"])
        group = public["hardlink_groups"][0]
        self.assertEqual((group["link_count"], group["selected_link_count"], group["links_outside_selected_roots"]), (3, 2, 1))
        self.assertIn("shared with something outside this activity", public["next_safe_actions"][0])

    def test_a_link_created_after_planning_holds_every_link(self):
        self.two_folders()
        candidate = self.plan()
        outside = self.base / "other-activity"
        outside.mkdir()
        os.link(self.root_a / "doc.pdf", outside / "doc.pdf")
        result = self.execute(candidate)
        self.assertFalse(result["ok"])
        self.assertEqual([(row["state"], row["code"]) for row in result["items"]],
                         [("retained", "activity_cleanup_file_changed")] * 2)
        self.assertTrue((self.root_a / "doc.pdf").exists() and (self.root_b / "doc.pdf").exists())
        self.assertEqual((outside / "doc.pdf").read_bytes(), _body("doc.pdf"))

    def test_alternate_data_streams_of_a_linked_file_are_bound_through_both_deletes(self):
        self.two_folders(ads=True)
        candidate = self.plan()
        items = candidate["material"]["items"]
        self.assertEqual(len(items[0]["alternate_streams"]), 1)
        self.assertEqual(items[0]["alternate_streams"], items[1]["alternate_streams"])
        result = self.execute(candidate)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["folders_empty"])

    def test_interruption_between_the_two_links_resumes_and_finishes(self):
        self.two_folders()
        candidate = self.plan()
        original = candidate["journal"].write

        def interrupt(name, document):
            if name == "item-0-deleted":
                raise KeyboardInterrupt()
            return original(name, document)
        with patch.object(candidate["journal"], "write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(candidate)
        self.assertFalse((self.root_a / "doc.pdf").exists())
        self.assertTrue((self.root_b / "doc.pdf").exists())
        result = self.execute(self.plan(resume=True))
        self.assertTrue(result["ok"], result)
        self.assertEqual([row["state"] for row in result["items"]], ["already_absent_after_intent", "deleted"])
        self.assertTrue(result["folders_empty"])

    def test_links_of_one_file_need_one_role_and_disposition(self):
        self.two_folders()
        self.document["items"][1].update(role="temporary", disposition="discard", discard_intent=True)
        self.write_request()
        public = self.plan()["public"]
        self.assertEqual(public["blockers"], ["activity_cleanup_hardlink_group_classification_mismatch"])

    def test_leftovers_are_reported_as_paths_and_distinct_files(self):
        self.two_folders(names=("one.pdf", "two.pdf"))
        self.document["items"] = self.document["items"][:2]  # only one.pdf's two links
        (self.root_b / ".env").write_bytes(b"SYNTHETIC_KEY=not-a-real-secret")
        self.write_request()
        result = self.execute(self.plan())
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["selected_items_complete"])
        self.assertFalse(result["folders_empty"])
        remaining = result["remaining"]
        self.assertEqual((remaining["remaining_path_count"], remaining["remaining_distinct_file_count"]), (3, 2))
        self.assertEqual((remaining["remaining_hard_linked_path_count"], remaining["remaining_hard_linked_file_count"]), (2, 1))
        self.assertEqual(remaining["remaining_possible_secret_config_count"], 1)
        text = " ".join(result["plain_summary"])
        self.assertIn("Selected items: 2 of 2 completed.", text)
        self.assertIn("NOT empty: 3 path(s) remain, which are 2 distinct file(s)", text)
        status = cleanup.status(self.plan(resume=True))
        self.assertFalse(status["whole_folder_cleanup_complete"])
        self.assertEqual(status["completion_boundaries"]["folders"]["state"], "files_remain")


@unittest.skipUnless(os.name == "nt", "Windows native deletion")
class SecretConfigTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp
    plan = fixture.ActivityCleanupTests.plan
    execute = fixture.ActivityCleanupTests.execute

    def config(self, **item):
        self.source.unlink()
        self.secret = self.external / ".env.local"
        self.secret.write_bytes(b"SYNTHETIC_TOKEN=not-a-real-secret")
        self.example = self.external / ".env.example"
        self.example.write_bytes(b"SYNTHETIC_TOKEN=\n")
        self.document["items"] = [
            {"path": str(self.secret), "reason": "Synthetic secret settings", **item},
            {"path": str(self.example), "role": "source", "reason": "Example settings without values",
             "disposition": "preserve"},
        ]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")

    def test_a_secret_file_is_never_uploaded(self):
        self.config(role="secret_config", disposition="preserve")
        public = self.plan()["public"]
        self.assertEqual(public["blockers"], ["activity_cleanup_secret_config_is_never_uploaded"])
        self.assertIn("never uploaded", public["next_safe_actions"][0])

    def test_discard_needs_the_person_confirmation_recorded(self):
        self.config(role="secret_config", disposition="discard", discard_intent=True)
        public = self.plan()["public"]
        self.assertEqual(public["blockers"], ["activity_cleanup_secret_config_discard_requires_person_confirmation"])

    def test_confirmed_secret_is_discarded_without_upload_and_the_example_is_an_ordinary_source(self):
        self.config(role="secret_config", disposition="discard", discard_intent=True, secret_values_kept_elsewhere=True)
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["blockers"])
        self.assertEqual(candidate["public"]["secret_config_discard_count"], 1)
        result = self.execute(candidate)
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.secret.exists() or self.example.exists())
        preserved = [call.args[0]["number"] for call in self.backend.preserve.call_args_list]
        self.assertEqual(preserved, [1])  # only the example file reached the preservation backend

    def test_retained_secret_stays_and_the_flag_is_refused_on_other_roles(self):
        self.config(role="secret_config", disposition="retain")
        result = self.execute(self.plan())
        self.assertTrue(self.secret.exists())
        self.assertEqual(result["items"][0]["state"], "retained")
        self.document["activity_id"] = "synthetic-activity-two"
        self.document["items"][0].update(role="temporary", disposition="discard", discard_intent=True,
                                         secret_values_kept_elsewhere=True)
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_classification_required")


class Letter182RealCliTests(letter180.Letter180ReconcileTests):
    """The customer's reproduction through the real CLI: one upload, two links removed."""

    def test_linked_pdf_in_two_folders_uploads_once_and_empties_both(self):
        root_a, root_b = self.base / "materials", self.base / "webapp"
        root_a.mkdir()
        root_b.mkdir()
        body = _body("camp.pdf")
        (root_a / "camp.pdf").write_bytes(body)
        os.link(root_a / "camp.pdf", root_b / "camp.pdf")
        self.document["roots"] = [str(root_a), str(root_b)]
        self.document["remove_empty_directories"] = []
        representative = [{"path": str(root_a / "camp.pdf"), "role": "source", "reason": "Synthetic linked PDF",
                           "disposition": "preserve"}]
        self.document["items"] = representative
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        code, held = self.run_cli("--dry-run")
        self.assertEqual(code, 1)
        self.assertEqual(held["blockers"], ["activity_cleanup_hardlink_not_fully_selected"])
        self.document["items"] = representative + [{**representative[0], "path": str(root_b / "camp.pdf")}]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        puts = []
        original_put = self.transport.put_object

        def counting_put(**kwargs):
            puts.append(kwargs.get("key", ""))
            return original_put(**kwargs)
        code, result = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
                                    patches=[(self.transport, "put_object", counting_put)])
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "completed")
        self.assertFalse((root_a / "camp.pdf").exists() or (root_b / "camp.pdf").exists())
        digest = __import__("hashlib").sha256(body).hexdigest()
        self.assertEqual(sum(key.endswith(digest) for key in puts), 1)  # the bytes went up once
        self.assertEqual(sum(value == body for value in self.transport.objects.values()), 1)
        self.assertTrue(result["folders_empty"])
        self.assertEqual(result["measurements"]["newly_deleted_distinct_file_count"], 1)


# The inherited letter-180 scenarios run in their own module.
for _name in [name for name in dir(Letter182RealCliTests) if name.startswith("test_") and "linked_pdf" not in name]:
    setattr(Letter182RealCliTests, _name, None)


if __name__ == "__main__":
    unittest.main()
