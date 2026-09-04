from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import project_runtime


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_receipt_bound_runtime(
    project: Path,
    *,
    version: str = "0.4.3",
) -> tuple[Path, Path, Path]:
    """Create one tiny cross-platform runtime image with an exact receipt."""

    runtime = project_runtime.runtime_path(project, version)
    executable = runtime / "Scripts" / "python.exe"
    module = runtime / "Lib" / "site-packages" / "wom_kit" / "project_runtime.py"
    archive_cli_module = module.with_name("archive_cli.py")
    package_origin = module.with_name("__init__.py")
    executable.parent.mkdir(parents=True, exist_ok=True)
    module.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"synthetic-python\n")
    module.write_bytes(b"# receipt-bound WOM module\n")
    archive_cli_module.write_bytes(b"# receipt-bound WOM CLI module\n")
    package_origin.write_bytes(f'__version__ = "{version}"\n'.encode("utf-8"))
    payload_sha256 = project_runtime._runtime_payload_sha256(runtime)
    verification = {
        "wheel_sha256": True,
        "pip_check": True,
        "version": True,
        "package_resources": True,
        "new_process": True,
        "supply_lock": True,
        "artifact_hashes": True,
        "artifact_sizes": True,
        "artifact_inventory": True,
        "installed_payload": True,
        "live_process": True,
    }
    receipt = {
        "schema": project_runtime.PROJECT_RUNTIME_RECEIPT_SCHEMA,
        "status": "verified",
        "created_at": "2026-08-27T00:00:00Z",
        "target_tag": f"v{version}",
        "target_version": version,
        "target_commit": "b" * 40,
        "wheel_file_name": f"wom_kit-{version}-py3-none-any.whl",
        "wheel_sha256": "sha256:" + "a" * 64,
        "supply_lock_sha256": "sha256:" + "c" * 64,
        "artifact_inventory": [
            {
                "role": "runtime",
                "distribution": "wom-kit",
                "version": version,
                "file_name": f"wom_kit-{version}-py3-none-any.whl",
                "size_bytes": 1,
                "sha256": "sha256:" + "a" * 64,
            },
            {
                "role": "dependency",
                "distribution": "synthetic-dependency",
                "version": "1.2.3",
                "file_name": "synthetic_dependency-1.2.3-cp312-cp312-win_amd64.whl",
                "size_bytes": 1,
                "sha256": "sha256:" + "d" * 64,
            },
        ],
        "installed_payload_sha256": "sha256:" + payload_sha256,
        "python_version": "3.12.0",
        "installer_running_version": version,
        "installed_distributions": [
            {"name": "wom-kit", "version": version},
            {"name": "synthetic-dependency", "version": "1.2.3"},
        ],
        "verification": verification,
        "global_path_mutation": False,
        "previous_runtime_deleted": False,
        "absolute_paths_echoed": False,
    }
    receipt_path = runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
    receipt_path.write_bytes(
        (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return runtime, executable, module


def _write_minimal_wheel(destination: Path, version: str) -> Path:
    wheel_name = f"wom_kit-{version}-py3-none-any.whl"
    wheel_path = destination / wheel_name
    dist_info = f"wom_kit-{version}.dist-info"
    manifest = {
        "schema": "wom-kit/package-resource-manifest/v0.1",
        "version": version,
        "source_of_truth": "synthetic project-runtime test",
        "file_count": 1,
        "files": [],
    }
    release_note = f"WOM-kit v{version}\n".encode("utf-8")
    manifest["files"].append(
        {
            "source": f"docs/releases/v{version}.md",
            "packaged": f"release-notes/v{version}.md",
            "bytes": len(release_note),
            "sha256": hashlib.sha256(release_note).hexdigest(),
        }
    )
    files = {
        "wom_kit/__init__.py": f'__version__ = "{version}"\n'.encode(),
        "wom_kit/archive_cli.py": (
            "import sys\n"
            f"VERSION = {version!r}\n"
            "def main():\n"
            "    if '--version' in sys.argv:\n"
            "        print('archive ' + VERSION)\n"
            "        return 0\n"
            "    return 0\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n"
        ).encode(),
        "wom_kit/resource_paths.py": (
            "import json\n"
            "from pathlib import Path\n"
            "PACKAGED_RESOURCES_ROOT = Path(__file__).resolve().parent / '_resources'\n"
            "def packaged_resource_manifest():\n"
            "    return json.loads((PACKAGED_RESOURCES_ROOT / 'resource-manifest.json').read_text(encoding='utf-8'))\n"
        ).encode(),
        "wom_kit/_resources/resource-manifest.json": (
            json.dumps(manifest, separators=(",", ":")) + "\n"
        ).encode(),
        f"wom_kit/_resources/release-notes/v{version}.md": release_note,
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            "Name: wom-kit\n"
            f"Version: {version}\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: wom-kit-test\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode(),
        f"{dist_info}/entry_points.txt": (
            "[console_scripts]\n"
            "archive = wom_kit.archive_cli:main\n"
        ).encode(),
    }
    rows: list[list[str]] = []
    for name, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append([name, f"sha256={digest}", str(len(data))])
    record_name = f"{dist_info}/RECORD"
    rows.append([record_name, "", ""])
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    files[record_name] = buffer.getvalue().encode()
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return wheel_path


def _write_dependency_wheel(
    destination: Path,
    *,
    distribution: str = "Synthetic-Dependency",
    version: str = "1.2.3",
) -> Path:
    normalized = distribution.lower().replace("-", "_")
    wheel_name = f"{normalized}-{version}-cp312-cp312-win_amd64.whl"
    wheel_path = destination / wheel_name
    dist_info = f"{normalized}-{version}.dist-info"
    files = {
        f"{normalized}/__init__.py": f'__version__ = "{version}"\n'.encode(),
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {distribution}\n"
            f"Version: {version}\n"
        ).encode(),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: wom-kit-test\n"
            "Root-Is-Purelib: false\n"
            "Tag: cp312-cp312-win_amd64\n"
        ).encode(),
    }
    rows: list[list[str]] = []
    for name, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append([name, f"sha256={digest}", str(len(data))])
    record_name = f"{dist_info}/RECORD"
    rows.append([record_name, "", ""])
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    files[record_name] = buffer.getvalue().encode()
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return wheel_path


def _supply_for_dependency(
    dependency_wheel: Path,
    *,
    target: str = "v0.4.3",
) -> project_runtime.RuntimeSupplyLock:
    raw = (
        json.dumps(
            {
                "schema": project_runtime.PROJECT_RUNTIME_SUPPLY_LOCK_SCHEMA,
                "target_tag": target,
                "interpreter": {
                    "implementation": "cpython",
                    "python_version": "3.12",
                    "python_tag": "cp312",
                    "abi_tag": "cp312",
                    "platform_tag": "win_amd64",
                },
                "artifacts": [
                    {
                        "role": "dependency",
                        "distribution": "Synthetic-Dependency",
                        "version": "1.2.3",
                        "file_name": dependency_wheel.name,
                        "url": (
                            "https://files.pythonhosted.org/packages/synthetic/"
                            + dependency_wheel.name
                        ),
                        "size_bytes": dependency_wheel.stat().st_size,
                        "sha256": (
                            "sha256:" + hashlib.sha256(dependency_wheel.read_bytes()).hexdigest()
                        ),
                    }
                ],
            },
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    supply = project_runtime.project_runtime_supply_lock(raw, expected_target=target)
    if supply is None:
        raise AssertionError("synthetic supply lock must be valid")
    return supply


class ProjectRuntimeTests(unittest.TestCase):
    def test_official_supply_lock_is_strict_and_hash_bound(self) -> None:
        attributes = (KIT_ROOT.parent / ".gitattributes").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "wom-kit/project-runtime-supply-lock-v*.json text eol=lf",
            attributes.splitlines(),
        )
        raw = (KIT_ROOT / "project-runtime-supply-lock-v0.4.18.json").read_bytes()
        policy = project_runtime.project_runtime_policy_document(
            (KIT_ROOT / "project-runtime-policy.json").read_bytes()
        )
        self.assertIsNotNone(policy)
        assert policy is not None
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.18.json",
        )
        self.assertEqual(
            policy["supply_lock_sha256"],
            "sha256:4be603856000aea49421dd7032b4cabd1ba967a123c17e58e215943fb060186f",
        )
        supply = project_runtime.project_runtime_supply_lock(
            raw,
            expected_target="v0.4.18",
        )
        self.assertIsNotNone(supply)
        assert supply is not None
        self.assertEqual(
            supply.sha256,
            "4be603856000aea49421dd7032b4cabd1ba967a123c17e58e215943fb060186f",
        )
        self.assertEqual(
            [(item.distribution, item.version, item.size_bytes, item.sha256) for item in supply.artifacts],
            [
                (
                    "PyYAML",
                    "6.0.3",
                    154003,
                    "5fcd34e47f6e0b794d17de1b4ff496c00986e1c83f7ab2fb8fcfe9616ff7477b",
                ),
                (
                    "unicodedata2",
                    "17.0.1",
                    484194,
                    "d1439ad3ee0daace878196de4466a86aa5015cb244b9b1d5d00db74344649722",
                ),
            ],
        )
        summary = supply.public_summary()
        self.assertFalse(summary["index_resolution"])
        self.assertFalse(summary["download_urls_echoed"])
        summary_text = json.dumps(summary).casefold()
        self.assertNotIn("https://", summary_text)
        self.assertNotIn("files.pythonhosted.org", summary_text)

    def test_supply_lock_rejects_duplicate_keys_unsafe_urls_and_wrong_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dependency = _write_dependency_wheel(Path(tmp))
            valid = _supply_for_dependency(dependency)
            document = json.loads(valid.raw_bytes)
            mutations = []
            wrong_hash = json.loads(valid.raw_bytes)
            wrong_hash["artifacts"][0]["sha256"] = "sha256:" + "0" * 63
            mutations.append(wrong_hash)
            wrong_size = json.loads(valid.raw_bytes)
            wrong_size["artifacts"][0]["size_bytes"] = 0
            mutations.append(wrong_size)
            wrong_host = json.loads(valid.raw_bytes)
            wrong_host["artifacts"][0]["url"] = (
                "https://example.invalid/" + dependency.name
            )
            mutations.append(wrong_host)
            wrong_query = json.loads(valid.raw_bytes)
            wrong_query["artifacts"][0]["url"] += "?index=shadow"
            mutations.append(wrong_query)
            extra_key = json.loads(valid.raw_bytes)
            extra_key["unexpected"] = True
            mutations.append(extra_key)
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    raw = (json.dumps(mutation, separators=(",", ":")) + "\n").encode()
                    self.assertIsNone(
                        project_runtime.project_runtime_supply_lock(
                            raw,
                            expected_target="v0.4.3",
                        )
                    )
            duplicate = valid.raw_bytes.replace(
                b'{"schema":',
                b'{"schema":"duplicate","schema":',
                1,
            )
            self.assertIsNone(project_runtime.project_runtime_supply_lock(duplicate))
            self.assertIsNone(
                project_runtime.project_runtime_supply_lock(
                    valid.raw_bytes,
                    expected_target="v0.4.4",
                )
            )

    def test_child_environment_discards_every_pip_control_and_disables_config(self) -> None:
        poisoned = {
            "PIP_INDEX_URL": "https://example.invalid/simple",
            "PIP_EXTRA_INDEX_URL": "https://shadow.invalid/simple",
            "PIP_CONFIG_FILE": "C:/unsafe/pip.ini",
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": "C:/unsafe/wheels",
            "PIP_TRUSTED_HOST": "example.invalid",
            "PIP_TARGET": "C:/unsafe/target",
            "PIP_PREFIX": "C:/unsafe/prefix",
            "PIP_REQUIREMENT": "C:/unsafe/requirements.txt",
            "PIP_CONSTRAINT": "C:/unsafe/constraints.txt",
        }
        with patch.dict(os.environ, poisoned, clear=False):
            environment = project_runtime._isolated_python_environment()
        self.assertEqual(environment["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(
            sorted(key for key in environment if key.upper().startswith("PIP_")),
            ["PIP_CONFIG_FILE"],
        )

    def test_artifact_download_rejects_unapproved_redirect_and_accepts_release_asset_host(self) -> None:
        class Response(io.BytesIO):
            def __init__(self, data: bytes, final_url: str) -> None:
                super().__init__(data)
                self._final_url = final_url

            def geturl(self) -> str:
                return self._final_url

        data = b"exact-wheel-bytes"
        digest = hashlib.sha256(data).hexdigest()
        github_url = (
            "https://github.com/mow-coding/zettel-kasten/releases/download/"
            "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rejected = root / "rejected.whl"
            with patch.object(
                project_runtime,
                "_open_runtime_artifact",
                return_value=Response(data, "https://example.invalid/untrusted.whl"),
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_artifact_redirect_unsafe",
                ):
                    project_runtime._download_exact_artifact(
                        url=github_url,
                        expected_sha256=digest,
                        expected_size=len(data),
                        destination=rejected,
                        callback=None,
                        stage="test-rejected-redirect",
                        source_kind="github_release",
                    )

            accepted = root / "accepted.whl"
            final_asset_url = (
                "https://release-assets.githubusercontent.com/github-production-release-asset/"
                "exact/object?sp=r&sig=opaque"
            )
            with patch.object(
                project_runtime,
                "_open_runtime_artifact",
                return_value=Response(data, final_asset_url),
            ):
                size = project_runtime._download_exact_artifact(
                    url=github_url,
                    expected_sha256=digest,
                    expected_size=len(data),
                    destination=accepted,
                    callback=None,
                    stage="test-accepted-redirect",
                    source_kind="github_release",
                )
            self.assertEqual(size, len(data))
            self.assertEqual(accepted.read_bytes(), data)
            redirect_handler = project_runtime._RuntimeArtifactRedirectHandler(
                source_kind="github_release",
                callback=None,
                stage="test-prefollow-redirect",
            )
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_artifact_redirect_unsafe",
            ):
                redirect_handler.redirect_request(
                    project_runtime.urllib.request.Request(github_url),
                    None,
                    302,
                    "Found",
                    {},
                    "https://example.invalid/untrusted.whl",
                )
            pypi_redirect_handler = project_runtime._RuntimeArtifactRedirectHandler(
                source_kind="pypi_file",
                callback=None,
                stage="test-pypi-no-redirect",
            )
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_artifact_redirect_unsafe",
            ):
                pypi_redirect_handler.redirect_request(
                    project_runtime.urllib.request.Request(
                        "https://files.pythonhosted.org/packages/exact/test.whl"
                    ),
                    None,
                    302,
                    "Found",
                    {},
                    "https://files.pythonhosted.org/packages/other/test.whl",
                )

    def test_runtime_mutation_snapshot_detects_and_then_confirms_orphan_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            tracker = project_runtime.RuntimeMutationTracker(
                before=project_runtime.runtime_root_snapshot(project),
                started=True,
                cleanup_verified=False,
            )
            runtimes = project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            runtimes.mkdir(parents=True)
            orphan = runtimes / ".v0.4.3-orphan"
            orphan.mkdir()
            self.assertFalse(project_runtime.runtime_mutation_restored(project, tracker))
            orphan.rmdir()
            runtimes.rmdir()
            self.assertTrue(project_runtime.runtime_mutation_restored(project, tracker))

    def test_shadow_reference_cleanup_uncertainty_is_a_distinct_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dependency = _write_dependency_wheel(root)
            supply = _supply_for_dependency(dependency)
            bootstrap = project_runtime.BootstrapWheel(
                version="0.4.3",
                tag="v0.4.3",
                url=(
                    "https://github.com/mow-coding/zettel-kasten/releases/download/"
                    "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
                ),
                sha256="a" * 64,
                file_name="wom_kit-0.4.3-py3-none-any.whl",
            )
            leaky_parent = root / "leaky-reference"

            class LeakyTemporaryDirectory:
                def __enter__(self) -> str:
                    leaky_parent.mkdir()
                    return str(leaky_parent)

                def __exit__(self, *args: object) -> bool:
                    return False

            bundle = type("Bundle", (), {"root": root})()

            def initialize(runtime: Path, **_kwargs: object) -> tuple[dict[str, bool], list[dict[str, object]], str]:
                runtime.mkdir()
                return {"pip_check": True}, [], "3.12.0"

            with (
                patch.object(
                    project_runtime.tempfile,
                    "TemporaryDirectory",
                    return_value=LeakyTemporaryDirectory(),
                ),
                patch.object(
                    project_runtime,
                    "_initialize_runtime_payload",
                    side_effect=initialize,
                ),
            ):
                with self.assertRaises(project_runtime.RuntimeReferenceCleanupError):
                    project_runtime._reference_payload_inventory(
                        bundle,
                        bootstrap=bootstrap,
                        supply=supply,
                        progress_callback=None,
                    )

    def test_distribution_inventory_authority_comes_from_exact_artifacts_not_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dependency = _write_dependency_wheel(Path(tmp))
            supply = _supply_for_dependency(dependency)
            bootstrap = project_runtime.BootstrapWheel(
                version="0.4.3",
                tag="v0.4.3",
                url=(
                    "https://github.com/mow-coding/zettel-kasten/releases/download/"
                    "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
                ),
                sha256="a" * 64,
                file_name="wom_kit-0.4.3-py3-none-any.whl",
            )
            exact = [
                {"name": "pip", "version": "25.0.1"},
                {"name": "Synthetic-Dependency", "version": "1.2.3"},
                {"name": "wom-kit", "version": "0.4.3"},
            ]
            self.assertEqual(
                project_runtime._validate_distribution_inventory(
                    exact,
                    bootstrap=bootstrap,
                    supply=supply,
                ),
                "25.0.1",
            )
            forged_receipt_inventory = [
                *exact,
                {"name": "extra-package", "version": "9.9.9"},
            ]
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_package_inventory_mismatch",
            ):
                project_runtime._validate_distribution_inventory(
                    forged_receipt_inventory,
                    bootstrap=bootstrap,
                    supply=supply,
                )

    def test_plan_requires_live_reverification_and_enforces_interpreter_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dependency = _write_dependency_wheel(root)
            supply = _supply_for_dependency(dependency)
            bootstrap = project_runtime.BootstrapWheel(
                version="0.4.3",
                tag="v0.4.3",
                url=(
                    "https://github.com/mow-coding/zettel-kasten/releases/download/"
                    "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
                ),
                sha256="a" * 64,
                file_name="wom_kit-0.4.3-py3-none-any.whl",
            )
            receipt_candidate = {
                "status": "receipt_candidate",
                "verified": False,
                "receipt_candidate_valid": True,
            }
            launcher = {"unsafe": False, "already_target": True}
            with (
                patch.object(
                    project_runtime,
                    "inspect_runtime",
                    return_value=receipt_candidate,
                ),
                patch.object(
                    project_runtime,
                    "launcher_snapshot",
                    return_value=launcher,
                ),
                patch.object(
                    project_runtime,
                    "runtime_supply_matches_current_interpreter",
                    return_value=False,
                ),
            ):
                preview, preview_blockers, preview_warnings = project_runtime.plan_runtime(
                    root,
                    "v0.4.3",
                    policy_state="required",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    bootstrap_summary=bootstrap.public_summary(),
                    supply=supply,
                    enforce_interpreter=False,
                )
                prepared, prepared_blockers, _prepared_warnings = project_runtime.plan_runtime(
                    root,
                    "v0.4.3",
                    policy_state="required",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    bootstrap_summary=bootstrap.public_summary(),
                    supply=supply,
                    enforce_interpreter=True,
                )
        self.assertNotIn("project_runtime_interpreter_not_locked", preview_blockers)
        self.assertTrue(preview_warnings)
        self.assertFalse(preview["interpreter_enforced"])
        self.assertTrue(preview["materialization_required"])
        self.assertFalse(preview["runtime_creation_required"])
        self.assertTrue(preview["live_reverification_required"])
        self.assertIn("project_runtime_interpreter_not_locked", prepared_blockers)
        self.assertTrue(prepared["interpreter_enforced"])

    def test_public_bootstrap_provenance_binds_exact_release_wheel_hash(self) -> None:
        digest = "a" * 64

        class Distribution:
            version = "0.4.3"

            @staticmethod
            def read_text(name: str) -> str | None:
                if name != "direct_url.json":
                    return None
                return json.dumps(
                    {
                        "url": "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.3/wom_kit-0.4.3-py3-none-any.whl",
                        "archive_info": {"hashes": {"sha256": digest}},
                    }
                )

        with patch.object(project_runtime.importlib.metadata, "distribution", return_value=Distribution()):
            wheel, summary = project_runtime.bootstrap_wheel_for_target("v0.4.3")
        self.assertIsNotNone(wheel)
        self.assertEqual(wheel.sha256, digest)
        self.assertTrue(summary["available"])
        self.assertEqual(summary["wheel_sha256"], f"sha256:{digest}")
        self.assertFalse(summary["download_url_echoed"])
        self.assertNotIn("url", summary)

    def test_public_bootstrap_rejects_installer_metadata_without_wheel_hash(self) -> None:
        class Distribution:
            version = "0.4.15"

            @staticmethod
            def read_text(name: str) -> str | None:
                if name != "direct_url.json":
                    return None
                return json.dumps(
                    {
                        "url": (
                            "https://github.com/mow-coding/zettel-kasten/"
                            "releases/download/v0.4.15/"
                            "wom_kit-0.4.15-py3-none-any.whl"
                        ),
                        "archive_info": {},
                    }
                )

        with patch.object(
            project_runtime.importlib.metadata,
            "distribution",
            return_value=Distribution(),
        ):
            wheel, summary = project_runtime.bootstrap_wheel_for_target(
                "v0.4.15"
            )

        self.assertIsNone(wheel)
        self.assertFalse(summary["available"])
        self.assertEqual(
            summary["reason_code"],
            "running_distribution_wheel_hash_unavailable",
        )
        self.assertTrue(
            any(
                "python.exe -m pip" in action
                and "SHA-256" in action
                for action in summary["next_safe_actions"]
            )
        )
        self.assertFalse(summary["download_url_echoed"])
        self.assertNotIn("url", summary)

    def test_public_bootstrap_rejects_malformed_recorded_wheel_hash(self) -> None:
        class Distribution:
            version = "0.4.15"

            @staticmethod
            def read_text(name: str) -> str | None:
                if name != "direct_url.json":
                    return None
                return json.dumps(
                    {
                        "url": (
                            "https://github.com/mow-coding/zettel-kasten/"
                            "releases/download/v0.4.15/"
                            "wom_kit-0.4.15-py3-none-any.whl"
                        ),
                        "archive_info": {
                            "hashes": {"sha256": "not-a-sha256"}
                        },
                    }
                )

        with patch.object(
            project_runtime.importlib.metadata,
            "distribution",
            return_value=Distribution(),
        ):
            wheel, summary = project_runtime.bootstrap_wheel_for_target(
                "v0.4.15"
            )

        self.assertIsNone(wheel)
        self.assertEqual(
            summary["reason_code"],
            "running_distribution_wheel_hash_unavailable",
        )

    def test_write_guard_requires_version_and_current_project_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            metadata = project / ".zettel-kasten"
            archive = project / "archive"
            metadata.mkdir(parents=True)
            archive.mkdir()
            (archive / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
            (metadata / "installed-version.txt").write_text("v0.4.3\n", encoding="utf-8")
            blocked = project_runtime.project_write_guard(
                archive,
                running_version="0.4.2",
            )
            same_version_unbound = project_runtime.project_write_guard(
                archive,
                running_version="0.4.3",
            )
            with (
                patch.object(
                    project_runtime,
                    "inspect_runtime",
                    return_value={
                        "receipt_candidate_valid": True,
                        "static_receipt_valid": True,
                        "live_payload_aligned": True,
                    },
                ),
                patch.object(
                    project_runtime,
                    "current_project_runtime_binding",
                    return_value={
                        "bound": True,
                        "reason_code": "current_project_runtime_bound",
                        "core_module_bindings": {
                            "archive_cli": {
                                "observed": True,
                                "expected_identity": True,
                                "inventory_entry_present": True,
                                "bytes_receipt_bound": True,
                                "reason_code": (
                                    "project_runtime_core_archive_cli_receipt_bound"
                                ),
                                "absolute_paths_echoed": False,
                                "hashes_echoed": False,
                            }
                        },
                    },
                ) as current_binding,
            ):
                running_module = Path("synthetic-project-archive-cli.py")
                aligned = project_runtime.project_write_guard(
                    archive,
                    running_version="0.4.3",
                    running_module_path=running_module,
                )
            update_lock = metadata / "version-update.lock"
            update_lock.write_text(
                '{"private":"must-not-be-echoed"}\n',
                encoding="utf-8",
            )
            recovery_required = project_runtime.project_write_guard(
                archive,
                running_version="0.4.3",
            )
        self.assertTrue(blocked["blocked"])
        self.assertEqual(blocked["reason_code"], "project_runtime_mismatch")
        self.assertEqual(
            blocked["project_runtime_argv"],
            [r".\.zettel-kasten\bin\archive.cmd"],
        )
        self.assertTrue(same_version_unbound["blocked"])
        self.assertEqual(
            same_version_unbound["detail_reason_code"],
            "project_runtime_static_receipt_invalid",
        )
        self.assertFalse(aligned["blocked"])
        self.assertTrue(
            aligned["core_module_bindings"]["archive_cli"]
            ["bytes_receipt_bound"]
        )
        self.assertEqual(
            current_binding.call_args.kwargs["running_module_path"],
            running_module,
        )
        self.assertEqual(
            current_binding.call_args.kwargs[
                "running_archive_cli_module_path"
            ],
            running_module,
        )
        self.assertTrue(recovery_required["blocked"])
        self.assertEqual(
            recovery_required["reason_code"],
            "project_update_recovery_required",
        )
        self.assertFalse(recovery_required["private_values_echoed"])
        self.assertNotIn("must-not-be-echoed", json.dumps(recovery_required))

    def test_write_guard_fails_closed_on_live_payload_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            archive = project / "archive"
            metadata = project / ".zettel-kasten"
            archive.mkdir(parents=True)
            (archive / "archive.yml").write_text(
                "archive_id: archive:test\n",
                encoding="utf-8",
            )
            metadata.mkdir(exist_ok=True)
            (metadata / "installed-version.txt").write_text(
                "v0.4.3\n",
                encoding="utf-8",
            )
            _runtime, _executable, module = _write_receipt_bound_runtime(project)
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            module.write_bytes(module.read_bytes() + b"# tampered\n")

            guarded = project_runtime.project_write_guard(
                archive,
                running_version="0.4.3",
                running_module_path=module,
            )

        self.assertTrue(guarded["blocked"])
        self.assertEqual(guarded["reason_code"], "project_runtime_mismatch")
        self.assertEqual(
            guarded["detail_reason_code"],
            "project_runtime_live_payload_mismatch",
        )
        self.assertFalse(guarded["absolute_paths_echoed"])

    def test_current_project_runtime_binding_requires_canonical_launcher_process(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime = project_runtime.runtime_path(project, "0.4.3")
            executable = runtime / "Scripts" / "python.exe"
            module = runtime / "Lib" / "site-packages" / "wom_kit" / "project_runtime.py"
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            executable.parent.mkdir(parents=True)
            module.parent.mkdir(parents=True)
            launcher.parent.mkdir(parents=True)
            executable.write_bytes(b"synthetic-python")
            module.write_text("# synthetic module\n", encoding="utf-8")
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))

            path_only = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=module.with_name("archive_cli.py"),
                running_project_runtime_module_path=module,
                running_package_origin_path=module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
            )
            _write_receipt_bound_runtime(project)
            aligned = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=module.with_name("archive_cli.py"),
                running_project_runtime_module_path=module,
                running_package_origin_path=module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
            )
            direct_console_script = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=module.with_name("archive_cli.py"),
                running_project_runtime_module_path=module,
                running_package_origin_path=module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=False,
                dont_write_bytecode=True,
            )
            global_process = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=sys.executable,
                running_module_path=Path(__file__),
                running_archive_cli_module_path=Path(__file__),
                running_project_runtime_module_path=Path(__file__),
                running_package_origin_path=Path(__file__),
                running_prefix=sys.prefix,
                isolated_mode=True,
                dont_write_bytecode=True,
            )

        self.assertFalse(path_only["bound"])
        self.assertEqual(
            path_only["reason_code"],
            "project_runtime_static_receipt_invalid",
        )
        self.assertTrue(aligned["bound"])
        self.assertEqual(aligned["reason_code"], "current_project_runtime_bound")
        self.assertTrue(aligned["live_payload_aligned"])
        self.assertTrue(aligned["running_module_receipt_bound"])
        self.assertFalse(direct_console_script["bound"])
        self.assertEqual(
            direct_console_script["reason_code"],
            "project_runtime_canonical_launcher_flags_missing",
        )
        self.assertFalse(global_process["bound"])
        self.assertEqual(
            global_process["reason_code"],
            "project_runtime_process_binding_mismatch",
        )
        self.assertFalse(global_process["absolute_paths_echoed"])

    def test_binding_accepts_exact_archive_cli_executed_as_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, executable, module = _write_receipt_bound_runtime(project)
            archive_cli_module = module.with_name("archive_cli.py")
            package_origin = module.with_name("__init__.py")
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            main_module = types.ModuleType("__main__")
            main_module.__file__ = str(archive_cli_module)
            main_module.__spec__ = types.SimpleNamespace(
                name="wom_kit.archive_cli",
                origin=str(archive_cli_module),
            )
            canonical_module = sys.modules.pop("wom_kit.archive_cli", None)
            try:
                with patch.dict(
                    sys.modules,
                    {"__main__": main_module},
                    clear=False,
                ):
                    binding = project_runtime.current_project_runtime_binding(
                        project,
                        "0.4.3",
                        running_executable=executable,
                        running_module_path=archive_cli_module,
                        running_project_runtime_module_path=module,
                        running_package_origin_path=package_origin,
                        running_prefix=runtime,
                        isolated_mode=True,
                        dont_write_bytecode=True,
                    )
            finally:
                if canonical_module is not None:
                    sys.modules["wom_kit.archive_cli"] = canonical_module

        self.assertTrue(binding["bound"])
        self.assertTrue(binding["core_modules_receipt_bound"])
        self.assertEqual(
            binding["reason_code"],
            "current_project_runtime_bound",
        )
        for detail in binding["core_module_bindings"].values():
            self.assertTrue(detail["observed"])
            self.assertTrue(detail["expected_identity"])
            self.assertTrue(detail["inventory_entry_present"])
            self.assertTrue(detail["bytes_receipt_bound"])
            self.assertFalse(detail["absolute_paths_echoed"])
            self.assertFalse(detail["hashes_echoed"])

    def test_binding_rejects_unrelated_main_module_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, executable, module = _write_receipt_bound_runtime(project)
            archive_cli_module = module.with_name("archive_cli.py")
            package_origin = module.with_name("__init__.py")
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            main_module = types.ModuleType("__main__")
            main_module.__file__ = str(archive_cli_module)
            main_module.__spec__ = types.SimpleNamespace(
                name="unrelated.main",
                origin=str(archive_cli_module),
            )
            canonical_module = sys.modules.pop("wom_kit.archive_cli", None)
            try:
                with patch.dict(
                    sys.modules,
                    {"__main__": main_module},
                    clear=False,
                ):
                    binding = project_runtime.current_project_runtime_binding(
                        project,
                        "0.4.3",
                        running_executable=executable,
                        running_module_path=archive_cli_module,
                        running_project_runtime_module_path=module,
                        running_package_origin_path=package_origin,
                        running_prefix=runtime,
                        isolated_mode=True,
                        dont_write_bytecode=True,
                    )
            finally:
                if canonical_module is not None:
                    sys.modules["wom_kit.archive_cli"] = canonical_module

        self.assertFalse(binding["bound"])
        self.assertFalse(binding["core_modules_receipt_bound"])
        self.assertEqual(
            binding["reason_code"],
            "project_runtime_core_modules_not_receipt_bound",
        )
        archive_cli_detail = binding["core_module_bindings"]["archive_cli"]
        self.assertFalse(archive_cli_detail["observed"])
        self.assertEqual(
            archive_cli_detail["reason_code"],
            "project_runtime_core_archive_cli_unobserved",
        )
        self.assertNotIn("path", archive_cli_detail)
        self.assertNotIn("sha256", archive_cli_detail)

    def test_runtime_inspection_rejects_receipt_bound_payload_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, _executable, module = _write_receipt_bound_runtime(project)

            before = project_runtime.inspect_runtime(project, "0.4.3")
            module.write_bytes(module.read_bytes() + b"# post-receipt tamper\n")
            after = project_runtime.inspect_runtime(project, "0.4.3")

        self.assertTrue(before["static_receipt_valid"])
        self.assertTrue(before["live_payload_aligned"])
        self.assertTrue(before["receipt_candidate_valid"])
        self.assertEqual(
            before["live_payload_sha256"],
            before["installed_payload_sha256"],
        )
        self.assertEqual(before["path"], runtime.relative_to(project).as_posix())
        self.assertTrue(after["static_receipt_valid"])
        self.assertFalse(after["live_payload_aligned"])
        self.assertFalse(after["receipt_candidate_valid"])
        self.assertFalse(after["absolute_paths_echoed"])

    def test_runtime_inspection_distinguishes_unavailable_from_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _write_receipt_bound_runtime(project)

            with patch.object(
                project_runtime,
                "_runtime_payload_observation",
                side_effect=project_runtime.ProjectRuntimeError(
                    "synthetic_observation_unavailable"
                ),
            ):
                unavailable = project_runtime.inspect_runtime(
                    project,
                    "0.4.3",
                )

        self.assertTrue(unavailable["static_receipt_valid"])
        self.assertFalse(unavailable["live_payload_aligned"])
        self.assertEqual(unavailable["live_payload_state"], "unavailable")
        self.assertEqual(
            unavailable["live_payload_reason_code"],
            "project_runtime_live_payload_unavailable",
        )
        self.assertFalse(unavailable["receipt_candidate_valid"])
        self.assertFalse(unavailable["absolute_paths_echoed"])

    def test_runtime_inspection_marks_live_check_not_reached_for_bad_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, _executable, _module = _write_receipt_bound_runtime(project)
            (runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME).write_bytes(
                b"{invalid-receipt\n"
            )

            inspected = project_runtime.inspect_runtime(project, "0.4.3")

        self.assertFalse(inspected["static_receipt_valid"])
        self.assertFalse(inspected["live_payload_aligned"])
        self.assertEqual(inspected["live_payload_state"], "not_reached")
        self.assertEqual(
            inspected["live_payload_reason_code"],
            "project_runtime_static_receipt_invalid",
        )

    def test_binding_rechecks_payload_after_reused_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, executable, module = _write_receipt_bound_runtime(project)
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            inspection = project_runtime.inspect_runtime(project, "0.4.3")
            module.write_bytes(module.read_bytes() + b"# swapped generation\n")

            binding = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=module.with_name("archive_cli.py"),
                running_project_runtime_module_path=module,
                running_package_origin_path=module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
                runtime_inspection=inspection,
            )

        self.assertFalse(binding["bound"])
        self.assertFalse(binding["live_payload_aligned"])
        self.assertEqual(
            binding["reason_code"],
            "project_runtime_live_payload_mismatch",
        )

    def test_binding_rejects_receipt_generation_change_after_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, executable, module = _write_receipt_bound_runtime(project)
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            inspection = project_runtime.inspect_runtime(project, "0.4.3")
            receipt_path = runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            receipt_path.write_bytes(receipt_path.read_bytes() + b"\n")

            binding = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=module.with_name("archive_cli.py"),
                running_project_runtime_module_path=module,
                running_package_origin_path=module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
                runtime_inspection=inspection,
            )

        self.assertFalse(binding["bound"])
        self.assertFalse(binding["receipt_generation_aligned"])
        self.assertEqual(
            binding["reason_code"],
            "project_runtime_static_receipt_invalid",
        )

    def test_runtime_inspection_rejects_symlink_swapped_payload_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            _runtime, _executable, module = _write_receipt_bound_runtime(project)
            outside = root / "outside.py"
            outside.write_bytes(module.read_bytes())
            module.unlink()
            try:
                module.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")

            inspected = project_runtime.inspect_runtime(project, "0.4.3")

        self.assertTrue(inspected["static_receipt_valid"])
        self.assertFalse(inspected["live_payload_aligned"])
        self.assertFalse(inspected["receipt_candidate_valid"])

    def test_descriptor_bound_read_rejects_observed_path_generation_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            replacement = root / "replacement.bin"
            target.write_bytes(b"receipt-bound")
            replacement.write_bytes(b"other-generation")
            target_before = target.lstat()
            replacement_stat = replacement.lstat()
            original_lstat = Path.lstat
            target_observations = 0

            def swapped_lstat(path: Path) -> os.stat_result:
                nonlocal target_observations
                if path == target:
                    target_observations += 1
                    return (
                        target_before
                        if target_observations == 1
                        else replacement_stat
                    )
                return original_lstat(path)

            with patch.object(Path, "lstat", swapped_lstat):
                observed = project_runtime._stable_regular_file_observation(
                    target,
                    limit=1024,
                    collect_bytes=True,
                    tree_shape_bound=True,
                )

        self.assertIsNone(observed)

    def test_payload_hash_rejects_directory_generation_change_during_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            first = runtime / "wom_kit" / "first.py"
            first.parent.mkdir(parents=True)
            first.write_bytes(b"first\n")
            original_sha256_file = project_runtime._sha256_file
            changed = False

            def mutate_tree(path: Path, **kwargs: object) -> tuple[str, int]:
                nonlocal changed
                result = original_sha256_file(path, **kwargs)
                if not changed:
                    changed = True
                    (runtime / "wom_kit" / "late.py").write_bytes(b"late\n")
                return result

            with patch.object(
                project_runtime,
                "_sha256_file",
                side_effect=mutate_tree,
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_tree_changed",
                ):
                    project_runtime._runtime_payload_sha256(runtime)

    def test_binding_requires_all_loaded_core_wom_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime, executable, module = _write_receipt_bound_runtime(project)
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))
            archive_cli_module = module.with_name("archive_cli.py")
            package_origin = module.with_name("__init__.py")

            binding = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=archive_cli_module,
                running_archive_cli_module_path=archive_cli_module,
                # A receipt-bound file with the wrong core-module identity must
                # not stand in for the loaded project_runtime module.
                running_project_runtime_module_path=archive_cli_module,
                running_package_origin_path=package_origin,
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
            )

        self.assertFalse(binding["bound"])
        self.assertFalse(binding["core_modules_receipt_bound"])
        self.assertEqual(
            binding["reason_code"],
            "project_runtime_core_modules_not_receipt_bound",
        )

    def test_binding_rejects_receipt_bound_non_wom_module_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            runtime = project_runtime.runtime_path(project, "0.4.3")
            executable = runtime / "Scripts" / "python.exe"
            module = runtime / "Lib" / "site-packages" / "unrelated.py"
            executable.parent.mkdir(parents=True)
            module.parent.mkdir(parents=True)
            executable.write_bytes(b"synthetic-python\n")
            module.write_bytes(b"# unrelated but payload-bound\n")
            # Add a real WOM module so the receipt itself describes a plausible
            # runtime; the running module argument deliberately points elsewhere.
            wom_module = (
                runtime
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "project_runtime.py"
            )
            wom_module.parent.mkdir(parents=True)
            wom_module.write_bytes(b"# WOM module\n")
            _runtime, _executable, _module = _write_receipt_bound_runtime(project)
            # The helper rewrites the payload, so add the unrelated file and
            # bind the resulting exact tree in the receipt once more.
            module.write_bytes(b"# unrelated but payload-bound\n")
            receipt_path = runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["installed_payload_sha256"] = (
                "sha256:" + project_runtime._runtime_payload_sha256(runtime)
            )
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True)
            launcher.write_bytes(project_runtime.launcher_bytes("0.4.3"))

            binding = project_runtime.current_project_runtime_binding(
                project,
                "0.4.3",
                running_executable=executable,
                running_module_path=module,
                running_archive_cli_module_path=wom_module.with_name("archive_cli.py"),
                running_project_runtime_module_path=wom_module,
                running_package_origin_path=wom_module.with_name("__init__.py"),
                running_prefix=runtime,
                isolated_mode=True,
                dont_write_bytecode=True,
            )

        self.assertFalse(binding["bound"])
        self.assertFalse(binding["running_module_aligned"])
        self.assertEqual(
            binding["reason_code"],
            "project_runtime_process_binding_mismatch",
        )

    @unittest.skipUnless(
        os.name == "nt"
        and sys.version_info[:2] == (3, 12)
        and platform.machine().casefold() in {"amd64", "x86_64"},
        "The v0.4.3 project runtime lock is CPython 3.12 Windows AMD64 only.",
    )
    def test_three_projects_update_only_one_and_leave_shared_launcher_unchanged(self) -> None:
        self.skipTest("superseded by complete runtime-candidate phase-boundary tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = [root / "project-040", root / "project-042", root / "project-043"]
            versions = ["0.4.0", "0.4.2", "0.4.3"]
            for project, version in zip(projects, versions, strict=True):
                metadata = project / ".zettel-kasten"
                metadata.mkdir(parents=True)
                (metadata / "installed-version.txt").write_text(f"v{version}\n", encoding="utf-8")
            shared_launcher = root / "shared" / "archive.exe"
            shared_launcher.parent.mkdir()
            shared_launcher.write_bytes(b"shared-v0.4.2-sentinel")
            shared_before = shared_launcher.read_bytes()
            untouched_before = [_tree_snapshot(projects[0]), _tree_snapshot(projects[2])]
            path_before = os.environ.get("PATH")

            wheel_path = _write_minimal_wheel(root, "0.4.3")
            dependency_path = _write_dependency_wheel(root)
            supply = _supply_for_dependency(dependency_path)
            wheel_sha256 = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
            bootstrap = project_runtime.BootstrapWheel(
                version="0.4.3",
                tag="v0.4.3",
                url="https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.3/wom_kit-0.4.3-py3-none-any.whl",
                sha256=wheel_sha256,
                file_name=wheel_path.name,
            )

            source_by_name = {
                wheel_path.name: wheel_path,
                dependency_path.name: dependency_path,
            }

            shadow_root = root / "python-path-shadow"
            shadow_package = shadow_root / "wom_kit"
            shadow_package.mkdir(parents=True)
            (shadow_package / "__init__.py").write_text(
                '__version__ = "shadow"\n',
                encoding="utf-8",
            )
            (shadow_package / "archive_cli.py").write_text(
                "print('PYTHONPATH-SHADOW-EXECUTED')\n"
                "raise SystemExit(91)\n",
                encoding="utf-8",
            )

            def copy_artifact(**kwargs: object) -> int:
                destination = kwargs["destination"]
                self.assertIsInstance(destination, Path)
                assert isinstance(destination, Path)
                source = source_by_name[destination.name]
                shutil.copyfile(source, destination)
                return source.stat().st_size

            poisoned_environment = {
                "PYTHONHOME": str(root / "missing-python-home"),
                "PYTHONPATH": str(shadow_root),
                "VIRTUAL_ENV": str(root / "unrelated-shared-venv"),
                "PIP_INDEX_URL": "https://example.invalid/simple",
                "PIP_EXTRA_INDEX_URL": "https://shadow.invalid/simple",
                "PIP_CONFIG_FILE": str(root / "missing-pip.ini"),
                "PIP_FIND_LINKS": str(root / "untrusted-wheelhouse"),
                "PIP_TARGET": str(root / "untrusted-target"),
            }
            tracker = project_runtime.RuntimeMutationTracker()
            with patch.dict(os.environ, poisoned_environment):
                with patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=copy_artifact,
                ):
                    prepared_bundle = project_runtime.prepare_runtime_bundle(
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                    )
                with patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=AssertionError(
                        "postapproval materialization must not use network"
                    ),
                ):
                    materialized = project_runtime.materialize_runtime(
                        projects[1],
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        prepared_bundle=prepared_bundle,
                        running_version="0.4.3",
                        mutation_tracker=tracker,
                    )
            prepared_summary = prepared_bundle.public_summary()
            self.assertTrue(prepared_summary["network_complete"])
            self.assertFalse(prepared_summary["post_approval_network_allowed"])
            self.assertNotIn("https://", json.dumps(prepared_summary))
            launcher = projects[1] / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
            launcher.parent.mkdir(parents=True, exist_ok=True)
            launcher.write_bytes(project_runtime.launcher_bytes("v0.4.3"))
            (projects[1] / ".zettel-kasten" / "installed-version.txt").write_text(
                "v0.4.3\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                ["cmd", "/d", "/c", str(launcher), "--version"],
                cwd=projects[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, **poisoned_environment},
            )
            self.assertEqual(
                completed.returncode,
                0,
                json.dumps(
                    {
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "scripts": sorted(
                            path.name
                            for path in (
                                materialized.final_path / "Scripts"
                            ).iterdir()
                        ),
                    }
                ),
            )
            self.assertIn("0.4.3", completed.stdout)
            self.assertNotIn("PYTHONPATH-SHADOW-EXECUTED", completed.stdout)
            self.assertTrue(materialized.created)
            site_packages = materialized.final_path / "Lib" / "site-packages"
            self.assertEqual(
                [
                    path.relative_to(site_packages).as_posix()
                    for package_root in (
                        site_packages / "wom_kit",
                        site_packages / "synthetic_dependency",
                    )
                    for path in sorted(package_root.rglob("*.pyc"))
                ],
                [],
            )
            candidate = project_runtime.inspect_runtime(
                projects[1],
                "v0.4.3",
                expected_commit="b" * 40,
                expected_wheel_sha256=wheel_sha256,
                expected_supply_lock_sha256=supply.sha256,
            )
            self.assertFalse(candidate["verified"])
            self.assertTrue(candidate["receipt_candidate_valid"])
            self.assertTrue(candidate["live_reverification_required_before_reuse"])
            runtime_receipt_path = (
                materialized.final_path / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            )
            receipt_document = json.loads(materialized.receipt_bytes)
            invalid_receipts = []
            top_extra = json.loads(materialized.receipt_bytes)
            top_extra["unapproved_extra"] = True
            invalid_receipts.append(top_extra)
            nested_extra = json.loads(materialized.receipt_bytes)
            nested_extra["verification"]["unapproved_extra"] = True
            invalid_receipts.append(nested_extra)
            malformed_inventory = json.loads(materialized.receipt_bytes)
            malformed_inventory["artifact_inventory"][0]["unapproved_extra"] = True
            invalid_receipts.append(malformed_inventory)
            for invalid_receipt in invalid_receipts:
                runtime_receipt_path.write_bytes(
                    (
                        json.dumps(invalid_receipt, ensure_ascii=False, indent=2)
                        + "\n"
                    ).encode("utf-8")
                )
                rejected_candidate = project_runtime.inspect_runtime(
                    projects[1],
                    "v0.4.3",
                    expected_commit="b" * 40,
                    expected_wheel_sha256=wheel_sha256,
                    expected_supply_lock_sha256=supply.sha256,
                )
                self.assertFalse(rejected_candidate["receipt_candidate_valid"])
            duplicate_receipt = materialized.receipt_bytes.replace(
                b'{\n  "schema":',
                b'{\n  "schema":"duplicate",\n  "schema":',
                1,
            )
            runtime_receipt_path.write_bytes(duplicate_receipt)
            self.assertFalse(
                project_runtime.inspect_runtime(
                    projects[1],
                    "v0.4.3",
                    expected_commit="b" * 40,
                    expected_wheel_sha256=wheel_sha256,
                    expected_supply_lock_sha256=supply.sha256,
                )["receipt_candidate_valid"]
            )
            runtime_receipt_path.write_bytes(materialized.receipt_bytes)
            self.assertEqual(receipt_document["status"], "verified")
            retained = materialized.final_path / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME
            self.assertEqual(
                {path.name for path in retained.iterdir()},
                {
                    project_runtime.PROJECT_RUNTIME_RETAINED_LOCK_NAME,
                    wheel_path.name,
                    dependency_path.name,
                },
            )
            self.assertEqual(list(site_packages.rglob("direct_url.json")), [])
            runtime_process_calls: list[list[str]] = []
            original_run_bounded = project_runtime._run_bounded

            def observe_runtime_process(argv: list[str], **kwargs: object) -> str:
                runtime_process_calls.append(list(argv))
                return original_run_bounded(argv, **kwargs)

            with (
                patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=AssertionError(
                        "valid reuse must not redownload artifacts"
                    ),
                ),
                patch.object(
                    project_runtime,
                    "_run_bounded",
                    side_effect=observe_runtime_process,
                ),
            ):
                reused = project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            self.assertFalse(reused.created)
            self.assertEqual(
                reused.installed_payload_sha256,
                materialized.installed_payload_sha256,
            )
            existing_python = str(
                materialized.final_path / "Scripts" / "python.exe"
            ).casefold()
            existing_process_calls = [
                argv
                for argv in runtime_process_calls
                if argv and argv[0].casefold() == existing_python
            ]
            self.assertTrue(existing_process_calls)
            self.assertTrue(all("-S" in argv for argv in existing_process_calls))
            self.assertFalse(
                any("pip" in {item.casefold() for item in argv} for argv in existing_process_calls)
            )
            self.assertFalse(
                any("archive.exe" in item.casefold() for argv in existing_process_calls for item in argv)
            )
            runtime_root_before_cleanup_error = project_runtime.runtime_root_snapshot(
                projects[1]
            )
            cleanup_error_tracker = project_runtime.RuntimeMutationTracker()
            private_reference_root = root / "must-not-be-echoed-reference-root"
            with (
                patch.object(
                    project_runtime,
                    "_reference_payload_inventory",
                    side_effect=project_runtime.RuntimeReferenceCleanupError(
                        private_reference_root
                    ),
                ),
                patch.object(
                    project_runtime,
                    "_runtime_process_verification",
                    side_effect=AssertionError(
                        "existing runtime must not execute after shadow cleanup uncertainty"
                    ),
                ),
            ):
                with self.assertRaises(project_runtime.RuntimeReferenceCleanupError) as caught:
                    project_runtime.materialize_runtime(
                        projects[1],
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        prepared_bundle=prepared_bundle,
                        mutation_tracker=cleanup_error_tracker,
                        running_version="0.4.3",
                    )
            self.assertEqual(
                str(caught.exception),
                "project_runtime_reference_cleanup_unverified",
            )
            self.assertNotIn(str(private_reference_root), str(caught.exception))
            self.assertFalse(cleanup_error_tracker.started)
            self.assertEqual(
                project_runtime.runtime_root_snapshot(projects[1]),
                runtime_root_before_cleanup_error,
            )
            with patch.object(
                project_runtime,
                "_reference_payload_inventory",
                return_value=(
                    project_runtime._normalized_runtime_payload_inventory(
                        materialized.final_path
                    ),
                    {"pip_check": False},
                ),
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_reuse_pip_check_unproven",
                ):
                    project_runtime.materialize_runtime(
                        projects[1],
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        prepared_bundle=prepared_bundle,
                        mutation_tracker=project_runtime.RuntimeMutationTracker(),
                        running_version="0.4.3",
                    )

            dist_info = site_packages / "wom_kit-0.4.3.dist-info"
            dist_info_extra = dist_info / "unbound-extra.txt"
            dist_info_extra.write_text("not wheel-authorized\n", encoding="utf-8")
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_installed_payload_inventory_mismatch",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            dist_info_extra.unlink()

            record_path = dist_info / "RECORD"
            record_before = record_path.read_bytes()
            record_lines = record_before.decode("utf-8").splitlines()
            record_lines[0] = record_lines[0].replace("sha256=", "sha256=A", 1)
            record_path.write_text("\n".join(record_lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_installed_payload_inventory_mismatch",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            record_path.write_bytes(record_before)

            receipt_path = runtime_receipt_path
            python_path = materialized.final_path / "Scripts" / "python.exe"
            python_before = python_path.read_bytes()
            python_path.write_bytes(python_before + b"receipt-self-authorized-tamper")
            forged_receipt = json.loads(materialized.receipt_bytes)
            forged_receipt["installed_payload_sha256"] = (
                "sha256:" + project_runtime._runtime_payload_sha256(materialized.final_path)
            )
            receipt_path.write_bytes(
                (json.dumps(forged_receipt, ensure_ascii=False, indent=2) + "\n").encode(
                    "utf-8"
                )
            )
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_existing_shadow_mismatch",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            python_path.write_bytes(python_before)
            receipt_path.write_bytes(materialized.receipt_bytes)

            extra_payload = (
                materialized.final_path
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "unbound_extra.py"
            )
            extra_payload.write_text("raise RuntimeError('unbound')\n", encoding="utf-8")
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_installed_payload_inventory_mismatch",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            extra_payload.unlink()

            retained_dependency = retained / dependency_path.name
            retained_dependency.write_bytes(retained_dependency.read_bytes() + b"tampered")
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_retained_artifact_mismatch",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            shutil.copyfile(dependency_path, retained_dependency)

            resource = (
                materialized.final_path
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "_resources"
                / "release-notes"
                / "v0.4.3.md"
            )
            resource.write_bytes(resource.read_bytes() + b"tampered")
            with self.assertRaises(project_runtime.ProjectRuntimeError):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    running_version="0.4.3",
                )
            self.assertEqual(_tree_snapshot(projects[0]), untouched_before[0])
            self.assertEqual(_tree_snapshot(projects[2]), untouched_before[1])
            self.assertEqual(shared_launcher.read_bytes(), shared_before)
            self.assertEqual(os.environ.get("PATH"), path_before)
            prepared_dependency = prepared_bundle.root / dependency_path.name
            prepared_dependency.write_bytes(
                prepared_dependency.read_bytes() + b"postapproval-drift"
            )
            drift_tracker = project_runtime.RuntimeMutationTracker()
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_prepared_bundle_drift",
            ):
                project_runtime.materialize_runtime(
                    projects[1],
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_bundle=prepared_bundle,
                    mutation_tracker=drift_tracker,
                    running_version="0.4.3",
                )
            self.assertFalse(drift_tracker.started)
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_bundle(prepared_bundle)
            )
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_bundle(prepared_bundle)
            )


if __name__ == "__main__":
    unittest.main()
