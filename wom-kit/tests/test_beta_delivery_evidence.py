"""Do not publish a mislabeled wheel or partial/failed installed check."""
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("publish_beta", Path(__file__).resolve().parents[1] / "tools/publish_beta.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class BetaDeliveryEvidenceTests(unittest.TestCase):
    def test_draft_discovery_does_not_use_public_tag_endpoint(self):
        draft = {'id': 17, 'tag_name': 'v0.4.38b1', 'draft': True}
        def api(*args):
            if '/releases/tags/' in args[-1]:
                raise RuntimeError('404 for unpublished draft')
            return json.dumps([[{'id': 16, 'tag_name': 'v0.4.37'}], [draft]])
        with patch.object(publisher, 'run', side_effect=api):
            self.assertEqual(publisher.find_release('synthetic/example', 'v0.4.38b1'), draft)
        with patch.object(publisher, 'run', return_value=json.dumps([[draft, draft]])):
            with self.assertRaises(ValueError): publisher.find_release('synthetic/example', 'v0.4.38b1')
        with patch.object(publisher, 'run', side_effect=RuntimeError('network failure')):
            with self.assertRaises(RuntimeError): publisher.find_release('synthetic/example', 'v0.4.38b1')

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
