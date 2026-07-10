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


def benchmark_abstract(index: int, char_count: int) -> str:
    seed = f"Benchmark abstract {index}. Local node memory and connection context. "
    repeated = (seed + "deterministic coverage evidence. ") * ((char_count // len(seed)) + 2)
    return repeated[:char_count].rstrip()


def write_fixture_archive(root: Path, *, zet_count: int, abstract_chars: int) -> float:
    started = time.perf_counter()
    zettels_root = root / "zettels"
    zettels_root.mkdir(parents=True)
    (root / "archive.yml").write_text(
        "archive_id: archive:personal:zet-catalog-benchmark\ntype: personal\n",
        encoding="utf-8",
    )
    for index in range(zet_count):
        zettel_id = f"zet_20260711_benchmark_{index:05d}"
        edge = "edges: []\n"
        if index:
            edge = (
                "edges:\n"
                "  - type: references\n"
                f"    target: zet_20260711_benchmark_{index - 1:05d}\n"
            )
        text = (
            "---\n"
            f"id: {zettel_id}\n"
            f"title: Benchmark zet {index}\n"
            "status: canonical\n"
            "kind: benchmark_fixture\n"
            f"abstract: {benchmark_abstract(index, abstract_chars)}\n"
            "facets:\n"
            "  domain: benchmark\n"
            + edge
            + "---\n\n# Benchmark body\n\nBODY_IS_NOT_PART_OF_THE_CATALOG\n"
        )
        (zettels_root / f"{zettel_id}.md").write_text(text, encoding="utf-8")
    return time.perf_counter() - started


def run_catalog_benchmark(
    root: Path,
    *,
    zet_count: int,
    page_size: int,
    max_estimated_tokens: int | None,
    projection: str,
    coverage_mode: str,
) -> dict[str, Any]:
    item_cache: dict[str, dict[str, Any]] = {}
    cursor = 0
    snapshot_id: str | None = None
    continuation_token: str | None = None
    collected_ids: list[str] = []
    page_seconds: list[float] = []
    frontmatter_files_scanned = 0
    cached_items_reused = 0
    path_metadata_checked = 0
    materialized_snapshot_pages = 0
    completion_revalidation_pages = 0
    max_page_estimated_items_json_tokens = 0
    pages_over_requested_token_budget = 0
    final_result: dict[str, Any] | None = None

    started = time.perf_counter()
    while True:
        page_started = time.perf_counter()
        result = archive_services.zet_catalog(
            root,
            projection=projection,
            coverage_mode=coverage_mode,
            cursor=cursor,
            page_size=page_size,
            max_estimated_tokens=max_estimated_tokens,
            expected_snapshot_id=snapshot_id,
            continuation_token=continuation_token,
            dry_run=True,
            item_cache=item_cache,
            materialize_session_snapshot=True,
        )
        page_seconds.append(time.perf_counter() - page_started)
        if not result.get("ok"):
            return {
                "ok": False,
                "blockers": result.get("blockers", []),
                "warnings": result.get("warnings", []),
            }
        final_result = result
        snapshot_id = snapshot_id or result["snapshot"]["id"]
        continuation_token = result["coverage"].get("continuation_token")
        collected_ids.extend(str(item["id"]) for item in result["items"])
        frontmatter_files_scanned += int(result["scan"]["frontmatter_files_scanned"])
        cached_items_reused += int(result["scan"]["cached_items_reused"])
        path_metadata_checked += int(result["scan"]["path_metadata_checked"])
        if result["session_consistency"]["materialized_snapshot_reused"]:
            materialized_snapshot_pages += 1
        if result["session_consistency"]["completion_revalidation_performed"]:
            completion_revalidation_pages += 1
        page_tokens = int(result["workload_estimate"]["page"]["estimated_items_json_tokens"])
        max_page_estimated_items_json_tokens = max(max_page_estimated_items_json_tokens, page_tokens)
        if (
            max_estimated_tokens is not None
            and page_tokens > max_estimated_tokens
            and not result["coverage"]["single_item_exceeds_token_budget"]
        ):
            pages_over_requested_token_budget += 1
        if result["coverage"]["complete"]:
            break
        cursor = int(result["coverage"]["next_cursor"])
    elapsed = time.perf_counter() - started
    assert final_result is not None

    unique_count = len(set(collected_ids))
    page_count = len(page_seconds)
    return {
        "ok": len(collected_ids) == zet_count and unique_count == zet_count,
        "schema": "wom-kit/zet-catalog-benchmark/v0.1",
        "fixture": {
            "zet_count": zet_count,
            "page_size": page_size,
            "max_estimated_tokens": max_estimated_tokens,
            "projection": projection,
            "coverage_mode": coverage_mode,
        },
        "coverage": {
            "page_count": page_count,
            "collected_count": len(collected_ids),
            "unique_count": unique_count,
            "complete": bool(final_result["coverage"]["complete"]),
            "snapshot_stable": final_result["snapshot"]["id"] == snapshot_id,
            "archive_wide_coverage_claim_ready": final_result["coverage"]["archive_wide_coverage_claim_ready"],
        },
        "scan": {
            "frontmatter_files_scanned_across_pass": frontmatter_files_scanned,
            "cached_items_reused_across_pass": cached_items_reused,
            "path_metadata_checked_across_pass": path_metadata_checked,
            "materialized_snapshot_pages": materialized_snapshot_pages,
            "completion_revalidation_pages": completion_revalidation_pages,
            "expected_cold_frontmatter_scan_count": zet_count,
            "cache_mode": final_result["scan"]["cache_mode"],
            "cache_persisted": final_result["scan"]["cache_persisted"],
        },
        "timing_seconds": {
            "catalog_pass": round(elapsed, 6),
            "first_page": round(page_seconds[0], 6),
            "later_pages_total": round(sum(page_seconds[1:]), 6),
            "slowest_page": round(max(page_seconds), 6),
        },
        "workload_estimate": final_result["workload_estimate"],
        "page_budget_observation": {
            "requested_max_estimated_tokens": max_estimated_tokens,
            "max_page_estimated_items_json_tokens": max_page_estimated_items_json_tokens,
            "pages_over_requested_token_budget": pages_over_requested_token_budget,
        },
        "safety": {
            "real_archive_read": False,
            "temporary_fixture_only": True,
            "zet_bodies_read": False,
            "provider_api_called": False,
            "files_persisted": False,
        },
        "warnings": final_result.get("warnings", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark exhaustive zet-catalog coverage against a temporary synthetic archive."
    )
    parser.add_argument("--zet-count", type=int, default=1000, help="Synthetic canonical zet count (1-10000).")
    parser.add_argument("--page-size", type=int, default=1000, help="Maximum items per page (1-10000).")
    parser.add_argument("--abstract-chars", type=int, default=120, help="Synthetic abstract characters (1-360).")
    parser.add_argument(
        "--projection",
        choices=sorted(archive_services.ZET_CATALOG_PROJECTIONS),
        default="full",
        help="Catalog item projection.",
    )
    parser.add_argument(
        "--coverage-mode",
        choices=sorted(archive_services.ZET_CATALOG_COVERAGE_MODES),
        default="page",
        help="Compatibility page mode or strict contiguous-prefix mode.",
    )
    parser.add_argument(
        "--max-estimated-tokens",
        type=int,
        default=None,
        help="Optional approximate items-only token budget per page.",
    )
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)

    if not 1 <= args.zet_count <= 10000:
        parser.error("--zet-count must be between 1 and 10000")
    if not 1 <= args.page_size <= archive_services.ZET_CATALOG_MAX_PAGE_SIZE:
        parser.error(f"--page-size must be between 1 and {archive_services.ZET_CATALOG_MAX_PAGE_SIZE}")
    if not 1 <= args.abstract_chars <= archive_services.ZET_ABSTRACT_MAX_CHARS:
        parser.error(f"--abstract-chars must be between 1 and {archive_services.ZET_ABSTRACT_MAX_CHARS}")
    if args.max_estimated_tokens is not None and args.max_estimated_tokens < 1:
        parser.error("--max-estimated-tokens must be positive")

    with tempfile.TemporaryDirectory(prefix="wom-zet-catalog-benchmark-") as tmp:
        archive_root = Path(tmp) / "archive"
        fixture_seconds = write_fixture_archive(
            archive_root,
            zet_count=args.zet_count,
            abstract_chars=args.abstract_chars,
        )
        result = run_catalog_benchmark(
            archive_root,
            zet_count=args.zet_count,
            page_size=args.page_size,
            max_estimated_tokens=args.max_estimated_tokens,
            projection=args.projection,
            coverage_mode=args.coverage_mode,
        )
        result["timing_seconds"]["fixture_generation"] = round(fixture_seconds, 6)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        coverage = result.get("coverage", {})
        timing = result.get("timing_seconds", {})
        workload = result.get("workload_estimate", {}).get("scope", {})
        print("WOM zet catalog synthetic benchmark")
        print(f"Complete: {coverage.get('complete', False)}")
        print(f"Collected: {coverage.get('collected_count', 0)} / {args.zet_count}")
        print(f"Pages: {coverage.get('page_count', 0)}")
        print(f"Catalog pass seconds: {timing.get('catalog_pass', 0)}")
        print(f"Estimated items JSON tokens: {workload.get('estimated_items_json_tokens', 0)}")
        print("Real archive read: no")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
