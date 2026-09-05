"""No-build diagnostics of the actual live classifier's fail-closed boundary."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import test_v0419_installed_runtime_failure_observation as existing
from wom_kit import archive_services as services, project_runtime as runtime
from wom_kit import project_update_transaction as transaction


driver, checker = existing.driver, existing.checker


class ComponentFailureObservationTests(unittest.TestCase):
    def exercise(self, fault, *, extra_probes=0):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "SYNTHETIC_PRIVATE_TOKEN"
            path.write_bytes(b"damaged" if fault == "file" else b"before")
            before = path.read_bytes()
            digest = transaction.digest_component(b"before")
            components = tuple(SimpleNamespace(component_ref=name, role=name,
                pre_sha256=digest, post_sha256=digest) for name in ("source", "runtime", "active_pin"))
            expected = {"head": "SYNTHETIC_PRIVATE_TOKEN", "branch": None}
            state = SimpleNamespace(project_root=root, mirror_path=root, runner=None,
                private_plan={"preflight_git_snapshot": expected}, source_pre_sha256=digest,
                source_post_sha256=digest, runtime_pre_sha256=digest, runtime_post_sha256=digest,
                runtime_candidate=SimpleNamespace(existing_runtime_repair_required=fault == "repair"),
                target_version="0.4.19", transaction=SimpleNamespace(intent=SimpleNamespace(components=components),
                    transaction_ref="update_" + "a" * 32),
                component_paths={"active_pin": path})
            current = {**expected, "head": "SYNTHETIC_OTHER_VALUE"} if fault == "source" else dict(expected)
            postimage = {"state": "unavailable" if fault == "runtime" else "failed" if fault == "repair" else "passed",
                         "reason_code": "project_runtime_existing_observation_unavailable" if fault == "runtime" else "verified",
                         "matches": fault not in {"runtime", "repair"}}
            snapshot = {"state": "passed", "reason_code": "verified", "snapshot": current}
            observer = driver.FirstUpdateObservation(stage="repair_fresh_resume")
            subject = object.__new__(transaction.ProjectUpdateTransaction)
            expectations = tuple(transaction.ComponentExpectation(item.component_ref, digest, digest) for item in components)
            profile, trace = sys.getprofile(), sys.gettrace()
            original_live = services._project_update_live_component_sha256
            def live_with_probes(selected):
                for _ in range(extra_probes):
                    services._wom_kit_project_update_git_snapshot_observation(selected.mirror_path, runner=selected.runner)
                return original_live(selected)
            with mock.patch.object(services, "_project_update_live_component_sha256", new=live_with_probes), \
                 mock.patch.object(services, "_wom_kit_project_update_git_snapshot_observation", return_value=snapshot) as source, \
                 mock.patch.object(runtime, "_existing_runtime_candidate_observation", return_value=postimage) as candidate, \
                 mock.patch.object(runtime, "runtime_repair_state_observation", return_value={
                     "state": "failed", "reason_code": "project_runtime_repair_state_invalid", "repair_state": "invalid"}) as repair:
                with observer.live_components():
                    live = services._project_update_live_component_sha256(state)
                    classification = transaction.classify_components(expectations, live)
                    self.assertEqual(classification.overall, "unknown")
                    with self.assertRaises(transaction.ProjectUpdateTransactionError) as caught:
                        subject._validate_live_for_event(None, (), classification)
                    self.assertEqual(caught.exception.code, "project_update_transaction_state_transition_invalid")
                self.assertIs(runtime.runtime_repair_state_observation, repair)
                self.assertIs(services._wom_kit_project_update_git_snapshot_observation, source)
                self.assertEqual(source.call_count, 1 + extra_probes)
                candidate.assert_called_once()
                self.assertEqual(repair.call_count, int(fault == "repair"))
            self.assertIs(sys.getprofile(), profile)
            self.assertIs(sys.gettrace(), trace)
            self.assertEqual(path.read_bytes(), before)
            payload = observer.failure_payload(native_observed=False, cli_code=1)
            raw = json.dumps({"ok": False, "schema": driver.SCHEMA, "reason_code": "repair_resume_failed",
                              "failure_observation": payload})
            self.assertEqual(checker._parse_runtime_failure_output(raw)["failure_observation"], payload)
            self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", raw)
            self.assertNotIn("SYNTHETIC_OTHER_VALUE", raw)
            self.assertNotIn(str(root), raw)
            self.assertNotIn(digest, raw)
            self.assertLess(len(raw.encode("utf-8")), 32768)
            return payload

    def test_actual_classifier_distinguishes_four_causes_without_repair_or_writes(self):
        for fault, role in (("source", "source"), ("runtime", "runtime"), ("repair", "runtime"), ("file", "active_pin")):
            with self.subTest(fault=fault):
                events = self.exercise(fault)["component_observation"]["events"]
                self.assertEqual([row["role"] for row in events
                    if row["boundary"] == "classification" and row["state"] == "unknown"], [role])
                if fault == "source":
                    self.assertEqual(next(row for row in events if row["boundary"] == "source")["changed_source_fields"], ["head"])
                if fault == "file":
                    file_row = next(row for row in events if row["boundary"] == "file")
                    self.assertEqual(file_row["state"], "passed")  # Actual bytes differ, not an invented read error.

    def test_optional_contract_rejects_private_unknown_and_unbounded_fields(self):
        value = self.exercise("source")
        for field, invalid in (("role", "SYNTHETIC_PRIVATE_TOKEN"), ("state", True),
                               ("reason_code", "SYNTHETIC_PRIVATE_TOKEN"),
                               ("boundary", "SYNTHETIC_PRIVATE_TOKEN"),
                               ("changed_source_fields", ["SYNTHETIC_PRIVATE_TOKEN"])):
            with self.subTest(field=field):
                altered = deepcopy(value)
                altered["component_observation"]["events"][0][field] = invalid
                with self.assertRaises(driver.JourneyCheckError):
                    driver.validate_first_update_observation(altered)
        for events in ([], value["component_observation"]["events"] * 33):
            altered = deepcopy(value)
            altered["component_observation"]["events"] = events
            with self.assertRaises(driver.JourneyCheckError):
                driver.validate_first_update_observation(altered)
        original = driver.FirstUpdateObservation().failure_payload(native_observed=False, cli_code=1)
        self.assertNotIn("component_observation", original)

    def test_decisive_classification_is_preserved_when_probe_capacity_is_full(self):
        events = self.exercise("source", extra_probes=40)["component_observation"]["events"]
        self.assertEqual(len(events), 32)
        self.assertEqual(events[0]["boundary"], "classification")
        self.assertEqual((events[0]["role"], events[0]["state"]), ("source", "unknown"))
        self.assertEqual(len([row for row in events if row["boundary"] == "classification"]), 3)

    def test_parser_rejects_individually_known_but_impossible_combinations(self):
        value = self.exercise("source")
        valid = {"boundary": "source", "role": "source", "state": "passed",
                 "reason_code": "verified", "changed_source_fields": ["head"]}
        combinations = (
            {"boundary": "classification"}, {"role": "runtime"},
            {"boundary": "runtime", "role": "runtime"},
            {"boundary": "file", "role": "runtime", "changed_source_fields": []},
            {"reason_code": "project_runtime_existing_payload_mismatch"},
            {"state": "unavailable", "reason_code": "project_git_snapshot_unavailable"},
            {"state": "exception", "changed_source_fields": []},
            {"state": "failed", "reason_code": "project_git_snapshot_unavailable", "changed_source_fields": []},
        )
        for overrides in combinations:
            with self.subTest(overrides=overrides):
                altered = deepcopy(value)
                altered["component_observation"]["events"] = [{**valid, **overrides}]
                with self.assertRaises(checker.WheelCheckError):
                    checker._parse_runtime_failure_output(json.dumps({"ok": False, "schema": driver.SCHEMA,
                        "reason_code": "repair_resume_failed", "failure_observation": altered}))

    def test_original_exception_result_and_wrappers_are_restored_without_retry(self):
        supplied, returned = object(), object()
        error = OSError("SYNTHETIC_PRIVATE_TOKEN")
        for fail in (False, True):
            with self.subTest(fail=fail):
                calls = []
                def original(state):
                    calls.append(state)
                    if fail:
                        raise error
                    return returned
                observer = driver.FirstUpdateObservation()
                with mock.patch.object(services, "_project_update_live_component_sha256", new=original):
                    with observer.live_components():
                        if fail:
                            with self.assertRaises(OSError) as caught:
                                services._project_update_live_component_sha256(supplied)
                            self.assertIs(caught.exception, error)
                        else:
                            self.assertIs(services._project_update_live_component_sha256(supplied), returned)
                    self.assertIs(services._project_update_live_component_sha256, original)
                self.assertEqual(calls, [supplied])
                self.assertIsNone(observer.component_observation)

    def test_unrelated_classifier_and_other_thread_never_borrow_a_sample(self):
        observer = driver.FirstUpdateObservation()
        subject = object.__new__(transaction.ProjectUpdateTransaction)
        expectation = transaction.ComponentExpectation("runtime", "sha256:" + "a" * 64, "sha256:" + "a" * 64)
        supplied = {"runtime": "sha256:" + "b" * 64}
        errors = []
        def other_thread():
            classification = transaction.classify_components((expectation,), supplied)
            try:
                subject._validate_live_for_event(None, (), classification)
            except transaction.ProjectUpdateTransactionError as error:
                errors.append(error.code)
        with observer.live_components():
            worker = threading.Thread(target=other_thread)
            worker.start()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            other_thread()  # Same thread, but no original live-component result.
        self.assertEqual(errors, ["project_update_transaction_state_transition_invalid"] * 2)
        self.assertIsNone(observer.component_observation)


if __name__ == "__main__":
    unittest.main()
