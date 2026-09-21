"""Retained wheel reuse cannot turn stale, failed or different bytes green."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("verify_release_artifact", Path(__file__).resolve().parents[1] / "tools/verify_release_artifact.py")
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)


class ReleaseArtifactReuseTests(unittest.TestCase):
    def test_exact_wheel_and_tree_reuse_rejects_stale_or_failed_proofs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wheel = root / "wom_kit-1.2.3-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("wom_kit-1.2.3.dist-info/METADATA", "Version: 1.2.3\n")
            row = {"name": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "size_bytes": wheel.stat().st_size}
            source = {"schema": "wom-kit/installed-wheel-artifact/v1", "source_tree": "a" * 40,
                      "candidate_commit": "b" * 40, "run_id": "1", "attempt": "2", "wheel": row}
            report = {"ok": True, "package_version": "1.2.3", "wheel_filename": wheel.name,
                      "wheel_sha256": row["sha256"], "installed_v0419_runtime_journey": {"ok": True}}
            (root / "source-proof.json").write_text(json.dumps(source), encoding="utf-8")
            (root / "wheel-check.json").write_text(json.dumps(report), encoding="utf-8")
            run = {"headSha": "b" * 40, "event": "pull_request", "conclusion": "success", "databaseId": 1, "attempt": 2,
                   "jobs": [{"name": name, "conclusion": "success"} for name in ["Required CI", "Installed public entrypoints and workflow gate (Windows py3.12)"]]}
            args = dict(tree="a" * 40, candidate="b" * 40, tag="v1.2.3", run=run)
            self.assertTrue(reuse.validate(root, **args)["ok"])
            for delta in [{"tree": "c" * 40}, {"candidate": "c" * 40}, {"tag": "v1.2.3b1"},
                          {"run": {**run, "attempt": 3}}, {"run": {**run, "conclusion": "failure"}},
                          {"run": {**run, "jobs": []}}]:
                with self.subTest(delta=delta), self.assertRaises(ValueError):
                    reuse.validate(root, **{**args, **delta})
            with wheel.open("ab") as out:
                out.write(b"changed")
            with self.assertRaisesRegex(ValueError, "retained_wheel_bytes_mismatch"):
                reuse.validate(root, **args)


if __name__ == "__main__":
    unittest.main()
