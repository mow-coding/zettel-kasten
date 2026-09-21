"""Do not publish a mislabeled wheel or partial/failed installed check."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("publish_beta", Path(__file__).resolve().parents[1] / "tools/publish_beta.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class BetaDeliveryEvidenceTests(unittest.TestCase):
    def test_only_bound_success_with_windows_journey_is_publishable(self):
        with tempfile.TemporaryDirectory() as temp:
            wheel = Path(temp) / "wom_kit-0.4.38b1-py3-none-any.whl"
            wheel.write_bytes(b"synthetic wheel bytes")
            source = {"version": "0.4.38b1", "tag": "v0.4.38b1", "base_commit": "a" * 40}
            proof = {"ok": True, "merge_commit": "a" * 40}
            report = {"ok": True, "package_version": source["version"], "wheel_filename": wheel.name,
                      "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                      "installed_v0419_runtime_journey": {"ok": True}}
            self.assertEqual(publisher.validate_inputs(source, proof, report, wheel)["size_bytes"], 21)
            for delta in [{"ok": False}, {"wheel_sha256": "b" * 64}, {"package_version": "0.4.38b2"},
                          {"installed_v0419_runtime_journey": {"state": "not_applicable"}}]:
                with self.subTest(delta=delta), self.assertRaises(ValueError):
                    publisher.validate_inputs(source, proof, {**report, **delta}, wheel)
            with self.assertRaises(ValueError):
                publisher.validate_inputs(source, {**proof, "merge_commit": "b" * 40}, report, wheel)


if __name__ == "__main__":
    unittest.main()
