from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import exact_operation_manifest as manifest_module  # noqa: E402
from wom_kit.exact_operation_manifest import (  # noqa: E402
    FIRST_STATUS_DEADLINE_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationItem,
    ExactOperationManifest,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_writer_lock,
    hash_field_value,
)


PRE_VALUE = b"before"
POST_VALUE = b"after"
SOURCE_VALUE = b"source"
IDENTITY_SHA256 = hash_field_value(b"synthetic-target-identity")


class _Payloads:
    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes:
        del item_id, field_ref
        heartbeat()
        return {
            "pre": PRE_VALUE,
            "post": POST_VALUE,
            "source": SOURCE_VALUE,
        }[state]


class _Target:
    def __init__(self, effect_count: int) -> None:
        self.values = {
            (f"synthetic/target-{ordinal:05d}.json", "source_properties"): PRE_VALUE
            for ordinal in range(effect_count)
        }


class _Writer:
    def __init__(self, target: _Target) -> None:
        self.target = target

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        if target_kind != "zettel" or value is None:
            raise RuntimeError("synthetic_target_invalid")
        heartbeat()
        self.target.values[(target_ref, field_ref)] = value


class _Verifier:
    def __init__(self, target: _Target) -> None:
        self.target = target

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        del target_ref
        if target_kind != "zettel":
            raise RuntimeError("synthetic_target_invalid")
        heartbeat()
        return IDENTITY_SHA256

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes:
        if target_kind != "zettel":
            raise RuntimeError("synthetic_target_invalid")
        heartbeat()
        return self.target.values[(target_ref, field_ref)]


def _manifest(effect_count: int) -> ExactOperationManifest:
    field = ExactFieldEffect(
        field_ref="source_properties",
        pre_sha256=hash_field_value(PRE_VALUE),
        post_sha256=hash_field_value(POST_VALUE),
        source_sha256=hash_field_value(SOURCE_VALUE),
    )
    return ExactOperationManifest.build(
        operation="notion_source_properties",
        archive_identity_sha256=hash_field_value(b"synthetic-archive"),
        items=(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=f"item:page-{ordinal:05d}",
                target_kind="zettel",
                target_ref=f"synthetic/target-{ordinal:05d}.json",
                target_identity_sha256=IDENTITY_SHA256,
                fields=(field,),
            )
            for ordinal in range(effect_count)
        ),
    )


def _authority() -> ExactOperationApprovalAuthority:
    return ExactOperationApprovalAuthority.from_reference(
        {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "1" * 32,
            "context_sha256": "sha256:" + "2" * 64,
            "approval_authority_sha256": "sha256:" + "3" * 64,
            "one_use": True,
        }
    )


def run_benchmark(effect_count: int, max_elapsed_seconds: float) -> dict[str, object]:
    if effect_count < 1 or effect_count > 100_000:
        raise ValueError("effect_count_out_of_range")
    manifest = _manifest(effect_count)
    target = _Target(effect_count)
    event_count = 0
    heartbeat_count = 0
    first_status_seconds: float | None = None
    maximum_status_gap_seconds = 0.0
    last_status_at: float | None = None

    with tempfile.TemporaryDirectory() as temporary:
        archive_root = Path(temporary) / "archive"
        archive_root.mkdir()
        with exact_operation_writer_lock(archive_root) as writer_lock:
            store = FileExactOperationCheckpointStore(
                archive_root,
                writer_lock=writer_lock,
            )
            checkpoint_scan_count = 0
            checkpoint_directory_sync_count = 0
            original_read = manifest_module._read_plain_file_snapshot
            original_directory_sync = manifest_module._fsync_directory

            def counted_read(path, *args, **kwargs):
                nonlocal checkpoint_scan_count
                if Path(path).parent == store.checkpoints_root:
                    checkpoint_scan_count += 1
                return original_read(path, *args, **kwargs)

            def counted_directory_sync(path: Path) -> bool:
                nonlocal checkpoint_directory_sync_count
                if path == store.checkpoints_root:
                    checkpoint_directory_sync_count += 1
                return original_directory_sync(path)

            started = time.monotonic()

            def progress(_event) -> None:
                nonlocal event_count
                nonlocal heartbeat_count
                nonlocal first_status_seconds
                nonlocal maximum_status_gap_seconds
                nonlocal last_status_at
                now = time.monotonic()
                event_count += 1
                if _event.stage == "heartbeat":
                    heartbeat_count += 1
                if first_status_seconds is None:
                    first_status_seconds = now - started
                if last_status_at is not None:
                    maximum_status_gap_seconds = max(
                        maximum_status_gap_seconds,
                        now - last_status_at,
                    )
                last_status_at = now

            manifest_module._read_plain_file_snapshot = counted_read
            manifest_module._fsync_directory = counted_directory_sync
            try:
                result = apply_exact_operation(
                    manifest,
                    payloads=_Payloads(),
                    writer=_Writer(target),
                    verifier=_Verifier(target),
                    checkpoint_store=store,
                    approval_authority=_authority(),
                    progress_hook=progress,
                )
            finally:
                manifest_module._read_plain_file_snapshot = original_read
                manifest_module._fsync_directory = original_directory_sync
            elapsed_seconds = time.monotonic() - started
            checkpoint_path = store._checkpoint_path(result["execution_sha256"])
            checkpoint_bytes = checkpoint_path.stat().st_size
            append_handle_closed_after_finalize = bool(
                not store._append_descriptors
                and not writer_lock._dependent_descriptors
            )

    checkpoint_count = effect_count * 3
    checks = {
        "completed": result["status"] == "completed",
        "effect_count_exact": result["field_count"] == effect_count,
        "checkpoint_count_exact": result["checkpoint_count"] == checkpoint_count,
        "linear_full_scan_count": checkpoint_scan_count == 2,
        "checkpoint_directory_sync_creation_only": (
            checkpoint_directory_sync_count == 1
        ),
        "append_handle_closed_after_finalize": append_handle_closed_after_finalize,
        "approval_bound": result["approval_binding_sha256"] is not None,
        "first_status_within_deadline": (
            first_status_seconds is not None
            and first_status_seconds < FIRST_STATUS_DEADLINE_SECONDS
        ),
        "status_gap_within_heartbeat_interval": (
            maximum_status_gap_seconds < HEARTBEAT_INTERVAL_SECONDS
        ),
        "elapsed_within_bound": elapsed_seconds < max_elapsed_seconds,
        "synthetic_only": True,
    }
    return {
        "ok": all(checks.values()),
        "schema": "wom-kit/exact-operation-checkpoint-benchmark/v1",
        "fixture": {
            "effect_count": effect_count,
            "checkpoint_count": checkpoint_count,
            "real_archive_read": False,
            "real_archive_write": False,
        },
        "result": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "checkpoints_per_second": round(checkpoint_count / elapsed_seconds, 3),
            "checkpoint_bytes": checkpoint_bytes,
            "full_checkpoint_scan_count": checkpoint_scan_count,
            "checkpoint_directory_sync_count": checkpoint_directory_sync_count,
            "first_status_seconds": (
                None
                if first_status_seconds is None
                else round(first_status_seconds, 6)
            ),
            "maximum_status_gap_seconds": round(
                maximum_status_gap_seconds,
                6,
            ),
            "progress_event_count": event_count,
            "heartbeat_event_count": heartbeat_count,
            "private_values_echoed": result["private_values_echoed"],
        },
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-count", type=int, default=8_566)
    parser.add_argument("--max-elapsed-seconds", type=float, default=180.0)
    parser.add_argument("--format", choices=("json",), default="json")
    args = parser.parse_args()
    report = run_benchmark(args.effect_count, args.max_elapsed_seconds)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
