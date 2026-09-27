"""Synthetic 11,132-file exact backup, actual local bare-remote transport."""
from contextlib import ExitStack
import json
import time
import unittest
from unittest.mock import patch

from wom_kit import git_backup_plan as planning, git_backup_writer as writer
from . import test_git_backup_writer as fixture


class GitBackupFullScaleTests(unittest.TestCase):
    def test_large_unicode_activity_backup_preserves_other_activity_changes(self):
        case = fixture.GitBackupWriterTests("runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        root = case.root
        directory = root / "selected-activity" / ("합성 긴 경로 " * 7).strip()
        directory.mkdir(parents=True)
        count = 11132
        started = time.monotonic()
        for index in range(count):
            (directory / f"합성자료-{index:05d}.txt").write_bytes(f"synthetic {index}\n".encode())
        excluded = {p: (root / p).read_bytes() for p in ("tracked.txt", "new-private.txt")}
        timings = {"fixture_seconds": time.monotonic() - started}
        print(json.dumps(timings), flush=True)
        captured = {}
        with ExitStack() as stack:
            for item in case.patches():
                stack.enter_context(item)
            started = time.monotonic()
            plan = planning.git_backup_plan(root, credential_mode="stored", _private_capture=captured)
            timings["plan_seconds"] = time.monotonic() - started
            print(json.dumps(timings), flush=True)
            self.assertTrue(plan["ok"], plan.get("blockers"))
            selected, others = [], []
            for row in captured["private_changes"]:
                ref = row["public_observation"]["change_ref"]
                if row["path"].startswith("selected-activity/"):
                    selected.append(ref)
                else:
                    others.append({"change_ref": ref, "scope": "other_session", "reason": "other_session_change"})
            self.assertEqual(len(selected), count)
            document = {"schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA,
                "expected_plan_sha256": plan["plan_sha256"],
                "selected_groups": [{"group_id": "group:synthetic-activity", "change_refs": sorted(selected),
                    "commit_subject": "Preserve selected synthetic activity"}], "excluded_changes": others}
            case.selection_path.write_text(json.dumps(document), encoding="utf-8")
            started = time.monotonic()
            prepared = writer.prepare_git_backup(root, expected_plan_sha256=plan["plan_sha256"],
                selection_manifest_path=case.selection_path, credential_mode="stored")
            timings["prepare_seconds"] = time.monotonic() - started
            print(json.dumps(timings), flush=True)
            started = time.monotonic()
            original_raw = writer._GitBackupBackend._git_raw
            def diagnose_raw(backend, args, **kwargs):
                start = time.monotonic()
                value = original_raw(backend, args, **kwargs)
                if value is None or value[0] != 0:
                    verb = next((v for v in ("read-tree", "add", "write-tree", "diff-tree", "ls-tree", "cat-file", "commit") if v in args), "other")
                    print(json.dumps({"git_phase": verb, "returncode": value[0] if value else None,
                        "elapsed_seconds": time.monotonic()-start, "input_bytes": len(kwargs.get("input_bytes") or b""),
                        "output_limit": kwargs.get("max_output_bytes"),
                        "timeout_seconds": kwargs.get("timeout_seconds", planning.GIT_BACKUP_LOCAL_TIMEOUT_SECONDS)}), flush=True)
                return value
            stack.enter_context(patch.object(writer._GitBackupBackend, "_git_raw", diagnose_raw))
            original_apply = writer._apply_prepared_with_claim
            observed = []
            for method in ("_commit_group", "_exact_add", "_push"):
                original_method = getattr(writer._GitBackupBackend, method)
                def track(backend, *args, _original=original_method, _method=method, **kwargs):
                    start = time.monotonic()
                    print("starting " + _method, flush=True)
                    try:
                        return _original(backend, *args, **kwargs)
                    except Exception as error:
                        observed.append((_method, type(error).__name__, getattr(error, "code", "unclassified")))
                        raise
                    finally:
                        print(_method + " seconds=" + str(round(time.monotonic() - start, 3)), flush=True)
                stack.enter_context(patch.object(writer._GitBackupBackend, method, track))
            def observe(*args, **kwargs):
                try:
                    return original_apply(*args, **kwargs)
                except Exception as error:
                    observed.append((type(error).__name__, getattr(error, "code", "unclassified")))
                    raise
            try:
                with patch.object(writer, "_apply_prepared_with_claim", observe):
                    result = writer.execute_git_backup(prepared, selection_manifest_path=case.selection_path,
                        reviewer_claim="person:synthetic", native=fixture._Native(), key_provider=fixture._KeyProvider())
            except Exception:
                if observed:
                    self.fail("synthetic_git_backup_failure: " + repr(observed))
                raise
            timings["execute_seconds"] = time.monotonic() - started
        self.assertTrue(result["ok"], result)
        terminal = case.assert_remote_matches_head()
        changed = case.git(root, "diff", "--name-only", "-z", case.initial_head, terminal).stdout.split("\0")
        changed = [path for path in changed if path]
        self.assertEqual(len(changed), count)
        self.assertTrue(all(path.startswith("selected-activity/") for path in changed))
        self.assertEqual(excluded, {path: (root / path).read_bytes() for path in excluded})
        self.assertEqual(case.git_dir(case.remote, "show", "main:tracked.txt").stdout, "before\n")
        self.assertEqual(len(case.transport_commands), 1)
        print(json.dumps({"synthetic_selected_files": count, "other_changes_preserved": len(excluded),
            "timings": timings, "remote_pushes": len(case.transport_commands)}, sort_keys=True), flush=True)


class ExactAddBatchTests(unittest.TestCase):
    def backend(self):
        return object.__new__(writer._GitBackupBackend)

    def test_batches_preserve_literal_unicode_paths_without_duplicates(self):
        backend = self.backend()
        paths = tuple("synthetic/" + "한" * 120 + f"-{n:05}.txt" for n in range(2500))
        calls = []
        def run(args, **kwargs):
            self.assertIn("--pathspec-file-nul", args)
            self.assertIn("--pathspec-from-file=-", args)
            raw = kwargs["input_bytes"]
            self.assertLessEqual(len(raw), 256 * 1024)
            rows = raw[:-1].decode("utf-8").split("\0")
            self.assertLessEqual(len(rows), 1024)
            calls.extend(rows)
            return 0, b""
        with patch.object(backend, "_git_raw", side_effect=run):
            self.assertEqual(backend._git_index_add(paths), (0, b""))
        self.assertEqual(calls, list(paths))

    def test_failed_batch_does_not_replay_prefix_or_stage_remaining_selection(self):
        backend = self.backend()
        paths = tuple(f"synthetic/{n:05}.txt" for n in range(2500))
        with patch.object(backend, "_git_raw", side_effect=[(0, b""), None]) as run:
            self.assertIsNone(backend._git_index_add(paths))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].kwargs["input_bytes"], writer._path_input(paths[:1024]))
        self.assertEqual(run.call_args_list[1].kwargs["input_bytes"], writer._path_input(paths[1024:2048]))

    def test_only_transient_lock_retries_same_batch(self):
        backend = self.backend()
        paths = tuple(f"synthetic/{n:05}.txt" for n in range(2050))
        calls = []
        def run(args, **kwargs):
            calls.append(kwargs["input_bytes"])
            if len(calls) == 2:
                kwargs["stderr_sink"].append(b"fatal: Unable to create 'synthetic/index.lock': File exists.")
                return 128, b""
            return 0, b""
        with patch.object(backend, "_git_raw", side_effect=run), patch.object(writer.time, "sleep"):
            self.assertEqual(backend._git_index_add(paths), (0, b""))
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[1], calls[2])
        self.assertEqual(calls[0] + calls[1] + calls[3], writer._path_input(paths))


class ExactAddBatchResumeTests(unittest.TestCase):
    def test_interrupted_second_batch_preserves_partial_stage_and_resumes_original_claim(self):
        from wom_kit.exact_human_approval_workflow import ExactHumanApprovalWorkflowError
        case = fixture.GitBackupWriterTests("runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        directory = case.root / "synthetic-batched"
        directory.mkdir()
        for index in range(1030):
            (directory / f"{index:05}.txt").write_bytes(f"synthetic {index}".encode())
        prepared = case.plan_and_prepare()
        original = writer._GitBackupBackend._git_raw
        batches = []
        def cut(backend, args, **kwargs):
            if "add" in args and not kwargs.get("extra_environment", {}).get("GIT_INDEX_FILE"):
                batches.append(kwargs["input_bytes"])
                if len(batches) == 2:
                    return 128, b""
            return original(backend, args, **kwargs)
        native = fixture._Native()
        with case.patches()[2], case.patches()[3], patch.object(writer._GitBackupBackend, "_git_raw", cut):
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.execute_git_backup(prepared, selection_manifest_path=case.selection_path,
                    reviewer_claim="person:local-operator", native=native, key_provider=fixture._KeyProvider())
        self.assertEqual(len(batches), 2)
        self.assertEqual(case.git(case.root, "rev-parse", "HEAD").stdout.strip(), case.initial_head)
        staged = case.git(case.root, "diff", "--cached", "--name-only", "-z").stdout.split("\0")
        self.assertEqual(len([p for p in staged if p]), 1024)
        self.assertFalse(case.transport_commands)
        loaded = writer.load_private_git_backup_bundle(case.root, manifest_sha256=prepared.manifest.manifest_sha256)
        # Tamper only with the index, preserving approved worktree identities.
        import subprocess
        target = "synthetic-batched/00000.txt"
        prior_oid = case.git(case.root, "rev-parse", ":" + target).stdout.strip()
        foreign_oid = subprocess.run(["git", "-C", str(case.root), "hash-object", "-w", "--stdin"],
            input=b"unapproved index bytes", capture_output=True, check=True).stdout.decode("ascii").strip()
        case.git(case.root, "update-index", "--cacheinfo", "100644", foreign_oid, target)
        with case.patches()[2], case.patches()[3]:
            with self.assertRaises(ExactHumanApprovalWorkflowError):
                writer.resume_git_backup(loaded, reviewer_claim="person:local-operator",
                    approval_id=case.only_claim_id(), key_provider=fixture._KeyProvider())
        self.assertFalse(case.transport_commands)
        self.assertEqual(case.git(case.root, "rev-parse", "HEAD").stdout.strip(), case.initial_head)
        case.git(case.root, "update-index", "--cacheinfo", "100644", prior_oid, target)
        with case.patches()[2], case.patches()[3]:
            resumed = writer.resume_git_backup(loaded, reviewer_claim="person:local-operator",
                approval_id=case.only_claim_id(), key_provider=fixture._KeyProvider())
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(native.calls, 1)
        self.assertEqual(len(case.transport_commands), 1)
        case.assert_remote_matches_head()
