from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from wom_kit import archive_services
from wom_kit import private_metadata_win32 as win32
from wom_kit import private_objet_metadata_writer as writer
from wom_kit import private_objet_metadata_writer_contract as contract


OBJECT_HEX = "a" * 64
OBJECT_ID = "sha256:" + OBJECT_HEX
SNAPSHOT = "sha256:" + ("b" * 64)
OBSERVATION = "sha256:" + ("c" * 64)
REVIEW = "sha256:" + ("d" * 64)
OPERATOR = "operator:approval-test"


def _intake() -> dict[str, object]:
    return {
        "schema": contract.INTAKE_SCHEMA,
        "object_id": OBJECT_ID,
        "privacy_class": "private_archive",
        "name_observation": {
            "original_filename": "synthetic-private-note.hwpx",
            "name_input_profile": "literal_unicode",
        },
        "media_observation": {
            "value": "application/octet-stream",
            "basis": "source_declared",
        },
        "size_bytes_observed": 321,
        "size_bytes_basis": "source_observed",
        "source_provenance": {
            "source_system": "synthetic",
            "source_record_id": None,
            "source_attachment_id": "synthetic-attachment",
            "source_snapshot_sha256": SNAPSHOT,
            "observation_evidence_sha256": OBSERVATION,
            "evidence_kind": "source_attachment_metadata",
            "captured_at": "2026-08-01T00:00:00Z",
        },
        "review_evidence": {
            "review_evidence_sha256": REVIEW,
            "review_status": "human_reviewed",
        },
    }


class PrivateMetadataWriterApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.name != "nt":
            self.skipTest("approval mutation is Windows-only")
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        environment = win32._approval_environment_status(self.root)
        if not environment.supported:
            self.temporary.cleanup()
            self.skipTest("test root is not a supported local NTFS volume")
        (self.root / "objects" / "manifests").mkdir(parents=True)
        (self.root / "private").mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: synthetic-private-approval\n",
            encoding="utf-8",
        )
        object_row = {
            "object_id": OBJECT_ID,
            "sha256": OBJECT_HEX,
            "logical_key": f"objects/sha256/aa/{OBJECT_HEX}",
            "locations": [{"provider": "synthetic"}],
            "provenance": {"source": "synthetic"},
        }
        (self.root / contract.OBJECT_MANIFEST_PATH).write_bytes(
            json.dumps(
                object_row,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        self.intake_relative = "private/intake.json"
        self.intake_bytes = contract.canonical_json_bytes(_intake())
        (self.root / self.intake_relative).write_bytes(self.intake_bytes)
        self.intake_sha256 = (
            "sha256:" + hashlib.sha256(self.intake_bytes).hexdigest()
        )

    def tearDown(self) -> None:
        if hasattr(self, "temporary"):
            self.temporary.cleanup()

    def _write(
        self,
        *,
        expected_plan_sha256: str | None,
        reviewed_by: str = OPERATOR,
    ) -> dict[str, object]:
        return archive_services._private_objet_source_metadata_write_legacy_core(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            expected_plan_sha256=expected_plan_sha256,
            dry_run=False,
            approve=True,
            reviewed_by=reviewed_by,
            affirm_private_metadata_reviewed=True,
            affirm_external_writers_quiescent=True,
        )

    def _dry_run(self) -> dict[str, object]:
        return archive_services.private_objet_source_metadata_write(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256=self.intake_sha256,
            dry_run=True,
            approve=False,
        )

    def test_public_approve_fixed_closes_before_archive_or_intake_access(
        self,
    ) -> None:
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        with (
            mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("archive access must not start"),
            ) as require_root,
            mock.patch.object(
                archive_services,
                "read_archive_id",
                side_effect=AssertionError("archive identity read must not start"),
            ) as read_id,
            mock.patch.object(
                writer,
                "_private_objet_metadata_write",
                side_effect=AssertionError("private writer must not start"),
            ) as private_writer,
        ):
            result = archive_services.private_objet_source_metadata_write(
                self.root,
                intake=self.intake_relative,
                expected_intake_sha256=self.intake_sha256,
                expected_plan_sha256="0" * 64,
                dry_run=False,
                approve=True,
                reviewed_by=OPERATOR,
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
        self.assertEqual(
            result,
            {
                "ok": False,
                "dry_run": False,
                "state": "blocked",
                "status": "blocked",
                "write_status": "blocked",
                "lifecycle_action": "private_objet_source_metadata_write",
                "blockers": [
                    "compound_exact_human_approval_binding_required"
                ],
                "reason_codes": [
                    "compound_exact_human_approval_binding_required"
                ],
                "warnings": [],
                "would_change": [],
                "files_written": [],
                "private_values_echoed": False,
            },
        )
        require_root.assert_not_called()
        read_id.assert_not_called()
        private_writer.assert_not_called()
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def _append_fixture(self) -> tuple[dict[str, object], dict[str, object]]:
        dry_run = self._dry_run()
        self.assertEqual(dry_run["action"], "append")
        receipt = writer._receipt_for_append_plan(
            dry_run["plan"],
            reviewed_by=OPERATOR,
            privacy_class="private_archive",
        )
        journal = writer._journal_for_receipt(receipt)
        return receipt, journal

    def _materialize_persistent_prefix(self) -> None:
        (self.root / "receipts" / "objects" / "private-source-metadata").mkdir(
            parents=True,
            exist_ok=True,
        )
        for relative in (
            contract.OBJECT_MANIFEST_LOCK,
            contract.PRIVATE_METADATA_LOCK,
        ):
            (self.root / relative).write_bytes(b"")

    def _applied_primary_snapshot(
        self,
        append_plan: dict[str, object],
    ) -> dict[str, object]:
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        manifest_stat = manifest_path.stat()
        receipt_stat = receipt_path.stat()
        return {
            "manifest_bytes": manifest_path.read_bytes(),
            "manifest_inode": manifest_stat.st_ino,
            "manifest_mtime_ns": manifest_stat.st_mtime_ns,
            "receipt_bytes": receipt_path.read_bytes(),
            "receipt_inode": receipt_stat.st_ino,
            "receipt_mtime_ns": receipt_stat.st_mtime_ns,
        }

    def _assert_no_transaction_residue(
        self,
        append_plan: dict[str, object],
    ) -> None:
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())

    def _object_drift_on_verification(
        self,
        fail_at: int,
    ) -> object:
        original = writer._verify_object_authority
        calls = 0

        def verify(*args: object, **kwargs: object) -> None:
            nonlocal calls
            calls += 1
            if calls == fail_at:
                raise writer._ApprovalFailure(
                    "private_metadata_object_manifest_changed_before_commit",
                    stage="manifest_replacement",
                    authority_state="unknown",
                )
            original(*args, **kwargs)

        return verify

    def _interruption_environment(
        self,
        *,
        hook: str,
        plan_sha256: str,
        marker: Path,
    ) -> dict[str, str]:
        environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            source_root
            if not existing
            else source_root + os.pathsep + existing
        )
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "WOM_P_ROOT": str(self.root),
                "WOM_P_INTAKE": self.intake_relative,
                "WOM_P_INTAKE_SHA": self.intake_sha256,
                "WOM_P_PLAN_SHA": plan_sha256,
                "WOM_P_MARKER": str(marker),
                "WOM_P_HOOK": hook,
            }
        )
        return environment

    def _interrupt_approval_at(
        self,
        *,
        hook: str,
        plan_sha256: str,
    ) -> dict[str, object]:
        marker = self.root.with_name(f"{self.root.name}-{hook}.marker")
        marker.unlink(missing_ok=True)
        child_source = textwrap.dedent(
            """
            import ctypes
            import hashlib
            import os
            from pathlib import Path
            import time

            from wom_kit import archive_services
            from wom_kit import private_metadata_win32 as win32

            root = Path(os.environ["WOM_P_ROOT"])
            marker = Path(os.environ["WOM_P_MARKER"])
            hook = os.environ["WOM_P_HOOK"]

            def reached(name):
                marker.write_text(name, encoding="utf-8")
                time.sleep(300)

            if hook == "first_lock":
                original = win32._PersistentCoordinationLock.acquire
                def acquire(lock):
                    result = original(lock)
                    if (
                        lock.kind
                        is win32.CoordinationLockKind.OBJECT_MANIFEST
                    ):
                        reached(hook)
                    return result
                win32._PersistentCoordinationLock.acquire = acquire
            elif hook.startswith("receipt_dir_"):
                original = win32._create_guarded_directory
                calls = 0
                target = int(hook.rsplit("_", 1)[1])
                def create_guarded_directory(*args, **kwargs):
                    global calls
                    result = original(*args, **kwargs)
                    calls += 1
                    if calls == target:
                        reached(hook)
                    return result
                win32._create_guarded_directory = create_guarded_directory
            elif hook in {"journal_twin", "receipt_twin"}:
                api = win32._api()
                original = api.create_hard_link
                calls = 0
                target = 1 if hook == "journal_twin" else 2
                def create_hard_link(*args):
                    global calls
                    result = original(*args)
                    calls += 1
                    if result and calls == target:
                        reached(hook)
                    return result
                api.create_hard_link = create_hard_link
            elif hook in {"journal_only", "receipt_only"}:
                original = win32._publish_hard_link
                calls = 0
                target = 1 if hook == "journal_only" else 2
                def publish(*args, **kwargs):
                    global calls
                    result = original(*args, **kwargs)
                    calls += 1
                    if calls == target:
                        reached(hook)
                    return result
                win32._publish_hard_link = publish
            elif hook == "manifest_full":
                original = win32._Win32BoundFile.flush
                def flush(
                    bound,
                    *,
                    reason=win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                ):
                    if bound.path.name.endswith(".manifest.tmp"):
                        reached(hook)
                    return original(bound, reason=reason)
                win32._Win32BoundFile.flush = flush
            elif hook == "manifest_partial":
                api = win32._api()
                original_write_file = api.write_file
                original_write_chunks = win32._Win32BoundFile.write_chunks
                manifest_handle = None

                def write_file(
                    handle,
                    buffer,
                    byte_count,
                    written,
                    overlapped,
                ):
                    result = original_write_file(
                        handle,
                        buffer,
                        byte_count,
                        written,
                        overlapped,
                    )
                    if (
                        result
                        and manifest_handle is not None
                        and int(handle) == int(manifest_handle)
                        and int(written._obj.value) > 0
                    ):
                        reached(hook)
                    return result

                def write_chunks(
                    bound,
                    chunks,
                    *,
                    expected_byte_count,
                    expected_sha256,
                    reason=win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                ):
                    global manifest_handle
                    if bound.path.name.endswith(".manifest.tmp"):
                        first = bytes(next(iter(chunks)))
                        prefix = first[:max(1, min(23, len(first) - 1))]
                        manifest_handle = bound.raw_handle
                        return original_write_chunks(
                            bound,
                            (prefix,),
                            expected_byte_count=len(prefix),
                            expected_sha256=(
                                "sha256:"
                                + hashlib.sha256(prefix).hexdigest()
                            ),
                            reason=reason,
                        )
                    return original_write_chunks(
                        bound,
                        chunks,
                        expected_byte_count=expected_byte_count,
                        expected_sha256=expected_sha256,
                        reason=reason,
                    )
                api.write_file = write_file
                win32._Win32BoundFile.write_chunks = write_chunks
            elif hook == "manifest_replaced":
                api = win32._api()
                original = api.set_file_information
                def set_file_information(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                ):
                    result = original(
                        handle,
                        information_class,
                        buffer,
                        buffer_size,
                    )
                    if (
                        result
                        and information_class
                        == win32._FILE_RENAME_INFO_CLASS
                    ):
                        reached(hook)
                    return result
                api.set_file_information = set_file_information
            elif hook in {
                "residue_true_before_close",
                "residue_close_before_false",
                "residue_false_before_postproof",
            }:
                api = win32._api()
                original_dispose = win32._dispose_bound_residue
                original_set_information = api.set_file_information
                original_close_handle = api.close_handle
                original_clear = win32._clear_disposition
                residue = {
                    "handle": None,
                    "close_failed": False,
                }

                def dispose_bound_residue(
                    guard,
                    bound,
                    *,
                    locks,
                ):
                    residue["handle"] = int(bound.raw_handle)
                    return original_dispose(
                        guard,
                        bound,
                        locks=locks,
                    )

                def close_handle(handle):
                    if (
                        int(handle) == residue["handle"]
                        and hook
                        in {
                            "residue_close_before_false",
                            "residue_false_before_postproof",
                        }
                        and not residue["close_failed"]
                    ):
                        residue["close_failed"] = True
                        return False
                    return original_close_handle(handle)

                def set_file_information(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                ):
                    result = original_set_information(
                        handle,
                        information_class,
                        buffer,
                        buffer_size,
                    )
                    disposition = getattr(buffer, "_obj", None)
                    if (
                        result
                        and int(handle) == residue["handle"]
                        and information_class
                        == win32._FILE_DISPOSITION_INFO_CLASS
                        and disposition is not None
                    ):
                        delete_file = int(disposition.delete_file)
                        if (
                            hook == "residue_true_before_close"
                            and delete_file == 1
                        ) or (
                            hook == "residue_false_before_postproof"
                            and delete_file == 0
                        ):
                            reached(hook)
                    return result

                def clear_disposition(
                    bound,
                    *,
                    reason,
                    operation,
                ):
                    if (
                        hook == "residue_close_before_false"
                        and int(bound.raw_handle) == residue["handle"]
                    ):
                        reached(hook)
                    return original_clear(
                        bound,
                        reason=reason,
                        operation=operation,
                    )

                win32._dispose_bound_residue = dispose_bound_residue
                api.close_handle = close_handle
                api.set_file_information = set_file_information
                win32._clear_disposition = clear_disposition
            elif hook in {
                "residue_failed_true_no_effect_before_same_handle",
                "residue_failed_true_delete_pending_before_same_handle",
                "residue_failed_true_after_link_one_before_release",
            }:
                api = win32._api()
                original_dispose = win32._dispose_bound_residue
                original_set_information = api.set_file_information
                original_set_disposition = win32._set_disposition
                original_later_proof = (
                    win32._prove_failed_disposition_name_guard_locks
                )
                original_terminal_release = (
                    win32._release_terminal_bound_authority
                )
                residue = {
                    "handle": None,
                    "later_fault": False,
                }

                def dispose_bound_residue(
                    guard,
                    bound,
                    *,
                    locks,
                ):
                    residue["handle"] = int(bound.raw_handle)
                    return original_dispose(
                        guard,
                        bound,
                        locks=locks,
                    )

                def set_file_information(
                    handle,
                    information_class,
                    buffer,
                    buffer_size,
                ):
                    disposition = getattr(buffer, "_obj", None)
                    if (
                        residue["handle"] is not None
                        and int(handle) == residue["handle"]
                        and information_class
                        == win32._FILE_DISPOSITION_INFO_CLASS
                        and disposition is not None
                        and int(disposition.delete_file) == 1
                    ):
                        if (
                            hook
                            == (
                                "residue_failed_true_"
                                "delete_pending_before_same_handle"
                            )
                        ):
                            assert original_set_information(
                                handle,
                                information_class,
                                buffer,
                                buffer_size,
                            )
                        ctypes.set_last_error(5)
                        return False
                    return original_set_information(
                        handle,
                        information_class,
                        buffer,
                        buffer_size,
                    )

                def set_disposition(
                    bound,
                    *,
                    reason,
                    operation,
                ):
                    try:
                        return original_set_disposition(
                            bound,
                            reason=reason,
                            operation=operation,
                        )
                    except win32.Win32SafetyError:
                        if hook in {
                            (
                                "residue_failed_true_"
                                "no_effect_before_same_handle"
                            ),
                            (
                                "residue_failed_true_"
                                "delete_pending_before_same_handle"
                            ),
                        }:
                            reached(hook)
                        raise

                def fail_later_proof(
                    guard,
                    bound,
                    *,
                    locks,
                    reason,
                ):
                    if (
                        hook
                        == (
                            "residue_failed_true_"
                            "after_link_one_before_release"
                        )
                        and int(bound.raw_handle) == residue["handle"]
                    ):
                        residue["later_fault"] = True
                        raise win32.Win32SafetyError(
                            reason,
                            operation=(
                                "synthetic_failed_true_exact_name_fault"
                            ),
                        )
                    return original_later_proof(
                        guard,
                        bound,
                        locks=locks,
                        reason=reason,
                    )

                def terminal_release(bound, *args, **kwargs):
                    if (
                        hook
                        == (
                            "residue_failed_true_"
                            "after_link_one_before_release"
                        )
                        and residue["later_fault"]
                        and int(bound.raw_handle) == residue["handle"]
                    ):
                        reached(hook)
                    return original_terminal_release(
                        bound,
                        *args,
                        **kwargs,
                    )

                win32._dispose_bound_residue = dispose_bound_residue
                api.set_file_information = set_file_information
                win32._set_disposition = set_disposition
                win32._prove_failed_disposition_name_guard_locks = (
                    fail_later_proof
                )
                win32._release_terminal_bound_authority = terminal_release
            else:
                raise RuntimeError("unknown interruption hook")

            archive_services._private_objet_source_metadata_write_legacy_core(
                root,
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                expected_plan_sha256=os.environ["WOM_P_PLAN_SHA"],
                dry_run=False,
                approve=True,
                reviewed_by="operator:interruption-test",
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
            """
        )
        environment = self._interruption_environment(
            hook=hook,
            plan_sha256=plan_sha256,
            marker=marker,
        )
        process = subprocess.Popen(
            [sys.executable, "-c", child_source],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 20
        try:
            while not marker.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    self.fail(
                        "interruption child exited before marker: "
                        f"returncode={process.returncode}\n{stdout}\n{stderr}"
                    )
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "checkpoint marker timed out")
            self.assertEqual(marker.read_text(encoding="utf-8"), hook)
            self.assertIsNone(
                process.poll(),
                "interruption child was not alive at the checkpoint",
            )
            process.kill()
            process.communicate(timeout=10)
            self.assertIsNotNone(process.returncode)
            self.assertNotEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            marker.unlink(missing_ok=True)
        return self._fresh_process_dry_run()

    def _fresh_process_dry_run(self) -> dict[str, object]:
        source = textwrap.dedent(
            """
            import json
            import os
            from pathlib import Path
            from wom_kit import archive_services

            result = archive_services.private_objet_source_metadata_write(
                Path(os.environ["WOM_P_ROOT"]),
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                dry_run=True,
                approve=False,
            )
            print(json.dumps(result, separators=(",", ":")))
            """
        )
        marker = self.root.with_name(f"{self.root.name}-dry-run.marker")
        environment = self._interruption_environment(
            hook="dry_run",
            plan_sha256="unused",
            marker=marker,
        )
        completed = subprocess.run(
            [sys.executable, "-c", source],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )
        return json.loads(completed.stdout.strip())

    def _terminal_failstop_approval(
        self,
        *,
        kind: str,
        plan_sha256: str,
    ) -> dict[str, object]:
        marker = self.root.with_name(
            f"{self.root.name}-terminal-{kind}.marker"
        )
        marker.unlink(missing_ok=True)
        child_source = textwrap.dedent(
            """
            import os
            from pathlib import Path

            from wom_kit import archive_services
            from wom_kit import private_metadata_win32 as win32
            from wom_kit import private_objet_metadata_writer as writer

            root = Path(os.environ["WOM_P_ROOT"])
            marker = Path(os.environ["WOM_P_MARKER"])
            kind = os.environ["WOM_P_HOOK"]
            api = win32._api()
            original_close_handle = api.close_handle
            original_get_handle_information = api.get_handle_information
            original_unlock = api.unlock_file
            target = {"handle": None}

            def mark(handle):
                target["handle"] = int(handle)
                marker.write_text(kind, encoding="utf-8")

            def close_handle(handle):
                if (
                    target["handle"] is not None
                    and int(handle) == target["handle"]
                ):
                    return False
                return original_close_handle(handle)

            def get_handle_information(handle, flags):
                if (
                    target["handle"] is not None
                    and int(handle) == target["handle"]
                ):
                    return True
                return original_get_handle_information(handle, flags)

            api.close_handle = close_handle
            api.get_handle_information = get_handle_information

            if kind == "residue":
                original_dispose = win32._dispose_bound_residue
                def dispose_bound_residue(guard, bound, *, locks):
                    mark(bound.raw_handle)
                    return original_dispose(guard, bound, locks=locks)
                win32._dispose_bound_residue = dispose_bound_residue
            elif kind == "residue_failed_true":
                original_dispose = win32._dispose_bound_residue
                original_set_disposition = win32._set_disposition

                def dispose_bound_residue(guard, bound, *, locks):
                    mark(bound.raw_handle)
                    return original_dispose(guard, bound, locks=locks)

                def fail_true_without_effect(
                    bound,
                    *,
                    reason,
                    operation,
                ):
                    if operation == "file_disposition_info":
                        raise win32.Win32SafetyError(
                            reason,
                            operation=operation,
                        )
                    return original_set_disposition(
                        bound,
                        reason=reason,
                        operation=operation,
                    )

                def fail_same_handle_proof(bound, *, reason):
                    raise win32.Win32SafetyError(
                        reason,
                        operation=(
                            "synthetic_failed_true_same_handle_unavailable"
                        ),
                    )

                win32._dispose_bound_residue = dispose_bound_residue
                win32._set_disposition = fail_true_without_effect
                win32._prove_failed_disposition_same_handle_no_change = (
                    fail_same_handle_proof
                )
            elif kind == "tracked":
                original_close_tracked = writer._close_tracked_handles
                def close_tracked_handles(state, win32_module):
                    bound = next(
                        item
                        for item in reversed(state.handles)
                        if not item.closed
                    )
                    mark(bound.raw_handle)
                    return original_close_tracked(state, win32_module)
                writer._close_tracked_handles = close_tracked_handles
            elif kind == "lock":
                original_pair_release = win32._PrivateMetadataLockPair.release
                def unlock_file(handle, *args):
                    if (
                        target["handle"] is not None
                        and int(handle) == target["handle"]
                    ):
                        return False
                    return original_unlock(handle, *args)
                def pair_release(pair):
                    mark(pair.private_metadata.bound.raw_handle)
                    return original_pair_release(pair)
                api.unlock_file = unlock_file
                win32._PrivateMetadataLockPair.release = pair_release
            elif kind == "guard":
                original_guard_close = win32._PrivateMetadataMutationGuard.close
                def guard_close(guard):
                    key = guard._order[-1]
                    mark(guard._handles[key])
                    return original_guard_close(guard)
                win32._PrivateMetadataMutationGuard.close = guard_close
            else:
                raise RuntimeError("unknown terminal fail-stop kind")

            archive_services._private_objet_source_metadata_write_legacy_core(
                root,
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                expected_plan_sha256=os.environ["WOM_P_PLAN_SHA"],
                dry_run=False,
                approve=True,
                reviewed_by="operator:terminal-failstop-test",
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
            raise SystemExit(99)
            """
        )
        environment = self._interruption_environment(
            hook=kind,
            plan_sha256=plan_sha256,
            marker=marker,
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", child_source],
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                completed.returncode,
                74,
                completed.stdout + completed.stderr,
            )
            self.assertTrue(marker.exists(), "terminal fail-stop was not armed")
            self.assertEqual(marker.read_text(encoding="utf-8"), kind)
            self.assertEqual(completed.stdout, "")
        finally:
            marker.unlink(missing_ok=True)
        return self._fresh_process_dry_run()

    def _dry_run_for_intake(
        self,
        *,
        intake_relative: str,
        intake_sha256: str,
    ) -> dict[str, object]:
        return archive_services.private_objet_source_metadata_write(
            self.root,
            intake=intake_relative,
            expected_intake_sha256=intake_sha256,
            dry_run=True,
            approve=False,
        )

    def _write_for_intake(
        self,
        *,
        intake_relative: str,
        intake_sha256: str,
        expected_plan_sha256: str,
        reviewed_by: str,
    ) -> dict[str, object]:
        return archive_services._private_objet_source_metadata_write_legacy_core(
            self.root,
            intake=intake_relative,
            expected_intake_sha256=intake_sha256,
            expected_plan_sha256=expected_plan_sha256,
            dry_run=False,
            approve=True,
            reviewed_by=reviewed_by,
            affirm_private_metadata_reviewed=True,
            affirm_external_writers_quiescent=True,
        )

    def _run_concurrent_approvals(
        self,
        requests: list[dict[str, str]],
    ) -> list[dict[str, object]]:
        start = self.root.with_name(f"{self.root.name}-concurrency.start")
        start.unlink(missing_ok=True)
        ready_paths = [
            self.root.with_name(
                f"{self.root.name}-concurrency-{index}.ready"
            )
            for index in range(len(requests))
        ]
        for ready in ready_paths:
            ready.unlink(missing_ok=True)
        source = textwrap.dedent(
            """
            import json
            import os
            from pathlib import Path
            import time

            from wom_kit import archive_services
            from wom_kit import private_metadata_win32 as win32

            ready = Path(os.environ["WOM_C_READY"])
            start = Path(os.environ["WOM_C_START"])
            ready.write_text("ready", encoding="utf-8")
            deadline = time.monotonic() + 30
            while not start.exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("concurrency start barrier timed out")
                time.sleep(0.01)

            result = archive_services._private_objet_source_metadata_write_legacy_core(
                Path(os.environ["WOM_P_ROOT"]),
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                expected_plan_sha256=os.environ["WOM_P_PLAN_SHA"],
                dry_run=False,
                approve=True,
                reviewed_by=os.environ["WOM_C_ACTOR"],
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
            print(json.dumps(result, separators=(",", ":")))
            """
        )
        processes: list[subprocess.Popen[str]] = []
        try:
            for index, request in enumerate(requests):
                environment = self._interruption_environment(
                    hook=f"concurrency_{index}",
                    plan_sha256=request["plan_sha256"],
                    marker=ready_paths[index],
                )
                environment.update(
                    {
                        "WOM_P_INTAKE": request["intake_relative"],
                        "WOM_P_INTAKE_SHA": request["intake_sha256"],
                        "WOM_C_ACTOR": request["reviewed_by"],
                        "WOM_C_READY": str(ready_paths[index]),
                        "WOM_C_START": str(start),
                    }
                )
                processes.append(
                    subprocess.Popen(
                        [sys.executable, "-c", source],
                        env=environment,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )

            deadline = time.monotonic() + 30
            while (
                not all(path.exists() for path in ready_paths)
                and time.monotonic() < deadline
            ):
                for process in processes:
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        self.fail(
                            "concurrency child exited before barrier: "
                            f"{stdout}\n{stderr}"
                        )
                time.sleep(0.01)
            self.assertTrue(
                all(path.exists() for path in ready_paths),
                "concurrency ready barrier timed out",
            )
            self.assertTrue(
                all(path.read_text(encoding="utf-8") == "ready"
                    for path in ready_paths)
            )
            self.assertTrue(
                all(process.poll() is None for process in processes),
                "concurrency child was not alive at the barrier",
            )
            start.write_text("start", encoding="utf-8")

            results: list[dict[str, object]] = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=90)
                self.assertEqual(
                    process.returncode,
                    0,
                    stdout + stderr,
                )
                results.append(json.loads(stdout.strip()))
            return results
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    try:
                        process.communicate(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            start.unlink(missing_ok=True)
            for ready in ready_paths:
                ready.unlink(missing_ok=True)

    def _make_objet_capture_fixture(self) -> tuple[Path, str]:
        (self.root / ".wom-sandbox").write_text(
            "sandbox\n",
            encoding="utf-8",
        )
        staged = self.root / "staging" / "incoming" / "concurrent.txt"
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged_bytes = b"concurrent objet capture payload\n"
        staged.write_bytes(staged_bytes)
        digest = hashlib.sha256(staged_bytes).hexdigest()
        source_plan = {
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "source_intake_plan",
            "blockers": [],
            "content_access": dict(
                archive_services.SOURCE_INTAKE_CONTENT_ACCESS_EXPECTATIONS
            ),
            "source_refs_for_draft": [],
        }
        plan_relative = (
            "receipts/sources/concurrency.source-intake-plan.json"
        )
        plan_path = self.root / plan_relative
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(source_plan), encoding="utf-8")
        selection = {
            "manifest_id": "approved:local-objet-capture:concurrency",
            "schema": "wom-kit/b4-selection/v0.2",
            "action": "local_objet_capture_approved",
            "archive_id": "synthetic-private-approval",
            "items": [
                {
                    "item_id": "concurrent-item",
                    "approved": True,
                    "input_kind": "local_path",
                    "staged_path": "staging/incoming/concurrent.txt",
                    "approved_object_id": f"sha256:{digest}",
                    "source_intake_receipt_path": plan_relative,
                    "source_intake_plan_sha256": (
                        archive_services.sha256_json_value(source_plan)
                    ),
                }
            ],
            "privacy_guards": {
                key: True
                for key in archive_services.OBJET_CAPTURE_REQUIRED_PRIVACY_GUARDS
            },
        }
        selection_path = self.root / "concurrent-selection.json"
        selection_path.write_text(json.dumps(selection), encoding="utf-8")
        return selection_path, digest

    def test_production_service_apply_and_replays_are_immutable(self) -> None:
        self.assertTrue(
            win32._MINIMAL_RENAME_PROFILE_APPROVAL_ENABLED
        )
        self.assertTrue(win32.approval_support_status(self.root).supported)
        append_plan = self._dry_run()
        applied = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
        )
        self.assertTrue(applied["ok"])
        self.assertEqual(applied["action"], "applied")
        self.assertEqual(applied["plan"], append_plan["plan"])
        self.assertEqual(applied["hold_context"], None)

        receipt_path = self.root / append_plan["plan"]["receipt_relative_path"]
        receipt_before = receipt_path.read_bytes()
        receipt_mtime_before = receipt_path.stat().st_mtime_ns
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        self.assertEqual(
            manifest_path.read_bytes(),
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ],
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())
        for relative in (
            contract.OBJECT_MANIFEST_LOCK,
            contract.PRIVATE_METADATA_LOCK,
        ):
            self.assertTrue((self.root / relative).is_file())

        stale_convergence = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
            reviewed_by="operator:different-replay",
        )
        self.assertEqual(stale_convergence["action"], "already_applied")
        self.assertNotEqual(
            stale_convergence["plan_sha256"],
            append_plan["plan_sha256"],
        )
        current = self._dry_run()
        self.assertEqual(current["action"], "already_applied")
        exact_replay = self._write(
            expected_plan_sha256=current["plan_sha256"],
            reviewed_by="operator:third-replay",
        )
        self.assertEqual(exact_replay["action"], "already_applied")
        self.assertEqual(receipt_path.read_bytes(), receipt_before)
        self.assertEqual(receipt_path.stat().st_mtime_ns, receipt_mtime_before)

    def test_concurrent_distinct_observations_serialize_and_replan_loser(
        self,
    ) -> None:
        first_intake = _intake()
        second_intake = _intake()
        second_intake["name_observation"] = {
            "original_filename": "synthetic-private-note-two.hwpx",
            "name_input_profile": "literal_unicode",
        }
        second_intake["source_provenance"] = {
            **second_intake["source_provenance"],
            "source_attachment_id": "synthetic-attachment-two",
            "observation_evidence_sha256": "sha256:" + ("e" * 64),
        }
        second_intake["review_evidence"] = {
            "review_evidence_sha256": "sha256:" + ("f" * 64),
            "review_status": "human_reviewed",
        }
        second_relative = "private/intake-two.json"
        second_bytes = contract.canonical_json_bytes(second_intake)
        (self.root / second_relative).write_bytes(second_bytes)
        second_sha256 = contract.sha256_digest(second_bytes)

        intakes = (
            (self.intake_relative, self.intake_sha256, first_intake),
            (second_relative, second_sha256, second_intake),
        )
        plans = [
            self._dry_run_for_intake(
                intake_relative=relative,
                intake_sha256=digest,
            )
            for relative, digest, _ in intakes
        ]
        self.assertEqual([plan["action"] for plan in plans], ["append"] * 2)
        self.assertNotEqual(
            plans[0]["plan_sha256"],
            plans[1]["plan_sha256"],
        )
        actors = (
            "operator:concurrent-distinct-a",
            "operator:concurrent-distinct-b",
        )
        results = self._run_concurrent_approvals(
            [
                {
                    "intake_relative": intakes[index][0],
                    "intake_sha256": intakes[index][1],
                    "plan_sha256": plans[index]["plan_sha256"],
                    "reviewed_by": actors[index],
                }
                for index in range(2)
            ]
        )
        self.assertEqual(
            sorted(result["action"] for result in results),
            ["applied", "blocked"],
        )
        winner_index = next(
            index
            for index, result in enumerate(results)
            if result["action"] == "applied"
        )
        loser_index = 1 - winner_index
        loser = results[loser_index]
        self.assertFalse(loser["ok"])
        self.assertIsNone(loser["plan"])
        self.assertIsNone(loser["plan_sha256"])
        self.assertEqual(
            loser["blockers"],
            ["private_metadata_plan_changed"],
        )

        loser_relative, loser_sha256, loser_intake = intakes[loser_index]
        fresh_loser = self._dry_run_for_intake(
            intake_relative=loser_relative,
            intake_sha256=loser_sha256,
        )
        self.assertEqual(fresh_loser["action"], "append")
        loser_retry_actor = "operator:concurrent-distinct-loser-retry"
        completed = self._write_for_intake(
            intake_relative=loser_relative,
            intake_sha256=loser_sha256,
            expected_plan_sha256=fresh_loser["plan_sha256"],
            reviewed_by=loser_retry_actor,
        )
        self.assertEqual(completed["action"], "applied")

        winner_row = contract.build_private_metadata_row(
            intakes[winner_index][2]
        )["stored_row_bytes"]
        loser_row = contract.build_private_metadata_row(loser_intake)[
            "stored_row_bytes"
        ]
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        self.assertEqual(manifest_path.read_bytes(), winner_row + loser_row)
        receipt_directory = self.root / contract.RECEIPT_DIRECTORY
        receipt_paths = sorted(receipt_directory.glob("*.json"))
        self.assertEqual(len(receipt_paths), 2)
        winner_receipt = json.loads(
            (
                self.root
                / plans[winner_index]["plan"]["receipt_relative_path"]
            ).read_text(encoding="utf-8")
        )
        loser_receipt = json.loads(
            (
                self.root
                / fresh_loser["plan"]["receipt_relative_path"]
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(winner_receipt["reviewed_by"], actors[winner_index])
        self.assertEqual(loser_receipt["reviewed_by"], loser_retry_actor)
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for plan in (plans[winner_index], fresh_loser):
            for relative in contract.owned_temp_relative_paths(
                plan["plan"]["authority_key_sha256"]
            ):
                self.assertFalse((self.root / relative).exists())

    def test_concurrent_same_observation_has_one_unordered_winner(
        self,
    ) -> None:
        append_plan = self._dry_run()
        actors = (
            "operator:concurrent-same-a",
            "operator:concurrent-same-b",
        )
        results = self._run_concurrent_approvals(
            [
                {
                    "intake_relative": self.intake_relative,
                    "intake_sha256": self.intake_sha256,
                    "plan_sha256": append_plan["plan_sha256"],
                    "reviewed_by": actor,
                }
                for actor in actors
            ]
        )
        self.assertEqual(
            sorted(result["action"] for result in results),
            ["already_applied", "applied"],
            results,
        )
        winner_index = next(
            index
            for index, result in enumerate(results)
            if result["action"] == "applied"
        )
        loser_index = 1 - winner_index
        self.assertEqual(
            results[loser_index]["plan"]["action"],
            "already_applied",
        )
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        self.assertEqual(
            manifest_path.read_bytes(),
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ],
        )
        receipt_directory = self.root / contract.RECEIPT_DIRECTORY
        receipt_paths = list(receipt_directory.glob("*.json"))
        self.assertEqual(len(receipt_paths), 1)
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        self.assertEqual(receipt_paths[0], receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["reviewed_by"], actors[winner_index])
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())

    def test_objet_capture_lock_blocks_private_approval_until_replan(
        self,
    ) -> None:
        selection_path, captured_digest = self._make_objet_capture_fixture()
        capture_plan = archive_services.objet_capture_dry_run(
            self.root,
            selection_path,
        )
        self.assertTrue(capture_plan["ok"], capture_plan)
        self.assertEqual(
            capture_plan["items"][0]["planned_action"],
            "capture",
        )
        append_plan = self._dry_run()
        self.assertEqual(append_plan["action"], "append")

        held = self.root.with_name(f"{self.root.name}-objet-lock.held")
        release = self.root.with_name(f"{self.root.name}-objet-lock.release")
        private_ready = self.root.with_name(
            f"{self.root.name}-private-lock.ready"
        )
        private_done = self.root.with_name(
            f"{self.root.name}-private-lock.done"
        )
        markers = (held, release, private_ready, private_done)
        for marker in markers:
            marker.unlink(missing_ok=True)

        capture_source = textwrap.dedent(
            """
            import json
            import os
            from pathlib import Path
            import time

            from wom_kit import archive_services
            from wom_kit import private_metadata_win32 as win32

            original_enter = archive_services._ObjetCaptureManifestLock.__enter__
            held = Path(os.environ["WOM_C_HELD"])
            release = Path(os.environ["WOM_C_RELEASE"])

            def enter(lock):
                result = original_enter(lock)
                held.write_text("held", encoding="utf-8")
                deadline = time.monotonic() + 30
                while not release.exists():
                    if time.monotonic() >= deadline:
                        raise RuntimeError("objet lock release timed out")
                    time.sleep(0.01)
                return result

            archive_services._ObjetCaptureManifestLock.__enter__ = enter
            result = archive_services._objet_capture_run(
                Path(os.environ["WOM_P_ROOT"]),
                Path(os.environ["WOM_C_SELECTION"]),
                approve=True,
                reviewed_by="person:concurrent-capture",
            )
            print(json.dumps(result, separators=(",", ":")))
            """
        )
        private_source = textwrap.dedent(
            """
            import json
            import os
            from pathlib import Path

            from wom_kit import archive_services
            from wom_kit import private_metadata_win32 as win32

            ready = Path(os.environ["WOM_C_PRIVATE_READY"])
            done = Path(os.environ["WOM_C_PRIVATE_DONE"])
            ready.write_text("ready", encoding="utf-8")
            result = archive_services._private_objet_source_metadata_write_legacy_core(
                Path(os.environ["WOM_P_ROOT"]),
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                expected_plan_sha256=os.environ["WOM_P_PLAN_SHA"],
                dry_run=False,
                approve=True,
                reviewed_by="operator:blocked-by-objet-capture",
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
            done.write_text("done", encoding="utf-8")
            print(json.dumps(result, separators=(",", ":")))
            """
        )
        capture_environment = self._interruption_environment(
            hook="objet_capture_lock",
            plan_sha256="unused",
            marker=held,
        )
        capture_environment.update(
            {
                "WOM_C_HELD": str(held),
                "WOM_C_RELEASE": str(release),
                "WOM_C_SELECTION": str(selection_path),
            }
        )
        private_environment = self._interruption_environment(
            hook="private_waiting_for_objet",
            plan_sha256=append_plan["plan_sha256"],
            marker=private_ready,
        )
        private_environment.update(
            {
                "WOM_C_PRIVATE_READY": str(private_ready),
                "WOM_C_PRIVATE_DONE": str(private_done),
            }
        )
        capture_process: subprocess.Popen[str] | None = None
        private_process: subprocess.Popen[str] | None = None
        try:
            capture_process = subprocess.Popen(
                [sys.executable, "-c", capture_source],
                env=capture_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 30
            while not held.exists() and time.monotonic() < deadline:
                if capture_process.poll() is not None:
                    stdout, stderr = capture_process.communicate()
                    self.fail(
                        "objet capture exited before holding lock: "
                        f"{stdout}\n{stderr}"
                    )
                time.sleep(0.01)
            self.assertTrue(held.exists(), "objet lock marker timed out")
            self.assertEqual(held.read_text(encoding="utf-8"), "held")
            self.assertIsNone(capture_process.poll())

            private_process = subprocess.Popen(
                [sys.executable, "-c", private_source],
                env=private_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 30
            while (
                not private_ready.exists()
                and time.monotonic() < deadline
            ):
                if private_process.poll() is not None:
                    stdout, stderr = private_process.communicate()
                    self.fail(
                        "private approval exited before lock attempt: "
                        f"{stdout}\n{stderr}"
                    )
                time.sleep(0.01)
            self.assertTrue(
                private_ready.exists(),
                "private approval ready marker timed out",
            )
            self.assertEqual(
                private_ready.read_text(encoding="utf-8"),
                "ready",
            )
            time.sleep(0.5)
            self.assertIsNone(
                private_process.poll(),
                "private approval did not block on the objet-capture lock",
            )
            self.assertFalse(
                private_done.exists(),
                "private approval completed while objet lock was held",
            )

            release.write_text("release", encoding="utf-8")
            capture_stdout, capture_stderr = capture_process.communicate(
                timeout=90
            )
            private_stdout, private_stderr = private_process.communicate(
                timeout=90
            )
            self.assertEqual(
                capture_process.returncode,
                0,
                capture_stdout + capture_stderr,
            )
            self.assertEqual(
                private_process.returncode,
                0,
                private_stdout + private_stderr,
            )
            capture_result = json.loads(capture_stdout.strip())
            private_result = json.loads(private_stdout.strip())
        finally:
            for process in (private_process, capture_process):
                if process is not None and process.poll() is None:
                    process.kill()
                    try:
                        process.communicate(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            for marker in markers:
                marker.unlink(missing_ok=True)

        self.assertTrue(capture_result["ok"], capture_result)
        self.assertEqual(
            capture_result["items"][0]["action"],
            "captured",
        )
        self.assertFalse(private_result["ok"])
        self.assertEqual(private_result["action"], "blocked")
        self.assertEqual(
            private_result["blockers"],
            ["private_metadata_plan_changed"],
        )
        self.assertIsNone(private_result["plan"])
        self.assertIsNone(private_result["plan_sha256"])
        object_manifest_path = self.root / contract.OBJECT_MANIFEST_PATH
        object_rows = [
            json.loads(line)
            for line in object_manifest_path.read_text(
                encoding="utf-8"
            ).splitlines()
            if line
        ]
        self.assertEqual(len(object_rows), 2)
        self.assertEqual(
            sum(
                row.get("object_id") == f"sha256:{captured_digest}"
                for row in object_rows
            ),
            1,
        )

        fresh = self._dry_run()
        self.assertEqual(fresh["action"], "append")
        self.assertNotEqual(
            fresh["plan_sha256"],
            append_plan["plan_sha256"],
        )
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "applied")
        self.assertEqual(
            (self.root / contract.PRIVATE_MANIFEST_PATH).read_bytes(),
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ],
        )

    def test_concurrent_shared_delete_reader_observes_only_atomic_jsonl(
        self,
    ) -> None:
        first_plan = self._dry_run()
        first = self._write(
            expected_plan_sha256=first_plan["plan_sha256"],
            reviewed_by="operator:reader-initial",
        )
        self.assertEqual(first["action"], "applied")
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_before = manifest_path.read_bytes()

        second_intake = _intake()
        second_intake["name_observation"] = {
            "original_filename": "reader-concurrency-two.hwpx",
            "name_input_profile": "literal_unicode",
        }
        second_intake["source_provenance"] = {
            **second_intake["source_provenance"],
            "source_attachment_id": "reader-concurrency-two",
            "observation_evidence_sha256": "sha256:" + ("1" * 64),
        }
        second_intake["review_evidence"] = {
            "review_evidence_sha256": "sha256:" + ("2" * 64),
            "review_status": "human_reviewed",
        }
        second_relative = "private/reader-concurrency-two.json"
        second_bytes = contract.canonical_json_bytes(second_intake)
        (self.root / second_relative).write_bytes(second_bytes)
        second_sha256 = contract.sha256_digest(second_bytes)
        second_plan = self._dry_run_for_intake(
            intake_relative=second_relative,
            intake_sha256=second_sha256,
        )
        self.assertEqual(second_plan["action"], "append")
        manifest_after = (
            manifest_before
            + contract.build_private_metadata_row(second_intake)[
                "stored_row_bytes"
            ]
        )

        ready = self.root.with_name(f"{self.root.name}-reader.ready")
        observed_new = self.root.with_name(
            f"{self.root.name}-reader.new"
        )
        stop = self.root.with_name(f"{self.root.name}-reader.stop")
        markers = (ready, observed_new, stop)
        for marker in markers:
            marker.unlink(missing_ok=True)
        reader_source = textwrap.dedent(
            """
            import ctypes
            import hashlib
            import json
            import os
            from pathlib import Path
            import time

            from wom_kit import private_objet_metadata as private_metadata
            from wom_kit import private_metadata_win32 as win32
            from wom_kit import private_objet_metadata_writer_contract as contract

            GENERIC_READ = 0x80000000
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            FILE_SHARE_DELETE = 0x00000004
            OPEN_EXISTING = 3
            FILE_ATTRIBUTE_NORMAL = 0x00000080
            SHARE_MODE = (
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            )
            INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            get_size = kernel32.GetFileSizeEx
            get_size.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_longlong),
            ]
            get_size.restype = ctypes.c_int
            read_file = kernel32.ReadFile
            read_file.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_void_p,
            ]
            read_file.restype = ctypes.c_int
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle.restype = ctypes.c_int

            path = Path(os.environ["WOM_R_PATH"])
            ready = Path(os.environ["WOM_R_READY"])
            observed_new = Path(os.environ["WOM_R_NEW"])
            stop = Path(os.environ["WOM_R_STOP"])
            old_digest = os.environ["WOM_R_OLD_SHA"]
            new_digest = os.environ["WOM_R_NEW_SHA"]
            old_size = int(os.environ["WOM_R_OLD_SIZE"])
            new_size = int(os.environ["WOM_R_NEW_SIZE"])
            counts = {
                "successful_reads": 0,
                "old": 0,
                "new": 0,
                "open_failures": 0,
                "size_failures": 0,
                "read_failures": 0,
                "read_size_mismatch": 0,
                "malformed": 0,
                "noncanonical": 0,
                "invalid_rows": 0,
                "unexpected_valid": 0,
            }
            deadline = time.monotonic() + 60
            while not stop.exists() and time.monotonic() < deadline:
                handle = create_file(
                    str(path),
                    GENERIC_READ,
                    SHARE_MODE,
                    None,
                    OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL,
                    None,
                )
                if handle == INVALID_HANDLE_VALUE:
                    counts["open_failures"] += 1
                    time.sleep(0.001)
                    continue
                try:
                    size = ctypes.c_longlong()
                    if not get_size(handle, ctypes.byref(size)):
                        counts["size_failures"] += 1
                        continue
                    if size.value <= 0 or size.value > 1024 * 1024:
                        counts["malformed"] += 1
                        continue
                    buffer = ctypes.create_string_buffer(size.value)
                    read = ctypes.c_uint32()
                    if not read_file(
                        handle,
                        buffer,
                        size.value,
                        ctypes.byref(read),
                        None,
                    ):
                        counts["read_failures"] += 1
                        continue
                    raw = bytes(buffer.raw[:read.value])
                    if read.value != size.value:
                        counts["read_size_mismatch"] += 1
                        continue
                finally:
                    close_handle(handle)

                valid = True
                if not raw.endswith(b"\\n") or b"\\n\\n" in raw:
                    counts["malformed"] += 1
                    valid = False
                parsed_rows = []
                if valid:
                    try:
                        for line in raw[:-1].split(b"\\n"):
                            value = json.loads(
                                line.decode("utf-8"),
                                parse_constant=lambda value: (
                                    (_ for _ in ()).throw(
                                        ValueError(value)
                                    )
                                ),
                            )
                            parsed_rows.append(value)
                            if contract.canonical_json_bytes(value) != line:
                                counts["noncanonical"] += 1
                                valid = False
                            if not private_metadata.validate_private_metadata_record(
                                value
                            )["accepted"]:
                                counts["invalid_rows"] += 1
                                valid = False
                    except (UnicodeDecodeError, ValueError, TypeError):
                        counts["malformed"] += 1
                        valid = False
                if not valid:
                    time.sleep(0.001)
                    continue

                counts["successful_reads"] += 1
                digest = hashlib.sha256(raw).hexdigest()
                if digest == old_digest and len(raw) == old_size:
                    counts["old"] += 1
                    if counts["old"] == 5:
                        ready.write_text("old:5", encoding="utf-8")
                elif digest == new_digest and len(raw) == new_size:
                    counts["new"] += 1
                    if counts["new"] == 5:
                        observed_new.write_text("new:5", encoding="utf-8")
                else:
                    counts["unexpected_valid"] += 1
                time.sleep(0.001)

            print(
                json.dumps(
                    {
                        "share_mode": SHARE_MODE,
                        "counts": counts,
                    },
                    separators=(",", ":"),
                )
            )
            """
        )
        writer_source = textwrap.dedent(
            """
            import json
            import os
            from pathlib import Path

            from wom_kit import archive_services

            result = archive_services._private_objet_source_metadata_write_legacy_core(
                Path(os.environ["WOM_P_ROOT"]),
                intake=os.environ["WOM_P_INTAKE"],
                expected_intake_sha256=os.environ["WOM_P_INTAKE_SHA"],
                expected_plan_sha256=os.environ["WOM_P_PLAN_SHA"],
                dry_run=False,
                approve=True,
                reviewed_by="operator:concurrent-reader-writer",
                affirm_private_metadata_reviewed=True,
                affirm_external_writers_quiescent=True,
            )
            print(json.dumps(result, separators=(",", ":")))
            """
        )
        reader_environment = self._interruption_environment(
            hook="concurrent_reader",
            plan_sha256="unused",
            marker=ready,
        )
        reader_environment.update(
            {
                "WOM_R_PATH": str(manifest_path),
                "WOM_R_READY": str(ready),
                "WOM_R_NEW": str(observed_new),
                "WOM_R_STOP": str(stop),
                "WOM_R_OLD_SHA": hashlib.sha256(
                    manifest_before
                ).hexdigest(),
                "WOM_R_NEW_SHA": hashlib.sha256(manifest_after).hexdigest(),
                "WOM_R_OLD_SIZE": str(len(manifest_before)),
                "WOM_R_NEW_SIZE": str(len(manifest_after)),
            }
        )
        writer_environment = self._interruption_environment(
            hook="concurrent_reader_writer",
            plan_sha256=second_plan["plan_sha256"],
            marker=observed_new,
        )
        writer_environment.update(
            {
                "WOM_P_INTAKE": second_relative,
                "WOM_P_INTAKE_SHA": second_sha256,
            }
        )
        reader_process: subprocess.Popen[str] | None = None
        writer_process: subprocess.Popen[str] | None = None
        try:
            reader_process = subprocess.Popen(
                [sys.executable, "-c", reader_source],
                env=reader_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 30
            while not ready.exists() and time.monotonic() < deadline:
                if reader_process.poll() is not None:
                    stdout, stderr = reader_process.communicate()
                    self.fail(
                        "reader exited before observing old manifest: "
                        f"{stdout}\n{stderr}"
                    )
                time.sleep(0.01)
            self.assertTrue(ready.exists(), "old manifest marker timed out")
            self.assertEqual(ready.read_text(encoding="utf-8"), "old:5")
            self.assertIsNone(reader_process.poll())

            writer_process = subprocess.Popen(
                [sys.executable, "-c", writer_source],
                env=writer_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            writer_stdout, writer_stderr = writer_process.communicate(
                timeout=90
            )
            self.assertEqual(
                writer_process.returncode,
                0,
                writer_stdout + writer_stderr,
            )
            writer_result = json.loads(writer_stdout.strip())
            writer_action = writer_result["action"]
            self.assertIn(writer_action, {"applied", "manual_hold"})

            # Ordinary FileRenameInfo is intentionally used instead of the
            # forbidden POSIX-replacement profile. A broad-sharing reader can
            # make NTFS return ERROR_ACCESS_DENIED before any rename occurs.
            # That exact result must be a cleaned no-change hold. It is not
            # authority to retry inside the failed invocation.
            if writer_action == "manual_hold":
                self.assertEqual(writer_result["action"], "manual_hold")
                self.assertEqual(
                    writer_result["blockers"],
                    ["private_metadata_manifest_replacement_failed"],
                )
                self.assertEqual(writer_result["files_written"], [])
                self.assertIsNone(writer_result["receipt_sha256"])
                self.assertEqual(
                    writer_result["hold_context"],
                    {
                        "failure_stage": "manifest_replacement",
                        "last_verified_authority_state": "before",
                        "cleanup_state": "completed",
                    },
                )
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertFalse(
                    (
                        self.root
                        / second_plan["plan"]["receipt_relative_path"]
                    ).exists()
                )
                self._assert_no_transaction_residue(second_plan)
            else:
                deadline = time.monotonic() + 30
                while (
                    not observed_new.exists()
                    and time.monotonic() < deadline
                ):
                    if reader_process.poll() is not None:
                        stdout, stderr = reader_process.communicate()
                        self.fail(
                            "reader exited before observing new manifest: "
                            f"{stdout}\n{stderr}"
                        )
                    time.sleep(0.01)
                self.assertTrue(
                    observed_new.exists(),
                    "new manifest marker timed out",
                )
                self.assertEqual(
                    observed_new.read_text(encoding="utf-8"),
                    "new:5",
                )
            stop.write_text("stop", encoding="utf-8")
            reader_stdout, reader_stderr = reader_process.communicate(
                timeout=30
            )
            self.assertEqual(
                reader_process.returncode,
                0,
                reader_stdout + reader_stderr,
            )
            reader_result = json.loads(reader_stdout.strip())

            if writer_action == "manual_hold":
                fresh_plan = self._dry_run_for_intake(
                    intake_relative=second_relative,
                    intake_sha256=second_sha256,
                )
                self.assertEqual(fresh_plan["action"], "append")
                completed = self._write_for_intake(
                    intake_relative=second_relative,
                    intake_sha256=second_sha256,
                    expected_plan_sha256=fresh_plan["plan_sha256"],
                    reviewed_by="operator:concurrent-reader-writer",
                )
                self.assertEqual(completed["action"], "applied")
        finally:
            for process in (writer_process, reader_process):
                if process is not None and process.poll() is None:
                    process.kill()
                    try:
                        process.communicate(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            for marker in markers:
                marker.unlink(missing_ok=True)

        counts = reader_result["counts"]
        self.assertEqual(reader_result["share_mode"], 0x7)
        self.assertGreaterEqual(counts["successful_reads"], 10)
        self.assertGreaterEqual(counts["old"], 5)
        if writer_action == "applied":
            self.assertGreaterEqual(counts["new"], 5)
        else:
            self.assertEqual(counts["new"], 0)
        self.assertEqual(counts["read_size_mismatch"], 0)
        self.assertEqual(counts["malformed"], 0)
        self.assertEqual(counts["noncanonical"], 0)
        self.assertEqual(counts["invalid_rows"], 0)
        self.assertEqual(counts["unexpected_valid"], 0)
        self.assertGreater(
            counts["successful_reads"],
            (
                counts["open_failures"]
                + counts["size_failures"]
                + counts["read_failures"]
            ),
        )
        self.assertEqual(manifest_path.read_bytes(), manifest_after)

    def test_interruption_after_first_persistent_lock_restarts_append(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="first_lock",
            plan_sha256=append_plan["plan_sha256"],
        )
        self.assertTrue((self.root / contract.OBJECT_MANIFEST_LOCK).is_file())
        self.assertFalse(
            (self.root / contract.PRIVATE_METADATA_LOCK).exists()
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(fresh["action"], "append")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "applied")
        self.assertTrue(
            (self.root / contract.PRIVATE_METADATA_LOCK).is_file()
        )

    def _assert_receipt_directory_interruption(
        self,
        *,
        created_count: int,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook=f"receipt_dir_{created_count}",
            plan_sha256=append_plan["plan_sha256"],
        )
        receipt_directories = (
            self.root / "receipts",
            self.root / "receipts" / "objects",
            self.root / "receipts" / "objects" / "private-source-metadata",
        )
        for index, directory in enumerate(receipt_directories, start=1):
            self.assertEqual(directory.is_dir(), index <= created_count)
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "append")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "applied")

    def test_interruption_after_receipts_directory_restarts_append(
        self,
    ) -> None:
        self._assert_receipt_directory_interruption(created_count=1)

    def test_interruption_after_receipt_objects_directory_restarts_append(
        self,
    ) -> None:
        self._assert_receipt_directory_interruption(created_count=2)

    def test_interruption_after_private_receipt_directory_restarts_append(
        self,
    ) -> None:
        self._assert_receipt_directory_interruption(created_count=3)

    def test_interruption_at_journal_twin_restarts_rollback(self) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="journal_twin",
            plan_sha256=append_plan["plan_sha256"],
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        temp_path = self.root / journal_temp
        journal_path = self.root / contract.JOURNAL_PATH
        self.assertTrue(temp_path.is_file())
        self.assertTrue(journal_path.is_file())
        self.assertEqual(temp_path.stat().st_ino, journal_path.stat().st_ino)
        self.assertEqual(temp_path.stat().st_nlink, 2)
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[1:]:
            self.assertFalse((self.root / relative).exists())
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse(temp_path.exists())
        self.assertFalse(journal_path.exists())

    def test_interruption_at_journal_only_restarts_rollback(self) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="journal_only",
            plan_sha256=append_plan["plan_sha256"],
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[1:]:
            self.assertFalse((self.root / relative).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())

    def test_interruption_at_partial_manifest_temp_restarts_rollback(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="manifest_partial",
            plan_sha256=append_plan["plan_sha256"],
        )
        owned_temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        manifest_temp = owned_temps[1]
        expected = contract.build_private_metadata_row(_intake())[
            "stored_row_bytes"
        ]
        observed = (self.root / manifest_temp).read_bytes()
        self.assertGreater(len(observed), 0)
        self.assertLess(len(observed), len(expected))
        self.assertTrue(expected.startswith(observed))
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertFalse((self.root / owned_temps[0]).exists())
        self.assertFalse((self.root / owned_temps[2]).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse((self.root / manifest_temp).exists())

    def test_interruption_at_full_manifest_temp_restarts_rollback(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="manifest_full",
            plan_sha256=append_plan["plan_sha256"],
        )
        owned_temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        manifest_temp = owned_temps[1]
        expected = contract.build_private_metadata_row(_intake())[
            "stored_row_bytes"
        ]
        self.assertEqual((self.root / manifest_temp).read_bytes(), expected)
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertFalse((self.root / owned_temps[0]).exists())
        self.assertFalse((self.root / owned_temps[2]).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse((self.root / manifest_temp).exists())

    def test_interruption_after_manifest_replace_restarts_recovery(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="manifest_replaced",
            plan_sha256=append_plan["plan_sha256"],
        )
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_before = manifest_path.read_bytes()
        manifest_stat_before = manifest_path.stat()
        self.assertEqual(
            manifest_before,
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ],
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        owned_temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        for relative in owned_temps:
            self.assertFalse((self.root / relative).exists())
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(fresh["action"], "recovery_required")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "recovery_completed")
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        manifest_stat_after = manifest_path.stat()
        self.assertEqual(manifest_stat_after.st_ino, manifest_stat_before.st_ino)
        self.assertEqual(
            manifest_stat_after.st_mtime_ns,
            manifest_stat_before.st_mtime_ns,
        )

    def test_interruption_at_receipt_twin_restarts_applied_cleanup(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="receipt_twin",
            plan_sha256=append_plan["plan_sha256"],
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        temp_path = self.root / receipt_temp
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        self.assertTrue(temp_path.is_file())
        self.assertTrue(receipt_path.is_file())
        self.assertEqual(temp_path.stat().st_ino, receipt_path.stat().st_ino)
        self.assertEqual(temp_path.stat().st_nlink, 2)
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_before = manifest_path.read_bytes()
        manifest_stat_before = manifest_path.stat()
        receipt_before = receipt_path.read_bytes()
        receipt_stat_before = receipt_path.stat()
        self.assertEqual(fresh["action"], "already_applied")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "already_applied")
        self.assertFalse(temp_path.exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        manifest_stat_after = manifest_path.stat()
        self.assertEqual(manifest_stat_after.st_ino, manifest_stat_before.st_ino)
        self.assertEqual(
            manifest_stat_after.st_mtime_ns,
            manifest_stat_before.st_mtime_ns,
        )
        self.assertEqual(receipt_path.read_bytes(), receipt_before)
        receipt_stat_after = receipt_path.stat()
        self.assertEqual(receipt_stat_after.st_ino, receipt_stat_before.st_ino)
        self.assertEqual(
            receipt_stat_after.st_mtime_ns,
            receipt_stat_before.st_mtime_ns,
        )

    def test_interruption_at_receipt_only_restarts_applied_cleanup(
        self,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook="receipt_only",
            plan_sha256=append_plan["plan_sha256"],
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        self.assertFalse((self.root / receipt_temp).exists())
        self.assertTrue(receipt_path.is_file())
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_before = manifest_path.read_bytes()
        manifest_stat_before = manifest_path.stat()
        receipt_before = receipt_path.read_bytes()
        receipt_stat_before = receipt_path.stat()
        self.assertEqual(fresh["action"], "already_applied")
        completed = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
        )
        self.assertEqual(completed["action"], "already_applied")
        self.assertFalse((self.root / receipt_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        manifest_stat_after = manifest_path.stat()
        self.assertEqual(manifest_stat_after.st_ino, manifest_stat_before.st_ino)
        self.assertEqual(
            manifest_stat_after.st_mtime_ns,
            manifest_stat_before.st_mtime_ns,
        )
        self.assertEqual(receipt_path.read_bytes(), receipt_before)
        receipt_stat_after = receipt_path.stat()
        self.assertEqual(receipt_stat_after.st_ino, receipt_stat_before.st_ino)
        self.assertEqual(
            receipt_stat_after.st_mtime_ns,
            receipt_stat_before.st_mtime_ns,
        )

    def _assert_terminal_residue_interruption(
        self,
        *,
        hook: str,
        journal_survives: bool,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._interrupt_approval_at(
            hook=hook,
            plan_sha256=append_plan["plan_sha256"],
        )
        journal_path = self.root / contract.JOURNAL_PATH
        self.assertEqual(journal_path.exists(), journal_survives)
        if journal_survives:
            self.assertTrue(journal_path.is_file())
            self.assertEqual(journal_path.stat().st_nlink, 1)
        self.assertTrue(
            (self.root / contract.PRIVATE_MANIFEST_PATH).is_file()
        )
        self.assertTrue(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).is_file()
        )
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())
        self.assertEqual(fresh["action"], "already_applied")
        self.assertNotEqual(fresh["action"], "manual_hold")

    def test_interruption_after_residue_true_before_close_restarts_clean_applied(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_true_before_close",
            journal_survives=False,
        )

    def test_interruption_after_residue_close_failure_before_false_is_clean(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_close_before_false",
            journal_survives=False,
        )

    def test_interruption_after_residue_false_before_postproof_keeps_journal(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_false_before_postproof",
            journal_survives=True,
        )

    def test_failed_true_no_effect_exit_before_same_handle_keeps_journal(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_failed_true_no_effect_before_same_handle",
            journal_survives=True,
        )

    def test_failed_true_delete_pending_exit_before_same_handle_is_clean(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_failed_true_delete_pending_before_same_handle",
            journal_survives=False,
        )

    def test_failed_true_post_link_one_exit_before_release_keeps_journal(
        self,
    ) -> None:
        self._assert_terminal_residue_interruption(
            hook="residue_failed_true_after_link_one_before_release",
            journal_survives=True,
        )

    def _assert_terminal_failstop_restart(
        self,
        *,
        kind: str,
        journal_survives: bool,
    ) -> None:
        append_plan = self._dry_run()
        fresh = self._terminal_failstop_approval(
            kind=kind,
            plan_sha256=append_plan["plan_sha256"],
        )
        journal_path = self.root / contract.JOURNAL_PATH
        self.assertEqual(journal_path.exists(), journal_survives)
        if journal_survives:
            self.assertEqual(journal_path.stat().st_nlink, 1)
        self.assertEqual(fresh["action"], "already_applied")
        replay = self._write(
            expected_plan_sha256=fresh["plan_sha256"],
            reviewed_by="operator:terminal-restart-test",
        )
        self.assertEqual(replay["action"], "already_applied")
        self.assertFalse(journal_path.exists())

    def test_residue_terminal_release_three_ambiguities_failstop_74(
        self,
    ) -> None:
        self._assert_terminal_failstop_restart(
            kind="residue",
            journal_survives=True,
        )

    def test_failed_true_terminal_three_ambiguities_failstop_74(
        self,
    ) -> None:
        self._assert_terminal_failstop_restart(
            kind="residue_failed_true",
            journal_survives=True,
        )

    def test_tracked_handle_three_release_ambiguities_failstop_74(
        self,
    ) -> None:
        self._assert_terminal_failstop_restart(
            kind="tracked",
            journal_survives=False,
        )

    def test_lock_handle_three_release_ambiguities_failstop_74(
        self,
    ) -> None:
        self._assert_terminal_failstop_restart(
            kind="lock",
            journal_survives=False,
        )

    def test_guard_handle_three_release_ambiguities_failstop_74(
        self,
    ) -> None:
        self._assert_terminal_failstop_restart(
            kind="guard",
            journal_survives=False,
        )

    def test_rollback_only_cleans_exact_residue_and_never_appends(self) -> None:
        receipt, journal = self._append_fixture()
        del receipt
        self._materialize_persistent_prefix()
        authority_key = journal["authority_key_sha256"]
        temp_paths = contract.owned_temp_relative_paths(authority_key)
        (self.root / contract.JOURNAL_PATH).write_bytes(
            contract.stored_json_bytes(journal)
        )
        expected_after = (
            contract.build_private_metadata_row(_intake())["stored_row_bytes"]
        )
        (self.root / temp_paths[1]).write_bytes(expected_after[:23])

        rollback = self._dry_run()
        self.assertEqual(rollback["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=rollback["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in temp_paths:
            self.assertFalse((self.root / relative).exists())
        self.assertFalse(
            (self.root / rollback["plan"]["receipt_relative_path"]).exists()
        )

    def test_rollback_disposes_exact_journal_publication_twin(self) -> None:
        _, journal = self._append_fixture()
        self._materialize_persistent_prefix()
        journal_temp = contract.owned_temp_relative_paths(
            journal["authority_key_sha256"]
        )[0]
        temp_path = self.root / journal_temp
        temp_path.write_bytes(contract.stored_json_bytes(journal))
        os.link(temp_path, self.root / contract.JOURNAL_PATH)
        self.assertEqual(temp_path.stat().st_nlink, 2)

        rollback = self._dry_run()
        self.assertEqual(rollback["action"], "rollback_required")
        completed = self._write(
            expected_plan_sha256=rollback["plan_sha256"],
        )
        self.assertEqual(completed["action"], "rollback_completed")
        self.assertFalse(temp_path.exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )

    def test_rollback_receipt_race_preserves_fixed_journal(self) -> None:
        receipt, journal = self._append_fixture()
        self._materialize_persistent_prefix()
        journal_path = self.root / contract.JOURNAL_PATH
        journal_path.write_bytes(contract.stored_json_bytes(journal))

        rollback = self._dry_run()
        self.assertEqual(rollback["action"], "rollback_required")
        receipt_path = self.root / rollback["plan"]["receipt_relative_path"]
        planted = contract.stored_json_bytes(receipt)
        original_absent = win32.path_is_absent
        raced = False

        def race_receipt(
            guard: object,
            path: Path,
            *,
            reason: str,
            operation: str,
        ) -> bool:
            nonlocal raced
            if (
                operation == "rollback_commit_receipt_absence"
                and not raced
            ):
                receipt_path.write_bytes(planted)
                raced = True
            return original_absent(
                guard,
                path,
                reason=reason,
                operation=operation,
            )

        with mock.patch.object(
            win32,
            "path_is_absent",
            side_effect=race_receipt,
        ):
            failed = self._write(
                expected_plan_sha256=rollback["plan_sha256"],
            )

        self.assertTrue(raced)
        self.assertEqual(failed["action"], "manual_hold")
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "preserved_unverified",
            },
        )
        self.assertEqual(receipt_path.read_bytes(), planted)
        self.assertTrue(journal_path.is_file())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(self._dry_run()["action"], "manual_hold")

    def test_recovery_publishes_receipt_without_rewriting_manifest(self) -> None:
        receipt, journal = self._append_fixture()
        self._materialize_persistent_prefix()
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_path.write_bytes(
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ]
        )
        (self.root / contract.JOURNAL_PATH).write_bytes(
            contract.stored_json_bytes(journal)
        )
        receipt_temp = contract.owned_temp_relative_paths(
            journal["authority_key_sha256"]
        )[2]
        (self.root / receipt_temp).write_bytes(
            contract.stored_json_bytes(receipt)[:29]
        )
        before = manifest_path.stat()

        recovery = self._dry_run()
        self.assertEqual(recovery["action"], "recovery_required")
        completed = self._write(
            expected_plan_sha256=recovery["plan_sha256"],
        )
        self.assertEqual(completed["action"], "recovery_completed")
        after = manifest_path.stat()
        self.assertEqual(after.st_ino, before.st_ino)
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(
            (self.root / recovery["plan"]["receipt_relative_path"]).read_bytes(),
            contract.stored_json_bytes(receipt),
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse((self.root / receipt_temp).exists())

    def test_separately_approved_completed_residue_cleanup_is_exact(self) -> None:
        append_plan = self._dry_run()
        applied = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
        )
        self.assertEqual(applied["action"], "applied")
        receipt_path = self.root / append_plan["plan"]["receipt_relative_path"]
        receipt_raw = receipt_path.read_bytes()
        receipt_mtime = receipt_path.stat().st_mtime_ns
        receipt = json.loads(receipt_raw.decode("utf-8"))
        journal = writer._journal_for_receipt(receipt)
        (self.root / contract.JOURNAL_PATH).write_bytes(
            contract.stored_json_bytes(journal)
        )

        cleanup_plan = self._dry_run()
        self.assertEqual(cleanup_plan["action"], "already_applied")
        cleaned = self._write(
            expected_plan_sha256=cleanup_plan["plan_sha256"],
            reviewed_by="operator:cleanup-approval",
        )
        self.assertEqual(cleaned["action"], "already_applied")
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(receipt_path.read_bytes(), receipt_raw)
        self.assertEqual(receipt_path.stat().st_mtime_ns, receipt_mtime)

    def test_completed_receipt_publication_twin_cleanup_keeps_final(self) -> None:
        append_plan = self._dry_run()
        applied = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
        )
        self.assertEqual(applied["action"], "applied")
        receipt_path = self.root / append_plan["plan"]["receipt_relative_path"]
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw.decode("utf-8"))
        journal = writer._journal_for_receipt(receipt)
        (self.root / contract.JOURNAL_PATH).write_bytes(
            contract.stored_json_bytes(journal)
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        temp_path = self.root / receipt_temp
        os.link(receipt_path, temp_path)
        self.assertEqual(receipt_path.stat().st_nlink, 2)

        cleanup_plan = self._dry_run()
        self.assertEqual(cleanup_plan["action"], "already_applied")
        cleaned = self._write(
            expected_plan_sha256=cleanup_plan["plan_sha256"],
        )
        self.assertEqual(cleaned["action"], "already_applied")
        self.assertFalse(temp_path.exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(receipt_path.read_bytes(), receipt_raw)
        self.assertEqual(receipt_path.stat().st_nlink, 1)

    def test_hardlink_failure_before_api_cleans_retained_owned_temp(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original = win32._publish_hard_link

        def fail_first_publication(*args: object, **kwargs: object) -> object:
            del args, kwargs
            raise win32.Win32SafetyError(
                win32.HARDLINK_PUBLICATION_FAILED,
                operation="synthetic_hardlink_failure",
            )

        with mock.patch.object(
            win32,
            "_publish_hard_link",
            side_effect=fail_first_publication,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertIsNotNone(original)
        self.assertEqual(failed["action"], "manual_hold")
        self.assertEqual(failed["plan"], append_plan["plan"])
        self.assertEqual(
            failed["plan_sha256"],
            append_plan["plan_sha256"],
        )
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_hardlink_publication_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "hardlink_publication",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(self._dry_run()["action"], "append")

    def test_journal_temp_flush_failure_transfers_and_cleans_authority(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_flush = win32._Win32BoundFile.flush
        failed_once = False

        def fail_journal_flush(
            bound: object,
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal failed_once
            if (
                not failed_once
                and getattr(bound, "path", Path()).name.endswith(
                    ".journal.tmp"
                )
            ):
                failed_once = True
                raise win32.Win32SafetyError(
                    win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                    operation="flush_file_buffers",
                )
            original_flush(bound, *args, **kwargs)

        with mock.patch.object(
            win32._Win32BoundFile,
            "flush",
            new=fail_journal_flush,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(failed_once)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_materialization_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(self._dry_run()["action"], "append")

    def test_journal_temp_create_api_failure_has_no_obligation(
        self,
    ) -> None:
        append_plan = self._dry_run()
        api = win32._api()
        original_create = api.create_file
        injected = False

        def fail_journal_create(*args: object) -> object:
            nonlocal injected
            if (
                not injected
                and args
                and str(args[0]).endswith(".journal.tmp")
                and len(args) > 4
                and args[4] == win32._CREATE_NEW
            ):
                injected = True
                ctypes.set_last_error(5)
                return api.invalid_handle_value
            return original_create(*args)

        with mock.patch.object(
            api,
            "create_file",
            side_effect=fail_journal_create,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_materialization_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "before",
                "cleanup_state": "not_required",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())

    def test_journal_temp_post_create_refusal_cleans_raw_authority(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_validate = win32._validate_regular_information
        injected = False

        def fail_post_create_validation(
            information: object,
            *,
            reason: str,
            operation: str,
            expected_link_count: int | None,
            expected_volume_serial: int | None,
        ) -> None:
            nonlocal injected
            if operation == "owned_temp_create_new" and not injected:
                injected = True
                raise win32.Win32SafetyError(
                    win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                    operation="owned_temp_post_create_validation",
                )
            original_validate(
                information,
                reason=reason,
                operation=operation,
                expected_link_count=expected_link_count,
                expected_volume_serial=expected_volume_serial,
            )

        with mock.patch.object(
            win32,
            "_validate_regular_information",
            side_effect=fail_post_create_validation,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_materialization_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(self._dry_run()["action"], "append")

    def test_journal_temp_final_digest_failure_cleans_exact_source(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_sha256 = win32._Win32BoundFile.sha256
        injected = False

        def wrong_journal_digest(
            bound: object,
            *args: object,
            **kwargs: object,
        ) -> str:
            nonlocal injected
            if (
                not injected
                and getattr(bound, "path", Path()).name.endswith(
                    ".journal.tmp"
                )
            ):
                injected = True
                return "sha256:" + ("0" * 64)
            return original_sha256(bound, *args, **kwargs)

        with mock.patch.object(
            win32._Win32BoundFile,
            "sha256",
            new=wrong_journal_digest,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_materialization_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())

    def test_journal_temp_final_identity_failure_keeps_specific_primary(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_validate = win32.validate_bound_path
        injected = False

        def reject_journal_identity(
            guard: object,
            bound: object,
            *,
            expected_link_count: int | None = None,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
        ) -> object:
            nonlocal injected
            if (
                not injected
                and getattr(bound, "path", Path()).name.endswith(
                    ".journal.tmp"
                )
                and reason == win32.OWNED_TEMP_SUBSTITUTED
            ):
                injected = True
                raise win32.Win32SafetyError(
                    win32.OWNED_TEMP_SUBSTITUTED,
                    operation="synthetic_owned_temp_identity",
                )
            return original_validate(
                guard,
                bound,
                expected_link_count=expected_link_count,
                reason=reason,
            )

        with mock.patch.object(
            win32,
            "validate_bound_path",
            side_effect=reject_journal_identity,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_substituted"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())

    def test_journal_hardlink_api_no_change_transfers_and_cleans(
        self,
    ) -> None:
        append_plan = self._dry_run()
        api = win32._api()

        def fail_create_hard_link(*args: object) -> bool:
            del args
            ctypes.set_last_error(5)
            return False

        with mock.patch.object(
            api,
            "create_hard_link",
            side_effect=fail_create_hard_link,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_hardlink_publication_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "hardlink_publication",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        self.assertFalse((self.root / journal_temp).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(self._dry_run()["action"], "append")

    def test_journal_hardlink_post_api_ambiguity_preserves_twin(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_open = win32._open_bound_file_absolute
        injected = False

        def fail_transitional_open(
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal injected
            if (
                kwargs.get("operation") == "hardlink_transitional_open"
                and not injected
            ):
                injected = True
                raise win32.Win32SafetyError(
                    win32.FINAL_VERIFICATION_FAILED,
                    operation="hardlink_transitional_open",
                )
            return original_open(*args, **kwargs)

        with mock.patch.object(
            win32,
            "_open_bound_file_absolute",
            side_effect=fail_transitional_open,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "preserved_unverified",
            },
        )
        journal_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[0]
        temp_path = self.root / journal_temp
        journal_path = self.root / contract.JOURNAL_PATH
        self.assertTrue(temp_path.is_file())
        self.assertTrue(journal_path.is_file())
        self.assertEqual(temp_path.stat().st_ino, journal_path.stat().st_ino)
        self.assertEqual(temp_path.stat().st_nlink, 2)
        self.assertEqual(self._dry_run()["action"], "rollback_required")

    def test_manifest_rename_api_no_change_cleans_mt_then_j(self) -> None:
        append_plan = self._dry_run()
        api = win32._api()
        original_set = api.set_file_information
        injected = False

        def fail_rename_once(
            handle: int,
            information_class: int,
            buffer: object,
            buffer_size: int,
        ) -> object:
            nonlocal injected
            if (
                information_class == win32._FILE_RENAME_INFO_CLASS
                and not injected
            ):
                injected = True
                ctypes.set_last_error(5)
                return False
            return original_set(
                handle,
                information_class,
                buffer,
                buffer_size,
            )

        with mock.patch.object(
            api,
            "set_file_information",
            side_effect=fail_rename_once,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_manifest_replacement_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "manifest_replacement",
                "last_verified_authority_state": "before",
                "cleanup_state": "completed",
            },
        )
        temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        self.assertFalse((self.root / temps[1]).exists())
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(self._dry_run()["action"], "append")

    def test_manifest_rename_post_api_ambiguity_preserves_recovery(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_open = win32._open_bound_file_absolute
        injected = False

        def fail_manifest_transitional(
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal injected
            if (
                kwargs.get("operation") == "manifest_transitional_open"
                and not injected
            ):
                injected = True
                raise win32.Win32SafetyError(
                    win32.FINAL_VERIFICATION_FAILED,
                    operation="manifest_transitional_open",
                )
            return original_open(*args, **kwargs)

        with mock.patch.object(
            win32,
            "_open_bound_file_absolute",
            side_effect=fail_manifest_transitional,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_final_verification_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "not_required",
            },
        )
        temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        self.assertFalse((self.root / temps[1]).exists())
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(
            (self.root / contract.PRIVATE_MANIFEST_PATH).read_bytes(),
            contract.build_private_metadata_row(_intake())[
                "stored_row_bytes"
            ],
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(self._dry_run()["action"], "recovery_required")

    def test_receipt_temp_flush_failure_cleans_rt_and_keeps_recovery(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_flush = win32._Win32BoundFile.flush
        injected = False

        def fail_receipt_flush(
            bound: object,
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal injected
            if (
                not injected
                and getattr(bound, "path", Path()).name.endswith(
                    ".receipt.tmp"
                )
            ):
                injected = True
                raise win32.Win32SafetyError(
                    win32.OWNED_TEMP_MATERIALIZATION_FAILED,
                    operation="flush_file_buffers",
                )
            original_flush(bound, *args, **kwargs)

        with mock.patch.object(
            win32._Win32BoundFile,
            "flush",
            new=fail_receipt_flush,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_owned_temp_materialization_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "owned_temp_materialization",
                "last_verified_authority_state": "after",
                "cleanup_state": "completed",
            },
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        self.assertFalse((self.root / receipt_temp).exists())
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertTrue(
            (self.root / contract.PRIVATE_MANIFEST_PATH).is_file()
        )
        self.assertEqual(self._dry_run()["action"], "recovery_required")

    def test_receipt_hardlink_api_no_change_cleans_rt_only(self) -> None:
        append_plan = self._dry_run()
        api = win32._api()
        original_create = api.create_hard_link
        calls = 0

        def fail_second_hardlink(*args: object) -> object:
            nonlocal calls
            calls += 1
            if calls == 2:
                ctypes.set_last_error(5)
                return False
            return original_create(*args)

        with mock.patch.object(
            api,
            "create_hard_link",
            side_effect=fail_second_hardlink,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(calls, 2)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_hardlink_publication_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "hardlink_publication",
                "last_verified_authority_state": "after",
                "cleanup_state": "completed",
            },
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        self.assertFalse((self.root / receipt_temp).exists())
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(self._dry_run()["action"], "recovery_required")

    def test_receipt_hardlink_post_api_ambiguity_preserves_twin(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_open = win32._open_bound_file_absolute
        publication_opens = 0

        def fail_second_transitional(
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal publication_opens
            if kwargs.get("operation") == "hardlink_transitional_open":
                publication_opens += 1
                if publication_opens == 2:
                    raise win32.Win32SafetyError(
                        win32.FINAL_VERIFICATION_FAILED,
                        operation="hardlink_transitional_open",
                    )
            return original_open(*args, **kwargs)

        with mock.patch.object(
            win32,
            "_open_bound_file_absolute",
            side_effect=fail_second_transitional,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(publication_opens, 2)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "preserved_unverified",
            },
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        temp_path = self.root / receipt_temp
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        self.assertTrue(temp_path.is_file())
        self.assertTrue(receipt_path.is_file())
        self.assertEqual(temp_path.stat().st_ino, receipt_path.stat().st_ino)
        self.assertEqual(temp_path.stat().st_nlink, 2)
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def _assert_journal_handoff_close_fault(
        self,
        *,
        fault_operation: str,
        expected_reason: str,
        expected_stage: str,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        original_terminal_release = win32._release_terminal_bound_authority
        original_set_disposition = win32._set_disposition
        events: list[tuple[str, int, str]] = []
        injected = False
        failed_handle: int | None = None
        later_dispositions = 0

        def fail_journal_transitional_close(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, failed_handle
            raw_handle = int(bound.raw_handle)
            if operation == fault_operation and not injected:
                injected = True
                failed_handle = raw_handle
                events.append(("ordinary_failed", raw_handle, operation))
                raise win32.Win32SafetyError(
                    reason,
                    operation=operation,
                )
            if injected:
                events.append(("later_close", raw_handle, operation))
            original_close(bound, reason=reason, operation=operation)

        def record_terminal_release(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.RESIDUE_DISPOSITION_FAILED,
            operation: str = "residue_terminal_authority_release",
        ) -> None:
            raw_handle = int(bound.raw_handle)
            events.append(("terminal_release", raw_handle, operation))
            original_terminal_release(
                bound,
                reason=reason,
                operation=operation,
            )

        def count_later_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal later_dispositions
            if injected:
                later_dispositions += 1
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        with (
            mock.patch.object(
                win32._Win32BoundFile,
                "close",
                new=fail_journal_transitional_close,
            ),
            mock.patch.object(
                win32,
                "_release_terminal_bound_authority",
                new=record_terminal_release,
            ),
            mock.patch.object(
                win32,
                "_set_disposition",
                new=count_later_disposition,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )

        self.assertTrue(injected)
        self.assertIsNotNone(failed_handle)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0][0], "ordinary_failed")
        self.assertEqual(events[1][0], "terminal_release")
        self.assertEqual(events[0][1], failed_handle)
        self.assertEqual(events[1][1], failed_handle)
        self.assertEqual(later_dispositions, 0)
        self.assertEqual(
            failed["blockers"],
            [
                expected_reason,
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": expected_stage,
                "last_verified_authority_state": "before",
                "cleanup_state": "incomplete",
            },
        )
        journal_path = self.root / contract.JOURNAL_PATH
        self.assertTrue(journal_path.is_file())
        self.assertFalse(
            (
                self.root
                / contract.owned_temp_relative_paths(
                    append_plan["plan"]["authority_key_sha256"]
                )[0]
            ).exists()
        )
        self.assertEqual(self._dry_run()["action"], "rollback_required")

    def test_journal_source_close_fault_terminalizes_before_later_close(
        self,
    ) -> None:
        self._assert_journal_handoff_close_fault(
            fault_operation="hardlink_source_close",
            expected_reason="private_metadata_residue_disposition_failed",
            expected_stage="residue_disposition",
        )

    def test_journal_transitional_close_fault_terminalizes_before_later_close(
        self,
    ) -> None:
        self._assert_journal_handoff_close_fault(
            fault_operation="hardlink_transitional_close",
            expected_reason="private_metadata_final_verification_failed",
            expected_stage="final_verification",
        )

    def _assert_manifest_handoff_close_fault(
        self,
        *,
        fault_operation: str,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        original_terminal_release = win32._release_terminal_bound_authority
        original_set_disposition = win32._set_disposition
        events: list[tuple[str, int, str]] = []
        injected = False
        failed_handle: int | None = None
        later_dispositions = 0

        def fail_manifest_handoff_close(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, failed_handle
            raw_handle = int(bound.raw_handle)
            if operation == fault_operation and not injected:
                injected = True
                failed_handle = raw_handle
                events.append(("ordinary_failed", raw_handle, operation))
                raise win32.Win32SafetyError(
                    reason,
                    operation=operation,
                )
            if injected:
                events.append(("later_close", raw_handle, operation))
            original_close(bound, reason=reason, operation=operation)

        def record_terminal_release(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.RESIDUE_DISPOSITION_FAILED,
            operation: str = "residue_terminal_authority_release",
        ) -> None:
            raw_handle = int(bound.raw_handle)
            events.append(("terminal_release", raw_handle, operation))
            original_terminal_release(
                bound,
                reason=reason,
                operation=operation,
            )

        def count_later_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal later_dispositions
            if injected:
                later_dispositions += 1
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        with (
            mock.patch.object(
                win32._Win32BoundFile,
                "close",
                new=fail_manifest_handoff_close,
            ),
            mock.patch.object(
                win32,
                "_release_terminal_bound_authority",
                new=record_terminal_release,
            ),
            mock.patch.object(
                win32,
                "_set_disposition",
                new=count_later_disposition,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )

        self.assertTrue(injected)
        self.assertIsNotNone(failed_handle)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0][0], "ordinary_failed")
        self.assertEqual(events[1][0], "terminal_release")
        self.assertEqual(events[0][1], failed_handle)
        self.assertEqual(events[1][1], failed_handle)
        self.assertEqual(later_dispositions, 0)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "incomplete",
            },
        )
        manifest_path = self.root / contract.PRIVATE_MANIFEST_PATH
        manifest_bytes = manifest_path.read_bytes()
        self.assertEqual(
            contract.sha256_digest(manifest_bytes),
            append_plan["plan"]["private_manifest_after"]["sha256"],
        )
        self.assertEqual(
            len(manifest_bytes),
            append_plan["plan"]["private_manifest_after"]["byte_count"],
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertFalse(
            (
                self.root
                / contract.owned_temp_relative_paths(
                    append_plan["plan"]["authority_key_sha256"]
                )[1]
            ).exists()
        )
        self.assertFalse(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).exists()
        )
        self.assertEqual(self._dry_run()["action"], "recovery_required")

    def test_manifest_source_close_fault_terminalizes_before_later_close(
        self,
    ) -> None:
        self._assert_manifest_handoff_close_fault(
            fault_operation="manifest_renamed_source_close",
        )

    def test_manifest_transitional_close_fault_terminalizes_before_later_close(
        self,
    ) -> None:
        self._assert_manifest_handoff_close_fault(
            fault_operation="manifest_transitional_close",
        )

    def _assert_already_applied_handoff_close_fault(
        self,
        *,
        fault_operation: str,
        receipt_twin: bool,
    ) -> None:
        append_plan = self._dry_run()
        receipt = writer._receipt_for_append_plan(
            append_plan["plan"],
            reviewed_by=OPERATOR,
            privacy_class="private_archive",
        )
        journal = writer._journal_for_receipt(receipt)
        applied = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
        )
        self.assertEqual(applied["action"], "applied")

        journal_path = self.root / contract.JOURNAL_PATH
        journal_path.write_bytes(contract.stored_json_bytes(journal))
        receipt_path = (
            self.root / append_plan["plan"]["receipt_relative_path"]
        )
        receipt_temp = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )[2]
        receipt_temp_path = self.root / receipt_temp
        if receipt_twin:
            os.link(receipt_path, receipt_temp_path)
            self.assertEqual(receipt_path.stat().st_nlink, 2)
            self.assertEqual(
                receipt_path.stat().st_ino,
                receipt_temp_path.stat().st_ino,
            )

        cleanup_plan = self._dry_run()
        self.assertEqual(cleanup_plan["action"], "already_applied")
        original_close = win32._Win32BoundFile.close
        original_terminal_release = win32._release_terminal_bound_authority
        original_set_disposition = win32._set_disposition
        original_inventory = writer._inventory_receipt_directory
        original_receipt_chain = writer._observe_receipt_directory_chain
        original_manifest_observation = writer._observe_private_manifest
        original_authority_chain = writer._build_complete_authority_chain
        original_planning_context = writer._build_planning_context
        original_path_is_absent = win32.path_is_absent
        events: list[tuple[str, int, str]] = []
        injected = False
        failed_handle: int | None = None
        later_dispositions = 0
        post_fault_observations = {
            "receipt_inventory": 0,
            "receipt_directory_chain": 0,
            "manifest_path_observation": 0,
            "authority_chain_rebuild": 0,
            "planning_context": 0,
            "path_absence": 0,
        }

        def fail_exact_handoff_close(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, failed_handle
            raw_handle = int(bound.raw_handle)
            if operation == fault_operation and not injected:
                injected = True
                failed_handle = raw_handle
                events.append(("ordinary_failed", raw_handle, operation))
                raise win32.Win32SafetyError(
                    reason,
                    operation=operation,
                )
            if injected:
                events.append(("later_close", raw_handle, operation))
            original_close(bound, reason=reason, operation=operation)

        def record_terminal_release(
            bound: win32._Win32BoundFile,
            *,
            reason: str = win32.RESIDUE_DISPOSITION_FAILED,
            operation: str = "residue_terminal_authority_release",
        ) -> None:
            raw_handle = int(bound.raw_handle)
            events.append(("terminal_release", raw_handle, operation))
            original_terminal_release(
                bound,
                reason=reason,
                operation=operation,
            )

        def count_later_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal later_dispositions
            if injected:
                later_dispositions += 1
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        def count_post_fault_call(
            name: str,
            original: object,
        ) -> object:
            def wrapped(*args: object, **kwargs: object) -> object:
                if injected:
                    post_fault_observations[name] += 1
                return original(*args, **kwargs)

            return wrapped

        with (
            mock.patch.object(
                win32._Win32BoundFile,
                "close",
                new=fail_exact_handoff_close,
            ),
            mock.patch.object(
                win32,
                "_release_terminal_bound_authority",
                new=record_terminal_release,
            ),
            mock.patch.object(
                win32,
                "_set_disposition",
                new=count_later_disposition,
            ),
            mock.patch.object(
                writer,
                "_inventory_receipt_directory",
                new=count_post_fault_call(
                    "receipt_inventory",
                    original_inventory,
                ),
            ),
            mock.patch.object(
                writer,
                "_observe_receipt_directory_chain",
                new=count_post_fault_call(
                    "receipt_directory_chain",
                    original_receipt_chain,
                ),
            ),
            mock.patch.object(
                writer,
                "_observe_private_manifest",
                new=count_post_fault_call(
                    "manifest_path_observation",
                    original_manifest_observation,
                ),
            ),
            mock.patch.object(
                writer,
                "_build_complete_authority_chain",
                new=count_post_fault_call(
                    "authority_chain_rebuild",
                    original_authority_chain,
                ),
            ),
            mock.patch.object(
                writer,
                "_build_planning_context",
                new=count_post_fault_call(
                    "planning_context",
                    original_planning_context,
                ),
            ),
            mock.patch.object(
                win32,
                "path_is_absent",
                new=count_post_fault_call(
                    "path_absence",
                    original_path_is_absent,
                ),
            ),
        ):
            failed = self._write(
                expected_plan_sha256=cleanup_plan["plan_sha256"],
            )

        self.assertTrue(injected)
        self.assertIsNotNone(failed_handle)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0][0], "ordinary_failed")
        self.assertEqual(events[1][0], "terminal_release")
        self.assertEqual(events[0][1], failed_handle)
        self.assertEqual(events[1][1], failed_handle)
        self.assertEqual(later_dispositions, 0)
        self.assertEqual(
            post_fault_observations,
            {
                "receipt_inventory": 0,
                "receipt_directory_chain": 0,
                "manifest_path_observation": 0,
                "authority_chain_rebuild": 0,
                "planning_context": 0,
                "path_absence": 0,
            },
        )
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertTrue(journal_path.is_file())
        self.assertEqual(self._dry_run()["action"], "already_applied")
        if receipt_twin and fault_operation != (
            "narrow_handoff_transitional_close"
        ):
            self.assertTrue(receipt_temp_path.is_file())
            self.assertEqual(receipt_path.stat().st_nlink, 2)
            self.assertEqual(
                receipt_path.stat().st_ino,
                receipt_temp_path.stat().st_ino,
            )
        else:
            self.assertFalse(receipt_temp_path.exists())
            self.assertEqual(receipt_path.stat().st_nlink, 1)

    def test_applied_fixed_journal_current_close_reproves_applied(
        self,
    ) -> None:
        self._assert_already_applied_handoff_close_fault(
            fault_operation="residue_handoff_current_close",
            receipt_twin=False,
        )

    def test_applied_fixed_journal_transitional_close_reproves_applied(
        self,
    ) -> None:
        self._assert_already_applied_handoff_close_fault(
            fault_operation="residue_handoff_transitional_close",
            receipt_twin=False,
        )

    def test_applied_receipt_twin_survivor_close_reproves_applied(
        self,
    ) -> None:
        self._assert_already_applied_handoff_close_fault(
            fault_operation="twin_survivor_narrow_close",
            receipt_twin=True,
        )

    def test_applied_receipt_twin_residue_close_reproves_applied(
        self,
    ) -> None:
        self._assert_already_applied_handoff_close_fault(
            fault_operation="twin_residue_narrow_close",
            receipt_twin=True,
        )

    def test_applied_receipt_twin_transition_close_reproves_applied(
        self,
    ) -> None:
        self._assert_already_applied_handoff_close_fault(
            fault_operation="narrow_handoff_transitional_close",
            receipt_twin=True,
        )

    def test_applied_journal_disposition_failure_keeps_primary_and_j(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_set_disposition = win32._set_disposition
        attempts = 0
        at_failure: dict[str, object] | None = None

        def fail_fixed_journal_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal attempts, at_failure
            if operation == "file_disposition_info":
                attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        with mock.patch.object(
            win32,
            "_set_disposition",
            side_effect=fail_fixed_journal_disposition,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(attempts, 1)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertTrue(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).is_file()
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_applied_journal_failed_true_unproved_no_change_is_incomplete(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_set_disposition = win32._set_disposition
        original_same_handle_proof = (
            win32._prove_failed_disposition_same_handle_no_change
        )
        disposition_attempts = 0
        proof_attempts = 0
        at_failure: dict[str, object] | None = None

        def fail_fixed_journal_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal disposition_attempts, at_failure
            if operation == "file_disposition_info":
                disposition_attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        def fail_same_handle_proof(
            bound: object,
            *,
            reason: str,
        ) -> None:
            nonlocal proof_attempts
            proof_attempts += 1
            raise win32.Win32SafetyError(
                reason,
                operation="synthetic_failed_true_same_handle_unavailable",
            )

        with (
            mock.patch.object(
                win32,
                "_set_disposition",
                side_effect=fail_fixed_journal_disposition,
            ),
            mock.patch.object(
                win32,
                "_prove_failed_disposition_same_handle_no_change",
                side_effect=fail_same_handle_proof,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(disposition_attempts, 1)
        self.assertEqual(proof_attempts, 1)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")
        self.assertIs(
            original_same_handle_proof,
            win32._prove_failed_disposition_same_handle_no_change,
        )

    def test_applied_journal_failed_true_changed_state_is_terminally_unlinked(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_set_disposition = win32._set_disposition
        original_clear = win32._clear_disposition
        disposition_attempts = 0
        clear_attempts = 0
        at_failure: dict[str, object] | None = None

        def set_delete_pending_but_report_failure(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal disposition_attempts, at_failure
            if operation == "file_disposition_info":
                disposition_attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                original_set_disposition(
                    bound,
                    reason=reason,
                    operation=operation,
                )
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_set_disposition(
                bound,
                reason=reason,
                operation=operation,
            )

        def count_clear(*args: object, **kwargs: object) -> None:
            nonlocal clear_attempts
            clear_attempts += 1
            original_clear(*args, **kwargs)

        with (
            mock.patch.object(
                win32,
                "_set_disposition",
                side_effect=set_delete_pending_but_report_failure,
            ),
            mock.patch.object(
                win32,
                "_clear_disposition",
                side_effect=count_clear,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(disposition_attempts, 1)
        self.assertEqual(clear_attempts, 0)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_applied_journal_post_close_absence_failure_is_preserved(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_absent = win32.path_is_absent
        injected = False

        def fail_journal_absence(
            guard: object,
            path: Path,
            *,
            reason: str,
            operation: str,
        ) -> bool:
            nonlocal injected
            if (
                operation == "residue_disposition_absence"
                and not injected
            ):
                injected = True
                raise win32.Win32SafetyError(
                    win32.FINAL_VERIFICATION_FAILED,
                    operation=operation,
                )
            return original_absent(
                guard,
                path,
                reason=reason,
                operation=operation,
            )

        with mock.patch.object(
            win32,
            "path_is_absent",
            side_effect=fail_journal_absence,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_final_verification_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "preserved_unverified",
            },
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertTrue(
            (
                self.root
                / append_plan["plan"]["receipt_relative_path"]
            ).is_file()
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_applied_journal_source_close_failure_restores_journal_for_restart(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        injected = False
        attempts = 0
        at_failure: dict[str, object] | None = None

        def fail_disposition_close_once(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, attempts, at_failure
            if operation == "residue_disposition_source_close" and not injected:
                injected = True
                attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_close(bound, reason=reason, operation=operation)

        with mock.patch.object(
            win32._Win32BoundFile,
            "close",
            new=fail_disposition_close_once,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertEqual(attempts, 1)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_applied_journal_restore_clear_failure_is_unknown_incomplete(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        original_clear = win32._clear_disposition
        close_attempts = 0
        clear_attempts = 0
        at_failure: dict[str, object] | None = None

        def fail_disposition_close_once(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal close_attempts, at_failure
            if (
                operation == "residue_disposition_source_close"
                and close_attempts == 0
            ):
                close_attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_close(bound, reason=reason, operation=operation)

        def fail_clear_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal clear_attempts
            if operation == "residue_disposition_restore":
                clear_attempts += 1
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_clear(
                bound,
                reason=reason,
                operation=operation,
            )

        with (
            mock.patch.object(
                win32._Win32BoundFile,
                "close",
                new=fail_disposition_close_once,
            ),
            mock.patch.object(
                win32,
                "_clear_disposition",
                side_effect=fail_clear_disposition,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(close_attempts, 1)
        self.assertEqual(clear_attempts, 1)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_applied_journal_restore_bytes_failure_is_unknown_incomplete(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        original_clear = win32._clear_disposition
        original_sha256 = (
            win32._Win32BoundFile._sha256_for_expected_link_count
        )
        close_attempts = 0
        clear_attempts = 0
        postclear_digest_attempts = 0
        at_failure: dict[str, object] | None = None

        def fail_disposition_close_once(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal close_attempts, at_failure
            if (
                operation == "residue_disposition_source_close"
                and close_attempts == 0
            ):
                close_attempts += 1
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation=operation,
                )
            original_close(bound, reason=reason, operation=operation)

        def track_clear_disposition(
            bound: object,
            *,
            reason: str,
            operation: str,
        ) -> None:
            nonlocal clear_attempts
            original_clear(
                bound,
                reason=reason,
                operation=operation,
            )
            if operation == "residue_disposition_restore":
                clear_attempts += 1

        def fail_postclear_digest(
            bound: object,
            *,
            max_bytes: int,
            expected_link_count: int | None,
            reason: str,
        ) -> str:
            nonlocal postclear_digest_attempts
            digest = original_sha256(
                bound,
                max_bytes=max_bytes,
                expected_link_count=expected_link_count,
                reason=reason,
            )
            if (
                clear_attempts
                and expected_link_count == 1
                and getattr(bound, "profile", None)
                is win32.FileHandleProfile.RESIDUE_DISPOSITION
            ):
                postclear_digest_attempts += 1
                return "sha256:" + ("0" * 64)
            return digest

        with (
            mock.patch.object(
                win32._Win32BoundFile,
                "close",
                new=fail_disposition_close_once,
            ),
            mock.patch.object(
                win32,
                "_clear_disposition",
                side_effect=track_clear_disposition,
            ),
            mock.patch.object(
                win32._Win32BoundFile,
                "_sha256_for_expected_link_count",
                new=fail_postclear_digest,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(close_attempts, 1)
        self.assertEqual(clear_attempts, 1)
        self.assertEqual(postclear_digest_attempts, 1)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_residue_disposition_failed",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "residue_disposition",
                "last_verified_authority_state": "applied",
                "cleanup_state": "incomplete",
            },
        )
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_terminal_replan_failure_preserves_completed_cleanup(
        self,
    ) -> None:
        append_plan = self._dry_run()
        at_failure: dict[str, object] | None = None

        def fail_terminal_replan(
            root: Path,
            *,
            state: object,
            expected_action: str,
        ) -> object:
            nonlocal at_failure
            self.assertEqual(expected_action, "already_applied")
            self.assertEqual(state.cleanup_state, "completed")
            self._assert_no_transaction_residue(append_plan)
            at_failure = self._applied_primary_snapshot(append_plan)
            raise writer._ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )

        with mock.patch.object(
            writer,
            "_verify_terminal_replan",
            side_effect=fail_terminal_replan,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_final_verification_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_success_then_tracked_handle_close_failure_is_reported(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        injected = False
        at_failure: dict[str, object] | None = None

        def fail_one_tracked_close(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, at_failure
            original_close(bound, reason=reason, operation=operation)
            if operation == "approval_tracked_handle_close" and not injected:
                injected = True
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.FINAL_VERIFICATION_FAILED,
                    operation=operation,
                )

        with mock.patch.object(
            win32._Win32BoundFile,
            "close",
            new=fail_one_tracked_close,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_final_verification_failed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "final_verification",
                "last_verified_authority_state": "applied",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_success_then_lock_release_failure_is_reported(self) -> None:
        append_plan = self._dry_run()
        original_release = win32._PrivateMetadataLockPair.release
        injected = False
        at_failure: dict[str, object] | None = None

        def fail_after_release(pair: object) -> None:
            nonlocal injected, at_failure
            original_release(pair)
            if not injected:
                injected = True
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.LOCK_IDENTITY_CHANGED,
                    operation="synthetic_lock_release",
                )

        with mock.patch.object(
            win32._PrivateMetadataLockPair,
            "release",
            new=fail_after_release,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_lock_identity_changed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "guard_or_lock",
                "last_verified_authority_state": "applied",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_success_then_unlock_api_failure_is_reported(self) -> None:
        append_plan = self._dry_run()
        api = win32._api()
        original_unlock = api.unlock_file
        injected = False
        at_failure: dict[str, object] | None = None

        def fail_first_unlock(*args: object) -> object:
            nonlocal injected, at_failure
            if not injected:
                injected = True
                at_failure = self._applied_primary_snapshot(append_plan)
                ctypes.set_last_error(5)
                return False
            return original_unlock(*args)

        with mock.patch.object(
            api,
            "unlock_file",
            side_effect=fail_first_unlock,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_lock_identity_changed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "guard_or_lock",
                "last_verified_authority_state": "applied",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_success_then_lock_handle_close_failure_is_reported(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        injected = False
        at_failure: dict[str, object] | None = None

        def fail_first_lock_close(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected, at_failure
            if operation == "coordination_lock_close" and not injected:
                injected = True
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.LOCK_IDENTITY_CHANGED,
                    operation=operation,
                )
            original_close(bound, reason=reason, operation=operation)

        with mock.patch.object(
            win32._Win32BoundFile,
            "close",
            new=fail_first_lock_close,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_lock_identity_changed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "guard_or_lock",
                "last_verified_authority_state": "applied",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_success_then_guard_close_failure_is_reported(self) -> None:
        append_plan = self._dry_run()
        original_close = win32._PrivateMetadataMutationGuard.close
        injected = False
        at_failure: dict[str, object] | None = None

        def fail_after_guard_close(guard: object) -> None:
            nonlocal injected, at_failure
            original_close(guard)
            if not injected:
                injected = True
                at_failure = self._applied_primary_snapshot(append_plan)
                raise win32.Win32SafetyError(
                    win32.MUTATION_GUARD_IDENTITY_CHANGED,
                    operation="synthetic_guard_close",
                )

        with mock.patch.object(
            win32._PrivateMetadataMutationGuard,
            "close",
            new=fail_after_guard_close,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(injected)
        self.assertIsNotNone(at_failure)
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_mutation_guard_identity_changed"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "guard_or_lock",
                "last_verified_authority_state": "applied",
                "cleanup_state": "completed",
            },
        )
        self._assert_no_transaction_residue(append_plan)
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            at_failure,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_object_drift_before_residue_needs_no_cleanup(self) -> None:
        append_plan = self._dry_run()
        with mock.patch.object(
            writer,
            "_verify_object_authority",
            side_effect=self._object_drift_on_verification(2),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_object_manifest_changed_before_commit"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "manifest_replacement",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "not_required",
            },
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())
        self.assertEqual(self._dry_run()["action"], "append")

    def test_object_drift_after_residue_cleans_exact_owned_names(self) -> None:
        append_plan = self._dry_run()
        with mock.patch.object(
            writer,
            "_verify_object_authority",
            side_effect=self._object_drift_on_verification(3),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_object_manifest_changed_before_commit"],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "manifest_replacement",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "completed",
            },
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        for relative in contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        ):
            self.assertFalse((self.root / relative).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(self._dry_run()["action"], "append")

    def test_object_drift_cleanup_disposition_failure_stops_order(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_dispose = win32._dispose_bound_residue
        failed_once = False

        def fail_manifest_disposition(
            guard: object,
            residue: object,
            *,
            locks: object,
        ) -> None:
            nonlocal failed_once
            if (
                not failed_once
                and getattr(residue, "path", Path()).name.endswith(
                    ".manifest.tmp"
                )
            ):
                failed_once = True
                raise win32.Win32SafetyError(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation="synthetic_manifest_cleanup_disposition",
                )
            original_dispose(guard, residue, locks=locks)

        with (
            mock.patch.object(
                writer,
                "_verify_object_authority",
                side_effect=self._object_drift_on_verification(3),
            ),
            mock.patch.object(
                win32,
                "_dispose_bound_residue",
                side_effect=fail_manifest_disposition,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(failed_once)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_object_manifest_changed_before_commit",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "manifest_replacement",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "incomplete",
            },
        )
        temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        self.assertTrue((self.root / temps[1]).is_file())
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(self._dry_run()["action"], "rollback_required")

    def test_object_drift_cleanup_lost_authority_preserves_all(
        self,
    ) -> None:
        append_plan = self._dry_run()
        lost_once = False

        def lose_manifest_authority(
            guard: object,
            current: object,
            *,
            reason: str,
        ) -> object:
            nonlocal lost_once
            del guard, reason
            if not lost_once and getattr(current, "path", Path()).name.endswith(
                ".manifest.tmp"
            ):
                lost_once = True
                current.close()
                raise win32.Win32MutationFailure(
                    win32.RESIDUE_DISPOSITION_FAILED,
                    operation="synthetic_manifest_cleanup_handoff",
                    checkpoint=win32.MutationCheckpoint.HANDOFF,
                    effect=win32.MutationEffect.NO_CHANGE_PROVED,
                )
            raise AssertionError("unexpected residue handoff")

        with (
            mock.patch.object(
                writer,
                "_verify_object_authority",
                side_effect=self._object_drift_on_verification(3),
            ),
            mock.patch.object(
                win32,
                "_handoff_to_residue_authority",
                side_effect=lose_manifest_authority,
            ),
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertTrue(lost_once)
        self.assertEqual(
            failed["blockers"],
            [
                "private_metadata_object_manifest_changed_before_commit",
                "private_metadata_owned_cleanup_incomplete",
            ],
        )
        self.assertEqual(
            failed["hold_context"],
            {
                "failure_stage": "manifest_replacement",
                "last_verified_authority_state": "unknown",
                "cleanup_state": "preserved_unverified",
            },
        )
        temps = contract.owned_temp_relative_paths(
            append_plan["plan"]["authority_key_sha256"]
        )
        self.assertTrue((self.root / temps[1]).is_file())
        self.assertTrue((self.root / contract.JOURNAL_PATH).is_file())
        self.assertEqual(self._dry_run()["action"], "rollback_required")

    def test_locked_object_and_private_aba_replacement_is_denied(
        self,
    ) -> None:
        first_plan = self._dry_run()
        applied = self._write(
            expected_plan_sha256=first_plan["plan_sha256"],
        )
        self.assertEqual(applied["action"], "applied")
        replay_plan = self._dry_run()
        self.assertEqual(replay_plan["action"], "already_applied")

        targets = (
            self.root / contract.OBJECT_MANIFEST_PATH,
            self.root / contract.PRIVATE_MANIFEST_PATH,
        )
        identities_before = {
            target: target.stat().st_ino for target in targets
        }
        original_replan = writer._locked_replan
        attempted = False
        denied: list[int | None] = []

        def synchronized_aba(*args: object, **kwargs: object) -> object:
            nonlocal attempted
            if not attempted:
                attempted = True
                for index, target in enumerate(targets):
                    replacement = (
                        self.root / "private" / f"aba-replacement-{index}"
                    )
                    replacement.write_bytes(target.read_bytes())
                    self.assertNotEqual(
                        replacement.stat().st_ino,
                        target.stat().st_ino,
                    )
                    try:
                        os.replace(replacement, target)
                    except OSError as exc:
                        denied.append(getattr(exc, "winerror", None))
                    else:
                        self.fail("retained authority allowed ABA replacement")
                    finally:
                        replacement.unlink(missing_ok=True)
                    self.assertEqual(
                        target.stat().st_ino,
                        identities_before[target],
                    )
            return original_replan(*args, **kwargs)

        with mock.patch.object(
            writer,
            "_locked_replan",
            side_effect=synchronized_aba,
        ):
            replay = self._write(
                expected_plan_sha256=replay_plan["plan_sha256"],
            )
        self.assertTrue(attempted)
        self.assertEqual(len(denied), 2)
        self.assertTrue(all(code in {5, 32} for code in denied))
        self.assertEqual(replay["action"], "already_applied")
        for target in targets:
            self.assertEqual(
                target.stat().st_ino,
                identities_before[target],
            )

    def test_byte_identical_different_identity_context_fails_preplan(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_replan = writer._locked_replan

        def inject_different_identity(
            *args: object,
            **kwargs: object,
        ) -> object:
            context, plan, plan_sha256, reasons = original_replan(
                *args,
                **kwargs,
            )
            snapshot = context.object_manifest
            self.assertIsNotNone(snapshot.identity)
            assert snapshot.identity is not None
            context.object_manifest = writer._FileSnapshot(
                path=snapshot.path,
                raw=snapshot.raw,
                state=snapshot.state,
                identity=(
                    snapshot.identity[0],
                    snapshot.identity[1] + 1,
                ),
            )
            return context, plan, plan_sha256, reasons

        with mock.patch.object(
            writer,
            "_locked_replan",
            side_effect=inject_different_identity,
        ):
            failed = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(failed["action"], "manual_hold")
        self.assertIsNone(failed["plan"])
        self.assertIsNone(failed["plan_sha256"])
        self.assertIsNone(failed["hold_context"])
        self.assertEqual(
            failed["blockers"],
            ["private_metadata_authority_state_unavailable"],
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )

    def test_intake_mismatch_precedes_missing_expected_plan(self) -> None:
        result = archive_services._private_objet_source_metadata_write_legacy_core(
            self.root,
            intake=self.intake_relative,
            expected_intake_sha256="sha256:" + ("9" * 64),
            expected_plan_sha256=None,
            dry_run=False,
            approve=True,
            reviewed_by=None,
            affirm_private_metadata_reviewed=False,
            affirm_external_writers_quiescent=False,
        )
        self.assertEqual(
            result["blockers"],
            ["private_metadata_intake_digest_mismatch"],
        )

    def test_object_authority_opens_only_after_object_lock_is_acquired(
        self,
    ) -> None:
        append_plan = self._dry_run()
        observed = {"pair_acquired": False, "object_open_checked": False}
        original_acquire = win32._PrivateMetadataLockPair.acquire
        original_open = win32._open_bound_file

        def acquire(pair: object) -> object:
            result = original_acquire(pair)
            observed["pair_acquired"] = True
            return result

        def open_bound(
            guard: object,
            relative_path: str,
            **kwargs: object,
        ) -> object:
            if relative_path == contract.OBJECT_MANIFEST_PATH:
                self.assertTrue(observed["pair_acquired"])
                observed["object_open_checked"] = True
            return original_open(guard, relative_path, **kwargs)

        with (
            mock.patch.object(
                win32._PrivateMetadataLockPair,
                "acquire",
                new=acquire,
            ),
            mock.patch.object(
                win32,
                "_open_bound_file",
                side_effect=open_bound,
            ),
        ):
            applied = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
            )
        self.assertEqual(applied["action"], "applied")
        self.assertTrue(observed["object_open_checked"])

    def test_preaccept_guard_release_failure_overrides_pending_refusal(
        self,
    ) -> None:
        original_close = win32._PrivateMetadataMutationGuard.close

        def close_with_fault(guard: object) -> None:
            original_close(guard)
            raise win32.Win32SafetyError(
                win32.MUTATION_GUARD_IDENTITY_CHANGED,
                operation="synthetic_guard_release_failure",
            )

        (self.root / self.intake_relative).write_bytes(b"{}")
        with (
            mock.patch.object(
                writer,
                "_approval_intake_preflight",
                return_value={
                    "reason": None,
                    "intake_sha256": self.intake_sha256,
                },
            ),
            mock.patch.object(
                win32._PrivateMetadataMutationGuard,
                "close",
                new=close_with_fault,
            ),
        ):
            result = self._write(
                expected_plan_sha256="sha256:" + ("e" * 64),
            )
        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_mutation_guard_identity_changed"],
        )

    def test_preaccept_tracked_close_uses_authority_unavailable_mapping(
        self,
    ) -> None:
        append_plan = self._dry_run()
        original_close = win32._Win32BoundFile.close
        injected = False

        def fail_after_one_tracked_close(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected
            original_close(bound, reason=reason, operation=operation)
            if operation == "approval_tracked_handle_close" and not injected:
                injected = True
                raise win32.Win32SafetyError(
                    reason,
                    operation=operation,
                )

        with mock.patch.object(
            win32._Win32BoundFile,
            "close",
            new=fail_after_one_tracked_close,
        ):
            result = self._write(
                expected_plan_sha256="sha256:" + ("e" * 64),
            )
        self.assertTrue(injected)
        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_authority_state_unavailable"],
        )
        self.assertFalse((self.root / contract.JOURNAL_PATH).exists())
        self.assertFalse(
            (self.root / contract.PRIVATE_MANIFEST_PATH).exists()
        )
        self.assertEqual(append_plan["action"], "append")

    def test_stale_convergence_tracked_close_uses_preaccept_mapping(
        self,
    ) -> None:
        append_plan = self._dry_run()
        applied = self._write(
            expected_plan_sha256=append_plan["plan_sha256"],
        )
        self.assertEqual(applied["action"], "applied")
        applied_snapshot = self._applied_primary_snapshot(append_plan)
        original_close = win32._Win32BoundFile.close
        injected = False

        def fail_after_one_tracked_close(
            bound: object,
            *,
            reason: str = win32.FINAL_VERIFICATION_FAILED,
            operation: str = "bound_handle_close",
        ) -> None:
            nonlocal injected
            original_close(bound, reason=reason, operation=operation)
            if operation == "approval_tracked_handle_close" and not injected:
                injected = True
                raise win32.Win32SafetyError(
                    reason,
                    operation=operation,
                )

        with mock.patch.object(
            win32._Win32BoundFile,
            "close",
            new=fail_after_one_tracked_close,
        ):
            result = self._write(
                expected_plan_sha256=append_plan["plan_sha256"],
                reviewed_by="operator:stale-close-failure",
            )
        self.assertTrue(injected)
        self.assertEqual(result["action"], "manual_hold")
        self.assertIsNone(result["plan"])
        self.assertIsNone(result["plan_sha256"])
        self.assertIsNone(result["hold_context"])
        self.assertEqual(
            result["blockers"],
            ["private_metadata_authority_state_unavailable"],
        )
        self.assertEqual(
            self._applied_primary_snapshot(append_plan),
            applied_snapshot,
        )
        self.assertEqual(self._dry_run()["action"], "already_applied")

    def test_locked_replan_errors_keep_exact_preplan_classification(
        self,
    ) -> None:
        append_plan = self._dry_run()
        cases = (
            (
                writer._SnapshotError("object_manifest_bytes_limit"),
                "private_metadata_object_manifest_bytes_limit_exceeded",
            ),
            (
                KeyError("synthetic-invalid-authority"),
                "private_metadata_authority_state_invalid",
            ),
        )
        for injected, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                with mock.patch.object(
                    writer,
                    "_build_planning_context",
                    side_effect=injected,
                ):
                    result = self._write(
                        expected_plan_sha256=append_plan["plan_sha256"],
                    )
                self.assertEqual(result["action"], "manual_hold")
                self.assertIsNone(result["plan"])
                self.assertIsNone(result["plan_sha256"])
                self.assertIsNone(result["hold_context"])
                self.assertEqual(result["blockers"], [expected_reason])
                self.assertFalse(
                    (self.root / contract.JOURNAL_PATH).exists()
                )


if __name__ == "__main__":
    unittest.main()
