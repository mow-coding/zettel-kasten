"""Opt-in beta tags live on a generated commit outside main (beta-delivery).

The updater requires the target to be reviewed main code. A generated beta
binding is accepted only when its single parent is on origin/main and every
changed file equals the parent with exactly the generator's substitutions.
Synthetic repositories only; the transformation mirrors tools/prepare_beta_source.py.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from wom_kit import archive_services, project_update_git_runner

BASE, BETA = "0.4.39", "0.4.40b7"
OLD_LOCK = f"wom-kit/project-runtime-supply-lock-v{BASE}.json"
NEW_LOCK = f"wom-kit/project-runtime-supply-lock-v{BETA}.json"


@unittest.skipUnless(shutil.which("git"), "git is required")
class GeneratedBetaBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "mirror"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "beta-test")
        self.git("config", "user.email", "beta-test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        lock = {"schema": "wom-kit/project-runtime-supply-lock/v0.1", "target_tag": f"v{BASE}", "artifacts": []}
        self.lock_bytes = (json.dumps(lock, indent=2) + "\n").encode()
        self.lock_sha = "sha256:" + hashlib.sha256(self.lock_bytes).hexdigest()
        note = b"# stable note\n"
        files = {
            "wom-kit/pyproject.toml": f'[project]\nversion = "{BASE}"\n'.encode(),
            "wom-kit/src/wom_kit/__init__.py": f'__version__ = "{BASE}"\n'.encode(),
            "wom_kit/__init__.py": f'__version__ = "{BASE}"\n'.encode(),
            OLD_LOCK: self.lock_bytes,
            "wom-kit/project-runtime-policy.json": (json.dumps(
                {"schema": "wom-kit/project-runtime-policy/v0.1", "supply_lock": OLD_LOCK, "supply_lock_sha256": self.lock_sha},
                indent=2) + "\n").encode(),
            "wom-kit/src/wom_kit/project_runtime.py": (
                f'POLICY = {{"supply_lock": "{OLD_LOCK}", "supply_lock_sha256": "{self.lock_sha}"}}\nOTHER_PIN = "sha256:{"a" * 64}"\n').encode(),
            f"wom-kit/docs/releases/v{BASE}.md": note,
            f"wom-kit/src/wom_kit/_resources/release-notes/v{BASE}.md": note,
            "wom-kit/src/wom_kit/_resources/resource-manifest.json": self.manifest(BASE, note),
            "wom-kit/src/wom_kit/archive_cli.py": b"print('reviewed code')\n",
        }
        for relative, data in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.git("add", "-A")
        self.git("commit", "-m", "reviewed main")
        self.main = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.main)
        self.runner = project_update_git_runner.TrustedProjectUpdateGitRunner.resolve_preapproval()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True).stdout.decode().strip()

    @staticmethod
    def manifest(version, note):
        return (json.dumps({"schema": "wom-kit/package-resource-manifest/v0.1", "version": version,
                            "source_of_truth": "wom-kit source resource directories", "file_count": 2,
                            "files": [{"source": "templates/a.md", "packaged": "templates/a.md", "bytes": 1, "sha256": "b" * 64},
                                      {"source": f"docs/releases/v{version}.md", "packaged": f"release-notes/v{version}.md",
                                       "bytes": len(note), "sha256": hashlib.sha256(note).hexdigest()}]}, indent=2) + "\n").encode()

    def generate(self, tamper=None):
        """Apply prepare_beta_source's substitutions, optionally one tampering."""
        self.git("checkout", "-q", "--detach", self.main)
        for relative in ("wom-kit/pyproject.toml", "wom-kit/src/wom_kit/__init__.py", "wom_kit/__init__.py"):
            path = self.root / relative
            path.write_bytes(path.read_bytes().replace(f'"{BASE}"'.encode(), f'"{BETA}"'.encode()))
        lock = json.loads(self.lock_bytes)
        lock["target_tag"] = "v" + BETA
        if tamper == "lock":
            lock["artifacts"] = [{"url": "https://example.invalid/evil.whl"}]
        new_lock = (json.dumps(lock, ensure_ascii=True, indent=2) + "\n").encode()
        (self.root / NEW_LOCK).write_bytes(new_lock)
        new_sha = "sha256:" + hashlib.sha256(new_lock).hexdigest()
        (self.root / "wom-kit/project-runtime-policy.json").write_bytes((json.dumps(
            {"schema": "wom-kit/project-runtime-policy/v0.1", "supply_lock": NEW_LOCK, "supply_lock_sha256": new_sha},
            indent=2) + "\n").encode())
        runtime = self.root / "wom-kit/src/wom_kit/project_runtime.py"
        text = runtime.read_bytes().replace(OLD_LOCK.encode(), NEW_LOCK.encode()).replace(self.lock_sha.encode(), new_sha.encode())
        if tamper == "runtime":
            text = text.replace(("a" * 64).encode(), ("c" * 64).encode())
        runtime.write_bytes(text)
        note = f"# WOM-kit v{BETA} opt-in beta\n".encode()
        (self.root / f"wom-kit/docs/releases/v{BETA}.md").write_bytes(note)
        (self.root / f"wom-kit/src/wom_kit/_resources/release-notes/v{BETA}.md").write_bytes(
            note + (b"extra" if tamper == "note" else b""))
        (self.root / f"wom-kit/src/wom_kit/_resources/release-notes/v{BASE}.md").unlink()
        (self.root / "wom-kit/src/wom_kit/_resources/resource-manifest.json").write_bytes(self.manifest(BETA, note))
        if tamper == "code":
            (self.root / "wom-kit/src/wom_kit/archive_cli.py").write_bytes(b"print('unreviewed code')\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"build: prepare v{BETA}")
        commit = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        return commit

    def verify(self, commit):
        return archive_services._wom_kit_generated_beta_binding_verified(self.root, commit, BETA, runner=self.runner)

    def test_exact_generated_binding_on_main_is_accepted(self):
        commit = self.generate()
        self.assertEqual(self.verify(commit), self.main)

    def test_any_extra_change_or_off_main_parent_is_refused(self):
        for tamper in ("code", "runtime", "lock", "note"):
            with self.subTest(tamper=tamper):
                self.assertIsNone(self.verify(self.generate(tamper)))
        # A parent that is not on origin/main (for example an unreviewed branch).
        self.git("checkout", "-q", "-b", "side", self.main)
        (self.root / "wom-kit/src/wom_kit/archive_cli.py").write_bytes(b"print('side')\n")
        self.git("commit", "-q", "-am", "side")
        side = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.main)
        self.main = side
        off_main = self.generate()
        self.assertIsNone(self.verify(off_main))

    def test_stable_target_is_never_treated_as_generated(self):
        commit = self.generate()
        self.assertIsNone(archive_services._wom_kit_generated_beta_binding_verified(
            self.root, commit, "0.4.40", runner=self.runner))


if __name__ == "__main__":
    unittest.main()
