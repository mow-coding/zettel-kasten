from __future__ import annotations

import argparse
import io
import json
import sys
import time
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any, Callable


KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = KIT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from wom_kit import archive_cli  # noqa: E402


ProgressCallback = Callable[[str, str, int | None, int | None], None]


def emit_synthetic_progress(
    callback: ProgressCallback,
    *,
    source_count: int,
    index_receipt_count: int,
) -> dict[str, int]:
    callback("edge-receipt-index", "start", None, None)
    callback("edge-receipt-index", "scanned", 0, index_receipt_count)
    index_milestones = {1, index_receipt_count}
    index_milestones.update(range(250, index_receipt_count, 250))
    for current in sorted(index_milestones):
        callback("edge-receipt-index", "scanned", current, index_receipt_count)
    callback("edge-receipt-index", "done", index_receipt_count, index_receipt_count)

    callback("edge-receipt-source-load", "start", None, None)
    candidate_total = 0
    cache_hits = 0
    for source_index in range(source_count):
        candidate_count = (source_index % 18) + 1
        candidate_total += candidate_count
        callback("edge-receipt-source-load-detail", "start", None, None)
        callback("edge-receipt-source-load-detail", "loaded", 0, candidate_count)
        callback("edge-receipt-source-load-detail", "loaded", 1, candidate_count)
        if candidate_count > 1:
            callback(
                "edge-receipt-source-load-detail",
                "loaded",
                candidate_count,
                candidate_count,
            )
        callback(
            "edge-receipt-source-load-detail",
            "done",
            candidate_count,
            candidate_count,
        )
        if source_index and source_index % 25 == 0:
            cache_hits += 1
            callback("edge-receipt-source-load-detail", "cache_hit", None, None)
        callback(
            "edge-receipt-source-load",
            f"aggregate sources={source_index + 1} candidates={candidate_total} cache_hits={cache_hits}",
            None,
            None,
        )
    callback(
        "edge-receipt-source-load",
        f"done sources={source_count} candidates={candidate_total} cache_hits={cache_hits}",
        None,
        None,
    )
    return {
        "sources": source_count,
        "candidates": candidate_total,
        "cache_hits": cache_hits,
    }


def measure_direct(
    *,
    detail: str,
    source_count: int,
    index_receipt_count: int,
) -> dict[str, Any]:
    stream = io.StringIO()
    callback = archive_cli.make_stage_progress_callback(
        True,
        label=f"doctor-{detail}",
        detail=detail,
    )
    assert callback is not None
    started = time.perf_counter()
    with redirect_stderr(stream):
        totals = emit_synthetic_progress(
            callback,
            source_count=source_count,
            index_receipt_count=index_receipt_count,
        )
    elapsed = time.perf_counter() - started
    output = stream.getvalue()
    return {
        "elapsed_seconds": round(elapsed, 6),
        "line_count": len(output.splitlines()),
        "utf8_bytes": len(output.encode("utf-8")),
        "final_summary_present": (
            f"done sources={totals['sources']} candidates={totals['candidates']} "
            f"cache_hits={totals['cache_hits']}"
        ) in output,
    }


def measure_shared(
    *,
    source_count: int,
    index_receipt_count: int,
) -> dict[str, Any]:
    stream = io.StringIO()
    started = time.perf_counter()
    with redirect_stderr(stream):
        reporter = archive_cli.CommandProgressReporter(
            True,
            label="runtime-context",
            heartbeat_interval_seconds=3600.0,
        )
        totals = emit_synthetic_progress(
            reporter.progress,
            source_count=source_count,
            index_receipt_count=index_receipt_count,
        )
        reporter.close()
    elapsed = time.perf_counter() - started
    output = stream.getvalue()
    return {
        "elapsed_seconds": round(elapsed, 6),
        "line_count": len(output.splitlines()),
        "utf8_bytes": len(output.encode("utf-8")),
        "final_summary_present": (
            f"done sources={totals['sources']} candidates={totals['candidates']} "
            f"cache_hits={totals['cache_hits']}"
        ) in output,
    }


def run_benchmark(*, source_count: int, index_receipt_count: int) -> dict[str, Any]:
    compact = measure_direct(
        detail="compact",
        source_count=source_count,
        index_receipt_count=index_receipt_count,
    )
    shared = measure_shared(
        source_count=source_count,
        index_receipt_count=index_receipt_count,
    )
    verbose = measure_direct(
        detail="verbose",
        source_count=source_count,
        index_receipt_count=index_receipt_count,
    )
    verbose_lines = max(1, int(verbose["line_count"]))
    verbose_bytes = max(1, int(verbose["utf8_bytes"]))
    line_reduction = 1.0 - (int(shared["line_count"]) / verbose_lines)
    byte_reduction = 1.0 - (int(shared["utf8_bytes"]) / verbose_bytes)
    timing_ratio = (
        float(verbose["elapsed_seconds"]) / max(float(shared["elapsed_seconds"]), 0.000001)
    )
    ok = (
        compact["line_count"] <= 4
        and shared["line_count"] <= 4
        and verbose["line_count"] > source_count * 4
        and compact["final_summary_present"]
        and shared["final_summary_present"]
        and line_reduction >= 0.99
        and byte_reduction >= 0.99
    )
    return {
        "ok": ok,
        "schema": "wom-kit/doctor-progress-volume-benchmark/v0.1",
        "fixture": {
            "source_load_count": source_count,
            "edge_receipt_index_count": index_receipt_count,
            "real_archive_read": False,
            "synthetic_events_only": True,
        },
        "results": {
            "direct_compact": compact,
            "shared_runtime_compact": shared,
            "direct_verbose": verbose,
        },
        "comparison": {
            "shared_line_reduction_fraction": round(line_reduction, 6),
            "shared_byte_reduction_fraction": round(byte_reduction, 6),
            "verbose_to_shared_elapsed_ratio": round(timing_ratio, 3),
            "timing_claim_boundary": (
                "In-memory stderr capture measures Python formatting/write overhead only; "
                "an interactive terminal can add more rendering cost."
            ),
        },
        "safety": {
            "provider_api_called": False,
            "credential_store_read": False,
            "files_written": False,
            "private_values_emitted": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark compact versus verbose Doctor progress using content-free synthetic events."
    )
    parser.add_argument("--source-count", type=int, default=8583)
    parser.add_argument("--index-receipt-count", type=int, default=21539)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)
    if not 1 <= args.source_count <= 50000:
        parser.error("--source-count must be between 1 and 50000")
    if not 1 <= args.index_receipt_count <= 1000000:
        parser.error("--index-receipt-count must be between 1 and 1000000")

    result = run_benchmark(
        source_count=args.source_count,
        index_receipt_count=args.index_receipt_count,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        shared = result["results"]["shared_runtime_compact"]
        verbose = result["results"]["direct_verbose"]
        comparison = result["comparison"]
        print("WOM Doctor progress-volume synthetic benchmark")
        print(f"Complete: {result['ok']}")
        print(f"Shared compact lines: {shared['line_count']}")
        print(f"Verbose lines: {verbose['line_count']}")
        print(f"Line reduction: {comparison['shared_line_reduction_fraction']:.2%}")
        print(f"Verbose/shared elapsed ratio: {comparison['verbose_to_shared_elapsed_ratio']}x")
        print("Real archive read: no")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
