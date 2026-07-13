from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = KIT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from wom_kit import archive_cli  # noqa: E402


def run_benchmark(*, file_count: int, files_per_directory: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".gitignore").write_text(
            "\n".join(archive_cli.RECOMMENDED_GITIGNORE_PATTERNS) + "\n",
            encoding="utf-8",
        )
        for index in range(file_count):
            folder = root / f"batch-{index // files_per_directory:05d}"
            folder.mkdir(exist_ok=True)
            (folder / f"safe-{index:07d}.json").write_text(
                '{"kind":"synthetic-safe-record"}\n',
                encoding="utf-8",
            )

        events: list[tuple[str, str, int | None, int | None]] = []
        doctor = archive_cli.Doctor(root, progress_callback=lambda *event: events.append(event))
        started = time.perf_counter()
        doctor._check_local_profile_and_secret_safety()
        elapsed = time.perf_counter() - started
        summary_messages = [
            message
            for stage, message, _current, _total in events
            if stage == "local-profile-secret-safety"
            and message.startswith("local profile secret safety summary ")
        ]
        expected_checked_files = file_count + 1
        errors = [item.as_dict() for item in doctor.diagnostics if item.severity == "ERROR"]
        warnings = [item.as_dict() for item in doctor.diagnostics if item.severity == "WARN"]
        summary = summary_messages[-1] if summary_messages else None
        expected_summary = (
            "local profile secret safety summary "
            f"checked_files={expected_checked_files} content_scanned={file_count} "
            "local_profiles=0 skipped_dirs=0"
        )
        ok = not errors and not warnings and summary == expected_summary
        return {
            "ok": ok,
            "schema": "wom-kit/local-profile-secret-safety-benchmark/v0.1",
            "fixture": {
                "safe_json_file_count": file_count,
                "gitignore_file_count": 1,
                "expected_checked_file_count": expected_checked_files,
                "files_per_directory": files_per_directory,
                "real_archive_read": False,
            },
            "result": {
                "elapsed_seconds": round(elapsed, 6),
                "files_per_second": round(expected_checked_files / max(elapsed, 0.000001), 3),
                "summary": summary,
                "error_count": len(errors),
                "warning_count": len(warnings),
                "archive_text_scanned_for_secret_patterns": doctor.read_observations()[
                    "archive_text_scanned_for_secret_patterns"
                ],
            },
            "claim_boundary": (
                "This synthetic benchmark measures the local profile and secret-safety walk on small safe JSON "
                "files. Real archive timing also depends on file sizes, storage, antivirus, and filesystem state."
            ),
            "safety": {
                "provider_api_called": False,
                "credential_store_read": False,
                "persistent_files_written": False,
                "temporary_fixture_files_written": True,
                "private_values_emitted": False,
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark local-profile secret-safety scanning with a temporary synthetic archive."
    )
    parser.add_argument("--file-count", type=int, default=5000)
    parser.add_argument("--files-per-directory", type=int, default=100)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)
    if not 1 <= args.file_count <= 100000:
        parser.error("--file-count must be between 1 and 100000")
    if not 1 <= args.files_per_directory <= 10000:
        parser.error("--files-per-directory must be between 1 and 10000")

    result = run_benchmark(
        file_count=args.file_count,
        files_per_directory=args.files_per_directory,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        benchmark = result["result"]
        print("WOM local-profile secret-safety synthetic benchmark")
        print(f"Complete: {result['ok']}")
        print(f"Checked files: {result['fixture']['expected_checked_file_count']}")
        print(f"Elapsed: {benchmark['elapsed_seconds']:.3f}s")
        print(f"Rate: {benchmark['files_per_second']:.2f} files/s")
        print("Real archive read: no")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
