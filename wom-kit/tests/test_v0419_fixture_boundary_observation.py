"""Exact comparison/stage diagnostics never change a real fixture decision."""

import inspect
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import CodeType, SimpleNamespace
import unittest
from unittest.mock import patch

from wom_kit import project_runtime
import test_v0419_runtime_noop as runtime_fixture
import test_v03296_private_metadata_writer_approval as writer_fixture


class FixtureBoundaryObservationTests(unittest.TestCase):
    def test_comparison_registration_is_exact_original_nested_code_and_source_line(self):
        diagnostic = runtime_fixture._RuntimeObservationDiagnostics()
        self.assertIs(type(diagnostic.shape_code), CodeType)
        self.assertIn(diagnostic.shape_code, project_runtime._walk_regular_files.__code__.co_consts)
        lines, first = inspect.getsourcelines(project_runtime._walk_regular_files)
        line = lines[runtime_fixture._DIRECTORY_IDENTITY_COMPARISON_LINE - first].strip()
        self.assertEqual(line, "if _stat_identity(directory_before) != _stat_identity(directory_after):")
        self.assertIn(runtime_fixture._DIRECTORY_IDENTITY_COMPARISON_LINE,
                      {line for _start, _end, line in diagnostic.shape_code.co_lines()})

    def test_real_shape_comparison_reports_only_exact_changed_fields_and_preserves_error(self):
        names = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_file_attributes")
        # Change benign integer identity fields only in the existing before /
        # after comparison. Type/reparse checks and filesystem calls stay real.
        for changed, expected in (("st_dev", "device"), ("st_ino", "inode"),
                                  ("st_mtime_ns", "mtime_ns"), ("st_file_attributes", "attributes")):
            with self.subTest(field=expected), tempfile.TemporaryDirectory(prefix="wom-shape-observation-") as tmp:
                root = Path(tmp)
                (root / "synthetic.txt").write_bytes(b"synthetic bytes")
                original_lstat = Path.lstat
                count = 0

                def observed_lstat(path, *args, **kwargs):
                    nonlocal count
                    value = original_lstat(path, *args, **kwargs)
                    if path == root:
                        count += 1
                        if count == 3:
                            values = {name: getattr(value, name, 0) for name in names}
                            values[changed] += 1
                            return SimpleNamespace(**values)
                    return value

                original_identity = project_runtime._stat_identity
                prior_trace, prior_profile = sys.gettrace(), sys.getprofile()
                with patch.object(Path, "lstat", new=observed_lstat), \
                        runtime_fixture._RuntimeObservationDiagnostics() as diagnostic:
                    with self.assertRaises(project_runtime.ProjectRuntimeError) as caught:
                        project_runtime._runtime_payload_sha256(root)
                self.assertEqual(caught.exception.args, ("project_runtime_tree_changed",))
                fields = [event["changed_identity_fields"] for event in diagnostic.snapshot()["events"]
                          if "changed_identity_fields" in event]
                self.assertEqual(fields, [[expected]])
                self.assertEqual(count, 3)
                self.assertIs(project_runtime._stat_identity, original_identity)
                self.assertIsNone(diagnostic.identity_pair)
                self.assertIs(sys.gettrace(), prior_trace)
                self.assertIs(sys.getprofile(), prior_profile)
                self.assertNotIn(str(root), json.dumps(diagnostic.snapshot()))
                self.assertNotIn("synthetic.txt", json.dumps(diagnostic.snapshot()))

    def test_identity_wrapper_forwards_once_and_never_compares_unrelated_calls(self):
        diagnostic = runtime_fixture._RuntimeObservationDiagnostics()
        diagnostic.owner_thread = threading.get_ident()
        diagnostic.active_boundaries.append("payload_inventory")
        result = (1, 2, 3, 4, 5, 6)
        calls = []

        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return result

        wrapper = diagnostic._wrap_directory_identity(original)
        self.assertIs(wrapper("private_marker", flag=True), result)
        self.assertEqual(calls, [(("private_marker",), {"flag": True})])
        self.assertEqual(diagnostic.snapshot()["events"], [])
        error = OSError("private_exception_marker")

        def failing():
            raise error

        with self.assertRaises(OSError) as caught:
            diagnostic._wrap_directory_identity(failing)()
        self.assertIs(caught.exception, error)
        self.assertIsNone(diagnostic.identity_pair)
        self.assertEqual(diagnostic.snapshot()["events"], [])

    def test_invalid_comparison_tuple_cannot_become_an_identity_diagnostic(self):
        with tempfile.TemporaryDirectory(prefix="wom-shape-type-") as tmp:
            original = project_runtime._stat_identity

            def malformed(value):
                result = original(value)
                return tuple(True if index == 0 else item for index, item in enumerate(result))

            with patch.object(project_runtime, "_stat_identity", new=malformed), \
                    runtime_fixture._RuntimeObservationDiagnostics() as diagnostic:
                project_runtime._runtime_payload_sha256(Path(tmp))
            self.assertFalse(any("changed_identity_fields" in event for event in diagnostic.snapshot()["events"]))

    def test_other_thread_identity_error_cannot_consume_owner_comparison(self):
        diagnostic = runtime_fixture._RuntimeObservationDiagnostics()
        diagnostic.owner_thread = threading.get_ident()
        diagnostic.active_boundaries.append("payload_inventory")
        original_pair = (123, (1, 2, 3, 4, 5, 6))
        diagnostic.identity_pair = original_pair
        error = OSError("private_other_thread_marker")
        caught = []

        def original():
            raise error

        def other():
            try:
                diagnostic._wrap_directory_identity(original)()
            except OSError as observed:
                caught.append(observed)

        worker = threading.Thread(target=other)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(caught, [error])
        self.assertIs(diagnostic.identity_pair, original_pair)
        self.assertEqual(diagnostic.snapshot()["events"], [])

    def test_stage_parser_accepts_only_bounded_monotonic_literal_prefix(self):
        def event(stage, elapsed):
            return json.dumps({"schema": writer_fixture._INTERRUPTION_STAGE_SCHEMA,
                               "stage": stage, "elapsed_ms": elapsed})

        lines = [event(stage, index * 100) for index, stage in enumerate(writer_fixture._INTERRUPTION_STAGES)]
        result = writer_fixture._interruption_stage_observation("\n".join(lines))
        self.assertEqual(result["last_stage"], "checkpoint")
        self.assertFalse(result["protocol_invalid"])
        self.assertTrue(result["product_completion_unknown"])
        for tail in ("private_secret_marker", event("private_secret_marker", 10), event("import_done", True),
                     event("import_done", -1), event("import_done", 80001), event("checkpoint", 1),
                     '{"schema":"private_secret_marker","stage":"import_done","elapsed_ms":1}',
                     event("import_done", 2)[:-1] + ',"private_secret_marker":true}',
                     event("import_done", 2)[:-1] + ',"elapsed_ms":3}'):
            with self.subTest(tail_kind=type(tail).__name__):
                rejected = writer_fixture._interruption_stage_observation(lines[0] + "\n" + tail)
                self.assertTrue(rejected["protocol_invalid"])
                self.assertEqual(rejected["events"], [{"stage": "import_start", "elapsed_ms": 0}])
                self.assertNotIn("private", json.dumps(rejected))
        for malformed in (None, b"private_secret_marker", "x" * 4097):
            with self.subTest(kind=type(malformed).__name__):
                rejected = writer_fixture._interruption_stage_observation(malformed)
                self.assertTrue(rejected["protocol_invalid"])
                self.assertEqual(rejected["last_stage"], "not_started")
        extra = writer_fixture._interruption_stage_observation("\n".join(lines) + "\nprivate_secret_marker")
        self.assertTrue(extra["protocol_invalid"])
        self.assertEqual(extra["events"], result["events"])

    def test_child_stage_literals_readiness_order_and_writer_deadline_remain_bounded(self):
        source = inspect.getsource(writer_fixture.PrivateMetadataWriterApprovalTests._interrupt_approval_at)
        budget_source = inspect.getsource(writer_fixture._InterruptionBudget)
        self.assertIn("launched_at + 60, launched_at + 80", budget_source)
        self.assertIn("min(now + 20, self.absolute_deadline)", budget_source)
        self.assertLess(source.index("budget = _InterruptionBudget(time.monotonic())"), source.index("process = subprocess.Popen("))
        self.assertIn("time.sleep(300)", source)
        self.assertIn("process.kill()", source)
        self.assertIn("return self._fresh_process_dry_run()", source)
        for stage in writer_fixture._INTERRUPTION_STAGES:
            self.assertEqual(source.count('test_stage("' + stage + '")'), 1)
        self.assertLess(source.index('test_stage("import_start")'), source.index("from wom_kit import archive_services"))
        self.assertLess(source.index('test_stage("import_done")'), source.index('test_stage("writer_start")'))
        self.assertLess(source.index('ready_pending.open("xb")'), source.index("os.link(ready_pending, ready)"))
        self.assertLess(source.index("os.fsync(stream.fileno())"), source.index("os.link(ready_pending, ready)"))
        self.assertLess(source.index("os.link(ready_pending, ready)"), source.index('test_stage("writer_start")'))
        self.assertLess(source.index('test_stage("writer_start")'), source.index("archive_services._private_objet_source_metadata_write_legacy_core("))

    def test_phase_budget_without_ready_and_early_exit_are_terminal(self):
        budget = writer_fixture._InterruptionBudget(100.0)
        args = dict(ready_state="absent", ready_identity=None, checkpoint_present=False)
        self.assertEqual(budget.observe(now=159.999, **args), "waiting_startup")
        with self.assertRaisesRegex(ValueError, "^interruption_startup_timeout$"):
            budget.observe(now=160.0, **args)
        fresh = writer_fixture._InterruptionBudget(100.0)
        with self.assertRaisesRegex(ValueError, "^interruption_child_exited$"):
            fresh.observe(now=101.0, child_exited=True, **args)

    def test_phase_budget_ready_and_immediate_checkpoint_same_poll_obey_child_order(self):
        identity = (1, 2, 3, 4, 5, 6)
        budget = writer_fixture._InterruptionBudget(0.0)
        self.assertEqual(budget.observe(now=18.0, ready_state="valid", ready_identity=identity,
                                       checkpoint_present=True), "checkpoint")
        self.assertEqual(budget.writer_deadline, 38.0)
        fresh = writer_fixture._InterruptionBudget(0.0)
        with self.assertRaisesRegex(ValueError, "^interruption_ready_order_invalid$"):
            fresh.observe(now=18.0, ready_state="absent", ready_identity=None, checkpoint_present=True)

    def test_phase_budget_malformed_late_or_replaced_readiness_never_starts_or_resets(self):
        identity = (1, 2, 3, 4, 5, 6)
        for state, observed in (("invalid", None), ("private_marker", identity), ([], identity),
                                ("valid", (True, 2, 3, 4, 5, 6)), ("valid", [1, 2, 3, 4, 5, 6])):
            with self.subTest(state_kind=type(state).__name__):
                budget = writer_fixture._InterruptionBudget(0.0)
                with self.assertRaisesRegex(ValueError, "^interruption_ready_invalid$"):
                    budget.observe(now=1.0, ready_state=state, ready_identity=observed, checkpoint_present=False)
                self.assertIsNone(budget.writer_deadline)
        late = writer_fixture._InterruptionBudget(0.0)
        with self.assertRaisesRegex(ValueError, "^interruption_startup_timeout$"):
            late.observe(now=60.001, ready_state="valid", ready_identity=identity, checkpoint_present=True)
        self.assertIsNone(late.writer_deadline)
        budget = writer_fixture._InterruptionBudget(0.0)
        budget.observe(now=10.0, ready_state="valid", ready_identity=identity, checkpoint_present=False)
        for now in (11.0, 12.0, 29.999):
            self.assertEqual(budget.observe(now=now, ready_state="valid", ready_identity=identity,
                                           checkpoint_present=False), "waiting_checkpoint")
            self.assertEqual(budget.writer_deadline, 30.0)
        with self.assertRaisesRegex(ValueError, "^interruption_ready_changed$"):
            budget.observe(now=29.999, ready_state="valid", ready_identity=(1, 7, 3, 4, 5, 6), checkpoint_present=True)
        self.assertEqual(budget.writer_deadline, 30.0)

    def test_phase_budget_writer_deadline_and_absolute_cap_reject_late_checkpoint(self):
        args = dict(ready_state="valid", ready_identity=(1, 2, 3, 4, 5, 6))
        budget = writer_fixture._InterruptionBudget(0.0)
        budget.observe(now=17.0, checkpoint_present=False, **args)
        with self.assertRaisesRegex(ValueError, "^interruption_checkpoint_timeout$"):
            budget.observe(now=37.0, checkpoint_present=True, **args)
        late = writer_fixture._InterruptionBudget(100.0)
        late.observe(now=159.999, checkpoint_present=False, **args)
        self.assertLessEqual(late.writer_deadline, 180.0)
        with self.assertRaisesRegex(ValueError, "^interruption_absolute_timeout$"):
            late.observe(now=180.0, checkpoint_present=True, **args)
        no_ready = writer_fixture._InterruptionBudget(100.0)
        with self.assertRaisesRegex(ValueError, "^interruption_absolute_timeout$"):
            no_ready.observe(now=180.001, ready_state="absent", ready_identity=None, checkpoint_present=False)

    def test_phase_budget_clock_is_monotonic_finite_and_not_bool(self):
        for now in (True, float("nan"), float("inf"), -1.0, "private_marker"):
            with self.subTest(kind=type(now).__name__):
                budget = writer_fixture._InterruptionBudget(0.0)
                with self.assertRaisesRegex(ValueError, "^interruption_clock_invalid$"):
                    budget.observe(now=now, ready_state="absent", ready_identity=None, checkpoint_present=False)

    def test_ready_snapshot_rejects_partial_wrong_and_changed_bytes_without_echo(self):
        with tempfile.TemporaryDirectory(prefix="wom-ready-observation-") as tmp:
            ready = Path(tmp) / "fixture.ready"
            self.assertEqual(writer_fixture._interruption_ready_snapshot(ready), ("absent", None))
            for content in (b"", b"wom-test", b"private_marker", writer_fixture._INTERRUPTION_READY_BYTES + b"x"):
                with self.subTest(size=len(content)):
                    ready.write_bytes(content)
                    self.assertEqual(writer_fixture._interruption_ready_snapshot(ready), ("invalid", None))
            ready.write_bytes(writer_fixture._INTERRUPTION_READY_BYTES)
            state, identity = writer_fixture._interruption_ready_snapshot(ready)
            self.assertEqual(state, "valid")
            self.assertEqual(len(identity), 6)
            original_open = Path.open

            def changed(path, *args, **kwargs):
                if path == ready:
                    original_open(path, "wb").close()
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", new=changed):
                self.assertEqual(writer_fixture._interruption_ready_snapshot(ready), ("invalid", None))


if __name__ == "__main__":
    unittest.main()
