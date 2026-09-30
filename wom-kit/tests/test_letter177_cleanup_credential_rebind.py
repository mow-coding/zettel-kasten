"""Beta letter 177: finish the 53 remaining cleanup items after a restart.

The customer's original activity-cleanup request named env: credential refs.
After a WOM update and a new process the variables were gone; the reconcile
preview showed no blockers but the approved run could not read the keys, and
nothing let the 53 unfinished items continue without redoing 1,017. Like the
desktop apps, the keys belong in the OS keychain: --reconcile may rebind only
the two credential refs (e.g. to credential-manager: exact targets) inside the
new approval, the preview says whether this process can read them, and an
unreadable pair is refused before the dialog. Completed items stay completed.

Synthetic archive, synthetic journal and mocked storage backend only.
"""

import argparse
import copy
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup
from wom_kit import archive_cli as cli
from wom_kit import archive_services as services

from . import test_activity_cleanup as fixture

STORAGE = {"provider_kind": "cloudflare-r2", "store_ref": "store:synthetic-r2",
           "endpoint_host": "synthetic-account.r2.cloudflarestorage.com", "bucket": "synthetic-bucket",
           "region": "auto", "access_key_id_ref": "env:WOM_SYNTHETIC_R2_ACCESS_177",
           "secret_access_key_ref": "env:WOM_SYNTHETIC_R2_SECRET_177"}
KEYCHAIN = {"access_key_id_ref": "credential-manager:wom-synthetic-r2-access-177",
            "secret_access_key_ref": "credential-manager:wom-synthetic-r2-secret-177"}


class CleanupCredentialRebindTests(unittest.TestCase):
    setUp = fixture.ActivityCleanupTests.setUp

    def partial_run(self):
        """1,070 items, 1,017 deleted by the original run, 53 still on disk."""
        self.document["storage"] = dict(STORAGE)
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = cleanup.plan(self.root, self.request, key_provider=self.key)
        original = candidate["material"]
        prototype = original["items"][0]
        original["items"] = []
        for number in range(1070):
            item = copy.deepcopy(prototype)
            item.pop("alternate_streams", None)
            item["number"] = number
            path = self.external / f"synthetic-{number:04d}.txt"
            item["path"] = str(path)
            if number >= 1017:
                path.write_bytes(f"synthetic remaining item {number}".encode())
                item["state"] = cleanup.file_state(path)
                item["object_id"] = "sha256:" + item["state"]["sha256"]
            original["items"].append(item)
        original["directories"] = []
        journal = candidate["journal"]
        journal.write("intent", original)
        for number in range(1017):
            journal.write(f"item-{number}-deleted", {"number": number, "state": "absent_after_bound_delete_intent"})
        return candidate

    def test_rebind_changes_only_the_two_refs_inside_the_new_approval(self):
        candidate = self.partial_run()
        plain = cleanup.reconcile_plan(candidate)
        rebound = cleanup.reconcile_plan(candidate, credential_refs=dict(KEYCHAIN))
        again = cleanup.reconcile_plan(candidate, credential_refs=dict(KEYCHAIN))
        self.assertEqual(rebound["public"]["completed_items_not_reprocessed"], 1017)
        self.assertEqual(rebound["public"]["pending_recovery_count"], 53)
        storage = rebound["material"]["storage"]
        self.assertEqual({k: storage[k] for k in KEYCHAIN}, KEYCHAIN)
        for field in ("provider_kind", "store_ref", "endpoint_host", "bucket", "region"):
            self.assertEqual(storage[field], STORAGE[field])
        # the original intent is untouched; the rebind is part of the new plan
        self.assertEqual(candidate["material"]["storage"], STORAGE)
        self.assertNotEqual(rebound["public"]["plan_sha256"], plain["public"]["plan_sha256"])
        self.assertEqual(rebound["public"]["plan_sha256"], again["public"]["plan_sha256"])
        rebind = rebound["material"]["reconciliation"]["credential_rebind"]
        self.assertTrue(rebind["remote_identity_unchanged"])
        self.assertNotIn("credential-manager", json.dumps(rebound["public"]))
        self.assertNotIn("WOM_SYNTHETIC_R2", json.dumps(rebound["public"]))
        result = fixture.ActivityCleanupTests.execute(self, rebound)
        self.assertTrue(result["ok"], result)
        self.assertEqual(sum(row["state"] == "already_deleted" for row in result["items"]), 1017)
        self.assertEqual(sum(row["state"] == "deleted" for row in result["items"]), 53)

    def test_invalid_rebind_is_refused(self):
        candidate = self.partial_run()
        for bad in ({"access_key_id_ref": "credential-manager:ok-name"},
                    {"access_key_id_ref": "credential-manager:a/b", "secret_access_key_ref": "env:X_SECRET"},
                    {**KEYCHAIN, "bucket": "another-bucket"}):
            with self.subTest(bad=sorted(bad)):
                with self.assertRaises(cleanup.ActivityCleanupError) as caught:
                    cleanup.reconcile_plan(candidate, credential_refs=bad)
                self.assertEqual(caught.exception.code, "activity_cleanup_credential_rebind_invalid")

    def test_refs_state_reports_an_env_ref_lost_with_its_process(self):
        env = {name: value for name, value in os.environ.items() if not name.startswith("WOM_SYNTHETIC_R2_")}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(cli._object_storage_credential_refs_state(STORAGE), "unresolved")
        with patch.dict(os.environ, {"WOM_SYNTHETIC_R2_ACCESS_177": "synthetic-access",
                                     "WOM_SYNTHETIC_R2_SECRET_177": "synthetic-secret"}):
            self.assertEqual(cli._object_storage_credential_refs_state(STORAGE), "resolvable")
        with patch.object(services, "_tiro_windows_credential_manager_read_secret",
                          return_value=("synthetic-secret", {})) as reader:
            self.assertEqual(cli._object_storage_credential_refs_state({**STORAGE, **KEYCHAIN}), "resolvable")
        # the object-storage path reads the exact OS target only, never a substring match
        self.assertTrue(all(call.kwargs.get("exact_only") is True for call in reader.call_args_list))

    def test_unreadable_refs_are_named_in_the_preview_and_refused_before_the_dialog(self):
        candidate = self.partial_run()
        env = {name: value for name, value in os.environ.items() if not name.startswith("WOM_SYNTHETIC_R2_")}

        def run(*flags):
            args = cli.build_parser().parse_args(
                ["activity-cleanup", str(self.root), "--request", str(self.request), "--reconcile",
                 "--no-progress", *flags])
            out = io.StringIO()
            with patch.object(cleanup, "plan", return_value=candidate), \
                    patch.object(cli, "_execute_exact_human_approved_write",
                                 side_effect=AssertionError("dialog opened")), \
                    patch.dict(os.environ, env, clear=True), redirect_stdout(out), redirect_stderr(io.StringIO()):
                args.func(args)
            return json.loads(out.getvalue())

        preview = run("--dry-run")
        self.assertEqual(preview["credential_refs_state"], "unresolved")
        self.assertIn("--rebind-access-key-id-ref", preview["credential_refs_next_action"])
        if os.name == "nt":
            refused = run("--approve", "--reviewed-by", "person:synthetic",
                          "--expected-plan-sha256", preview["plan_sha256"])
            self.assertFalse(refused["ok"])
            self.assertIn("activity_cleanup_credential_ref_unresolved", json.dumps(refused))
        # the rebind flags belong to --reconcile only and come as a pair
        args = cli.build_parser().parse_args(
            ["activity-cleanup", str(self.root), "--request", str(self.request), "--dry-run", "--no-progress",
             "--rebind-access-key-id-ref", KEYCHAIN["access_key_id_ref"]])
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            args.func(args)
        self.assertIn("activity_cleanup_credential_rebind_pair_required", out.getvalue())


if __name__ == "__main__":
    unittest.main()
