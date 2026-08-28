from __future__ import annotations

import hashlib
import io
import json
import os
import re
import runpy
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from contextlib import nullcontext
from pathlib import Path
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
ROOT = KIT_ROOT.parent
SOURCE_ROOT = KIT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "wom_kit"
BENCHMARK_PATH = KIT_ROOT / "tools" / "benchmark_v0412_link_index.py"
REFERENCE_PATH = (
    KIT_ROOT
    / "docs"
    / "evidence"
    / "v0.4.12-link-index-windows-reference.json"
)
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
REFERENCE_SHA256 = (
    "c3c768a573fc2a7206a1a8bd11d673c9c05f5daac9026e562978c44a6fae8492"
)
V0412_RELEASE_NOTES_SHA256 = (
    "1e0a0ffd9a29d505f6a91541797d4227770cf687e633d1a822f64e153c9849fa"
)
V0412_BENCHMARK_SHA256 = (
    "d521a0d308008c64ea0bd9e79975747106b3a5f3e308519d11fe32d8ffbb64ff"
)


def _source_version() -> str:
    source = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
    matches = re.findall(
        r'(?m)^__version__ = "('
        r"(?:0|[1-9][0-9]*)\."
        r"(?:0|[1-9][0-9]*)\."
        r'(?:0|[1-9][0-9]*))"\r?$',
        source,
    )
    if len(matches) != 1 or source.count("__version__") != 1:
        raise AssertionError("source version declaration is not exact")
    return matches[0]


def _build_source_bound_test_wheel(
    directory: Path,
    *,
    version: str | None = None,
) -> Path:
    version = version or _source_version()
    wheel = directory / f"wom_kit-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE_ROOT.rglob("*")):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(SOURCE_ROOT).parts
            if (
                "__pycache__" in relative_parts
                or path.suffix.casefold() in {".pyc", ".pyo"}
            ):
                continue
            archive.write(path, Path(*relative_parts).as_posix())
        archive.writestr(
            f"wom_kit-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: wom-kit\nVersion: {version}\n",
        )
        archive.writestr(
            f"wom_kit-{version}.dist-info/WHEEL",
            "Wheel-Version: 1.0\nTag: py3-none-any\n",
        )
    return wheel


class V0412LinkIndexBenchmarkTests(unittest.TestCase):
    def assert_provenance_hashes(self, provenance: dict[str, object]) -> None:
        for key in (
            "source_tree_sha256",
            "git_commit_sha256",
            "benchmark_script_sha256",
            "wheel_sha256",
            "wheel_package_tree_sha256",
        ):
            self.assertRegex(str(provenance[key]), SHA256_PATTERN)
        self.assertRegex(
            str(provenance["git_commit_oid"]),
            r"^(?:sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})$",
        )
        self.assertRegex(
            str(provenance["git_source_tree_oid"]),
            r"^(?:sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})$",
        )

    def assert_serialized_delivery(self, report: dict[str, object]) -> None:
        delivery = report["status_delivery"]
        thresholds = report["thresholds_seconds"]
        assert isinstance(delivery, dict)
        assert isinstance(thresholds, dict)
        self.assertLessEqual(
            delivery["first_serialized_write_seconds_max"],
            thresholds["first_serialized_write"],
        )
        self.assertLessEqual(
            delivery["first_serialized_flush_seconds_max"],
            thresholds["first_serialized_flush"],
        )
        self.assertLessEqual(
            delivery["max_serialized_flush_gap_seconds"],
            thresholds["max_serialized_flush_gap"],
        )
        self.assertGreater(delivery["serialized_utf8_bytes"], 0)
        self.assertGreater(delivery["serialized_write_calls"], 0)
        self.assertGreater(delivery["serialized_flush_calls"], 0)
        self.assertRegex(delivery["serialized_streams_sha256"], SHA256_PATTERN)
        progress_safety = report["serialized_progress_safety"]
        assert isinstance(progress_safety, dict)
        self.assertTrue(
            all(value == 0 for value in progress_safety.values()),
            progress_safety,
        )

    def test_committed_windows_reference_and_required_ci_are_exact(self) -> None:
        reference_raw = REFERENCE_PATH.read_bytes()
        self.assertEqual(
            hashlib.sha256(reference_raw).hexdigest(),
            REFERENCE_SHA256,
        )
        report = json.loads(reference_raw.decode("utf-8", "strict"))
        self.assertTrue(report["ok"], report)
        self.assertEqual(
            report["schema"],
            "wom-kit/v0412-link-index-benchmark/v0.2",
        )
        self.assertEqual(report["profile"], "full")
        self.assertEqual(report["reason_codes"], [])
        self.assertEqual(report["environment"]["os_family"], "windows")
        self.assertEqual(report["environment"]["pointer_bits"], 64)
        self.assertRegex(
            report["environment"]["environment_fingerprint_sha256"],
            SHA256_PATTERN,
        )
        self.assertEqual(report["counts"]["zettels"], 8_616)
        self.assertEqual(report["counts"]["objets"], 22_441)
        self.assertEqual(report["counts"]["manifest_size_bytes"], 37 * 1024 * 1024)
        self.assertEqual(report["counts"]["cold_samples_per_state"], 5)
        self.assertEqual(report["counts"]["warm_samples_per_state"], 10)
        self.assertTrue(all(report["checks"].values()), report["checks"])
        self.assertTrue(
            all(value == 0 for value in report["output_safety"].values()),
            report["output_safety"],
        )
        for field in (
            "private_values_echoed",
            "absolute_paths_echoed",
            "zettel_ids_echoed",
            "object_ids_echoed",
        ):
            self.assertIs(report[field], False)
        timing = report["plan_durations_seconds"]
        thresholds = report["thresholds_seconds"]
        self.assertLessEqual(timing["cold_ready"]["p95"], thresholds["cold_plan_p95"])
        self.assertLessEqual(
            timing["cold_already_present"]["p95"],
            thresholds["cold_plan_p95"],
        )
        self.assertLessEqual(timing["warm_ready"]["p95"], thresholds["warm_plan_p95"])
        self.assertLessEqual(
            timing["warm_already_present"]["p95"],
            thresholds["warm_plan_p95"],
        )
        self.assert_serialized_delivery(report)
        self.assertEqual(report["status_delivery"]["serialized_stream_count"], 30)
        self.assertGreaterEqual(report["status_delivery"]["serialized_line_count"], 60)
        self.assertTrue(report["checks"]["provenance_stable_during_benchmark"])
        self.assertEqual(
            report["instrumentation"]["full_manifest_json_parser_calls"],
            0,
        )
        self.assertEqual(
            report["instrumentation"]["legacy_full_zettel_resolver_calls"],
            0,
        )
        provenance = report["provenance"]
        self.assert_provenance_hashes(provenance)
        self.assertTrue(provenance["wheel_matches_source_tree"])
        self.assertTrue(provenance["source_tree_matches_git_commit"])
        self.assertTrue(provenance["benchmark_script_matches_git_commit"])
        self.assertTrue(provenance["release_evidence_eligible"])
        self.assertEqual(provenance["scoped_uncommitted_entry_count"], 0)
        self.assertEqual(provenance["source_inventory_delta_count"], 0)
        self.assertEqual(provenance["git_status_change_count"], 0)
        self.assertFalse(provenance["private_paths_included"])

        def git_bytes(*arguments: str) -> bytes:
            completed = subprocess.run(
                ["git", "-C", str(ROOT), *arguments],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            return bytes(completed.stdout)

        recorded_commit_oid = str(provenance["git_commit_oid"]).split(
            ":", 1
        )[1]
        tag_ref = "refs/tags/v0.4.12"
        self.assertEqual(
            git_bytes("cat-file", "-t", tag_ref)
            .decode("ascii", "strict")
            .strip(),
            "tag",
        )
        tag_commit_oid = git_bytes(
            "rev-parse",
            f"{tag_ref}^{{commit}}",
        ).decode("ascii", "strict").strip()
        ancestry = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "merge-base",
                "--is-ancestor",
                recorded_commit_oid,
                tag_commit_oid,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.assertEqual(ancestry.returncode, 0)
        recorded_commit_content = git_bytes(
            "cat-file",
            "commit",
            recorded_commit_oid,
        )
        recorded_commit_object = (
            b"commit "
            + str(len(recorded_commit_content)).encode("ascii")
            + b"\0"
            + recorded_commit_content
        )
        self.assertEqual(
            provenance["git_commit_sha256"],
            "sha256:"
            + hashlib.sha256(recorded_commit_object).hexdigest(),
        )
        recorded_source_tree_oid = git_bytes(
            "rev-parse",
            f"{recorded_commit_oid}:wom-kit/src/wom_kit",
        ).decode("ascii", "strict").strip()
        tag_source_tree_oid = git_bytes(
            "rev-parse",
            f"{tag_commit_oid}:wom-kit/src/wom_kit",
        ).decode("ascii", "strict").strip()
        self.assertEqual(recorded_source_tree_oid, tag_source_tree_oid)
        self.assertEqual(
            provenance["git_source_tree_oid"].split(":", 1)[1],
            tag_source_tree_oid,
        )
        recorded_benchmark = git_bytes(
            "cat-file",
            "blob",
            f"{recorded_commit_oid}:wom-kit/tools/benchmark_v0412_link_index.py",
        )
        tag_benchmark = git_bytes(
            "cat-file",
            "blob",
            f"{tag_commit_oid}:wom-kit/tools/benchmark_v0412_link_index.py",
        )
        self.assertEqual(recorded_benchmark, tag_benchmark)
        self.assertEqual(
            hashlib.sha256(tag_benchmark).hexdigest(),
            V0412_BENCHMARK_SHA256,
        )
        self.assertEqual(
            provenance["benchmark_script_sha256"],
            "sha256:" + V0412_BENCHMARK_SHA256,
        )
        tag_release_notes = git_bytes(
            "cat-file",
            "blob",
            f"{tag_commit_oid}:wom-kit/docs/releases/v0.4.12.md",
        )
        self.assertEqual(
            hashlib.sha256(tag_release_notes).hexdigest(),
            V0412_RELEASE_NOTES_SHA256,
        )

        rendered = REFERENCE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(rendered, r"[A-Za-z]:[\\/]")
        self.assertNotIn("receipt", rendered.casefold())
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("link_index_scale:", workflow)
        self.assertIn("pip wheel", workflow)
        self.assertIn('-Filter "wom_kit-*.whl"', workflow)
        self.assertNotIn('wom_kit-0.4.12-*.whl', workflow)
        self.assertIn("--wheel", workflow)
        self.assertIn("--profile full", workflow)
        self.assertIn("- link_index_scale", workflow)
        self.assertIn("LINK_INDEX_SCALE_RESULT", workflow)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(
            "wom-kit/tools/benchmark_v0412_link_index.py text eol=lf",
            attributes,
        )

    def test_candidate_version_is_strictly_derived_from_source(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        version_globals = namespace["_source_expected_version"].__globals__
        original_package_root = version_globals["PACKAGE_ROOT"]
        with tempfile.TemporaryDirectory(
            prefix="wom-link-index-source-version-"
        ) as temporary:
            package_root = Path(temporary) / "wom_kit"
            package_root.mkdir()
            init_path = package_root / "__init__.py"
            version_globals["PACKAGE_ROOT"] = package_root
            try:
                init_path.write_text(
                    '"""Synthetic package."""\n\n__version__ = "9.8.7"\n',
                    encoding="utf-8",
                )
                self.assertEqual(
                    namespace["_source_expected_version"](),
                    "9.8.7",
                )

                invalid_sources = (
                    "__version__ = '9.8.7'\n",
                    '__version__ = "09.8.7"\n',
                    '__version__ = "9.8.7rc1"\n',
                    '__version__ = "9.8.7"\n__version__ = "9.8.8"\n',
                    '# __version__\nVERSION = "9.8.7"\n',
                )
                for invalid_source in invalid_sources:
                    with self.subTest(source=invalid_source):
                        init_path.write_text(invalid_source, encoding="utf-8")
                        with self.assertRaisesRegex(
                            namespace["BenchmarkContractError"],
                            "benchmark_source_version_invalid",
                        ):
                            namespace["_source_expected_version"]()
            finally:
                version_globals["PACKAGE_ROOT"] = original_package_root

    def test_candidate_wheel_metadata_must_match_source_version(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == "wom_kit" or name.startswith("wom_kit.")
        }
        for name in saved_modules:
            sys.modules.pop(name, None)
        try:
            with tempfile.TemporaryDirectory(
                prefix="wom-link-index-wrong-wheel-version-"
            ) as temporary:
                temporary_root = Path(temporary)
                wheel = _build_source_bound_test_wheel(
                    temporary_root,
                    version="99.99.99",
                )
                provenance = namespace["_provenance_document"](wheel)
                self.assertEqual(
                    provenance["source_version"],
                    _source_version(),
                )
                self.assertEqual(provenance["wheel_version"], "99.99.99")
                self.assertFalse(provenance["wheel_version_exact"])
                with self.assertRaisesRegex(
                    namespace["BenchmarkContractError"],
                    "benchmark_runtime_wheel_binding_mismatch",
                ):
                    with namespace["_activated_captured_wheel_runtime"](
                        wheel,
                        provenance,
                        runtime_root=temporary_root / "runtime",
                    ):
                        self.fail(
                            "version-mismatched wheel runtime was activated"
                        )
        finally:
            for name in tuple(sys.modules):
                if name == "wom_kit" or name.startswith("wom_kit."):
                    sys.modules.pop(name, None)
            sys.modules.update(saved_modules)

    def test_reduced_benchmark_captures_real_serialized_progress_and_provenance(
        self,
    ) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        full_profile = namespace["FULL_PROFILE"]
        reduced_profile = namespace["REDUCED_PROFILE"]
        self.assertEqual(full_profile.zettel_count, 8_616)
        self.assertEqual(full_profile.object_count, 22_441)
        self.assertEqual(full_profile.manifest_target_bytes, 37 * 1024 * 1024)

        environment = dict(os.environ)
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(
            prefix="wom-v0412-benchmark-test-wheel-"
        ) as temporary:
            wheel = _build_source_bound_test_wheel(Path(temporary))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BENCHMARK_PATH),
                    "--profile",
                    "reduced",
                    "--format",
                    "json",
                    "--wheel",
                    str(wheel),
                ],
                cwd=KIT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
                check=False,
            )
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 180.0)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(completed.returncode, 0, completed.stdout)
        report = json.loads(completed.stdout)

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["schema"], "wom-kit/v0412-link-index-benchmark/v0.2")
        self.assertEqual(report["profile"], "reduced")
        self.assertEqual(report["reason_codes"], [])
        self.assertEqual(report["counts"]["zettels"], reduced_profile.zettel_count)
        self.assertEqual(report["counts"]["objets"], reduced_profile.object_count)
        self.assertEqual(
            report["counts"]["manifest_size_bytes"],
            reduced_profile.manifest_target_bytes,
        )
        self.assertEqual(report["counts"]["ready_targets"], 1)
        self.assertEqual(report["counts"]["already_present_targets"], 1)

        for duration in report["setup_durations_seconds"].values():
            self.assertGreaterEqual(float(duration), 0.0)
        timing = report["plan_durations_seconds"]
        self.assertLessEqual(
            max(
                float(timing["cold_ready"]["p95"]),
                float(timing["cold_already_present"]["p95"]),
            ),
            20.0,
        )
        self.assertLessEqual(float(timing["warm_ready"]["p95"]), 5.0)
        self.assertLessEqual(float(timing["warm_already_present"]["p95"]), 5.0)
        self.assertEqual(timing["cold_ready"]["state"], "ready")
        self.assertEqual(timing["warm_ready"]["state"], "ready")
        self.assertEqual(timing["cold_already_present"]["state"], "already_present")
        self.assertEqual(timing["warm_already_present"]["state"], "already_present")

        self.assert_serialized_delivery(report)
        delivery = report["status_delivery"]
        expected_plan_calls = 2 * (
            reduced_profile.cold_iterations + reduced_profile.warm_iterations
        )
        self.assertEqual(delivery["serialized_stream_count"], expected_plan_calls)
        self.assertGreaterEqual(delivery["serialized_line_count"], expected_plan_calls * 2)
        self.assertGreaterEqual(delivery["serialized_flush_calls"], expected_plan_calls * 2)

        instrumentation = report["instrumentation"]
        self.assertEqual(instrumentation["normal_plan_calls"], expected_plan_calls)
        self.assertEqual(instrumentation["authority_lookup_calls"], expected_plan_calls)
        self.assertEqual(instrumentation["target_manifest_rows_returned"], expected_plan_calls)
        self.assertEqual(
            instrumentation["target_manifest_json_parses"],
            expected_plan_calls * 2,
        )
        self.assertEqual(instrumentation["non_target_lookup_json_parses"], 0)
        self.assertEqual(instrumentation["legacy_full_zettel_resolver_calls"], 0)
        self.assertEqual(instrumentation["full_manifest_json_parser_calls"], 0)

        provenance = report["provenance"]
        self.assert_provenance_hashes(provenance)
        self.assertEqual(
            provenance["source_tree_sha256"],
            provenance["wheel_package_tree_sha256"],
        )
        self.assertTrue(provenance["wheel_matches_source_tree"])
        self.assertTrue(provenance["wheel_distribution_exact"])
        self.assertTrue(provenance["wheel_version_exact"])
        self.assertEqual(provenance["source_version"], _source_version())
        self.assertEqual(provenance["wheel_version"], _source_version())
        self.assertRegex(
            provenance["loaded_runtime_package_tree_sha256"],
            SHA256_PATTERN,
        )
        self.assertRegex(
            provenance["loaded_runtime_initial_module_binding_sha256"],
            SHA256_PATTERN,
        )
        self.assertRegex(
            provenance["loaded_runtime_final_module_binding_sha256"],
            SHA256_PATTERN,
        )
        self.assertRegex(
            provenance["executing_benchmark_script_sha256"],
            SHA256_PATTERN,
        )
        self.assertRegex(
            provenance["bootstrap_supervisor_provenance_sha256"],
            SHA256_PATTERN,
        )
        self.assertEqual(
            provenance["executing_benchmark_script_sha256"],
            provenance["benchmark_script_sha256"],
        )
        self.assertIs(provenance["bootstrap_verified"], True)
        self.assertEqual(
            provenance["loaded_runtime_package_tree_sha256"],
            provenance["wheel_package_tree_sha256"],
        )
        self.assertGreaterEqual(
            provenance["loaded_runtime_final_module_count"],
            provenance["loaded_runtime_initial_module_count"],
        )
        self.assertFalse(provenance["private_paths_included"])
        self.assertFalse(provenance["release_evidence_eligible"])

        authority = report["authority"]
        self.assertRegex(authority["index_generation"], r"^gen:[0-9a-f]{32}$")
        self.assertRegex(authority["manifest_sha256"], SHA256_PATTERN)
        self.assertTrue(all(report["checks"].values()), report["checks"])
        self.assertTrue(
            all(value == 0 for value in report["output_safety"].values()),
            report["output_safety"],
        )
        self.assertIs(report["private_values_echoed"], False)
        self.assertIs(report["absolute_paths_echoed"], False)
        self.assertIs(report["zettel_ids_echoed"], False)
        self.assertIs(report["object_ids_echoed"], False)

        rendered = completed.stdout
        self.assertNotIn(namespace["PRIVATE_SENTINEL"], rendered)
        self.assertNotIn(str(KIT_ROOT), rendered)
        self.assertNotRegex(rendered, r"[A-Za-z]:[\\/]")
        self.assertIsNone(re.search(r"zet_[A-Za-z0-9]", rendered))
        self.assertNotIn(namespace["_object_id"](0), rendered)
        self.assertNotIn(namespace["_object_id"](1), rendered)
        self.assertNotIn("receipt", rendered.casefold())

    def test_loaded_driver_a_executes_captured_driver_b(self) -> None:
        """A supervisor already loaded from A must measure captured B, not A."""

        namespace = runpy.run_path(str(BENCHMARK_PATH))
        benchmark_globals = namespace["_capture_supervisor_authority"].__globals__
        original_bindings = {
            name: benchmark_globals[name]
            for name in (
                "BENCHMARK_PATH",
                "KIT_ROOT",
                "SOURCE_ROOT",
                "PACKAGE_ROOT",
            )
        }
        driver_a = BENCHMARK_PATH.read_bytes()
        driver_a_sha256 = "sha256:" + hashlib.sha256(driver_a).hexdigest()
        try:
            with tempfile.TemporaryDirectory(
                prefix="wom-v0412-driver-swap-"
            ) as temporary:
                temporary_root = Path(temporary)
                captured_wheel = _build_source_bound_test_wheel(
                    temporary_root
                )
                repo = temporary_root / "repo"
                kit = repo / "wom-kit"
                source = kit / "src"
                package = source / "wom_kit"
                tools = kit / "tools"
                package.mkdir(parents=True)
                tools.mkdir(parents=True)
                with zipfile.ZipFile(captured_wheel, "r") as wheel_archive:
                    for member in wheel_archive.infolist():
                        if member.is_dir() or not member.filename.startswith(
                            "wom_kit/"
                        ):
                            continue
                        target = source.joinpath(*member.filename.split("/"))
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(wheel_archive.read(member))

                driver_b_path = tools / "benchmark_v0412_link_index.py"
                driver_b = driver_a + b"\nDRIVER_SWAP_VARIANT = 'B'\n"
                driver_b_path.write_bytes(driver_b)
                driver_b_sha256 = (
                    "sha256:" + hashlib.sha256(driver_b).hexdigest()
                )
                self.assertNotEqual(driver_a_sha256, driver_b_sha256)

                for arguments in (
                    ("init",),
                    ("config", "core.autocrlf", "false"),
                    ("config", "user.name", "WOM Test"),
                    ("config", "user.email", "wom-test@example.invalid"),
                    ("add", "."),
                    ("commit", "-m", "captured driver B"),
                ):
                    subprocess.run(
                        ["git", *arguments],
                        cwd=repo,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                benchmark_globals.update(
                    {
                        "BENCHMARK_PATH": driver_b_path,
                        "KIT_ROOT": kit,
                        "SOURCE_ROOT": source,
                        "PACKAGE_ROOT": package,
                    }
                )
                args = namespace["build_parser"]().parse_args(
                    [
                        "--profile",
                        "reduced",
                        "--format",
                        "json",
                        "--wheel",
                        str(captured_wheel),
                    ]
                )
                completed = namespace["_launch_captured_worker"](args)
                self.assertEqual(completed.stderr, b"")
                self.assertEqual(completed.returncode, 0, completed.stdout)
                report = json.loads(completed.stdout.decode("utf-8"))

                self.assertTrue(report["ok"], report)
                self.assertTrue(
                    report["checks"]["captured_driver_bootstrap_verified"]
                )
                self.assertEqual(
                    report["provenance"]["benchmark_script_sha256"],
                    driver_b_sha256,
                )
                self.assertEqual(
                    report["provenance"][
                        "executing_benchmark_script_sha256"
                    ],
                    driver_b_sha256,
                )
                self.assertNotEqual(
                    report["provenance"][
                        "executing_benchmark_script_sha256"
                    ],
                    driver_a_sha256,
                )
                self.assertTrue(
                    report["provenance"]["bootstrap_verified"]
                )
        finally:
            benchmark_globals.update(original_bindings)

    def test_import_window_uses_exact_captured_wheel_runtime(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        benchmark_globals = namespace["_provenance_document"].__globals__
        saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == "wom_kit" or name.startswith("wom_kit.")
        }
        for name in saved_modules:
            sys.modules.pop(name, None)
        original_source_root = benchmark_globals["SOURCE_ROOT"]
        original_package_root = benchmark_globals["PACKAGE_ROOT"]
        try:
            with tempfile.TemporaryDirectory(
                prefix="wom-v0412-runtime-binding-"
            ) as temporary:
                temporary_root = Path(temporary)
                wheel = _build_source_bound_test_wheel(temporary_root)
                initial_provenance = namespace["_provenance_document"](
                    wheel
                )

                # Simulate source A becoming hostile source B only during the
                # import window, then returning to A before final provenance.
                # The measured modules must still come from captured wheel A.
                poisoned_source = temporary_root / "poisoned" / "src"
                poisoned_package = poisoned_source / "wom_kit"
                poisoned_package.mkdir(parents=True)
                (poisoned_package / "__init__.py").write_text(
                    "POISONED_RUNTIME = True\n",
                    encoding="utf-8",
                )
                (poisoned_package / "archive_services.py").write_text(
                    "raise RuntimeError('source B was imported')\n",
                    encoding="utf-8",
                )
                benchmark_globals["SOURCE_ROOT"] = poisoned_source
                benchmark_globals["PACKAGE_ROOT"] = poisoned_package
                clean_sys_path = list(sys.path)
                sys.path.insert(0, str(poisoned_source))
                runtime_root = temporary_root / "runtime-a"
                try:
                    with namespace[
                        "_activated_captured_wheel_runtime"
                    ](
                        wheel,
                        initial_provenance,
                        runtime_root=runtime_root,
                    ) as authority:
                        binding = authority.snapshot()
                        loaded_services = benchmark_globals[
                            "archive_services"
                        ]
                        loaded_path = Path(
                            str(loaded_services.__file__)
                        ).resolve()
                        loaded_path.relative_to(runtime_root.resolve())
                        self.assertFalse(
                            getattr(
                                loaded_services,
                                "POISONED_RUNTIME",
                                False,
                            )
                        )
                        self.assertEqual(
                            binding["runtime_package_tree_sha256"],
                            initial_provenance[
                                "wheel_package_tree_sha256"
                            ],
                        )
                        self.assertGreaterEqual(
                            int(binding["loaded_module_count"]),
                            4,
                        )
                finally:
                    try:
                        sys.path.remove(str(poisoned_source))
                    except ValueError:
                        pass

                benchmark_globals["SOURCE_ROOT"] = original_source_root
                benchmark_globals["PACKAGE_ROOT"] = original_package_root
                final_provenance = namespace["_provenance_document"](wheel)
                self.assertEqual(final_provenance, initial_provenance)
                self.assertFalse(
                    any(
                        name == "wom_kit" or name.startswith("wom_kit.")
                        for name in sys.modules
                    )
                )
                self.assertEqual(sys.path, clean_sys_path)

                # A second activation in the same interpreter proves that the
                # first run left no source path, module, or benchmark-global
                # authority behind.
                with namespace["_activated_captured_wheel_runtime"](
                    wheel,
                    initial_provenance,
                    runtime_root=temporary_root / "runtime-repeat",
                ) as repeat_authority:
                    self.assertGreaterEqual(
                        int(
                            repeat_authority.snapshot()[
                                "loaded_module_count"
                            ]
                        ),
                        4,
                    )
                self.assertFalse(
                    any(
                        name == "wom_kit" or name.startswith("wom_kit.")
                        for name in sys.modules
                    )
                )
                self.assertEqual(sys.path, clean_sys_path)

                sys.modules["wom_kit"] = mock.Mock()
                try:
                    with self.assertRaisesRegex(
                        namespace["BenchmarkContractError"],
                        "benchmark_runtime_preloaded",
                    ):
                        with namespace[
                            "_activated_captured_wheel_runtime"
                        ](
                            wheel,
                            initial_provenance,
                            runtime_root=temporary_root / "runtime-b",
                        ):
                            self.fail("preloaded runtime was accepted")
                finally:
                    sys.modules.pop("wom_kit", None)
        finally:
            benchmark_globals["SOURCE_ROOT"] = original_source_root
            benchmark_globals["PACKAGE_ROOT"] = original_package_root
            for name in tuple(sys.modules):
                if name == "wom_kit" or name.startswith("wom_kit."):
                    sys.modules.pop(name, None)
            sys.modules.update(saved_modules)

    def test_unsafe_wheel_members_fail_closed_before_materialization(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))

        def unsafe_wheel(member_name: str, *, external_attr: int = 0) -> bytes:
            stream = io.BytesIO()
            with zipfile.ZipFile(
                stream,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr("wom_kit/__init__.py", "")
                member = zipfile.ZipInfo(member_name)
                member.external_attr = external_attr
                archive.writestr(member, "unsafe")
                archive.writestr(
                    "wom_kit-0.4.12.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: wom-kit\nVersion: 0.4.12\n",
                )
                archive.writestr(
                    "wom_kit-0.4.12.dist-info/WHEEL",
                    "Wheel-Version: 1.0\nTag: py3-none-any\n",
                )
            return stream.getvalue()

        cases = (
            unsafe_wheel("../outside.py"),
            unsafe_wheel("/absolute.py"),
            unsafe_wheel("C:/absolute.py"),
            unsafe_wheel(
                "wom_kit/symlink.py",
                external_attr=(stat.S_IFLNK | 0o777) << 16,
            ),
            unsafe_wheel(
                "wom_kit/reparse.py",
                external_attr=0x0400,
            ),
        )
        for wheel_raw in cases:
            with self.subTest(wheel_sha256=hashlib.sha256(wheel_raw).hexdigest()):
                with self.assertRaisesRegex(
                    namespace["BenchmarkContractError"],
                    "benchmark_wheel_member_unsafe",
                ):
                    namespace["_wheel_package_inventory_from_bytes"](
                        wheel_raw
                    )

    def test_serialized_safety_counts_private_values_without_echoing_them(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        sentinel = namespace["PRIVATE_SENTINEL"]
        zettel_id = namespace["_zettel_id"](0)
        object_id = namespace["_object_id"](0)
        serialized = "\n".join((sentinel, zettel_id, object_id))
        safety = namespace["_serialized_output_safety"](
            serialized,
            forbidden_values=(sentinel, zettel_id, object_id),
            zettel_ids=(zettel_id,),
            object_ids=(object_id,),
        )
        self.assertGreater(safety["private_sentinel_occurrences"], 0)
        self.assertGreater(safety["zettel_id_occurrences"], 0)
        self.assertGreater(safety["object_id_occurrences"], 0)
        rendered = json.dumps(safety, sort_keys=True)
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn(zettel_id, rendered)
        self.assertNotIn(object_id, rendered)

    def test_serialized_safety_detects_non_target_ids_and_all_bodies(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        sentinel = namespace["PRIVATE_SENTINEL"]
        zettel_ids = tuple(namespace["_zettel_id"](index) for index in range(5))
        object_ids = tuple(namespace["_object_id"](index) for index in range(5))
        non_target_zettel = zettel_ids[4]
        non_target_object = object_ids[4]
        unrelated_sha256 = "sha256:" + ("f" * 64)
        serialized = "\n".join(
            (
                non_target_zettel + "_receipt",
                non_target_object + "0",
                unrelated_sha256,
            )
        )

        safety = namespace["_serialized_output_safety"](
            serialized,
            forbidden_values=(),
            zettel_ids=zettel_ids,
            object_ids=object_ids,
        )

        self.assertEqual(safety["zettel_id_occurrences"], 1)
        self.assertEqual(safety["object_id_occurrences"], 1)
        non_target_body = namespace["_zettel_text"](
            4,
            existing_object_id=object_ids[1],
        ).split("---\n", 2)[-1]
        self.assertEqual(non_target_body, "\n" + sentinel + "\n")
        rendered = json.dumps(safety, sort_keys=True)
        self.assertNotIn(non_target_zettel, rendered)
        self.assertNotIn(non_target_object, rendered)
        self.assertNotIn(sentinel, rendered)

    def test_serialized_safety_detects_runner_independent_absolute_paths(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        safety = namespace["_serialized_output_safety"](
            'path=/workspace/private\npath="D:\\private"\npath=\\\\server\\share',
            forbidden_values=(),
            zettel_ids=(),
            object_ids=(),
        )
        self.assertGreaterEqual(safety["absolute_path_occurrences"], 3)
        rendered = json.dumps(safety, sort_keys=True)
        self.assertNotIn("workspace", rendered)
        self.assertNotIn("server", rendered)

    def test_full_profile_commit_binding_rejects_git_status_only_change(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        provenance = {
            "source_tree_matches_git_commit": True,
            "benchmark_script_matches_git_commit": True,
            "source_inventory_delta_count": 0,
            "git_status_change_count": 0,
            "scoped_uncommitted_entry_count": 0,
        }
        self.assertTrue(
            namespace["_profile_source_bound_to_commit"](
                namespace["FULL_PROFILE"],
                provenance,
            )
        )
        provenance["git_status_change_count"] = 1
        self.assertFalse(
            namespace["_profile_source_bound_to_commit"](
                namespace["FULL_PROFILE"],
                provenance,
            )
        )
        self.assertTrue(
            namespace["_profile_source_bound_to_commit"](
                namespace["REDUCED_PROFILE"],
                provenance,
            )
        )

    def test_dangling_package_symlink_fails_closed_before_file_filter(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        with tempfile.TemporaryDirectory(
            prefix="wom-v0412-dangling-package-link-"
        ) as temporary:
            source = Path(temporary) / "src"
            package = source / "wom_kit"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("# fixture\n", encoding="utf-8")
            dangling = package / "ignored-link.py"
            try:
                dangling.symlink_to(package / "missing-target.py")
            except OSError:
                # Windows may not grant symlink creation. Emulate exactly the
                # relevant dangling-entry contract: link-like is true while
                # is_file is false, and prove the link check runs first.
                dangling.write_text("placeholder\n", encoding="utf-8")
                original_is_symlink = Path.is_symlink
                original_is_file = Path.is_file

                def is_symlink(candidate: Path) -> bool:
                    return candidate == dangling or original_is_symlink(candidate)

                def is_file(candidate: Path) -> bool:
                    return candidate != dangling and original_is_file(candidate)

                link_context = mock.patch.object(
                    Path,
                    "is_symlink",
                    autospec=True,
                    side_effect=is_symlink,
                )
                file_context = mock.patch.object(
                    Path,
                    "is_file",
                    autospec=True,
                    side_effect=is_file,
                )
            else:
                link_context = nullcontext()
                file_context = nullcontext()

            benchmark_globals = namespace["_source_package_inventory"].__globals__
            benchmark_globals["SOURCE_ROOT"] = source
            benchmark_globals["PACKAGE_ROOT"] = package
            with link_context, file_context:
                with self.assertRaisesRegex(
                    namespace["BenchmarkContractError"],
                    "source_package_symlink_forbidden",
                ):
                    namespace["_source_package_inventory"]()

    def test_missing_wheel_failure_does_not_echo_the_supplied_path(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONUTF8"] = "1"
        with tempfile.TemporaryDirectory(
            prefix="wom-v0412-missing-wheel-"
        ) as temporary:
            missing = Path(temporary) / "private-name.whl"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BENCHMARK_PATH),
                    "--profile",
                    "reduced",
                    "--format",
                    "json",
                    "--wheel",
                    str(missing),
                ],
                cwd=KIT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stderr, "")
            self.assertNotIn(str(missing), completed.stdout)
            self.assertNotIn(temporary, completed.stdout)
        report = json.loads(completed.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["reason_codes"], ["benchmark_internal_error"])
        self.assertEqual(
            report["schema"],
            "wom-kit/v0412-link-index-benchmark/v0.2",
        )
        self.assertFalse(report["private_values_echoed"])
        self.assertFalse(report["absolute_paths_echoed"])
        self.assertFalse(report["zettel_ids_echoed"])
        self.assertFalse(report["object_ids_echoed"])

    def test_gitignored_package_member_cannot_claim_commit_binding(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        with tempfile.TemporaryDirectory(
            prefix="wom-v0412-ignored-package-proof-"
        ) as temporary:
            repo = Path(temporary)
            kit = repo / "wom-kit"
            source = kit / "src"
            package = source / "wom_kit"
            tools = kit / "tools"
            package.mkdir(parents=True)
            tools.mkdir(parents=True)
            (package / "__init__.py").write_text(
                '__version__ = "9.8.7"\n',
                encoding="utf-8",
            )
            benchmark = tools / "benchmark_v0412_link_index.py"
            benchmark.write_text(
                "# committed synthetic benchmark\n",
                encoding="utf-8",
            )
            (repo / ".gitignore").write_text(
                "wom-kit/src/wom_kit/ghost.py\n",
                encoding="utf-8",
            )
            for arguments in (
                ("init",),
                ("config", "core.autocrlf", "false"),
                ("config", "user.name", "WOM Test"),
                ("config", "user.email", "wom-test@example.invalid"),
                ("add", "."),
                ("commit", "-m", "synthetic committed package"),
            ):
                subprocess.run(
                    ["git", *arguments],
                    cwd=repo,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            ignored = package / "ghost.py"
            ignored.write_text(
                "IGNORED_PACKAGE_MEMBER = True\n",
                encoding="utf-8",
            )
            wheel = repo / "wom_kit-9.8.7-py3-none-any.whl"
            with zipfile.ZipFile(
                wheel,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.write(
                    package / "__init__.py",
                    "wom_kit/__init__.py",
                )
                archive.write(ignored, "wom_kit/ghost.py")
                archive.writestr(
                    "wom_kit-9.8.7.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: wom-kit\nVersion: 9.8.7\n",
                )
                archive.writestr(
                    "wom_kit-9.8.7.dist-info/WHEEL",
                    "Wheel-Version: 1.0\nTag: py3-none-any\n",
                )

            benchmark_globals = namespace["_provenance_document"].__globals__
            benchmark_globals["KIT_ROOT"] = kit
            benchmark_globals["SOURCE_ROOT"] = source
            benchmark_globals["PACKAGE_ROOT"] = package
            benchmark_globals["BENCHMARK_PATH"] = benchmark
            provenance = namespace["_provenance_document"](wheel)

        self.assertTrue(provenance["wheel_matches_source_tree"])
        self.assertEqual(provenance["source_version"], "9.8.7")
        self.assertEqual(provenance["wheel_version"], "9.8.7")
        self.assertTrue(provenance["wheel_version_exact"])
        self.assertFalse(provenance["source_tree_matches_git_commit"])
        self.assertEqual(provenance["source_inventory_delta_count"], 1)
        self.assertEqual(provenance["git_status_change_count"], 0)
        self.assertGreaterEqual(
            provenance["scoped_uncommitted_entry_count"],
            1,
        )

    def test_sha256_git_inventory_uses_literal_package_pathspec(self) -> None:
        namespace = runpy.run_path(str(BENCHMARK_PATH))
        with tempfile.TemporaryDirectory(
            prefix="wom-v0412-sha256-git-proof-"
        ) as temporary:
            repo = Path(temporary)
            initialized = subprocess.run(
                ["git", "init", "--object-format=sha256"],
                cwd=repo,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if initialized.returncode != 0:
                self.skipTest("Git SHA-256 repository support unavailable")

            kit = repo / "wom-kit"
            source = kit / "src"
            package = source / "wom_kit"
            tools = kit / "tools"
            package.mkdir(parents=True)
            tools.mkdir(parents=True)
            package_member = package / "__init__.py"
            package_member.write_text(
                '__version__ = "0.4.12"\n',
                encoding="utf-8",
            )
            # A textual-prefix sibling must not enter the literal package
            # inventory selected for wom_kit/.
            (source / "wom_kit_shadow.py").write_text(
                "SHADOW = True\n",
                encoding="utf-8",
            )
            benchmark = tools / "benchmark_v0412_link_index.py"
            benchmark.write_text("# sha256 benchmark\n", encoding="utf-8")
            for arguments in (
                ("config", "core.autocrlf", "false"),
                ("config", "user.name", "WOM Test"),
                ("config", "user.email", "wom-test@example.invalid"),
                ("add", "."),
                ("commit", "-m", "sha256 synthetic package"),
            ):
                subprocess.run(
                    ["git", *arguments],
                    cwd=repo,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            wheel = repo / "wom_kit-0.4.12-py3-none-any.whl"
            with zipfile.ZipFile(
                wheel,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.write(package_member, "wom_kit/__init__.py")
                archive.writestr(
                    "wom_kit-0.4.12.dist-info/METADATA",
                    "Metadata-Version: 2.1\nName: wom-kit\nVersion: 0.4.12\n",
                )
                archive.writestr(
                    "wom_kit-0.4.12.dist-info/WHEEL",
                    "Wheel-Version: 1.0\nTag: py3-none-any\n",
                )

            benchmark_globals = namespace["_provenance_document"].__globals__
            benchmark_globals["KIT_ROOT"] = kit
            benchmark_globals["SOURCE_ROOT"] = source
            benchmark_globals["PACKAGE_ROOT"] = package
            benchmark_globals["BENCHMARK_PATH"] = benchmark
            committed_inventory = namespace["_git_head_package_inventory"](
                "wom-kit/src"
            )
            provenance = namespace["_provenance_document"](wheel)

        self.assertEqual(set(committed_inventory), {"wom_kit/__init__.py"})
        self.assertRegex(provenance["git_commit_oid"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(
            provenance["git_source_tree_oid"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertTrue(provenance["source_tree_matches_git_commit"])
        self.assertTrue(provenance["benchmark_script_matches_git_commit"])
        self.assertEqual(provenance["git_status_change_count"], 0)


if __name__ == "__main__":
    unittest.main()
