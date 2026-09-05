"""Forward existing field-level failures without copying compared values."""

from copy import deepcopy
import json
import unittest

import test_v0419_installed_runtime_failure_observation as existing
from wom_kit import archive_services as services


driver, checker = existing.driver, existing.checker


class PreparationFailureObservationTests(unittest.TestCase):
    def envelope(self, revalidation=None):
        result = {"project_runtime": {"preparation_revalidation": revalidation}} if revalidation is not None else {}
        result["blockers"] = ["project_version_update_state_changed_during_runtime_preparation", "SYNTHETIC_PRIVATE_TOKEN"]
        original = deepcopy(result)
        payload = driver.FirstUpdateObservation().failure_payload(native_observed=False, cli_code=1, cli_result=result)
        self.assertEqual(result, original)
        return {"ok": False, "schema": driver.SCHEMA, "reason_code": "public_update_failed", "failure_observation": payload}

    def test_each_real_product_check_retains_its_state_with_no_compared_values(self):
        self.assertEqual(driver.PREPARATION_CHECKS, services.WOM_KIT_PROJECT_UPDATE_RUNTIME_PREPARATION_CHECKS)
        for name in driver.PREPARATION_CHECKS:
            for state in driver.PREPARATION_STATES:
                with self.subTest(name=name, state=state):
                    observations = {key: ("passed", "SYNTHETIC_PRIVATE_TOKEN") for key in driver.PREPARATION_CHECKS}
                    observations[name] = state, "SYNTHETIC_PRIVATE_TOKEN"
                    value = services.wom_kit_project_update_runtime_preparation_revalidation(observations)
                    value["checks"][name]["compared_value"] = "SYNTHETIC_PRIVATE_TOKEN"
                    envelope = self.envelope(value)
                    raw = json.dumps(envelope)
                    parsed = checker._parse_runtime_failure_output(raw)["failure_observation"]
                    self.assertEqual(parsed["preparation_observation"]["checks"][name], state)
                    self.assertEqual(parsed["cli"]["preparation_revalidation_state"], value["state"])
                    self.assertEqual(parsed["cli"]["reason_codes"],
                        ["project_version_update_state_changed_during_runtime_preparation"])
                    self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", raw)

    def test_legacy_absence_and_unclassified_missing_state_are_not_failed_checks(self):
        legacy = self.envelope()
        self.assertNotIn("preparation_observation", legacy["failure_observation"])
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(legacy)), legacy)
        for supplied in (None, {}, [], {"git_snapshot": {"state": "SYNTHETIC_PRIVATE_TOKEN"}}):
            with self.subTest(supplied=type(supplied).__name__):
                value = self.envelope({"state": "failed", "checks": supplied})
                states = value["failure_observation"]["preparation_observation"]["checks"]
                self.assertEqual(set(states.values()), {"unclassified"})
                self.assertEqual(checker._parse_runtime_failure_output(json.dumps(value)), value)
                self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", json.dumps(value))

    def test_parent_refuses_private_fields_and_impossible_aggregate(self):
        product = services.wom_kit_project_update_runtime_preparation_revalidation(
            {name: ("passed", "verified") for name in driver.PREPARATION_CHECKS})
        original = self.envelope(product)
        cases = []
        for key, value in (("schema", "SYNTHETIC_PRIVATE_TOKEN"), ("extra", "SYNTHETIC_PRIVATE_TOKEN"),
                           ("checks", [])):
            changed = deepcopy(original)
            changed["failure_observation"]["preparation_observation"][key] = value
            cases.append(changed)
        for key, value in (("private_check", "failed"), ("runtime_plan", "SYNTHETIC_PRIVATE_TOKEN"),
                           ("runtime_plan", True), ("runtime_plan", {"state": "passed"}), ("runtime_plan", "failed")):
            changed = deepcopy(original)
            changed["failure_observation"]["preparation_observation"]["checks"][key] = value
            cases.append(changed)
        changed = deepcopy(original)
        del changed["failure_observation"]["preparation_observation"]["checks"]["runtime_plan"]
        cases.append(changed)
        for changed in cases:
            with self.subTest(case=cases.index(changed)):
                with self.assertRaises(checker.WheelCheckError):
                    checker._parse_runtime_failure_output(json.dumps(changed))

    def test_combined_allowed_reason_and_blocker_saturation_keeps_valid_envelope(self):
        codes = sorted(driver.OBSERVED_FAILURE_CODES | driver.FirstUpdateObservation._LITERAL_CODES)
        self.assertGreaterEqual(len(codes), 65)
        product = services.wom_kit_project_update_runtime_preparation_revalidation(
            {name: ("failed" if name == "prepared_runtime_payload" else "passed", "verified")
             for name in driver.PREPARATION_CHECKS})
        original = {"reason_code": codes[0], "reason_codes": codes[1:33], "blockers": codes[33:65],
                    "project_runtime": {"preparation_revalidation": product}}
        payload = driver.FirstUpdateObservation().failure_payload(native_observed=False, cli_code=1, cli_result=original)
        self.assertEqual(len(payload["cli"]["reason_codes"]), 32)
        self.assertEqual(original["reason_codes"], codes[1:33])
        self.assertEqual(payload["preparation_observation"]["checks"]["prepared_runtime_payload"], "failed")
        envelope = {"ok": False, "schema": driver.SCHEMA, "reason_code": "public_update_failed", "failure_observation": payload}
        self.assertEqual(checker._parse_runtime_failure_output(json.dumps(envelope)), envelope)


if __name__ == "__main__":
    unittest.main()
