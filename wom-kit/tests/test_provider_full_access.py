"""Provider composition uses the real session grant broker for every stage."""
import json
from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from wom_kit import provider_tiro, provider_workflows as workflows, archive_cli as cli, archive_services as services
from wom_kit import exact_human_approval_workflow as broker, imap_message_fetch, provider_artifacts as artifacts
import test_provider_imap as imap_helpers
import test_v0424_session_permission_modes as permissions


class ProviderFullAccessTests(unittest.TestCase):
    def call(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = cli.main(list(args))
        result = json.loads(output.getvalue())
        self.assertEqual(status, 0, result)
        return result

    def test_public_tiro_and_imap_full_pipeline_reuses_full_access_without_additional_dialogs(self):
        fixture = permissions.SessionPermissionModeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        # The session fixture supplies real Git/session behavior; provider
        # intake additionally needs the normal initialized archive contracts.
        shutil.copytree(Path(__file__).parents[1] / "examples/fake-life-archive", fixture.root, dirs_exist_ok=True)
        task = fixture.establish("provider")
        fixture.set_mode(task, "allow_all")
        root = fixture.root
        (root / "synthetic-tiro.json").write_text(json.dumps({"schema": provider_tiro.BUNDLE_SCHEMA,
            "notes": [{"guid": "synthetic-note"}], "paragraphs_by_note": {"synthetic-note": [{"content": "Unique provider granted source"}]}}))
        dialogs = fixture.native.calls
        # Production constructs a fresh key facade per operation. Reuse the
        # synthetic key bytes, not the fixture's single active consumer object.
        with patch.object(broker, "_production_key_provider", side_effect=lambda: type(fixture.key)()), \
                patch.dict(os.environ, fixture.env(task)):
            flags = ("tiro-content-import", str(root), "--bundle", "synthetic-tiro.json", "--batch-id", "granted")
            plan = self.call(*flags, "--dry-run")
            result = self.call(*flags, "--approve", "--reviewed-by", permissions.REVIEWER,
                "--expected-plan-sha256", plan["plan_sha256"])
            self.assertTrue(result["capture_completed"], result)
            self.assertTrue(result["search_verified"])
            bindings = services.load_source_bindings(root)
            bindings["sources"] = [*services.source_bindings_list(bindings),
                {"source_id": "mail-synthetic", "source_type": "imap_mailbox"}]
            services.archive_internal_path(root, "source-bindings.yml").write_text(json.dumps(bindings), encoding="utf-8")
            flags = ("imap-mailbox-message-fetch", str(root), "--source-id", "mail-synthetic", "--batch-id", "mail-granted",
                "--imap-host", "mail.example.invalid", "--username-ref", "env:SYNTHETIC_USER", "--app-password-ref", "env:SYNTHETIC_PASSWORD",
                "--sync", "--extract-mime", "--format", "json")
            plan = self.call(*flags, "--dry-run")
            client = imap_helpers.Client({b"4": imap_helpers.message("CLI_searchable_uniquequokka")})
            first_raw = client.messages[b"4"]
            with patch.object(imap_message_fetch, "_client_factory", return_value=client), \
                    patch.dict(os.environ, {"SYNTHETIC_USER": "synthetic", "SYNTHETIC_PASSWORD": "synthetic"}):
                result = self.call(*flags, "--approve", "--reviewed-by", permissions.REVIEWER,
                    "--expected-plan-sha256", plan["plan_sha256"])
            first_receipt = artifacts.read_json(root, result["receipt_path"])
            second_raw = imap_helpers.message("CLI_searchable_uniquesloth")
            second_client = imap_helpers.Client({b"4": first_raw, b"8": second_raw})
            for batch_id, active_client in (("mail-second", second_client),
                    ("mail-no-new", imap_helpers.Client(second_client.messages)),
                    ("mail-empty", imap_helpers.Client({}))):
                next_flags = list(flags)
                next_flags[next_flags.index("--batch-id") + 1] = batch_id
                plan = self.call(*next_flags, "--dry-run")
                with patch.object(imap_message_fetch, "_client_factory", return_value=active_client), \
                        patch.dict(os.environ, {"SYNTHETIC_USER": "synthetic", "SYNTHETIC_PASSWORD": "synthetic"}):
                    result = self.call(*next_flags, "--approve", "--reviewed-by", permissions.REVIEWER,
                        "--expected-plan-sha256", plan["plan_sha256"])
                self.assertTrue(result["capture_completed"] and result["search_verified"], result)
                if batch_id == "mail-second":
                    after = artifacts.read_json(root, result["receipt_path"])
                    old = next(row for row in first_receipt["bindings"] if row["role"] == "email_attachment")
                    new = next(row for row in after["bindings"] if row["role"] == "email_attachment")
                    self.assertEqual(old["child_object_id"], new["child_object_id"])
                    self.assertNotEqual(old["parent_object_id"], new["parent_object_id"])
                    self.assertEqual(result["reused_intake_item_count"], 1)
                else:
                    self.assertEqual(active_client.calls, [])
            self.assertEqual(second_client.calls, [b"8"])
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["capture_completed"], result)
        self.assertTrue(result["search_verified"])
        self.assertTrue(services.search_archive(root, "CLI_searchable_uniquequokka")["results"])
        self.assertTrue(services.search_archive(root, "CLI_searchable_uniquesloth")["results"])
        self.assertEqual(fixture.native.calls, dialogs)
