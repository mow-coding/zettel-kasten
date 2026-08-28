from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Any
from unittest import mock


KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = KIT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from wom_kit import archive_cli  # noqa: E402
from wom_kit import archive_doctor  # noqa: E402
from wom_kit import archive_services  # noqa: E402
from wom_kit import schema_validator  # noqa: E402


BENCHMARK_SCHEMA = "wom-kit/doctor-letter148-scale-benchmark/v0.1"
TIMESTAMP = "2026-08-27T00:00:00+00:00"
REVIEWER = "person:letter148-scale-benchmark"
PRIVATE_TITLE_SENTINEL = "LETTER148_PRIVATE_TITLE_DO_NOT_ECHO"
PRIVATE_BODY_SENTINEL = "LETTER148_PRIVATE_BODY_DO_NOT_ECHO"
PRIVATE_PATH_SENTINEL = "letter148-private-path-do-not-echo.md"
PRIVATE_SENTINELS = (
    PRIVATE_TITLE_SENTINEL,
    PRIVATE_BODY_SENTINEL,
    PRIVATE_PATH_SENTINEL,
)
ELAPSED_SECONDS_RE = re.compile(r"\belapsed=(\d+(?:\.\d+)?)s\b")


@dataclass(frozen=True)
class ScaleProfile:
    name: str
    unique_objets: int
    zettels: int
    mint_receipts: int
    retired_receipts: int


FULL_PROFILE = ScaleProfile(
    name="letter148-full",
    unique_objets=22_441,
    zettels=8_612,
    mint_receipts=3_345,
    retired_receipts=3_346,
)
REDUCED_PROFILE = ScaleProfile(
    name="normal-suite-reduced",
    unique_objets=31,
    zettels=20,
    mint_receipts=5,
    retired_receipts=6,
)


class BenchmarkFailure(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _require_schema(value: Any, schema_name: str) -> None:
    if schema_validator.validate_schema(value, schema_name):
        raise BenchmarkFailure("synthetic_fixture_schema_invalid")


def _copy_archive_skeleton(root: Path) -> None:
    template = KIT_ROOT / "examples" / "fake-life-archive"
    root.mkdir(parents=True)
    for relative in (
        ".gitignore",
        "AGENTS.md",
        "archive.yml",
        "archive-identity.yml",
        "provider-bindings.yml",
        "source-bindings.yml",
        "db/schema.sql",
        "views/homebase.yml",
        "zettel-kasten/actions.yml",
        "zettel-kasten/policies.yml",
        "zettel-kasten/types.yml",
        "zettel-kasten/zettel-rules.yml",
    ):
        source = template.joinpath(*relative.split("/"))
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative in (
        "inbox",
        "zettels",
        "source-maps",
        "objects/manifests",
        "objects/sample",
        "receipts/mint/retired-drafts",
    ):
        root.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)
    (root / "objects" / "manifests" / "derived-text.jsonl").write_text(
        "",
        encoding="utf-8",
    )


def _source_frontmatter(zettel_id: str) -> dict[str, Any]:
    return {
        "id": zettel_id,
        "title": "Synthetic scale source",
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "archive_id": "archive:personal:fake-life",
        "status": "draft",
        "kind": "benchmark_fixture",
        "abstract": "Synthetic scale fixture source abstract.",
        "facets": {
            "domain": "benchmark",
            "record_type": "scale_fixture",
        },
        "assets": [],
        "edges": [],
        "provenance": {
            "created_by": REVIEWER,
            "created_in": "archive:personal:fake-life",
            "source": "letter148_scale_benchmark",
            "derived_from": [],
        },
        "visibility": {
            "scope": "private",
            "allowed_archives": [],
            "source_visibility": "private",
        },
    }


def _render_zettel(
    frontmatter: dict[str, Any],
    body: str,
) -> bytes:
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    facets = (
        frontmatter.get("facets")
        if isinstance(frontmatter.get("facets"), dict)
        else {}
    )
    provenance = (
        frontmatter.get("provenance")
        if isinstance(frontmatter.get("provenance"), dict)
        else {}
    )
    visibility = (
        frontmatter.get("visibility")
        if isinstance(frontmatter.get("visibility"), dict)
        else {}
    )
    lines = [
        "---",
        f"id: {quote(frontmatter['id'])}",
        f"title: {quote(frontmatter['title'])}",
        f"created_at: {quote(frontmatter['created_at'])}",
        f"updated_at: {quote(frontmatter['updated_at'])}",
        f"archive_id: {quote(frontmatter['archive_id'])}",
        f"status: {quote(frontmatter['status'])}",
        f"kind: {quote(frontmatter['kind'])}",
        f"abstract: {quote(frontmatter['abstract'])}",
        "facets:",
        f"  domain: {quote(facets.get('domain'))}",
        f"  record_type: {quote(facets.get('record_type'))}",
        "assets: []",
        "edges: []",
        "provenance:",
        f"  created_by: {quote(provenance.get('created_by'))}",
        f"  created_in: {quote(provenance.get('created_in'))}",
        f"  source: {quote(provenance.get('source'))}",
        "  derived_from: []",
        "visibility:",
        f"  scope: {quote(visibility.get('scope'))}",
        "  allowed_archives: []",
        f"  source_visibility: {quote(visibility.get('source_visibility'))}",
    ]
    promotion = frontmatter.get("promotion")
    if isinstance(promotion, dict):
        lines.extend(
            [
                "promotion:",
                f"  stage: {quote(promotion.get('stage'))}",
                f"  reviewed_by: {quote(promotion.get('reviewed_by'))}",
                f"  reviewed_at: {quote(promotion.get('reviewed_at'))}",
                "  checklist_version: "
                + quote(promotion.get("checklist_version")),
            ]
        )
    mint = frontmatter.get("mint")
    if isinstance(mint, dict):
        lines.extend(
            [
                "mint:",
                f"  stage: {quote(mint.get('stage'))}",
                f"  minted_at: {quote(mint.get('minted_at'))}",
                f"  reviewed_by: {quote(mint.get('reviewed_by'))}",
                f"  authority_mode: {quote(mint.get('authority_mode'))}",
                f"  receipt_path: {quote(mint.get('receipt_path'))}",
                "  draft_snapshot_path: "
                + quote(mint.get("draft_snapshot_path")),
                "  checklist_version: "
                + quote(mint.get("checklist_version")),
            ]
        )
    return ("\n".join(lines) + "\n---\n\n" + body.rstrip() + "\n").encode(
        "utf-8"
    )


def _plain_canonical_frontmatter(
    zettel_id: str,
    *,
    title: str,
) -> dict[str, Any]:
    value = _source_frontmatter(zettel_id)
    value["title"] = title
    value["status"] = "canonical"
    value["promotion"] = {
        "stage": "promoted",
        "reviewed_by": REVIEWER,
        "reviewed_at": TIMESTAMP,
        "checklist_version": "zettel-promotion/v0.2",
    }
    return value


def _minted_canonical_frontmatter(
    zettel_id: str,
    *,
    title: str,
    receipt_path: str,
    snapshot_path: str,
) -> dict[str, Any]:
    value = _plain_canonical_frontmatter(zettel_id, title=title)
    value["mint"] = {
        "stage": "minted",
        "minted_at": TIMESTAMP,
        "reviewed_by": REVIEWER,
        "authority_mode": archive_services.MINT_AUTHORITY_MODE,
        "receipt_path": receipt_path,
        "draft_snapshot_path": snapshot_path,
        "checklist_version": archive_services.MINT_CHECKLIST_VERSION,
    }
    return value


def _build_applied_mint_receipt(
    root: Path,
    *,
    zettel_id: str,
    title: str,
    source_path: Path,
    source_relative: str,
    source_frontmatter: dict[str, Any],
    source_body: str,
    target_relative: str,
    target_sha256: str,
    receipt_relative: str,
    snapshot_relative: str,
    validate_fixture_schema: bool,
) -> dict[str, Any]:
    receipt = archive_services.build_mint_receipt_preview(
        archive_root=root,
        source_path=source_path,
        frontmatter=source_frontmatter,
        zettel_id=zettel_id,
        title=title,
        draft_path=source_relative,
        proposed_canonical_path=target_relative,
        proposed_receipt_path=receipt_relative,
        proposed_snapshot_path=snapshot_relative,
        checklist=[],
        near_duplicates=[],
        first_read_check=(
            archive_services.explicit_abstract_publication_check(
                source_frontmatter
            )
        ),
        abstract_review_basis=archive_services.build_abstract_review_basis(
            source_frontmatter,
            source_body,
            review_status="reviewed_at_publication",
            evidence_kind="mint_zettel",
        ),
        blockers=[],
        warnings=[],
    )
    receipt["receipt_id"] = f"receipt:mint:{zettel_id}"
    receipt["receipt_path"] = receipt_relative
    receipt["dry_run"] = False
    receipt["timestamp"] = TIMESTAMP
    receipt["reviewed_by"] = REVIEWER
    receipt["reviewed_at"] = TIMESTAMP
    receipt["target"] = {
        "path": target_relative,
        "status": "canonical",
        "sha256": target_sha256,
    }
    receipt["zettel"] = {"id": zettel_id, "title": title}
    receipt["result"] = {
        "created_paths": [
            target_relative,
            receipt_relative,
            snapshot_relative,
        ]
    }
    if validate_fixture_schema:
        _require_schema(receipt, "mint-receipt.schema.json")
    return receipt


def _write_object_fixture(root: Path, count: int) -> None:
    manifest_path = root / "objects" / "manifests" / "files.jsonl"
    seen_digests: set[str] = set()
    with manifest_path.open("wb") as manifest:
        for index in range(count):
            body = index.to_bytes(8, "big") + b"-letter148-scale-objet"
            digest = _sha256_bytes(body)
            if digest in seen_digests:
                raise BenchmarkFailure("synthetic_object_digest_collision")
            seen_digests.add(digest)
            relative = f"objects/sha256/{digest[:2]}/{digest}"
            object_path = root.joinpath(*relative.split("/"))
            _write_bytes(object_path, body)
            record = {
                "object_id": f"sha256:{digest}",
                "sha256": digest,
                "logical_key": relative,
                "mime": "application/octet-stream",
                "size_bytes": len(body),
                "locations": [
                    {
                        "provider": "local",
                        "path": relative,
                        "availability": "available",
                    }
                ],
                "provenance": {
                    "created_in": "archive:personal:fake-life",
                    "source": "letter148_scale_benchmark",
                },
            }
            if index in {0, count - 1}:
                _require_schema(record, "object-manifest-entry.schema.json")
            manifest.write(_json_bytes(record))
    if len(seen_digests) != count:
        raise BenchmarkFailure("synthetic_object_count_mismatch")


def _write_lifecycle_fixture(root: Path, profile: ScaleProfile) -> None:
    shared_id = "zet_20260827_letter148_shared_source"
    shared_relative = f"inbox/{shared_id}.md"
    shared_path = root / "inbox" / f"{shared_id}.md"
    shared_frontmatter = _source_frontmatter(shared_id)
    shared_body = "Synthetic shared source body."
    shared_bytes = _render_zettel(shared_frontmatter, shared_body)
    _write_bytes(shared_path, shared_bytes)

    seed_id = "zet_20260827_letter148_minted_00000"
    seed_source_relative = f"inbox/{seed_id}.md"
    seed_source_path = root / "inbox" / f"{seed_id}.md"
    seed_source_frontmatter = _source_frontmatter(seed_id)
    seed_source_body = "Synthetic retirement seed body."
    seed_source_bytes = _render_zettel(
        seed_source_frontmatter,
        seed_source_body,
    )
    _write_bytes(seed_source_path, seed_source_bytes)

    shared_snapshot_relative = "receipts/mint/drafts/shared-source.md"
    seed_snapshot_relative = f"receipts/mint/drafts/{seed_id}.md"
    _write_bytes(
        root.joinpath(*shared_snapshot_relative.split("/")),
        shared_bytes,
    )
    _write_bytes(
        root.joinpath(*seed_snapshot_relative.split("/")),
        seed_source_bytes,
    )

    for index in range(profile.mint_receipts):
        zettel_id = f"zet_20260827_letter148_minted_{index:05d}"
        title = f"Synthetic minted scale zet {index}"
        target_relative = f"zettels/{zettel_id}.md"
        receipt_relative = f"receipts/mint/{zettel_id}.mint.json"
        if index == 0:
            source_path = seed_source_path
            source_relative = seed_source_relative
            source_frontmatter = seed_source_frontmatter
            source_body = seed_source_body
            snapshot_relative = seed_snapshot_relative
        else:
            source_path = shared_path
            source_relative = shared_relative
            source_frontmatter = shared_frontmatter
            source_body = shared_body
            snapshot_relative = shared_snapshot_relative

        target_frontmatter = _minted_canonical_frontmatter(
            zettel_id,
            title=title,
            receipt_path=receipt_relative,
            snapshot_path=snapshot_relative,
        )
        target_bytes = _render_zettel(
            target_frontmatter,
            f"Synthetic minted scale body {index}.",
        )
        target_path = root.joinpath(*target_relative.split("/"))
        _write_bytes(target_path, target_bytes)
        receipt = _build_applied_mint_receipt(
            root,
            zettel_id=zettel_id,
            title=title,
            source_path=source_path,
            source_relative=source_relative,
            source_frontmatter=source_frontmatter,
            source_body=source_body,
            target_relative=target_relative,
            target_sha256=_sha256_bytes(target_bytes),
            receipt_relative=receipt_relative,
            snapshot_relative=snapshot_relative,
            validate_fixture_schema=index
            in {0, profile.mint_receipts - 1},
        )
        _write_bytes(
            root.joinpath(*receipt_relative.split("/")),
            _json_bytes(receipt),
        )

    indexed = archive_services.index_archive(root)
    if indexed.get("ok") is not True:
        raise BenchmarkFailure("retirement_builder_index_blocked")
    retirement_plan = archive_services.minted_draft_retirement_plan(
        root,
        relative_path=seed_source_relative,
    )
    if retirement_plan.get("ok") is not True:
        raise BenchmarkFailure("retirement_builder_seed_blocked")
    seed_receipt = retirement_plan.get("receipt_preview")
    if not isinstance(seed_receipt, dict):
        raise BenchmarkFailure("retirement_builder_preview_missing")

    for index in range(profile.retired_receipts):
        if index == 0:
            retired_id = seed_id
            source_relative = seed_source_relative
        else:
            retired_id = f"zet_20260827_letter148_retired_{index:05d}"
            source_relative = f"inbox/retired-evidence-{index:05d}.md"
        receipt_relative = (
            "receipts/mint/retired-drafts/"
            f"{retired_id}.retire-draft.json"
        )
        receipt = json.loads(json.dumps(seed_receipt))
        receipt["receipt_id"] = f"receipt:mint-retired-draft:{retired_id}"
        receipt["receipt_path"] = receipt_relative
        receipt["dry_run"] = False
        receipt["timestamp"] = TIMESTAMP
        receipt["reviewed_by"] = REVIEWER
        receipt["reviewed_at"] = TIMESTAMP
        receipt["source"]["path"] = source_relative
        receipt["zettel"]["id"] = retired_id
        receipt["result"] = {
            "removed_paths": [source_relative],
            "created_paths": [receipt_relative],
        }
        _require_schema(
            receipt,
            "mint-retired-draft-receipt.schema.json",
        )
        _write_bytes(
            root.joinpath(*receipt_relative.split("/")),
            _json_bytes(receipt),
        )

    seed_source_path.unlink()

    plain_count = profile.zettels - profile.mint_receipts - 1
    if plain_count < 1:
        raise BenchmarkFailure("synthetic_zettel_profile_invalid")
    for index in range(plain_count):
        zettel_id = f"zet_20260827_letter148_plain_{index:05d}"
        title = (
            PRIVATE_TITLE_SENTINEL
            if index == 0
            else f"Synthetic plain scale zet {index}"
        )
        body = (
            PRIVATE_BODY_SENTINEL
            if index == 0
            else f"Synthetic plain scale body {index}."
        )
        filename = (
            PRIVATE_PATH_SENTINEL
            if index == 0
            else f"{zettel_id}.md"
        )
        frontmatter = _plain_canonical_frontmatter(
            zettel_id,
            title=title,
        )
        _write_bytes(
            root / "zettels" / filename,
            _render_zettel(frontmatter, body),
        )


def _count_fixture(root: Path) -> dict[str, int]:
    manifest_path = root / "objects" / "manifests" / "files.jsonl"
    manifest_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "unique_objets": len(
            {
                str(row.get("object_id") or "")
                for row in manifest_rows
                if isinstance(row, dict)
            }
        ),
        "object_manifest_rows": len(manifest_rows),
        "zettels": sum(
            1
            for folder in (root / "zettels", root / "inbox")
            for _path in folder.rglob("*.md")
        ),
        "mint_receipts": len(
            list((root / "receipts" / "mint").glob("*.mint.json"))
        ),
        "retired_receipts": len(
            list(
                (
                    root
                    / "receipts"
                    / "mint"
                    / "retired-drafts"
                ).glob("*.retire-draft.json")
            )
        ),
    }


def build_fixture(root: Path, profile: ScaleProfile) -> dict[str, Any]:
    started = time.perf_counter()
    _copy_archive_skeleton(root)
    _write_object_fixture(root, profile.unique_objets)
    _write_lifecycle_fixture(root, profile)
    counts = _count_fixture(root)
    expected = {
        "unique_objets": profile.unique_objets,
        "object_manifest_rows": profile.unique_objets,
        "zettels": profile.zettels,
        "mint_receipts": profile.mint_receipts,
        "retired_receipts": profile.retired_receipts,
    }
    if counts != expected:
        raise BenchmarkFailure("synthetic_fixture_count_mismatch")
    return {
        "profile": profile.name,
        **counts,
        "fixture_generation_seconds": round(
            time.perf_counter() - started,
            6,
        ),
        "fixture_generation_excluded_from_doctor_timing": True,
    }


def _progress_elapsed_seconds(stderr: str) -> list[float]:
    return [float(value) for value in ELAPSED_SECONDS_RE.findall(stderr)]


def _maximum_status_gap(
    elapsed_values: list[float],
    operation_seconds: float,
) -> float:
    if not elapsed_values:
        return operation_seconds
    ordered = sorted(elapsed_values)
    boundaries = [0.0, *ordered, operation_seconds]
    return max(
        max(0.0, later - earlier)
        for earlier, later in zip(boundaries, boundaries[1:])
    )


def _private_values_present(*values: str) -> bool:
    combined = "\n".join(values)
    return any(sentinel in combined for sentinel in PRIVATE_SENTINELS)


def _object_store_hash_paths(root: Path, call_args: list[Any]) -> list[str]:
    object_root = (root / "objects" / "sha256").resolve()
    paths: list[str] = []
    for call in call_args:
        candidate = Path(call.args[0]).resolve()
        try:
            relative = candidate.relative_to(object_root)
        except ValueError:
            continue
        if len(relative.parts) == 2:
            paths.append(os.path.normcase(str(candidate)))
    return paths


def run_operational_doctor(
    root: Path,
    *,
    expected_objets: int,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    stage_timings: dict[str, float] = {}

    class InstrumentedDoctor(archive_cli.Doctor):
        def _run_stage(self, stage_name: str, stage_func: Any) -> None:
            stage_started = time.perf_counter()
            try:
                return super()._run_stage(stage_name, stage_func)
            finally:
                stage_timings[stage_name] = (
                    time.perf_counter() - stage_started
                )

        def _load_object_manifest_records(self, *, audit: bool) -> None:
            counters["object_manifest_load_calls"] += 1
            if not self._object_manifest_records_loaded:
                counters["object_manifest_parse_passes"] += 1
            return super()._load_object_manifest_records(audit=audit)

        def _check_object_manifest(self) -> None:
            counters["object_manifest_stage_scans"] += 1
            return super()._check_object_manifest()

        def _check_zettels(self) -> None:
            counters["zettel_stage_scans"] += 1
            return super()._check_zettels()

        def _check_inbox_pipeline_audit(self) -> None:
            counters["inbox_pipeline_scans"] += 1
            return super()._check_inbox_pipeline_audit()

        def _check_mint_receipts(self) -> None:
            counters["mint_receipt_stage_scans"] += 1
            return super()._check_mint_receipts()

        def _check_retired_draft_receipts(self) -> None:
            counters["retired_receipt_stage_scans"] += 1
            return super()._check_retired_draft_receipts()

    stdout = io.StringIO()
    stderr = io.StringIO()
    real_stable_hash = archive_doctor.observe_stable_regular_file_sha256
    real_edge_index = archive_services.edge_receipt_paths_by_source_segment
    started = time.perf_counter()
    with (
        mock.patch.object(archive_cli, "Doctor", InstrumentedDoctor),
        mock.patch.object(
            archive_doctor,
            "observe_stable_regular_file_sha256",
            wraps=real_stable_hash,
        ) as stable_hash,
        mock.patch.object(
            archive_services,
            "edge_receipt_paths_by_source_segment",
            wraps=real_edge_index,
        ) as edge_index,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        exit_code = archive_cli.main(
            [
                "doctor",
                str(root),
                "--summary",
                "--format",
                "json",
                "--object-byte-verification",
                "operational",
                "--progress",
            ]
        )
    operation_seconds = time.perf_counter() - started
    stdout_value = stdout.getvalue()
    stderr_value = stderr.getvalue()
    try:
        summary = json.loads(stdout_value)
    except json.JSONDecodeError as exc:
        raise BenchmarkFailure("operational_summary_json_invalid") from exc
    progress_times = _progress_elapsed_seconds(stderr_value)
    first_status_seconds = progress_times[0] if progress_times else operation_seconds
    max_status_gap_seconds = _maximum_status_gap(
        progress_times,
        operation_seconds,
    )
    object_stable_hash_paths = _object_store_hash_paths(
        root,
        stable_hash.call_args_list,
    )
    byte_summary = summary.get("object_byte_verification")
    if not isinstance(byte_summary, dict):
        byte_summary = {}
    states = byte_summary.get("states")
    if not isinstance(states, dict):
        states = {}
    private_values_emitted = _private_values_present(
        stdout_value,
        stderr_value,
    )
    checks = {
        "completed_within_180_seconds": operation_seconds <= 180.0,
        "first_status_within_2_seconds": first_status_seconds <= 2.0,
        "heartbeat_gap_within_10_seconds": max_status_gap_seconds <= 10.0,
        "object_stable_hash_calls_zero": not object_stable_hash_paths,
        "object_manifest_parsed_once": (
            counters["object_manifest_parse_passes"] == 1
        ),
        "object_manifest_stage_scanned_once": (
            counters["object_manifest_stage_scans"] == 1
        ),
        "zettel_stage_scanned_once": counters["zettel_stage_scans"] == 1,
        "inbox_pipeline_scanned_once": (
            counters["inbox_pipeline_scans"] == 1
        ),
        "mint_receipt_stage_scanned_once": (
            counters["mint_receipt_stage_scans"] == 1
        ),
        "retired_receipt_stage_scanned_once": (
            counters["retired_receipt_stage_scans"] == 1
        ),
        "edge_receipt_index_built_at_most_once": edge_index.call_count <= 1,
        "private_values_not_emitted": not private_values_emitted,
        "operational_mode_reported": byte_summary.get("mode") == "operational",
        "all_local_objets_marked_unverified": (
            byte_summary.get("unique_local_file_count") == expected_objets
            and states.get("bytes_unverified") == expected_objets
            and states.get("rehashed_now") == 0
        ),
        "cli_exit_code_zero": exit_code == 0,
        "summary_reports_ok": summary.get("ok") is True,
    }
    return {
        "ok": all(checks.values()),
        "cli_exit_code": exit_code,
        "summary_ok": bool(summary.get("ok")),
        "timing_seconds": {
            "doctor_operational": round(operation_seconds, 6),
            "first_status": round(first_status_seconds, 6),
            "maximum_status_gap": round(max_status_gap_seconds, 6),
            "content_free_stages": {
                stage: round(seconds, 6)
                for stage, seconds in sorted(stage_timings.items())
            },
            "completion_and_overhead": round(
                max(0.0, operation_seconds - sum(stage_timings.values())),
                6,
            ),
        },
        "progress": {
            "content_free_status_line_count": len(progress_times),
            "heartbeat_interval_limit_seconds": 10,
        },
        "instrumentation": {
            **dict(sorted(counters.items())),
            "object_stable_hash_calls": len(object_stable_hash_paths),
            "non_object_stable_hash_calls": (
                stable_hash.call_count - len(object_stable_hash_paths)
            ),
            "total_stable_hash_calls": stable_hash.call_count,
            "edge_receipt_index_builds": edge_index.call_count,
        },
        "object_byte_verification": {
            "mode": byte_summary.get("mode"),
            "unique_local_file_count": byte_summary.get(
                "unique_local_file_count"
            ),
            "states": states,
        },
        "privacy": {
            "private_title_emitted": PRIVATE_TITLE_SENTINEL
            in (stdout_value + stderr_value),
            "private_body_emitted": PRIVATE_BODY_SENTINEL
            in (stdout_value + stderr_value),
            "private_path_emitted": PRIVATE_PATH_SENTINEL
            in (stdout_value + stderr_value),
        },
        "checks": checks,
    }


def run_deep_full_doctor(
    root: Path,
    *,
    expected_objets: int,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    stage_timings: dict[str, float] = {}

    class InstrumentedDeepDoctor(archive_cli.Doctor):
        def _run_stage(self, stage_name: str, stage_func: Any) -> None:
            stage_started = time.perf_counter()
            try:
                return super()._run_stage(stage_name, stage_func)
            finally:
                stage_timings[stage_name] = (
                    time.perf_counter() - stage_started
                )

        def _load_object_manifest_records(self, *, audit: bool) -> None:
            counters["object_manifest_load_calls"] += 1
            if not self._object_manifest_records_loaded:
                counters["object_manifest_parse_passes"] += 1
            return super()._load_object_manifest_records(audit=audit)

        def _check_object_manifest(self) -> None:
            counters["object_manifest_stage_scans"] += 1
            return super()._check_object_manifest()

        def _check_zettels(self) -> None:
            counters["zettel_stage_scans"] += 1
            return super()._check_zettels()

        def _check_inbox_pipeline_audit(self) -> None:
            counters["inbox_pipeline_scans"] += 1
            return super()._check_inbox_pipeline_audit()

        def _check_mint_receipts(self) -> None:
            counters["mint_receipt_stage_scans"] += 1
            return super()._check_mint_receipts()

        def _check_retired_draft_receipts(self) -> None:
            counters["retired_receipt_stage_scans"] += 1
            return super()._check_retired_draft_receipts()

    stdout = io.StringIO()
    stderr = io.StringIO()
    real_stable_hash = archive_doctor.observe_stable_regular_file_sha256
    real_edge_index = archive_services.edge_receipt_paths_by_source_segment
    started = time.perf_counter()
    with (
        mock.patch.object(archive_cli, "Doctor", InstrumentedDeepDoctor),
        mock.patch.object(
            archive_doctor,
            "observe_stable_regular_file_sha256",
            wraps=real_stable_hash,
        ) as stable_hash,
        mock.patch.object(
            archive_services,
            "edge_receipt_paths_by_source_segment",
            wraps=real_edge_index,
        ) as edge_index,
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        # Deliberately omit --object-byte-verification: this gate exercises
        # the real default deep CLI contract, not a test-only mode override.
        exit_code = archive_cli.main(
            [
                "doctor",
                str(root),
                "--summary",
                "--format",
                "json",
                "--progress",
            ]
        )
    operation_seconds = time.perf_counter() - started
    stdout_value = stdout.getvalue()
    stderr_value = stderr.getvalue()
    try:
        summary = json.loads(stdout_value)
    except json.JSONDecodeError as exc:
        raise BenchmarkFailure("deep_summary_json_invalid") from exc
    progress_times = _progress_elapsed_seconds(stderr_value)
    first_status_seconds = progress_times[0] if progress_times else operation_seconds
    max_status_gap_seconds = _maximum_status_gap(
        progress_times,
        operation_seconds,
    )
    normalized_paths = _object_store_hash_paths(
        root,
        stable_hash.call_args_list,
    )
    path_counts = Counter(normalized_paths)
    byte_summary = summary.get("object_byte_verification")
    if not isinstance(byte_summary, dict):
        byte_summary = {}
    states = byte_summary.get("states")
    if not isinstance(states, dict):
        states = {}
    completion = byte_summary.get("completion_revalidation")
    if not isinstance(completion, dict):
        completion = {}
    private_values_emitted = _private_values_present(
        stdout_value,
        stderr_value,
    )
    checks = {
        "completed_within_180_seconds": operation_seconds <= 180.0,
        "first_status_within_2_seconds": first_status_seconds <= 2.0,
        "heartbeat_gap_within_10_seconds": max_status_gap_seconds <= 10.0,
        "object_stable_hash_call_count_exact": len(normalized_paths)
        == expected_objets,
        "stable_hash_unique_path_count_exact": len(path_counts)
        == expected_objets,
        "each_path_hashed_once": all(count == 1 for count in path_counts.values()),
        "object_manifest_parsed_once": (
            counters["object_manifest_parse_passes"] == 1
        ),
        "object_manifest_stage_scanned_once": (
            counters["object_manifest_stage_scans"] == 1
        ),
        "zettel_stage_scanned_once": counters["zettel_stage_scans"] == 1,
        "inbox_pipeline_scanned_once": (
            counters["inbox_pipeline_scans"] == 1
        ),
        "mint_receipt_stage_scanned_once": (
            counters["mint_receipt_stage_scans"] == 1
        ),
        "retired_receipt_stage_scanned_once": (
            counters["retired_receipt_stage_scans"] == 1
        ),
        "edge_receipt_index_built_at_most_once": edge_index.call_count <= 1,
        "private_values_not_emitted": not private_values_emitted,
        "default_deep_mode_reported": byte_summary.get("mode") == "deep",
        "all_objets_rehashed_now": states.get("rehashed_now")
        == expected_objets,
        "no_objet_bytes_unverified": states.get("bytes_unverified") == 0,
        "completion_revalidation_current": (
            completion.get("state") == "current"
            and completion.get("revalidated_unique_local_file_count")
            == expected_objets
        ),
        "cli_exit_code_zero": exit_code == 0,
        "summary_reports_ok": summary.get("ok") is True,
    }
    return {
        "ok": all(checks.values()),
        "cli_exit_code": exit_code,
        "summary_ok": bool(summary.get("ok")),
        "timing_seconds": {
            "doctor_deep_full": round(operation_seconds, 6),
            "first_status": round(first_status_seconds, 6),
            "maximum_status_gap": round(max_status_gap_seconds, 6),
            "content_free_stages": {
                stage: round(seconds, 6)
                for stage, seconds in sorted(stage_timings.items())
            },
            "completion_and_overhead": round(
                max(0.0, operation_seconds - sum(stage_timings.values())),
                6,
            ),
        },
        "progress": {
            "content_free_status_line_count": len(progress_times),
            "heartbeat_interval_limit_seconds": 10,
        },
        "stable_hash_calls": len(normalized_paths),
        "unique_paths_hashed": len(path_counts),
        "maximum_hashes_for_one_path": max(path_counts.values(), default=0),
        "instrumentation": {
            **dict(sorted(counters.items())),
            "object_stable_hash_calls": len(normalized_paths),
            "non_object_stable_hash_calls": (
                stable_hash.call_count - len(normalized_paths)
            ),
            "total_stable_hash_calls": stable_hash.call_count,
            "edge_receipt_index_builds": edge_index.call_count,
        },
        "object_byte_verification": {
            "mode": byte_summary.get("mode"),
            "unique_local_file_count": byte_summary.get(
                "unique_local_file_count"
            ),
            "states": states,
            "completion_revalidation": completion,
        },
        "privacy": {
            "private_title_emitted": PRIVATE_TITLE_SENTINEL
            in (stdout_value + stderr_value),
            "private_body_emitted": PRIVATE_BODY_SENTINEL
            in (stdout_value + stderr_value),
            "private_path_emitted": PRIVATE_PATH_SENTINEL
            in (stdout_value + stderr_value),
        },
        "checks": checks,
    }


def run_benchmark(profile: ScaleProfile) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="wom-letter148-doctor-scale-"
    ) as temporary:
        archive_root = Path(temporary) / "archive"
        fixture = build_fixture(archive_root, profile)
        operational = run_operational_doctor(
            archive_root,
            expected_objets=profile.unique_objets,
        )
        deep = run_deep_full_doctor(
            archive_root,
            expected_objets=profile.unique_objets,
        )
    ok = operational["ok"] and deep["ok"]
    return {
        "ok": ok,
        "schema": BENCHMARK_SCHEMA,
        "profile": profile.name,
        "fixture": fixture,
        "operational_doctor": operational,
        "deep_full_doctor": deep,
        "safety": {
            "real_archive_read": False,
            "temporary_fixture_only": True,
            "provider_api_called": False,
            "archive_writes_persisted": False,
            "private_values_emitted": False,
        },
    }


def _safe_failure(reason_code: str, profile: ScaleProfile) -> dict[str, Any]:
    return {
        "ok": False,
        "schema": BENCHMARK_SCHEMA,
        "profile": profile.name,
        "reason_code": reason_code,
        "private_values_emitted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Letter 148 full-operational and default-deep Doctor "
            "scale gate against a temporary synthetic archive."
        )
    )
    profile_group = parser.add_mutually_exclusive_group(required=True)
    profile_group.add_argument(
        "--full-scale",
        action="store_true",
        help="Use the exact Letter 148 production-scale cardinalities.",
    )
    profile_group.add_argument(
        "--reduced",
        action="store_true",
        help="Use the bounded normal-suite fixture.",
    )
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)
    profile = FULL_PROFILE if args.full_scale else REDUCED_PROFILE
    try:
        result = run_benchmark(profile)
    except BenchmarkFailure as exc:
        result = _safe_failure(exc.reason_code, profile)
    except Exception:
        result = _safe_failure("benchmark_internal_error", profile)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("WOM Doctor Letter 148 synthetic scale benchmark")
        print(f"Profile: {result['profile']}")
        print(f"Complete: {result['ok']}")
        if result.get("reason_code"):
            print(f"Reason code: {result['reason_code']}")
        elif result.get("operational_doctor"):
            timing = result["operational_doctor"]["timing_seconds"]
            print(f"Operational Doctor seconds: {timing['doctor_operational']}")
            print(f"First status seconds: {timing['first_status']}")
            print(f"Maximum status gap seconds: {timing['maximum_status_gap']}")
            print(
                "Deep stable hashes: "
                f"{result['deep_full_doctor']['stable_hash_calls']}"
            )
        print("Real archive read: no")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
