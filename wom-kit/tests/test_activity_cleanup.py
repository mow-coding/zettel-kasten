"""Synthetic external files only: actual native bound delete plus failure replay."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from wom_kit import activity_cleanup as cleanup


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class ActivityCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "archive"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples/fake-life-archive", self.root)
        self.external = self.base / "external"
        self.external.mkdir()
        self.source = self.external / "PRIVATE_SYNTHETIC.txt"
        self.source.write_bytes(b"synthetic source")
        self.request = self.base / "request.json"
        self.document = {"schema": cleanup.SCHEMA, "activity_id": "synthetic-activity",
            "roots": [str(self.external)], "items": [{"path": str(self.source), "role": "source",
                "reason": "Original synthetic test source", "disposition": "preserve"}],
            "remove_empty_directories": [str(self.external)]}
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        self.backend = Mock()
        self.backend.verify.return_value = True
        self.claim = Mock(spec=["assert_ready_for_context", "public_summary"])
        self.claim.public_summary.return_value = {"approval_id": "approval_" + "a" * 32, "approval_mechanism": "synthetic"}
        self.key = _KeyProvider()

    def plan(self, resume=False):
        return cleanup.plan(self.root, self.request, resume=resume, key_provider=self.key)

    def execute(self, candidate):
        with patch.object(cleanup.services, "_require_exact_human_operation_approval", return_value={"synthetic": True}):
            return cleanup.execute(candidate, reviewer="person:synthetic", claim=self.claim, backend=self.backend)

    def test_plan_is_read_only_and_classification_is_not_filename_heuristic(self):
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["blockers"])
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(candidate["public"]))
        self.assertFalse((self.root / cleanup.ROOT).exists())
        self.document["items"][0]["role"] = "unknown"
        self.request.write_text(json.dumps(self.document))
        self.assertIn("activity_cleanup_unknown_classification", self.plan()["public"]["blockers"])

    def test_directory_only_metadata_churn_keeps_plan_while_content_changes_do_not(self):
        # Letter 173 A: preview and approve differed only in folder size rows
        # (0 <-> 4096 on Windows). Folder size and mtime carry no content that the
        # listing does not already record, so they must not change the plan.
        nested = self.external / "nested"
        nested.mkdir()
        (nested / "kept.txt").write_bytes(b"unselected but inventoried")
        first = self.plan()["public"]["plan_sha256"]
        scratch = nested / "transient.tmp"
        scratch.write_bytes(b"x")
        scratch.unlink()
        os.utime(nested, ns=(1, 1))
        original_lstat = Path.lstat
        class _FlippedDirectorySize:
            def __init__(self, info):
                self._info = info
                self.st_size = 4096 if info.st_size == 0 else 0
            def __getattr__(self, name):
                return getattr(self._info, name)
        def windows_like_lstat(path):
            info = original_lstat(path)
            return _FlippedDirectorySize(info) if stat.S_ISDIR(info.st_mode) else info
        with patch.object(Path, "lstat", windows_like_lstat):
            self.assertEqual(self.plan()["public"]["plan_sha256"], first)
        self.assertEqual(self.plan()["public"]["plan_sha256"], first)
        (nested / "new.txt").write_bytes(b"new file")
        self.assertNotEqual(self.plan()["public"]["plan_sha256"], first)
        (nested / "new.txt").unlink()
        self.assertEqual(self.plan()["public"]["plan_sha256"], first)
        (nested / "kept.txt").write_bytes(b"unselected content changed")
        self.assertNotEqual(self.plan()["public"]["plan_sha256"], first)

    def test_refusal_before_approval_reports_no_effects(self):
        # Letter 173 request 2: a plan mismatch refused before any write is not an
        # unknown outcome.
        import io
        from contextlib import redirect_stdout
        from wom_kit import archive_cli
        output = io.StringIO()
        with redirect_stdout(output):
            code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                "--approve", "--expected-plan-sha256", "sha256:" + "0" * 64, "--reviewed-by", "person:synthetic"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result["effects_state"], "none")
        self.assertIn(result["reason_codes"][0], {"activity_cleanup_plan_changed", "activity_cleanup_native_delete_not_supported"})
        self.assertFalse((self.root / cleanup.ROOT).exists())

    def test_preview_reports_content_free_stages_and_counts(self):
        # Letter 173 B: a long preview/approve must not look like a hang.
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from wom_kit import archive_cli
        progress_log = self.base / "progress.jsonl"
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                "--dry-run", "--progress-log", str(progress_log)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["ok"])
        stderr = errors.getvalue()
        for stage in ("activity-cleanup-inventory", "activity-cleanup-hash"):
            self.assertIn(stage, stderr)
            self.assertIn(stage, progress_log.read_text(encoding="utf-8"))
        for private in ("PRIVATE_SYNTHETIC", str(self.external), "Original synthetic test source"):
            self.assertNotIn(private, stderr)
            self.assertNotIn(private, progress_log.read_text(encoding="utf-8"))
        quiet = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(quiet):
            archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request), "--dry-run", "--no-progress"])
        self.assertNotIn("activity-cleanup-hash", quiet.getvalue())
        inside = io.StringIO()
        with redirect_stdout(inside):
            code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                "--dry-run", "--progress-log", str(self.root / "progress.jsonl")])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(inside.getvalue())["reason_codes"], ["activity_cleanup_progress_log_path_unsafe"])
        self.assertFalse((self.root / "progress.jsonl").exists())

    @unittest.skipUnless(shutil.which("git"), "Git inventory")
    def test_git_history_dirty_files_and_other_worktree_are_distinguished(self):
        def git(*args):
            return subprocess.run(["git", "-C", str(self.external), *args],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init")
        git("config", "user.email", "synthetic@example.invalid")
        git("config", "user.name", "Synthetic")
        git("add", "PRIVATE_SYNTHETIC.txt")
        git("commit", "-m", "Synthetic base")
        (self.external / ".env").write_text("SYNTHETIC_ONLY=1")
        self.source.write_bytes(b"synthetic changed source")
        git("worktree", "add", "-b", "synthetic-other", str(self.base / "other-worktree"), "HEAD")
        candidate = self.plan()
        facts = candidate["public"]["git"][0]
        self.assertTrue(facts["repository"])
        self.assertTrue(facts["has_uncommitted_or_untracked_files"])
        self.assertTrue(facts["external_worktree_dependency"])
        self.assertGreater(candidate["public"]["inventory"]["git_metadata_file_count"], 0)
        self.assertGreater(candidate["public"]["inventory"]["possible_secret_config_count"], 0)
        self.document["items"] = [{"path": str(self.external / ".git" / "HEAD"),
            "role": "evidence", "reason": "Synthetic Git history", "disposition": "preserve"}]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        blocked = self.plan()
        self.assertIn("activity_cleanup_shared_git_metadata_requires_worktree_detach", blocked["public"]["blockers"])
        self.assertTrue((self.external / ".git" / "HEAD").exists())

    @unittest.skipUnless(os.name == "nt" and shutil.which("git"), "Windows Git deletion guard")
    def test_worktree_added_after_git_plan_retains_shared_history(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.external), *args],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init")
        git("config", "user.email", "synthetic@example.invalid")
        git("config", "user.name", "Synthetic")
        git("add", "PRIVATE_SYNTHETIC.txt")
        git("commit", "-m", "Synthetic base")
        history_file = self.external / ".git" / "HEAD"
        self.document["items"] = [{"path": str(history_file), "role": "evidence",
            "reason": "Synthetic Git history", "disposition": "preserve"}]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["git"])
        git("worktree", "add", "-b", "synthetic-other", str(self.base / "other-worktree"), "HEAD")
        result = self.execute(candidate)
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"][0]["code"], "activity_cleanup_shared_git_metadata_requires_worktree_detach")
        self.assertTrue(history_file.exists())
        self.backend.preserve.assert_not_called()

    @unittest.skipUnless(os.name == "nt" and shutil.which("git"), "Windows native Git folder cleanup")
    def test_selected_git_history_dirty_and_secret_candidate_cover_entire_folder(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.external), *args],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init")
        git("config", "user.email", "synthetic@example.invalid")
        git("config", "user.name", "Synthetic")
        git("add", "PRIVATE_SYNTHETIC.txt")
        git("commit", "-m", "Synthetic base")
        self.source.write_bytes(b"synthetic dirty source")
        (self.external / ".env").write_text("SYNTHETIC_ONLY=1")
        files = sorted(path for path in self.external.rglob("*") if path.is_file())
        directories = sorted((path for path in self.external.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts), reverse=True)
        self.document["items"] = [{"path": str(path), "role": "evidence" if path.is_relative_to(self.external / ".git") else "source",
            "reason": "Explicit synthetic Git history or working source", "disposition": "preserve"} for path in files]
        self.document["remove_empty_directories"] = [str(path) for path in directories] + [str(self.external)]
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["blockers"])
        self.assertTrue(candidate["public"]["git"][0]["has_uncommitted_or_untracked_files"])
        self.assertEqual(candidate["public"]["inventory"]["selected_file_count"],
            candidate["public"]["inventory"]["file_or_link_count"])
        result = self.execute(candidate)
        self.assertTrue(result["ok"], [(row, files[row["number"]].relative_to(self.external))
            for row in result["items"] if row["state"] == "retained"])
        self.assertFalse(self.external.exists())
        self.assertEqual(self.backend.preserve.call_count, len(files))
        self.assertFalse(result["whole_folder_preservation_claimed"])
        self.assertEqual(result["remaining"]["scope_completion"], "empty")

    @unittest.skipUnless(os.name == "nt", "Windows native deletion")
    def test_exact_files_deleted_empty_directory_removed_and_resume_is_idempotent(self):
        result = self.execute(self.plan())
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.source.exists())
        self.assertFalse(self.external.exists())
        self.backend.preserve.assert_called_once()
        self.backend.verify.assert_called_once()
        result = self.execute(self.plan(resume=True))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["state"], "already_deleted")
        self.backend.preserve.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Windows native deletion")
    def test_changed_file_and_unverified_remote_are_retained(self):
        candidate = self.plan()
        self.source.write_bytes(b"foreign replacement")
        result = self.execute(candidate)
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"][0]["code"], "activity_cleanup_file_changed")
        self.backend.preserve.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows native sharing lock")
    def test_locked_external_file_is_retained_without_preservation_claim(self):
        from wom_kit import legacy_cleanup_bound_delete as bound
        candidate = self.plan()
        api = bound._windows_api()
        handle = api.create_file(str(self.source), api.GENERIC_READ, 0, None,
            api.OPEN_EXISTING, 0, None)
        self.assertNotEqual(int(handle), api.invalid_handle)
        try:
            result = self.execute(candidate)
        finally:
            api.close_handle(handle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["items"][0]["state"], "retained")
        self.assertTrue(self.source.exists())
        self.backend.preserve.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows native deletion")
    def test_remote_failure_then_resume_and_new_files_are_not_deleted(self):
        self.backend.verify.return_value = False
        result = self.execute(self.plan())
        self.assertFalse(result["ok"])
        self.assertTrue(self.source.exists())
        extra = self.external / "new.txt"
        extra.write_bytes(b"new file outside selection")
        self.backend.verify.return_value = True
        result = self.execute(self.plan(resume=True))
        self.assertFalse(result["ok"])
        self.assertFalse(self.source.exists())
        self.assertTrue(extra.exists())
        self.assertEqual(result["directories"][0]["state"], "retained_nonempty_or_changed")

    @unittest.skipUnless(os.name == "nt", "Windows native deletion")
    def test_interruption_after_delete_resumes_without_repeating_delete(self):
        candidate = self.plan()
        original = candidate["journal"].write
        def interrupt(name, document):
            if name.endswith("-deleted"):
                raise KeyboardInterrupt()
            return original(name, document)
        with patch.object(candidate["journal"], "write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(candidate)
        self.assertFalse(self.source.exists())
        result = self.execute(self.plan(resume=True))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["items"][0]["state"], "already_absent_after_intent")

    @unittest.skipUnless(os.name == "nt", "Windows read-only disposition recovery")
    def test_readonly_file_deleted_then_resumed_after_completion_record_interruption(self):
        self.source.chmod(stat.S_IREAD)
        candidate = self.plan()
        original = candidate["journal"].write
        def interrupt(name, document):
            if name.endswith("-deleted"):
                raise KeyboardInterrupt()
            return original(name, document)
        with patch.object(candidate["journal"], "write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(candidate)
        self.assertFalse(self.source.exists())
        resumed = self.execute(self.plan(resume=True))
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["items"][0]["state"], "already_absent_after_intent")

    @unittest.skipUnless(os.name == "nt", "Windows native deletion")
    def test_tampered_intent_and_expired_authority_cannot_delete(self):
        candidate = self.plan()
        self.backend.verify.return_value = False
        self.execute(candidate)
        intent = self.root / candidate["journal"].relative("intent")
        value = json.loads(intent.read_bytes())
        value["document"]["items"][0]["state"]["sha256"] = "0" * 64
        intent.write_text(json.dumps(value))
        with self.assertRaises(cleanup.ActivityCleanupError):
            self.plan(resume=True)
        self.assertTrue(self.source.exists())

    @unittest.skipUnless(os.name == "nt", "Windows complete synthetic pipeline")
    def test_official_intake_upload_offload_external_cleanup_pipeline(self):
        import io
        from contextlib import ExitStack, redirect_stdout, redirect_stderr
        from wom_kit import archive_cli, archive_services as services
        from wom_kit import exact_human_approval_workflow as broker, exact_human_approval_windows as windows
        from .test_v0421_source_intake_chain_exact_approval import _Native
        from .test_object_storage_preservation import _MemoryTransport
        common = dict(archive_id=services.read_archive_id(self.root), profile_id="profile:synthetic:activity",
            profile_slug="synthetic-activity", provider_kind="cloudflare-r2", storage_account_ref="synthetic-store",
            bucket_name="synthetic-activity-bucket", region="auto", endpoint_ref="provider:endpoint:synthetic",
            objet_prefix="archives/synthetic/objets/", visibility="private")
        binding = services.build_object_storage_provider_binding(**common)
        (self.root / "provider-bindings.yml").write_text(services.dump_yaml({"version": "provider-bindings/v0.1",
            "archive_id": common["archive_id"], "bindings": [binding]}), encoding="utf-8")
        relative = services.object_storage_provider_setup_receipt_path(common["bucket_name"])
        receipt = services.build_object_storage_provider_setup_receipt(**common, receipt_path=relative,
            reviewed_by="person:synthetic", timestamp="2026-09-23T00:00:00Z", dry_run=False, manual_steps=[])
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt), encoding="utf-8")
        services.index_archive(self.root)
        self.document["storage"] = {"provider_kind": "cloudflare-r2", "store_ref": "synthetic-store"}
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        from wom_kit import object_storage_upload_exact as upload
        plans = []
        original_plan = upload.plan_object_storage_upload
        def remember(*args, **kwargs):
            value = original_plan(*args, **kwargs)
            plans.append(value.public_document())
            return value
        class InterruptedAfterPut(_MemoryTransport):
            def put_object(inner, **kwargs):
                result = super().put_object(**kwargs)
                inner.fail_once = True
                return result
            def head_object(inner, **kwargs):
                if getattr(inner, "fail_once", False):
                    inner.fail_once = False
                    return {"present": False, "presence_state": "unavailable", "verification_state": "unavailable"}
                return super().head_object(**kwargs)
        transport = InterruptedAfterPut() if getattr(self, "interrupt_after_put", False) else _MemoryTransport()
        get_count = [0]
        original_head = transport.head_object
        def count_whole_gets(**kwargs):
            result = original_head(**kwargs)
            if not kwargs.get("presence_only", False) and result.get("present") is True and result.get("checksum_sha256"):
                get_count[0] += 1
            return result
        transport.head_object = count_whole_gets
        native = _Native()
        output = io.StringIO()
        with ExitStack() as stack:
            if getattr(self, "interrupt_intake", False):
                from wom_kit import objet_capture_selection_exact as selection
                original_selection = selection.execute_existing_intake_capture_selection_in_chain
                failed = [False]
                def interrupt_selection(*args, **kwargs):
                    if not failed[0]:
                        failed[0] = True
                        raise OSError("synthetic interruption after intake receipt")
                    return original_selection(*args, **kwargs)
                stack.enter_context(patch.object(selection, "execute_existing_intake_capture_selection_in_chain", side_effect=interrupt_selection))
            if getattr(self, "interrupt_capture", False) or getattr(self, "interrupt_after_capture", False):
                original_capture = services.objet_capture_apply
                capture_failed = [False]
                def interrupt_capture(*args, **kwargs):
                    if not capture_failed[0]:
                        capture_failed[0] = True
                        if getattr(self, "interrupt_after_capture", False):
                            original_capture(*args, **kwargs)
                        raise OSError("synthetic capture interruption")
                    return original_capture(*args, **kwargs)
                stack.enter_context(patch.object(services, "objet_capture_apply", side_effect=interrupt_capture))
            stack.enter_context(patch.object(upload, "plan_object_storage_upload", side_effect=remember))
            stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
            stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=native))
            stack.enter_context(patch.object(archive_cli, "_object_storage_live_transport_factory", return_value=lambda: transport))
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                    "--approve", "--reviewed-by", "person:synthetic"])
            if any(getattr(self, flag, False) for flag in ("interrupt_after_put", "interrupt_intake", "interrupt_capture", "interrupt_after_capture")):
                partial = json.loads(output.getvalue())
                self.assertEqual(code, 1, partial)
                self.assertTrue(self.source.exists())
                self.assertEqual(transport.put_calls, 1 if getattr(self, "interrupt_after_put", False) else 0)
                output = io.StringIO()
                with redirect_stdout(output), redirect_stderr(io.StringIO()):
                    code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                        "--resume", "--reviewed-by", "person:synthetic"])
                from wom_kit import exact_approval_claims
                claims = exact_approval_claims.list_exact_human_approval_claims(self.root, status="started", key_provider=self.key)
                self.assertEqual(claims["claims"], [], (json.loads(output.getvalue()), claims["started_operation_counts"]))
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0, (result, plans))
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.source.exists())
        self.assertEqual(transport.put_calls, 1)
        if not getattr(self, "interrupt_after_put", False):
            self.assertEqual(get_count[0], 1, "composed upload and cleanup must share whole-byte proof")
        self.assertIn(b"synthetic source", transport.objects.values())
        self.assertFalse(any(p.is_file() for p in (self.root / "staging/incoming/activity-synthetic-activity").glob("*")))
        oid = "sha256:" + __import__("hashlib").sha256(b"synthetic source").hexdigest()
        self.assertFalse((self.root / "objects/sha256" / oid[7:9] / oid[7:]).exists())
        self.assertNotIn("PRIVATE_SYNTHETIC", output.getvalue())
        if getattr(self, "check_remote_only_staging", False):
            from wom_kit.remote_preservation_proof import PreservationVerifier, ProofStore
            duplicate = self.root / "staging/incoming/remote-only-duplicate"
            duplicate.mkdir(parents=True)
            (duplicate / "source.txt").write_bytes(b"synthetic source")
            verifier = PreservationVerifier(transport, store_ref="synthetic-store",
                execution_sha256="sha256:" + "a" * 64,
                proof_store=ProofStore(self.root, key_provider=self.key))
            staged = services.staged_cleanup_check(self.root, "staging/incoming/remote-only-duplicate",
                remote_verifier=verifier, remote_provider_kind="cloudflare-r2")
            self.assertTrue(staged["safe_to_cleanup"], staged)
            self.assertFalse((self.root / "objects/sha256" / oid[7:9] / oid[7:]).exists(),
                "remote proof must not restore local bytes")
        if getattr(self, "expect_no_dialog", False):
            self.assertEqual(native.calls, 0)
            from wom_kit import object_storage_scope as scope
            output_list = self.base / "session-objects.txt"
            selection = scope.export_scope_list(self.root, output=output_list,
                this_session=True, key_provider=self.key)
            self.assertTrue(selection["ok"], selection)
            self.assertEqual(selection["selected_object_count"], 1)
            self.assertEqual(output_list.read_text(encoding="utf-8"), oid + "\n")

    @unittest.skipUnless(os.name == "nt", "Windows full pipeline")
    def test_remote_only_staging_uses_offloaded_object_without_restore(self):
        self.check_remote_only_staging = True
        self.test_official_intake_upload_offload_external_cleanup_pipeline()

    @unittest.skipUnless(os.name == "nt", "Windows full access pipeline")
    def test_full_access_official_pipeline_has_zero_additional_dialogs(self):
        from .test_v0424_session_permission_modes import SessionPermissionModeTests
        from wom_kit import work_session_registration as registration
        fixture = SessionPermissionModeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.root = self.root
        fixture.store = registration._store(self.root)
        task = fixture.establish("activity-cleanup")
        fixture.set_mode(task, "allow_all")
        self.expect_no_dialog = True
        with patch.dict(os.environ, fixture.env(task)):
            self.test_official_intake_upload_offload_external_cleanup_pipeline()

    @unittest.skipUnless(os.name == "nt", "Windows interrupted composed pipeline")
    def test_full_access_recovers_uploaded_bytes_without_second_put_or_orphan_claim(self):
        self.interrupt_after_put = True
        self.test_full_access_official_pipeline_has_zero_additional_dialogs()

    @unittest.skipUnless(os.name == "nt", "Windows interrupted intake pipeline")
    def test_full_access_resumes_after_intake_record_before_capture(self):
        self.interrupt_intake = True
        self.test_full_access_official_pipeline_has_zero_additional_dialogs()

    @unittest.skipUnless(os.name == "nt", "Windows interrupted selection pipeline")
    def test_full_access_resumes_after_selection_before_capture(self):
        self.interrupt_capture = True
        self.test_full_access_official_pipeline_has_zero_additional_dialogs()

    @unittest.skipUnless(os.name == "nt", "Windows completed capture recovery")
    def test_full_access_recovers_capture_before_chain_completion_receipt(self):
        self.interrupt_after_capture = True
        self.test_full_access_official_pipeline_has_zero_additional_dialogs()

    @unittest.skipUnless(os.name == "nt", "Windows writer lock")
    def test_concurrent_writer_and_expired_grant_do_not_delete(self):
        candidate = self.plan()
        with candidate["journal"].writer_lock():
            with self.assertRaisesRegex(cleanup.ActivityCleanupError, "writer_active"):
                self.execute(candidate)
        self.claim.public_summary.return_value["approval_mechanism"] = cleanup.PERMISSION_INTERACTIVE_INTENT_MECHANISM
        from wom_kit import exact_human_approval_workflow as broker
        with patch.object(broker, "_resolved_session_permission", return_value=(None, "expired")):
            with self.assertRaisesRegex(cleanup.ActivityCleanupError, "permission_expired"):
                self.execute(candidate)
        self.assertTrue(self.source.exists())
        self.backend.preserve.assert_not_called()

    def test_partial_staging_copy_resumes_without_discarding_foreign_residue(self):
        candidate = self.plan()
        backend = object.__new__(cleanup.OfficialPreservationBackend)
        backend.root, backend.material = self.root, candidate["material"]
        item = candidate["material"]["items"][0]
        staged = self.root / backend._staged(item)
        staged.parent.mkdir(parents=True, exist_ok=True)
        partial = staged.with_suffix(staged.suffix + ".copying")
        partial.write_bytes(b"synthetic")
        self.assertEqual(backend._stage(item).read_bytes(), b"synthetic source")
        self.assertFalse(partial.exists())
        staged.unlink()
        partial.write_bytes(b"foreign bytes")
        with self.assertRaisesRegex(cleanup.ActivityCleanupError, "staging_conflict"):
            backend._stage(item)
        self.assertEqual(partial.read_bytes(), b"foreign bytes")
        self.assertTrue(self.source.exists())

    def test_unsupported_platform_refuses_before_any_journal_or_backend_write(self):
        candidate = self.plan()
        with patch.object(cleanup.os, "name", "posix"):
            with self.assertRaisesRegex(cleanup.ActivityCleanupError, "native_delete_not_supported"):
                self.execute(candidate)
        self.assertFalse((self.root / cleanup.ROOT).exists())
        self.backend.preserve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
