"""Actual private registry reads and public CLI queries; synthetic data only."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_query as query
from wom_kit import work_session_registry as registry


ARCHIVE_ID = "archive:synthetic:session-query"


class SessionQueryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-query-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.archive_sha = approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID)
        self.store = registry.WorkSessionRegistryStore(self.root, self.archive_sha)

    def files(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def transition(self, action, **kwargs):
        planned = registry.plan_transition(self.store.read(), action=action, **kwargs)
        with exact.ExactOperationWriterLock(self.root) as held:
            # Fixture setup only; this is not an application approval substitute.
            self.store.commit(planned, held_lock=held,
                              verify_human_authority=lambda sha: sha == planned.plan_sha256)
        return planned.result_refs

    def populate(self):
        app, = self.transition("register-app", label="PRIVATE_SYNTHETIC_APP")
        stream, session = self.transition("create", client_app_ref=app, label="PRIVATE_SYNTHETIC_TASK")
        self.transition("claim", client_app_ref=app, work_session_ref=session)
        return app, stream, session

    def cli(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(["work-session", str(self.root), *argv])
        self.assertEqual(stderr.getvalue(), "")
        return code, json.loads(stdout.getvalue())

    def test_empty_public_cli_is_read_only_without_native_claim_or_registry_creation(self):
        before = self.files()
        code, result = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["counts"], {"registry_kind_total": 0, "selected": 0, "excluded_by_filters": 0})
        self.assertFalse(result["artifact_attribution_evaluated"])
        self.assertEqual(before, self.files())
        self.assertFalse(self.store.path.exists())

    def test_default_json_parse_errors_do_not_echo_private_arguments(self):
        before = self.files()
        for option in ("--page-size", "--action", "--kind", "--format", "--unknown-option"):
            with self.subTest(option=option):
                code, result = self.cli(option, "PRIVATE_ARGUMENT_MARKER")
                self.assertEqual(code, 2)
                self.assertFalse(result["ok"])
                self.assertFalse(result["private_values_echoed"])
                self.assertNotIn("PRIVATE_ARGUMENT_MARKER", json.dumps(result))
        for option in ("--ref", "--cursor"):
            with self.subTest(option=option):
                code, result = self.cli(option, "PRIVATE_ARGUMENT_MARKER")
                self.assertEqual(code, 1)
                self.assertNotIn("PRIVATE_ARGUMENT_MARKER", json.dumps(result))
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(["work-session", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("--action", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(before, self.files())

    def test_real_registry_list_and_inspect_do_not_echo_labels_or_claims(self):
        app, stream, session = self.populate()
        before = self.files()
        claim = self.store.read()._document["sessions"][session]["claim_ref"]
        for kind, ref in (("app", app), ("workstream", stream), ("session", session)):
            with self.subTest(kind=kind):
                code, listed = self.cli("--kind", kind, "--dry-run")
                self.assertEqual(code, 0)
                self.assertEqual([item["ref"] for item in listed["items"]], [ref])
                code, detail = self.cli("--action", "inspect", "--kind", kind, "--ref", ref)
                self.assertEqual(code, 0)
                rendered = json.dumps([listed, detail])
                self.assertNotIn("PRIVATE_SYNTHETIC", rendered)
                self.assertNotIn(claim, rendered)
                self.assertNotIn(str(self.root), rendered)
                self.assertFalse(detail["query_is_write_authority"])
        self.assertEqual(detail["item"]["binding"], self.store.read().binding(session).document())
        self.assertEqual(before, self.files())

    def test_other_app_filters_cover_full_registry_and_unknown_is_not_empty(self):
        app, stream, session = self.populate()
        other, = self.transition("register-app", label="PRIVATE_SECOND_APP")
        self.transition("create", client_app_ref=other, label="PRIVATE_SECOND_TASK")
        result = query.query_work_sessions(self.root, client_app_ref=app, workstream_ref=stream)
        self.assertEqual(result["counts"], {"registry_kind_total": 2, "selected": 1, "excluded_by_filters": 1})
        self.assertEqual(result["items"][0]["ref"], session)
        with self.assertRaisesRegex(query.WorkSessionQueryError, "work_session_query_not_found"):
            query.query_work_sessions(self.root, client_app_ref="client_app_" + "f" * 32)

    def test_cursor_rejects_new_generation_and_changed_query_without_writes(self):
        self.populate()
        self.transition("register-app", label="PRIVATE_SECOND_APP")
        first = query.query_work_sessions(self.root, kind="app", page_size=1)
        cursor = first["pagination"]["next_cursor"]
        with self.assertRaisesRegex(query.WorkSessionQueryError, "snapshot_pagination_query_changed"):
            query.query_work_sessions(self.root, kind="workstream", page_size=1, cursor=cursor)
        self.transition("register-app", label="PRIVATE_THIRD_APP")
        before = self.files()
        code, result = self.cli("--kind", "app", "--page-size", "1", "--cursor", cursor)
        self.assertEqual(code, 1)
        self.assertEqual(result["reason_code"], "snapshot_pagination_generation_changed")
        self.assertEqual(before, self.files())

    def test_queries_continue_while_existing_writer_lock_is_held(self):
        self.populate()
        with exact.ExactOperationWriterLock(self.root) as held:
            result = query.query_work_sessions(self.root)
            self.assertEqual(result["counts"]["selected"], 1)
            held.verify_held()

    def test_fresh_process_public_cli_reads_the_same_generation_without_effects(self):
        _app, _stream, session = self.populate()
        before = self.files()
        environment = dict(os.environ)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONPATH"] = str(Path(archive_cli.__file__).resolve().parents[1])
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with exact.ExactOperationWriterLock(self.root) as held:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "wom_kit.cli_entry", "work-session", str(self.root),
                 "--action", "inspect", "--ref", session, "--format", "json", "--no-progress"],
                cwd=self.root.parent, env=environment, capture_output=True, text=True,
                encoding="utf-8", timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            held.verify_held()
        self.assertEqual(completed.returncode, 0, "fresh process query failed")
        self.assertEqual(completed.stderr, "")
        result = json.loads(completed.stdout)
        self.assertEqual(result["registry"]["snapshot_sha256"], self.store.read().sha256)
        self.assertEqual(result["item"]["ref"], session)
        self.assertNotIn("PRIVATE_SYNTHETIC", completed.stdout)
        self.assertEqual(before, self.files())

    def test_new_generation_after_capture_does_not_mix_rows_and_summary(self):
        self.populate()
        original = query._capture
        captured = []

        def capture_then_append(root):
            snapshot = original(root)
            captured.append(snapshot)
            self.transition("register-app", label="PRIVATE_CONCURRENT_APP")
            return snapshot

        with patch.object(query, "_capture", side_effect=capture_then_append):
            result = query.query_work_sessions(self.root, kind="app")
        self.assertEqual(result["registry"]["snapshot_sha256"], captured[0].sha256)
        self.assertEqual(result["registry"]["app_count"], 1)
        self.assertEqual(result["counts"]["registry_kind_total"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(query.query_work_sessions(self.root, kind="app")["registry"]["app_count"], 2)

    def test_bad_inputs_and_private_storage_error_have_only_fixed_codes(self):
        for kwargs in ({"kind": []}, {"action": {}}, {"page_size": True}, {"page_size": 2001},
                       {"client_app_ref": "PRIVATE_INVALID"}, {"action": "inspect", "reference": []},
                       {"kind": "app", "workstream_ref": "workstream_" + "a" * 32}):
            with self.subTest(kwargs=list(kwargs)):
                with self.assertRaises(query.WorkSessionQueryError) as caught:
                    query.query_work_sessions(self.root, **kwargs)
                self.assertIsNone(caught.exception.__context__)
                self.assertNotIn("PRIVATE", str(caught.exception))
        with patch.object(registry.WorkSessionRegistryStore, "read", side_effect=OSError("PRIVATE_STORAGE_PATH")):
            code, result = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(result["reason_code"], "work_session_query_unavailable")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_whole_6773_session_generation_pages_without_truncation_or_repeated_row_binding(self):
        empty = registry.RegistrySnapshot.empty(self.archive_sha)
        document = {**empty._document, "revision": 1, "previous_sha256": empty.sha256,
                    "apps": {}, "workstreams": {}, "sessions": {}}
        app = "client_app_" + "a" * 32
        document["apps"][app] = {"label": "PRIVATE_SCALE_APP", "identity_level": "self_declared"}
        for number in range(6773):
            suffix = f"{number:032x}"
            stream, session = "workstream_" + suffix, "work_session_" + suffix
            document["workstreams"][stream] = {"label": "PRIVATE_SCALE_TASK", "active_session_ref": session}
            document["sessions"][session] = {
                "client_app_ref": app, "workstream_ref": stream, "revision": 1, "state": "created",
                "claim_ref": None, "predecessor_ref": None, "handoff_app_ref": None,
            }
        frozen = registry.RegistrySnapshot(document)
        self.store.path.mkdir(parents=True)
        (self.store.path / "000000000001.json").write_bytes(registry._canonical(frozen._document))
        before = self.files()
        cursor, seen, pages = None, [], 0
        with patch.object(registry.RegistrySnapshot, "binding", side_effect=AssertionError("per-row full validation")):
            while True:
                result = query.query_work_sessions(self.root, page_size=2000, cursor=cursor)
                seen.extend(item["ref"] for item in result["items"])
                pages += 1
                self.assertEqual(result["pagination"]["total_count"], 6773)
                self.assertFalse(result["pagination"]["cursor_is_authority"])
                cursor = result["pagination"]["next_cursor"]
                if cursor is None:
                    break
        self.assertEqual(pages, 4)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(document["sessions"]))
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
