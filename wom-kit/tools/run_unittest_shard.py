#!/usr/bin/env python3
"""Run one deterministic, complete shard of the WOM-kit unittest modules."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class TestModule:
    path: Path
    relative_path: str
    byte_length: int


def discover_test_modules(tests_dir: Path) -> tuple[TestModule, ...]:
    resolved = tests_dir.resolve()
    if not resolved.is_dir():
        raise ValueError("tests_dir_not_directory")

    modules = []
    cwd = Path.cwd().resolve()
    for path in resolved.glob("test_*.py"):
        if not path.is_file():
            continue
        resolved_path = path.resolve()
        modules.append(
            TestModule(
                path=resolved_path,
                relative_path=(
                    resolved_path.relative_to(cwd).as_posix()
                    if resolved_path.is_relative_to(cwd)
                    else resolved_path.as_posix()
                ),
                byte_length=path.stat().st_size,
            )
        )
    if not modules:
        raise ValueError("no_test_modules_found")
    return tuple(sorted(modules, key=lambda item: item.relative_path))


def assign_test_shards(
    modules: Sequence[TestModule],
    shard_count: int,
) -> tuple[tuple[TestModule, ...], ...]:
    if shard_count < 1:
        raise ValueError("shard_count_must_be_positive")
    if shard_count > len(modules):
        raise ValueError("shard_count_exceeds_module_count")

    buckets: list[list[TestModule]] = [[] for _ in range(shard_count)]
    bucket_weights = [0] * shard_count
    for module in sorted(
        modules,
        key=lambda item: (-item.byte_length, item.relative_path),
    ):
        target = min(range(shard_count), key=lambda index: (bucket_weights[index], index))
        buckets[target].append(module)
        bucket_weights[target] += module.byte_length

    return tuple(
        tuple(sorted(bucket, key=lambda item: item.relative_path))
        for bucket in buckets
    )


def shard_manifest(
    modules: Sequence[TestModule],
    shard_count: int,
) -> dict[str, object]:
    shards = assign_test_shards(modules, shard_count)
    assigned = [module.relative_path for shard in shards for module in shard]
    expected = sorted(module.relative_path for module in modules)
    return {
        "schema": "wom-kit/ci-unittest-shards/v0.1",
        "shard_count": shard_count,
        "test_module_count": len(modules),
        "complete": sorted(assigned) == expected,
        "duplicate_assignment_count": len(assigned) - len(set(assigned)),
        "unassigned_count": len(set(expected) - set(assigned)),
        "shards": [
            {
                "index": index,
                "module_count": len(shard),
                "source_bytes": sum(module.byte_length for module in shard),
                "modules": [module.relative_path for module in shard],
            }
            for index, shard in enumerate(shards)
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=Path("wom-kit/tests"),
    )
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--manifest-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        modules = discover_test_modules(args.tests_dir)
        manifest = shard_manifest(modules, args.shard_count)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not manifest["complete"]:
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2

    if args.manifest_only:
        print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        return 0

    if args.shard_index is None:
        print("shard_index_required", file=sys.stderr)
        return 2
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        print("shard_index_out_of_range", file=sys.stderr)
        return 2

    selected = assign_test_shards(modules, args.shard_count)[args.shard_index]
    print(
        json.dumps(
            {
                "schema": "wom-kit/ci-unittest-shard-selection/v0.1",
                "shard_count": args.shard_count,
                "shard_index": args.shard_index,
                "module_count": len(selected),
                "source_bytes": sum(module.byte_length for module in selected),
                "modules": [module.relative_path for module in selected],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "-v",
            *(module.relative_path for module in selected),
        ],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
