from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
SOURCE_PACKAGE = (KIT_ROOT / "src" / "wom_kit").resolve()


class RootSourceCheckoutShimTests(unittest.TestCase):
    def test_root_shim_prefers_this_checkout_over_external_namespace_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            poison_root = Path(tmp)
            poison_package = poison_root / "wom_kit"
            poison_package.mkdir()
            (poison_package / "archive_cli.py").write_text(
                "raise RuntimeError('external namespace archive_cli imported')\n",
                encoding="utf-8",
            )
            (poison_package / "archive_services.py").write_text(
                "raise RuntimeError('external namespace archive_services imported')\n",
                encoding="utf-8",
            )
            child_env = os.environ.copy()
            child_env["PYTHONPATH"] = str(poison_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import json, pathlib, wom_kit, "
                        "wom_kit.archive_cli, wom_kit.archive_services; "
                        "print(json.dumps({"
                        "'version': wom_kit.__version__, "
                        "'paths': list(wom_kit.__path__), "
                        "'archive_cli': str(pathlib.Path("
                        "wom_kit.archive_cli.__file__).resolve()), "
                        "'archive_services': str(pathlib.Path("
                        "wom_kit.archive_services.__file__).resolve())"
                        "}, sort_keys=True))"
                    ),
                ],
                cwd=REPO_ROOT,
                env=child_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)

        self.assertEqual(payload["version"], "0.3.307")
        self.assertEqual(Path(payload["paths"][0]).resolve(), SOURCE_PACKAGE)
        self.assertEqual(
            Path(payload["archive_cli"]).resolve().parent,
            SOURCE_PACKAGE,
        )
        self.assertEqual(
            Path(payload["archive_services"]).resolve().parent,
            SOURCE_PACKAGE,
        )


if __name__ == "__main__":
    unittest.main()
