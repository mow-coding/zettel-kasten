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

from wom_kit import archive_services  # noqa: E402
from wom_kit import archive_cli  # noqa: E402


def write_fixture(root: Path, receipt_count: int) -> float:
    started = time.perf_counter()
    edge_root = root / archive_services.ZETTEL_EDGE_RECEIPTS_DIR
    edge_root.mkdir(parents=True)
    for index in range(receipt_count):
        source_id = f"zet_20260712_edge_benchmark_{index:05d}"
        payload = {
            "receipt_kind": "zettel_edge_write",
            "source_zettel_path": f"zettels/{source_id}.md",
            "edge_id": f"edge:benchmark:{index:05d}",
            "created_at": "2026-07-12T00:00:00Z",
        }
        receipt_path = edge_root / f"{source_id}.semantic.{index:05d}.zettel-edge.json"
        receipt_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return time.perf_counter() - started


def run_benchmark(root: Path, *, receipt_count: int, target_index: int) -> dict[str, Any]:
    progress_events: list[tuple[str, str, int | None, int | None]] = []
    doctor = archive_cli.Doctor(
        root,
        progress_callback=lambda stage, message, current, total: progress_events.append(
            (stage, message, current, total)
        ),
    )
    target_id = f"zet_20260712_edge_benchmark_{target_index:05d}"
    target_relative = f"zettels/{target_id}.md"
    started = time.perf_counter()
    target_receipts = doctor._edge_receipts_for_source(
        target_relative,
        source_zettel_id=target_id,
    )
    first_lookup_seconds = time.perf_counter() - started
    started = time.perf_counter()
    cached_receipts = doctor._edge_receipts_for_source(
        target_relative,
        source_zettel_id=target_id,
    )
    cached_lookup_seconds = time.perf_counter() - started

    path_index = doctor.edge_receipt_paths_by_source_segment or {}
    source_segment = archive_services.zettel_edge_filename_segment(target_id)
    candidate_count = len(path_index.get(source_segment, []))
    index_build_count = sum(
        1 for stage, message, _current, _total in progress_events
        if stage == "edge-receipt-index" and message == "start"
    )
    source_load_count = sum(
        1 for stage, message, _current, _total in progress_events
        if stage == "edge-receipt-source-load" and message == "start"
    )
    filename_index_completed = (
        "edge-receipt-index",
        "done",
        receipt_count,
        receipt_count,
    ) in progress_events
    ok = (
        len(path_index) == receipt_count
        and candidate_count == 1
        and len(target_receipts) == 1
        and target_receipts is cached_receipts
        and index_build_count == 1
        and source_load_count == 1
        and filename_index_completed
    )
    return {
        "ok": ok,
        "schema": "wom-kit/doctor-edge-receipt-index-benchmark/v0.1",
        "fixture": {
            "edge_receipt_count": receipt_count,
            "source_group_count": len(path_index),
            "target_index": target_index,
            "target_candidate_count": candidate_count,
        },
        "result": {
            "target_receipts_loaded": len(target_receipts),
            "filename_index_completed": filename_index_completed,
            "doctor_index_build_count": index_build_count,
            "doctor_target_load_count": source_load_count,
            "second_lookup_used_cache": target_receipts is cached_receipts,
            "full_receipt_corpus_opened": False,
            "targeted_receipt_documents_opened": candidate_count,
        },
        "timing_seconds": {
            "doctor_first_lookup": round(first_lookup_seconds, 6),
            "doctor_cached_lookup": round(cached_lookup_seconds, 6),
        },
        "safety": {
            "real_archive_read": False,
            "temporary_fixture_only": True,
            "provider_api_called": False,
            "files_persisted": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the full-Doctor edge receipt index phase against a temporary synthetic archive."
    )
    parser.add_argument(
        "--receipt-count",
        type=int,
        default=8583,
        help="Synthetic edge receipt count (1-20000).",
    )
    parser.add_argument("--target-index", type=int, default=8, help="Synthetic source index to load after indexing.")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)
    if not 1 <= args.receipt_count <= 20000:
        parser.error("--receipt-count must be between 1 and 20000")
    if not 0 <= args.target_index < args.receipt_count:
        parser.error("--target-index must refer to a generated receipt")

    with tempfile.TemporaryDirectory(prefix="wom-doctor-edge-index-benchmark-") as tmp:
        archive_root = Path(tmp) / "archive"
        fixture_seconds = write_fixture(archive_root, args.receipt_count)
        result = run_benchmark(
            archive_root,
            receipt_count=args.receipt_count,
            target_index=args.target_index,
        )
        result["timing_seconds"]["fixture_generation"] = round(fixture_seconds, 6)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        fixture = result["fixture"]
        timing = result["timing_seconds"]
        print("WOM Doctor edge-receipt index synthetic benchmark")
        print(f"Complete: {result['ok']}")
        print(f"Doctor first lookup: {fixture['edge_receipt_count']} receipts in {timing['doctor_first_lookup']}s")
        print(f"Doctor index builds: {result['result']['doctor_index_build_count']}")
        print(f"Target receipt documents opened: {result['result']['targeted_receipt_documents_opened']}")
        print(f"Doctor cached lookup seconds: {timing['doctor_cached_lookup']}")
        print("Real archive read: no")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
