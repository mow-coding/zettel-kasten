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

    def test_created_draft_uses_response_identity_and_receipt_without_rediscovery(self):
        draft = {'id': 17, 'tag_name': 'v0.4.38b1', 'draft': True, 'prerelease': True, 'assets': []}
        with tempfile.TemporaryDirectory() as temp:
            notes = Path(temp) / 'notes.md'
            notes.write_text('Synthetic beta notes', encoding='utf-8')
            receipt = Path(temp) / 'release-identity.json'
            with patch.object(publisher, 'find_release', return_value=None) as discovery, \
                    patch.object(publisher, 'release_api', return_value=draft) as create:
                self.assertEqual(publisher.obtain_release('synthetic/example', draft['tag_name'], notes, receipt), draft)
                discovery.assert_called_once()
                self.assertEqual(create.call_args.args[3]['make_latest'], 'false')
            with patch.object(publisher, 'find_release', side_effect=AssertionError('no rediscovery')), \
                    patch.object(publisher, 'release_api', side_effect=AssertionError('no recreation')), \
                    patch.object(publisher, 'run', return_value=json.dumps(draft)) as get:
                self.assertEqual(publisher.obtain_release('synthetic/example', draft['tag_name'], notes, receipt), draft)
                get.assert_called_once_with('gh', 'api', 'repos/synthetic/example/releases/17')
            with self.assertRaises(ValueError):
                publisher.obtain_release('synthetic/other', draft['tag_name'], notes, receipt)
            for changed in [{'tag_name': 'v0.4.38b2'}, {'prerelease': False}, {'id': True}]:
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    publisher.release_identity({**draft, **changed}, draft['tag_name'])

    def test_assets_use_numeric_endpoints_and_preserve_binary_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            wheel = Path(temp) / 'synthetic.whl'
            wheel.write_bytes(b'\x00\xffsynthetic')
            with patch.object(publisher, 'run', return_value=json.dumps({'id': 29})) as upload:
                self.assertEqual(publisher.upload_asset('synthetic/example', 17, wheel), {'id': 29})
                self.assertIn('/releases/17/assets?name=synthetic.whl', upload.call_args.args[4])
            def fetch(args, **kwargs):
                self.assertEqual(args[2], 'repos/synthetic/example/releases/assets/29')
                self.assertTrue(kwargs['check'])
                kwargs['stdout'].write(b'\x00\xffsynthetic')
            output = Path(temp) / 'download.whl'
            with patch.object(publisher.subprocess, 'run', side_effect=fetch):
                publisher.download_asset('synthetic/example', {'id': 29}, output)
            self.assertEqual(output.read_bytes(), wheel.read_bytes())

    def test_publication_uses_created_identity_through_upload_verify_and_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            wheel = directory / 'wom_kit-0.4.38b1-py3-none-any.whl'
            wheel.write_bytes(b'synthetic')
            source = {'version': '0.4.38b1', 'tag': 'v0.4.38b1', 'base_commit': 'a' * 40}
            proof = {'ok': True, 'merge_commit': 'a' * 40, 'pull_request': 7}
            check = {'ok': True, 'package_version': source['version'], 'wheel_filename': wheel.name,
                     'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                     'installed_v0419_runtime_journey': {'ok': True}}
            for name, value in [('beta-source', source), ('source-proof', proof), ('wheel-check', check)]:
                (directory / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
            draft = {'id': 17, 'tag_name': source['tag'], 'draft': True, 'prerelease': True, 'assets': []}
            uploaded = {}
            def command(*args):
                self.assertNotEqual(args[:2], ('gh', 'release'))
                if args[:2] == ('git', 'status') or args[:2] == ('git', 'ls-remote'): return ''
                if args == ('git', 'rev-parse', 'HEAD^'): return source['base_commit']
                if args == ('git', 'rev-parse', 'HEAD'): return 'b' * 40
                if args == ('git', 'rev-parse', 'HEAD^{tree}'): return 'c' * 40
                if args[:2] in [('git', 'tag'), ('git', 'push')]: return ''
                if args[:2] == ('gh', 'api'):
                    self.assertTrue(args[-1].endswith('/releases/latest'))
                    return json.dumps({'tag_name': 'v0.4.37'})
                if args[-1] == 'import wom_kit;print(wom_kit.__version__)': return source['version']
                return ''  # synthetic venv and pip commands
            def api(repo, endpoint, method, payload):
                if method == 'POST':
                    self.assertEqual(endpoint, 'releases')
                    return draft
                self.assertEqual((endpoint, method), ('releases/17', 'PATCH'))
                self.assertEqual(len(uploaded), 3)
                return {**draft, 'draft': False}
            def upload(repo, release_id, path):
                self.assertEqual(release_id, 17)
                asset = {'id': len(uploaded) + 1, 'name': path.name}
                uploaded[asset['id']] = path.read_bytes()
                return asset
            def fetch(repo, asset, destination): destination.write_bytes(uploaded[asset['id']])
            def anonymous(url, destination):
                destination.write_bytes(wheel.read_bytes())
                return publisher.artifact_row(destination)
            with patch.object(publisher, 'run', side_effect=command), \
                    patch.object(publisher, 'find_release', return_value=None) as discovery, \
                    patch.object(publisher, 'release_api', side_effect=api), \
                    patch.object(publisher, 'upload_asset', side_effect=upload), \
                    patch.object(publisher, 'download_asset', side_effect=fetch), \
                    patch.object(publisher, 'download', side_effect=anonymous):
                result = publisher.publish('synthetic/example', directory)
                self.assertEqual(result['public_fresh_install'], 'passed')
                self.assertTrue((directory / 'public-verification.json').exists())
                discovery.assert_called_once()

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
