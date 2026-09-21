"""Explicit beta selection must not contaminate stable discovery."""
import json
import unittest
from unittest.mock import Mock, patch

from wom_kit import version_policy as policy, project_runtime as runtime, archive_services as services


class BetaVersionContractTests(unittest.TestCase):
    def test_beta_number_and_stable_order(self):
        labels = ["v0.4.38", "v0.4.38b10", "v0.4.38b2", "v0.4.37"]
        self.assertEqual(sorted(labels, key=services.version_sort_key),
                         ["v0.4.37", "v0.4.38b2", "v0.4.38b10", "v0.4.38"])
        self.assertEqual(services.latest_semver_tag(["v0.4.37", "v0.4.38b100"]), "v0.4.37")
        self.assertIsNone(services.latest_semver_tag(["v0.4.38b100"]))
        self.assertIsNone(policy.stable_version_value("0.4.38b2"))
        self.assertEqual(runtime._version("v0.4.38b2"), "0.4.38b2")

    def test_invalid_beta_aliases_and_untrusted_labels_rejected(self):
        for value in [None, 7, {}, "0.4.38b0", "0.4.38b01", "0.4.38b-1", "0.4.38beta1", "0.4.38b１", "0.4.38b1/../../x", "0.4.38b1+local", "x" * 65]:
            self.assertIsNone(policy.release_version_value(value), value)
            self.assertIsNone(runtime._version(value), value)

    def test_bootstrap_requires_matching_beta_url_and_installed_hash(self):
        version = "0.4.38b2"
        url = f"https://github.com/mow-coding/zettel-kasten/releases/download/v{version}/wom_kit-{version}-py3-none-any.whl"
        distribution = Mock(version=version)
        distribution.read_text.return_value = json.dumps({"url": url, "archive_info": {"hashes": {"sha256": "a" * 64}}})
        with patch.object(runtime.importlib.metadata, "distribution", return_value=distribution):
            wheel, report = runtime.bootstrap_wheel_for_target("v" + version)
            self.assertTrue(report["available"])
            self.assertEqual(wheel.version, version)
            self.assertEqual(wheel.tag, "v" + version)
            self.assertIsNone(runtime.bootstrap_wheel_for_target("v0.4.38b3")[0])
            distribution.read_text.return_value = json.dumps({"url": url, "archive_info": {}})
            self.assertIsNone(runtime.bootstrap_wheel_for_target("v" + version)[0])

    def test_beta_runtime_path_is_unique(self):
        self.assertEqual(runtime.runtime_logical_path("v0.4.38b2"), ".zettel-kasten/runtimes/v0.4.38b2")
        self.assertNotEqual(runtime.runtime_logical_path("v0.4.38b2"), runtime.runtime_logical_path("v0.4.38"))
        self.assertIn(b"v0.4.38b2", runtime.launcher_bytes("v0.4.38b2"))
        self.assertIn(b"wom_kit.cli_entry", runtime.launcher_bytes("v0.4.38b2"))


if __name__ == "__main__":
    unittest.main()
