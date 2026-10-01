"""v0.4.55 (owner request 2026-10-01): WOM's own byproducts are deleted, not left to pile up.

A synthetic project holds what WOM leaves behind: runtimes for earlier
versions, bootstrap environments under LOCALAPPDATA, update results, handoff
capsules and journals, temporary files and an abandoned restore download.
The rules: keep the pinned and the previous runtime, keep the newest records,
keep anything pending or in progress, delete the rest; never echo paths.

Synthetic folders, fake dialog; no client data.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import system_cleanup as cleanup
from wom_kit import work_session_permission as permission
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation

import test_v0433_object_storage_upload as _upload_fixture

DAY = 86400
NOW = time.time()


def _touch(path: Path, *, age: float, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (NOW - age, NOW - age))
    return path


def _runtime(project: Path, version: str, *, receipt: bool = True, age: float = 30 * DAY) -> Path:
    folder = project / ".zettel-kasten" / "runtimes" / f"v{version}"
    _touch(folder / "Lib" / "site-packages" / "wom_kit" / "__init__.py", age=age, data=b"0" * 1000)
    if receipt:
        _touch(folder / "runtime-receipt.json", age=age, data=json.dumps(
            {"schema": "wom-kit/project-runtime-receipt/v0.1", "target_version": version}).encode())
    os.utime(folder, (NOW - age, NOW - age))
    return folder


def _journal(path: Path, *, age: float, kind: str = "doctor", completed: bool = True, acknowledged: bool = True):
    records = [{"operation_kind": kind, "event": "started", "terminal": False}]
    if completed:
        records.append({"operation_kind": kind, "event": "completed", "terminal": True, "result_available": True,
                        "terminal_delivery_acknowledged": acknowledged})
    _touch(path, age=age, data="\n".join(json.dumps(row) for row in records).encode() + b"\n")


class SystemCleanupPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0455-cleanup-")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.project = base / "project"
        self.archive = self.project / "archive"
        self.archive.mkdir(parents=True)
        (self.archive / "archive.yml").write_text("archive_id: archive:test:cleanup\n", encoding="utf-8")
        zk = self.project / ".zettel-kasten"
        _touch(zk / "installed-version.txt", age=DAY, data=b"v0.4.54\n")
        self.local = base / "localappdata"
        self.temp = base / "temp"
        self.temp.mkdir()
        environment = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)})
        environment.start()
        self.addCleanup(environment.stop)
        temp_dir = patch.object(tempfile, "tempdir", str(self.temp))
        temp_dir.start()
        self.addCleanup(temp_dir.stop)

    def build(self):
        project, zk = self.project, self.project / ".zettel-kasten"
        for version in ("0.4.52", "0.4.53", "0.4.54"):
            _runtime(project, version)
        _runtime(project, "0.4.51", receipt=False)  # not recognisably WOM's: kept
        for index in range(8):  # with the one-day-old file below, the 5 newest stay and 4 old ones go
            _touch(zk / "diagnostics" / f"project-version-update-{index:032x}.json", age=(10 + index) * DAY)
        _touch(zk / "diagnostics" / f"project-version-update-{99:032x}.json", age=DAY)
        for index in range(7):
            _touch(zk / "private" / "version-update-terminal" / f"{index:064x}.json", age=(10 + index) * DAY)
        _touch(zk / "private" / "version-update-terminal" / ".handoff.guard", age=30 * DAY)
        for index in range(24):  # newest 20 kept
            _journal(zk / "operations" / f"{index:064x}.jsonl", age=(8 + index) * DAY)
        _journal(zk / "operations" / f"{100:064x}.jsonl", age=60 * DAY, kind="project_version_update",
                 acknowledged=False)  # pending delivery: kept
        _touch(zk / "operations" / f"{101:064x}.jsonl", age=61 * DAY, data=b'{"torn": tr')  # junk
        bootstrap = self.local / "WOM"
        for name, age in ((f"bootstrap-v0452-{'a' * 32}", 20 * DAY), (f"bootstrap-v0453-{'b' * 32}", 10 * DAY),
                          (f"bootstrap-v0455-{'c' * 32}", 10 * DAY), (f"bootstrap-v0454-{'d' * 32}", 3600),
                          ("bootstrap-v049", 90 * DAY), (f"bootstrap-v0446-camp-{'e' * 32}", 40 * DAY)):
            _touch(bootstrap / name / "pyvenv.cfg", age=age, data=b"home = x\n")
            _touch(bootstrap / name / "Lib" / "big.bin", age=age, data=b"0" * 5000)
            os.utime(bootstrap / name, (NOW - age, NOW - age))
        _touch(bootstrap / "notes.txt", age=30 * DAY)
        _touch(bootstrap / "bootstrap-v0440-not-a-venv" / "file.txt", age=30 * DAY)  # no pyvenv.cfg: kept
        _touch(self.temp / "wom-git-backup-abc.index", age=3 * DAY)
        _touch(self.temp / "wom-git-backup-young.index", age=60)
        _touch(self.temp / "someone-else.tmp", age=30 * DAY)
        sinks = self.archive / "profiles" / "local" / "exact-operations" / "restore-sinks" / ("e" * 64)
        _touch(sinks / "obj.part", age=3 * DAY)
        _touch(sinks.parent / ("f" * 64) / "obj.part", age=60)
        for index in range(7):
            _touch(self.archive / ".wom-scratch" / "diagnostics" / f"{index:032x}.json", age=(10 + index) * DAY)
        _touch(self.archive / "receipts" / "keep.json", age=90 * DAY)

    def test_the_plan_deletes_only_finished_or_superseded_byproducts(self):
        self.build()
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertTrue(plan["ok"], plan)
        categories = plan["categories"]
        self.assertEqual(categories["old_runtimes"]["count"], 1)  # v0.4.52 only
        self.assertEqual(categories["update_results"]["count"], 4)
        self.assertEqual(categories["update_handoff_capsules"]["count"], 2)
        self.assertEqual(categories["operation_journals"]["count"], 5)  # 4 beyond the newest 20 + the torn one
        self.assertEqual(categories["bootstrap_environments"]["count"], 4)  # v0452, v0453, v049, v0446-camp
        self.assertEqual(categories["temporary_files"]["count"], 1)
        self.assertEqual(categories["restore_partials"]["count"], 1)
        self.assertEqual(categories["archive_results"]["count"], 2)
        self.assertIn("unrecognised_runtime_kept", plan["kept_notes"])
        self.assertNotIn(str(self.project), json.dumps(plan))
        self.assertNotIn(str(self.local), json.dumps(plan))

    def test_approve_deletes_the_plan_and_keeps_everything_else(self):
        self.build()
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        result = cleanup.approve_system_cleanup(self.archive, expected_plan_sha256=plan["plan_sha256"],
                                                reviewed_by="person:synthetic", now=NOW)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["bytes_freed"], plan["bytes_freed_total"])
        zk = self.project / ".zettel-kasten"
        runtimes = sorted(path.name for path in (zk / "runtimes").iterdir())
        self.assertEqual(runtimes, ["v0.4.51", "v0.4.53", "v0.4.54"])
        self.assertEqual(len(list((zk / "diagnostics").iterdir())), 5)
        self.assertTrue((zk / "operations" / f"{100:064x}.jsonl").exists())
        self.assertFalse((zk / "operations" / f"{101:064x}.jsonl").exists())
        self.assertTrue((zk / "private" / "version-update-terminal" / ".handoff.guard").exists())
        bootstrap = sorted(path.name[:15] for path in (self.local / "WOM").iterdir())
        self.assertEqual(bootstrap, ["bootstrap-v0440", "bootstrap-v0454", "bootstrap-v0455", "notes.txt"])
        self.assertTrue((self.temp / "someone-else.tmp").exists())
        self.assertTrue((self.temp / "wom-git-backup-young.index").exists())
        self.assertFalse((self.temp / "wom-git-backup-abc.index").exists())
        self.assertTrue((self.archive / "receipts" / "keep.json").exists())
        receipt = json.loads((self.archive / result["receipt_relative_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["bytes_freed"], result["bytes_freed"])
        again = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertEqual(again["blockers"], ["system_cleanup_nothing_to_delete"])

    def test_a_changed_plan_is_refused_without_effects(self):
        self.build()
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        _touch(self.temp / "wom-comctl32-v6-new.manifest", age=5 * DAY)
        with self.assertRaises(cleanup.SystemCleanupError) as caught:
            cleanup.approve_system_cleanup(self.archive, expected_plan_sha256=plan["plan_sha256"],
                                           reviewed_by="person:synthetic", now=NOW)
        self.assertEqual(caught.exception.code, "system_cleanup_plan_changed")
        self.assertTrue((self.project / ".zettel-kasten" / "runtimes" / "v0.4.52").exists())

    def test_an_update_in_progress_or_a_pending_delivery_keeps_project_items(self):
        self.build()
        zk = self.project / ".zettel-kasten"
        _touch(zk / "version-update.lock", age=60)
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertEqual(plan["categories"]["old_runtimes"]["count"], 0)
        self.assertEqual(plan["categories"]["operation_journals"]["count"], 0)
        self.assertIn("project_update_in_progress_project_items_kept", plan["kept_notes"])
        (zk / "version-update.lock").unlink()
        _touch(zk / "private" / "version-update-terminal" / "display-pending.json", age=60)
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertEqual(plan["categories"]["update_results"]["count"], 0)
        self.assertEqual(plan["categories"]["update_handoff_capsules"]["count"], 0)
        self.assertEqual(plan["categories"]["old_runtimes"]["count"], 1)
        self.assertIn("update_result_delivery_pending_results_kept", plan["kept_notes"])

    def test_the_automatic_prune_after_an_update_touches_only_project_items(self):
        self.build()
        summary = cleanup.auto_prune_after_update(self.project, now=NOW)
        self.assertEqual(summary["deleted"]["old_runtimes"]["count"], 1)
        self.assertEqual(summary["deleted"]["update_results"]["count"], 4)
        self.assertEqual(len(list((self.local / "WOM").iterdir())), 8)
        self.assertTrue((self.temp / "wom-git-backup-abc.index").exists())
        self.assertTrue((self.archive / ".wom-scratch" / "diagnostics" / f"{6:032x}.json").exists())

    def test_the_running_interpreter_and_an_unreadable_pin_are_never_deleted(self):
        self.build()
        (self.project / ".zettel-kasten" / "installed-version.txt").write_text("garbage", encoding="utf-8")
        plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertEqual(plan["categories"]["old_runtimes"]["count"], 0)
        self.assertEqual(plan["categories"]["bootstrap_environments"]["count"], 0)
        self.assertIn("project_pin_unreadable_runtimes_kept", plan["kept_notes"])
        (self.project / ".zettel-kasten" / "installed-version.txt").write_text("v0.4.54\n", encoding="utf-8")
        running = self.project / ".zettel-kasten" / "runtimes" / "v0.4.52"
        with patch.object(cleanup, "_running_prefixes", return_value=[running.resolve()]):
            plan = cleanup.plan_system_cleanup(self.archive, now=NOW)
        self.assertEqual(plan["categories"]["old_runtimes"]["count"], 0)


class SystemCleanupCliTests(unittest.TestCase):
    """Borrows the v0.4.33 CLI fixture (fake dialog) without its tests."""

    for _name, _value in vars(_upload_fixture.UploadCliTests).items():
        if not _name.startswith("test") and _name not in {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__"}:
            locals()[_name] = _value
    del _name, _value

    def test_dry_run_and_one_dialog_approve(self):
        root = self.archive.root
        for index in range(7):
            _touch(root / ".wom-scratch" / "diagnostics" / f"{index:032x}.json", age=(10 + index) * DAY)
        with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "no-local")}):
            code, plan = self.run_cli("system-cleanup", str(root), "--dry-run")
            self.assertEqual(code, 0, plan)
            self.assertEqual(plan["categories"]["archive_results"]["count"], 2)
            self.assertEqual(self.native.calls, 0)
            code, result = self.run_cli("system-cleanup", str(root), "--approve", "--reviewed-by", _upload_fixture.REVIEWER,
                                        "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["deleted"]["archive_results"]["count"], 2)
        self.assertNotIn(str(root), "".join(self.outputs))

    def test_the_cleanup_kind_is_grantable_and_its_copy_is_korean(self):
        from wom_kit import exact_human_approval_windows as windows
        kind = ExactHumanApprovalOperation.system_cleanup
        self.assertIn(kind, permission.GRANTABLE_OPERATIONS)
        for table in (windows._OPERATION_LABELS, windows._OPERATION_QUESTIONS, windows._OPERATION_SUMMARIES,
                      windows._OPERATION_APPROVE_BUTTONS):
            self.assertIn(kind, table)
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))


if __name__ == "__main__":
    unittest.main()
