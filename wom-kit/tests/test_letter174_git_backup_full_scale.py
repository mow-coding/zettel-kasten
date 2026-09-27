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
