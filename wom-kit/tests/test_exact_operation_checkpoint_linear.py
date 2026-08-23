from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import exact_operation_manifest as manifest_module  # noqa: E402
from wom_kit.exact_operation_manifest import (  # noqa: E402
    ExactFieldEffect,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_writer_lock,
    hash_field_value,
)


EXECUTION_SHA256 = "sha256:" + "a" * 64


def _line(value: dict[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )


class _OneEffectTarget:
    def __init__(self) -> None:
        self.value = b"before"


class _OneEffectPayloads:
    def field_value(self, *, item_id, field_ref, state, heartbeat):
        del item_id, field_ref
        heartbeat()
        return {
            "pre": b"before",
            "post": b"after",
            "source": b"source",
        }[state]


class _OneEffectWriter:
    def __init__(self, target: _OneEffectTarget) -> None:
        self.target = target

    def write_field(
        self,
        *,
        target_kind,
        target_ref,
        field_ref,
        value,
        heartbeat,
    ) -> None:
        del target_kind, target_ref, field_ref
        heartbeat()
        self.target.value = value


class _OneEffectVerifier:
    def __init__(self, target: _OneEffectTarget) -> None:
        self.target = target

    def target_identity_sha256(
        self,
        *,
        target_kind,
        target_ref,
        heartbeat,
    ) -> str:
        del target_kind, target_ref
        heartbeat()
        return hash_field_value(b"identity")

    def read_field(
        self,
        *,
        target_kind,
        target_ref,
        field_ref,
        heartbeat,
    ) -> bytes:
        del target_kind, target_ref, field_ref
        heartbeat()
        return self.target.value


def _one_effect_manifest() -> ExactOperationManifest:
    return ExactOperationManifest.build(
        operation="checkpoint_test",
        archive_identity_sha256=hash_field_value(b"archive"),
        items=(
            ExactOperationItem(
                ordinal=0,
                item_id="item:one",
                target_kind="zettel",
                target_ref="synthetic/one.json",
                target_identity_sha256=hash_field_value(b"identity"),
                fields=(
                    ExactFieldEffect(
                        field_ref="source_properties",
                        pre_sha256=hash_field_value(b"before"),
                        post_sha256=hash_field_value(b"after"),
                        source_sha256=hash_field_value(b"source"),
                    ),
                ),
            ),
        ),
    )


def _many_effect_manifest(effect_count: int) -> ExactOperationManifest:
    field = ExactFieldEffect(
        field_ref="source_properties",
        pre_sha256=hash_field_value(b"before"),
        post_sha256=hash_field_value(b"after"),
        source_sha256=hash_field_value(b"source"),
    )
    return ExactOperationManifest.build(
        operation="checkpoint_progress_test",
        archive_identity_sha256=hash_field_value(b"archive"),
        items=(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=f"item:{ordinal}",
                target_kind="zettel",
                target_ref=f"synthetic/{ordinal}.json",
                target_identity_sha256=hash_field_value(b"identity"),
                fields=(field,),
            )
            for ordinal in range(effect_count)
        ),
    )


class ExactOperationCheckpointLinearTests(unittest.TestCase):
    def test_benchmark_harness_proves_linear_scan_and_progress_contract(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    KIT_ROOT
                    / "tools"
                    / "benchmark_exact_operation_checkpoint_store.py"
                ),
                "--effect-count",
                "25",
                "--max-elapsed-seconds",
                "30",
                "--format",
                "json",
            ],
            cwd=KIT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["fixture"]["effect_count"], 25)
        self.assertEqual(report["fixture"]["checkpoint_count"], 75)
        self.assertEqual(report["result"]["full_checkpoint_scan_count"], 2)
        self.assertEqual(report["result"]["checkpoint_directory_sync_count"], 1)
        self.assertTrue(report["checks"]["approval_bound"])
        self.assertTrue(report["checks"]["first_status_within_deadline"])
        self.assertTrue(
            report["checks"]["status_gap_within_heartbeat_interval"]
        )

    def test_append_scans_once_and_directory_syncs_only_on_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                self.assertEqual(
                    store.load(EXECUTION_SHA256, heartbeat=lambda: None),
                    [],
                )
                original_read = manifest_module._read_plain_file_snapshot
                original_directory_sync = manifest_module._fsync_directory
                with (
                    patch.object(
                        manifest_module,
                        "_read_plain_file_snapshot",
                        wraps=original_read,
                    ) as checkpoint_scans,
                    patch.object(
                        manifest_module,
                        "_fsync_directory",
                        wraps=original_directory_sync,
                    ) as directory_syncs,
                ):
                    for sequence in range(500):
                        store.append(
                            EXECUTION_SHA256,
                            {"sequence": sequence},
                            heartbeat=lambda: None,
                        )
                self.assertEqual(checkpoint_scans.call_count, 0)
                self.assertEqual(directory_syncs.call_count, 1)

                resumed = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                with patch.object(
                    manifest_module,
                    "_read_plain_file_snapshot",
                    wraps=original_read,
                ) as resume_scans:
                    rows = resumed.load(
                        EXECUTION_SHA256,
                        heartbeat=lambda: None,
                    )
                self.assertEqual(resume_scans.call_count, 1)
                self.assertEqual(len(rows), 500)
                self.assertEqual(rows[-1], {"sequence": 499})

    def test_apply_progress_uses_constant_time_completed_field_counter(self) -> None:
        effect_count = 100
        manifest = _many_effect_manifest(effect_count)
        target = _OneEffectTarget()
        observed_mappings = []
        events = []
        original_load = manifest_module._load_checkpoint_state

        class _CountingCompletedFields(dict):
            def __init__(self, value):
                super().__init__(value)
                self.iterated_entries = 0

            def items(self):
                for key, value in super().items():
                    self.iterated_entries += 1
                    yield key, value

            def values(self):
                for value in super().values():
                    self.iterated_entries += 1
                    yield value

        def counted_load(*args, **kwargs):
            state = original_load(*args, **kwargs)
            counted = _CountingCompletedFields(state.completed_fields)
            state.completed_fields = counted
            observed_mappings.append(counted)
            return state

        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                with patch.object(
                    manifest_module,
                    "_load_checkpoint_state",
                    side_effect=counted_load,
                ):
                    result = apply_exact_operation(
                        manifest,
                        payloads=_OneEffectPayloads(),
                        writer=_OneEffectWriter(target),
                        verifier=_OneEffectVerifier(target),
                        checkpoint_store=store,
                        progress_hook=events.append,
                    )

        self.assertEqual(result["field_count"], effect_count)
        self.assertEqual(len(observed_mappings), 1)
        self.assertEqual(observed_mappings[0].iterated_entries, 0)
        item_events = [event for event in events if event.stage == "item_verified"]
        self.assertEqual(len(item_events), effect_count)
        self.assertEqual(item_events[-1].completed_fields, effect_count)

    def test_checkpoint_creation_directory_sync_failure_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                with patch.object(
                    manifest_module,
                    "_fsync_directory",
                    return_value=False,
                ):
                    with self.assertRaises(ExactOperationManifestError) as blocked:
                        store.append(
                            EXECUTION_SHA256,
                            {"sequence": 0},
                            heartbeat=lambda: None,
                        )
                self.assertEqual(
                    blocked.exception.code,
                    "exact_operation_checkpoint_write_failed",
                )
                self.assertNotIn(EXECUTION_SHA256, store._append_descriptors)
                self.assertFalse(store._append_cursors[EXECUTION_SHA256].exists)

    def test_existing_canonical_jsonl_is_extended_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                path = store._checkpoint_path(EXECUTION_SHA256)
                prefix = _line({"legacy": 0}) + _line({"legacy": 1})
                path.write_bytes(prefix)

                store.append(
                    EXECUTION_SHA256,
                    {"legacy": 2},
                    heartbeat=lambda: None,
                )

                self.assertEqual(path.read_bytes(), prefix + _line({"legacy": 2}))
                self.assertEqual(
                    list(store.load(EXECUTION_SHA256, heartbeat=lambda: None)),
                    [{"legacy": 0}, {"legacy": 1}, {"legacy": 2}],
                )

    def test_stale_store_cursor_and_external_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                first = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                stale = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                first.load(EXECUTION_SHA256, heartbeat=lambda: None)
                stale.load(EXECUTION_SHA256, heartbeat=lambda: None)
                first.append(
                    EXECUTION_SHA256,
                    {"sequence": 0},
                    heartbeat=lambda: None,
                )
                path = first._checkpoint_path(EXECUTION_SHA256)
                durable = path.read_bytes()

                with self.assertRaises(ExactOperationManifestError) as collision:
                    stale.append(
                        EXECUTION_SHA256,
                        {"sequence": 1},
                        heartbeat=lambda: None,
                    )
                self.assertEqual(
                    collision.exception.code,
                    "exact_operation_checkpoint_write_failed",
                )
                self.assertEqual(path.read_bytes(), durable)

                with path.open("ab") as handle:
                    handle.write(_line({"external": True}))
                    handle.flush()
                    os.fsync(handle.fileno())
                externally_changed = path.read_bytes()
                with self.assertRaises(ExactOperationManifestError) as drifted:
                    first.append(
                        EXECUTION_SHA256,
                        {"sequence": 2},
                        heartbeat=lambda: None,
                    )
                self.assertEqual(
                    drifted.exception.code,
                    "exact_operation_checkpoint_write_failed",
                )
                self.assertEqual(path.read_bytes(), externally_changed)

    def test_concurrent_stores_share_lock_mutex_and_one_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                stores = (
                    FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    ),
                    FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    ),
                )
                for store in stores:
                    store.load(EXECUTION_SHA256, heartbeat=lambda: None)

                def append(store, sequence):
                    try:
                        store.append(
                            EXECUTION_SHA256,
                            {"sequence": sequence},
                            heartbeat=lambda: None,
                        )
                    except ExactOperationManifestError as error:
                        return error.code
                    return "ok"

                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(
                        executor.map(
                            append,
                            stores,
                            (0, 1),
                        )
                    )
                self.assertEqual(
                    sorted(results),
                    ["exact_operation_checkpoint_write_failed", "ok"],
                )
                reader = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                rows = reader.load(EXECUTION_SHA256, heartbeat=lambda: None)
                self.assertEqual(len(rows), 1)
                self.assertIn(rows[0]["sequence"], (0, 1))

    def test_truncation_replacement_and_tail_tamper_block_next_append(self) -> None:
        for mutation in ("truncate", "replace", "tail_tamper"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary,
            ):
                archive_root = Path(temporary) / "archive"
                archive_root.mkdir()
                with exact_operation_writer_lock(archive_root) as writer_lock:
                    store = FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    )
                    store.append(
                        EXECUTION_SHA256,
                        {"sequence": 0},
                        heartbeat=lambda: None,
                    )
                    path = store._checkpoint_path(EXECUTION_SHA256)
                    raw = path.read_bytes()
                    prior = path.stat()
                    if mutation == "truncate":
                        path.write_bytes(raw[:-1])
                    elif mutation == "tail_tamper":
                        path.write_bytes(raw[:-1] + b" ")
                    else:
                        store._close_append_descriptor(
                            EXECUTION_SHA256,
                            suppress_errors=False,
                        )
                        replacement = path.with_suffix(".replacement")
                        replacement.write_bytes(raw)
                        os.replace(replacement, path)
                    os.utime(
                        path,
                        ns=(
                            prior.st_atime_ns,
                            prior.st_mtime_ns + 1_000_000_000,
                        ),
                    )

                    changed = path.read_bytes()
                    with self.assertRaises(ExactOperationManifestError) as blocked:
                        store.append(
                            EXECUTION_SHA256,
                            {"sequence": 1},
                            heartbeat=lambda: None,
                        )
                    self.assertEqual(
                        blocked.exception.code,
                        "exact_operation_checkpoint_write_failed",
                    )
                    self.assertEqual(path.read_bytes(), changed)

    def test_cached_same_size_corruption_is_rejected_by_metadata_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                store.append(
                    EXECUTION_SHA256,
                    {"sequence": 0},
                    heartbeat=lambda: None,
                )
                path = store._checkpoint_path(EXECUTION_SHA256)
                prior = path.stat()
                raw = bytearray(path.read_bytes())
                raw[2] = ord("x")
                path.write_bytes(raw)
                os.utime(
                    path,
                    ns=(prior.st_atime_ns, prior.st_mtime_ns + 1_000_000_000),
                )

                with self.assertRaises(ExactOperationManifestError) as corrupted:
                    store.append(
                        EXECUTION_SHA256,
                        {"sequence": 1},
                        heartbeat=lambda: None,
                    )
                self.assertEqual(
                    corrupted.exception.code,
                    "exact_operation_checkpoint_write_failed",
                )

    def test_truncated_duplicate_and_noncanonical_prefixes_are_rejected(self) -> None:
        invalid_documents = (
            b'{"sequence":0}',
            b"\n",
            b'{"sequence": 0}\n',
            b'{"sequence":0,"sequence":1}\n',
        )
        for raw in invalid_documents:
            with (
                self.subTest(raw=raw),
                tempfile.TemporaryDirectory() as temporary,
            ):
                archive_root = Path(temporary) / "archive"
                archive_root.mkdir()
                with exact_operation_writer_lock(archive_root) as writer_lock:
                    store = FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    )
                    store._checkpoint_path(EXECUTION_SHA256).write_bytes(raw)
                    with self.assertRaises(ExactOperationManifestError) as invalid:
                        store.load(
                            EXECUTION_SHA256,
                            heartbeat=lambda: None,
                        )
                    self.assertEqual(
                        invalid.exception.code,
                        "exact_operation_checkpoint_store_invalid",
                    )

    def test_newline_less_crash_tail_blocks_resume_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                store.append(
                    EXECUTION_SHA256,
                    {"sequence": 0},
                    heartbeat=lambda: None,
                )
                path = store._checkpoint_path(EXECUTION_SHA256)

            with path.open("ab") as handle:
                handle.write(b'{"crash_tail":')
                handle.flush()
                os.fsync(handle.fileno())

            with exact_operation_writer_lock(archive_root) as writer_lock:
                resumed = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                with self.assertRaises(ExactOperationManifestError) as invalid:
                    resumed.resume_checkpoint_present(EXECUTION_SHA256)
                self.assertEqual(
                    invalid.exception.code,
                    "exact_operation_checkpoint_store_invalid",
                )

    def test_writer_lock_identity_drift_blocks_append_before_file_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                original_lstat = manifest_module.os.lstat
                lock_info = original_lstat(writer_lock.path)

                class _DriftedLockInfo:
                    st_ino = lock_info.st_ino + 1

                    def __getattr__(self, name):
                        return getattr(lock_info, name)

                drifted_lock_info = _DriftedLockInfo()

                def drift_lock_identity(path):
                    if Path(path) == writer_lock.path:
                        return drifted_lock_info
                    return original_lstat(path)

                with patch.object(
                    manifest_module.os,
                    "lstat",
                    side_effect=drift_lock_identity,
                ):
                    with self.assertRaises(ExactOperationManifestError) as blocked:
                        store.append(
                            EXECUTION_SHA256,
                            {"sequence": 0},
                            heartbeat=lambda: None,
                        )
                self.assertEqual(
                    blocked.exception.code,
                    "exact_operation_writer_lock_invalid",
                )
                self.assertFalse(store._checkpoint_path(EXECUTION_SHA256).exists())

    def test_writer_lock_exit_closes_cached_append_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                store.append(
                    EXECUTION_SHA256,
                    {"sequence": 0},
                    heartbeat=lambda: None,
                )
                descriptor = store._append_descriptors[EXECUTION_SHA256]
                self.assertGreaterEqual(os.fstat(descriptor).st_size, 1)
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_finalize_reloads_and_revalidates_the_entire_checkpoint_chain(self) -> None:
        manifest = _one_effect_manifest()
        target = _OneEffectTarget()
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                durable_store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )

                class _TamperBeforeFinalize:
                    def load(self, execution_sha256, *, heartbeat):
                        return durable_store.load(
                            execution_sha256,
                            heartbeat=heartbeat,
                        )

                    def append(
                        self,
                        execution_sha256,
                        checkpoint,
                        *,
                        heartbeat,
                    ) -> None:
                        durable_store.append(
                            execution_sha256,
                            checkpoint,
                            heartbeat=heartbeat,
                        )

                    def finalize(self, result, *, heartbeat):
                        execution_sha256 = result["execution_sha256"]
                        durable_store._close_append_descriptor(
                            execution_sha256,
                            suppress_errors=False,
                        )
                        path = durable_store._checkpoint_path(execution_sha256)
                        rows = [
                            json.loads(line)
                            for line in path.read_text(encoding="ascii").splitlines()
                        ]
                        rows[0]["item_id"] = "item:tampered"
                        with path.open("wb") as handle:
                            for row in rows:
                                handle.write(_line(row))
                            handle.flush()
                            os.fsync(handle.fileno())
                        return durable_store.finalize(
                            result,
                            heartbeat=heartbeat,
                        )

                with self.assertRaises(ExactOperationManifestError) as blocked:
                    apply_exact_operation(
                        manifest,
                        payloads=_OneEffectPayloads(),
                        writer=_OneEffectWriter(target),
                        verifier=_OneEffectVerifier(target),
                        checkpoint_store=_TamperBeforeFinalize(),
                    )
                self.assertEqual(
                    blocked.exception.code,
                    "exact_operation_result_receipt_failed",
                )
                self.assertEqual(list(durable_store.results_root.glob("*.json")), [])

    def test_fsynced_row_survives_abrupt_process_exit_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            program = "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "from wom_kit.exact_operation_manifest import (",
                    "    FileExactOperationCheckpointStore,",
                    "    exact_operation_writer_lock,",
                    ")",
                    "root = Path(sys.argv[1])",
                    "execution = sys.argv[2]",
                    "with exact_operation_writer_lock(root) as writer_lock:",
                    "    store = FileExactOperationCheckpointStore(",
                    "        root, writer_lock=writer_lock",
                    "    )",
                    "    store.append(",
                    "        execution, {\"durable\": True}, heartbeat=lambda: None",
                    "    )",
                    "    os._exit(73)",
                )
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(SRC_ROOT)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    program,
                    str(archive_root),
                    EXECUTION_SHA256,
                ],
                cwd=KIT_ROOT,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 73, completed.stderr)

            with exact_operation_writer_lock(archive_root) as writer_lock:
                resumed = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                self.assertEqual(
                    list(
                        resumed.load(
                            EXECUTION_SHA256,
                            heartbeat=lambda: None,
                        )
                    ),
                    [{"durable": True}],
                )


if __name__ == "__main__":
    unittest.main()
