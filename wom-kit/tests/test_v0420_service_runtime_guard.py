"""Non-CLI caller origin never substitutes for actual loaded core CLI origin."""

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from wom_kit import project_runtime as subject
import test_project_runtime as fixture


class ServiceRuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-service-runtime-")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "project"
        self.runtime, self.executable, self.module = fixture._write_receipt_bound_runtime(self.project)
        self.service = self.module.with_name("work_session_service.py")
        self.service.write_bytes(b"# synthetic receipt-bound service\n")
        receipt_path = self.runtime / subject.PROJECT_RUNTIME_RECEIPT_NAME
        receipt = json.loads(receipt_path.read_bytes())
        receipt["installed_payload_sha256"] = "sha256:" + subject._runtime_payload_sha256(self.runtime)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.archive = self.project / "archive"
        self.archive.mkdir()
        (self.archive / "archive.yml").write_text("archive_id: archive:synthetic:service\n", encoding="utf-8")
        launcher = self.project / subject.PROJECT_RUNTIME_LAUNCHER_RELATIVE
        launcher.parent.mkdir(parents=True)
        launcher.write_bytes(subject.launcher_bytes("0.4.3"))
        (self.project / ".zettel-kasten" / "installed-version.txt").write_text("v0.4.3\n", encoding="utf-8")

    def test_default_exact_forwarding_and_explicit_none_use_same_real_verifier(self):
        original = subject.current_project_runtime_binding
        inputs = []

        def bound(project, target, **kwargs):
            inputs.append(dict(kwargs))
            # Represent a synthetic process; file/receipt/core verification
            # itself is real, never replaced with a successful bool/result.
            return original(project, target, **kwargs, running_executable=self.executable,
                running_project_runtime_module_path=self.module,
                running_package_origin_path=self.module.with_name("__init__.py"),
                running_prefix=self.runtime, isolated_mode=True, dont_write_bytecode=True)

        loaded = types.ModuleType("wom_kit.archive_cli")
        loaded.__file__ = str(self.module.with_name("archive_cli.py"))
        unrelated_main = types.ModuleType("__main__")
        with patch.object(subject, "current_project_runtime_binding", new=bound), \
                patch.dict(sys.modules, {"wom_kit.archive_cli": loaded, "__main__": unrelated_main}):
            old = subject.project_write_guard(self.archive, running_version="0.4.3", running_module_path=self.service)
            new = subject.project_write_guard(self.archive, running_version="0.4.3", running_module_path=self.service,
                                               running_archive_cli_module_path=None)
            with patch.dict(sys.modules, {"wom_kit.archive_cli": None}):
                missing = subject.project_write_guard(self.archive, running_version="0.4.3", running_module_path=self.service,
                                                       running_archive_cli_module_path=None)
            loaded.__file__ = str(self.service)
            forged = subject.project_write_guard(self.archive, running_version="0.4.3", running_module_path=self.service,
                                                  running_archive_cli_module_path=None)
        self.assertEqual(inputs[0]["running_archive_cli_module_path"], self.service)
        self.assertIsNone(inputs[1]["running_archive_cli_module_path"])
        self.assertTrue(old["blocked"])
        self.assertFalse(new["blocked"])
        self.assertTrue(missing["blocked"] and forged["blocked"])
        self.assertFalse(missing["core_module_bindings"]["archive_cli"]["observed"])
        self.assertFalse(forged["core_module_bindings"]["archive_cli"]["expected_identity"])
        self.assertNotIn(str(self.project), json.dumps([old, new, missing, forged]))


if __name__ == "__main__":
    unittest.main()
