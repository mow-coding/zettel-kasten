from __future__ import annotations

import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_services


@unittest.skipUnless(os.name == "nt", "Windows CAS primitive")
class WindowsCasNoReplaceTests(unittest.TestCase):
    @staticmethod
    def _file_system_control(
        path: Path,
        control_code: int,
        *,
        output_size: int = 0,
    ) -> tuple[int, bytes]:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        device_io_control = kernel32.DeviceIoControl
        device_io_control.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        device_io_control.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        handle = create_file(
            str(path),
            0x80000000 | 0x40000000,
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,
            0,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            output = (
                ctypes.create_string_buffer(output_size)
                if output_size
                else None
            )
            returned = wintypes.DWORD()
            ctypes.set_last_error(0)
            if not device_io_control(
                handle,
                control_code,
                None,
                0,
                output,
                output_size,
                ctypes.byref(returned),
                None,
            ):
                return ctypes.get_last_error(), b""
            return (
                0,
                b""
                if output is None
                else bytes(output.raw[: int(returned.value)]),
            )
        finally:
            close_handle(handle)

    @staticmethod
    def _set_ntfs_ea(path: Path, name: str, value: bytes) -> int:
        import ctypes
        from ctypes import wintypes

        class IoStatusBlock(ctypes.Structure):
            _fields_ = [
                ("status_or_pointer", ctypes.c_void_p),
                ("information", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        nt_set_ea_file = ntdll.NtSetEaFile
        nt_set_ea_file.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(IoStatusBlock),
            wintypes.LPVOID,
            wintypes.ULONG,
        ]
        nt_set_ea_file.restype = ctypes.c_long

        encoded_name = name.encode("ascii")
        encoded = (
            struct.pack(
                "<IBBH",
                0,
                0,
                len(encoded_name),
                len(value),
            )
            + encoded_name
            + b"\0"
            + value
        )
        buffer = ctypes.create_string_buffer(encoded)
        handle = create_file(
            str(path),
            0x80000000 | 0x00000008 | 0x00000010 | 0x00000080,
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,
            0,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            io_status = IoStatusBlock()
            return int(
                nt_set_ea_file(
                    handle,
                    ctypes.byref(io_status),
                    buffer,
                    len(encoded),
                )
            ) & 0xFFFFFFFF
        finally:
            close_handle(handle)

    @staticmethod
    def _read_ntfs_eas(path: Path) -> list[tuple[str, bytes]]:
        import ctypes
        from ctypes import wintypes

        class IoStatusBlock(ctypes.Structure):
            _fields_ = [
                ("status_or_pointer", ctypes.c_void_p),
                ("information", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        nt_query_ea_file = ntdll.NtQueryEaFile
        nt_query_ea_file.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(IoStatusBlock),
            wintypes.LPVOID,
            wintypes.ULONG,
            wintypes.BOOLEAN,
            wintypes.LPVOID,
            wintypes.ULONG,
            wintypes.LPVOID,
            wintypes.BOOLEAN,
        ]
        nt_query_ea_file.restype = ctypes.c_long

        handle = create_file(
            str(path),
            0x80000000 | 0x00000008 | 0x00000080,
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,
            0,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer = ctypes.create_string_buffer(64 * 1024)
            io_status = IoStatusBlock()
            status = int(
                nt_query_ea_file(
                    handle,
                    ctypes.byref(io_status),
                    buffer,
                    len(buffer),
                    False,
                    None,
                    0,
                    None,
                    True,
                )
            ) & 0xFFFFFFFF
            if status == 0xC0000052:  # STATUS_NO_EAS_ON_FILE
                return []
            if status != 0:
                raise OSError(f"NtQueryEaFile failed: 0x{status:08x}")
            result: list[tuple[str, bytes]] = []
            offset = 0
            total = int(io_status.information)
            while offset < total:
                next_offset, _flags, name_size, value_size = (
                    struct.unpack_from("<IBBH", buffer.raw, offset)
                )
                name_start = offset + 8
                value_start = name_start + name_size + 1
                result.append(
                    (
                        buffer.raw[
                            name_start : name_start + name_size
                        ].decode("ascii"),
                        bytes(
                            buffer.raw[
                                value_start : value_start + value_size
                            ]
                        ),
                    )
                )
                if next_offset == 0:
                    break
                offset += next_offset
            return result
        finally:
            close_handle(handle)

    def test_backup_path_preemption_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-backup-race-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "swap"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            previous.write_bytes(b"FOREIGN-PREVIOUS")

            with self.assertRaises(OSError):
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                )

            self.assertEqual(canonical.read_bytes(), b"old")
            self.assertEqual(swap.read_bytes(), b"new")
            self.assertEqual(previous.read_bytes(), b"FOREIGN-PREVIOUS")

    def test_empty_default_stream_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-empty-old-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "replacement"
            previous = parent / "previous"
            canonical.write_bytes(b"")
            swap.write_bytes(b"new")

            archive_services._replace_activity_group_file_with_backup_windows(
                canonical,
                swap,
                previous,
                expected_replaced_bytes=b"",
                expected_replacement_bytes=b"new",
                max_bytes=1024,
                error_prefix="windows_cas_test",
            )

            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertFalse(previous.exists())

    def test_matching_readonly_files_complete_without_residue(self) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(prefix="wom-cas-readonly-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "replacement"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            set_attributes = kernel32.SetFileAttributesW
            set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
            set_attributes.restype = wintypes.BOOL
            file_attribute_readonly = 0x00000001
            file_attribute_normal = 0x00000080
            for candidate in (canonical, swap):
                if not set_attributes(
                    str(candidate),
                    file_attribute_readonly,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
            try:
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                )

                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertFalse(previous.exists())
            finally:
                for candidate in (canonical, swap, previous):
                    if candidate.exists():
                        set_attributes(str(candidate), file_attribute_normal)

    def test_canonical_preemption_between_moves_preserves_all_occupants(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-name-race-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "swap"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")

            def preempt_public_name(stage: str) -> None:
                if stage == "canonical_moved_to_previous":
                    canonical.write_bytes(b"FOREIGN-CANONICAL")

            with self.assertRaises(OSError):
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                    _failpoint=preempt_public_name,
                )

            self.assertEqual(canonical.read_bytes(), b"FOREIGN-CANONICAL")
            self.assertEqual(swap.read_bytes(), b"new")
            self.assertEqual(previous.read_bytes(), b"old")

    def test_named_streams_refuse_before_first_move(self) -> None:
        for streamed_role in ("canonical", "replacement"):
            with self.subTest(streamed_role=streamed_role):
                with tempfile.TemporaryDirectory(
                    prefix="wom-cas-named-stream-"
                ) as tmp:
                    parent = Path(tmp)
                    canonical = parent / "canonical"
                    swap = parent / "swap"
                    previous = parent / "previous"
                    canonical.write_bytes(b"old")
                    swap.write_bytes(b"new")
                    streamed_path = (
                        canonical
                        if streamed_role == "canonical"
                        else swap
                    )
                    named_stream = Path(
                        str(streamed_path) + ":wom_review_private"
                    )
                    named_stream.write_bytes(b"PRIVATE-ADS-BYTES")

                    with self.assertRaisesRegex(
                        OSError,
                        "canonical_swap_named_stream_unsupported",
                    ):
                        archive_services._replace_activity_group_file_with_backup_windows(
                            canonical,
                            swap,
                            previous,
                            expected_replaced_bytes=b"old",
                            expected_replacement_bytes=b"new",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                        )

                    self.assertEqual(canonical.read_bytes(), b"old")
                    self.assertEqual(swap.read_bytes(), b"new")
                    self.assertFalse(previous.exists())
                    self.assertEqual(
                        named_stream.read_bytes(),
                        b"PRIVATE-ADS-BYTES",
                    )

    def test_ntfs_eas_refuse_before_first_move(self) -> None:
        lxmod_value = struct.pack("<I", 0o100600)
        for ea_role in ("canonical", "replacement"):
            with self.subTest(ea_role=ea_role):
                with tempfile.TemporaryDirectory(
                    prefix="wom-cas-ntfs-ea-"
                ) as tmp:
                    parent = Path(tmp)
                    canonical = parent / "canonical"
                    swap = parent / "replacement"
                    previous = parent / "previous"
                    canonical.write_bytes(b"old")
                    swap.write_bytes(b"new")
                    ea_path = canonical if ea_role == "canonical" else swap
                    status = self._set_ntfs_ea(
                        ea_path,
                        "$LXMOD",
                        lxmod_value,
                    )
                    if status in {0xC0000010, 0xC000004F}:
                        self.skipTest("temporary volume does not support EAs")
                    self.assertEqual(status, 0)
                    expected_eas = [("$LXMOD", lxmod_value)]
                    self.assertEqual(
                        self._read_ntfs_eas(ea_path),
                        expected_eas,
                    )
                    namespace_stages: list[str] = []

                    with self.assertRaisesRegex(
                        OSError,
                        "canonical_swap_backup_stream_unsupported",
                    ):
                        archive_services._replace_activity_group_file_with_backup_windows(
                            canonical,
                            swap,
                            previous,
                            expected_replaced_bytes=b"old",
                            expected_replacement_bytes=b"new",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                            _failpoint=namespace_stages.append,
                        )

                    self.assertEqual(namespace_stages, [])
                    self.assertEqual(canonical.read_bytes(), b"old")
                    self.assertEqual(swap.read_bytes(), b"new")
                    self.assertFalse(previous.exists())
                    self.assertEqual(
                        self._read_ntfs_eas(ea_path),
                        expected_eas,
                    )

    def test_ntfs_object_ids_refuse_before_first_move(self) -> None:
        fsctl_create_or_get_object_id = 0x000900C0
        fsctl_get_object_id = 0x0009009C
        for object_id_role in ("canonical", "replacement"):
            with self.subTest(object_id_role=object_id_role):
                with tempfile.TemporaryDirectory(
                    prefix="wom-cas-object-id-"
                ) as tmp:
                    parent = Path(tmp)
                    canonical = parent / "canonical"
                    swap = parent / "replacement"
                    previous = parent / "previous"
                    canonical.write_bytes(b"old")
                    swap.write_bytes(b"new")
                    object_id_path = (
                        canonical
                        if object_id_role == "canonical"
                        else swap
                    )
                    error, object_id = self._file_system_control(
                        object_id_path,
                        fsctl_create_or_get_object_id,
                        output_size=64,
                    )
                    if error in {1, 50}:
                        self.skipTest(
                            "temporary volume does not support object IDs"
                        )
                    self.assertEqual(error, 0)
                    self.assertEqual(len(object_id), 64)
                    namespace_stages: list[str] = []

                    with self.assertRaisesRegex(
                        OSError,
                        "canonical_swap_backup_stream_unsupported",
                    ):
                        archive_services._replace_activity_group_file_with_backup_windows(
                            canonical,
                            swap,
                            previous,
                            expected_replaced_bytes=b"old",
                            expected_replacement_bytes=b"new",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                            _failpoint=namespace_stages.append,
                        )

                    self.assertEqual(namespace_stages, [])
                    self.assertEqual(canonical.read_bytes(), b"old")
                    self.assertEqual(swap.read_bytes(), b"new")
                    self.assertFalse(previous.exists())
                    query_error, observed_object_id = (
                        self._file_system_control(
                            object_id_path,
                            fsctl_get_object_id,
                            output_size=64,
                        )
                    )
                    self.assertEqual(query_error, 0)
                    self.assertEqual(observed_object_id, object_id)

    def test_sparse_files_refuse_before_first_move(self) -> None:
        fsctl_set_sparse = 0x000900C4
        for sparse_role in ("canonical", "replacement"):
            with self.subTest(sparse_role=sparse_role):
                with tempfile.TemporaryDirectory(
                    prefix="wom-cas-sparse-"
                ) as tmp:
                    parent = Path(tmp)
                    canonical = parent / "canonical"
                    swap = parent / "replacement"
                    previous = parent / "previous"
                    canonical.write_bytes(b"old")
                    swap.write_bytes(b"new")
                    sparse_path = (
                        canonical if sparse_role == "canonical" else swap
                    )
                    error, _output = self._file_system_control(
                        sparse_path,
                        fsctl_set_sparse,
                    )
                    if error in {1, 50}:
                        self.skipTest(
                            "temporary volume does not support sparse files"
                        )
                    self.assertEqual(error, 0)
                    self.assertTrue(
                        int(sparse_path.stat().st_file_attributes)
                        & 0x00000200
                    )
                    namespace_stages: list[str] = []

                    with self.assertRaisesRegex(
                        OSError,
                        "canonical_swap_backup_stream_unsupported",
                    ):
                        archive_services._replace_activity_group_file_with_backup_windows(
                            canonical,
                            swap,
                            previous,
                            expected_replaced_bytes=b"old",
                            expected_replacement_bytes=b"new",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                            _failpoint=namespace_stages.append,
                        )

                    self.assertEqual(namespace_stages, [])
                    self.assertEqual(canonical.read_bytes(), b"old")
                    self.assertEqual(swap.read_bytes(), b"new")
                    self.assertFalse(previous.exists())
                    self.assertTrue(
                        int(sparse_path.stat().st_file_attributes)
                        & 0x00000200
                    )

    def test_security_descriptor_mismatch_refuses_before_first_move(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-security-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "swap"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            changed_acl = subprocess.run(
                ["icacls", str(canonical), "/inheritance:d"],
                check=False,
                capture_output=True,
                text=True,
            )
            if changed_acl.returncode != 0:
                self.skipTest("icacls cannot create an isolated test DACL")

            with self.assertRaisesRegex(
                OSError,
                "canonical_swap_metadata_mismatch",
            ):
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                )

            self.assertEqual(canonical.read_bytes(), b"old")
            self.assertEqual(swap.read_bytes(), b"new")
            self.assertFalse(previous.exists())

    def test_integrity_label_mismatch_refuses_before_first_move(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="wom-cas-integrity-label-"
        ) as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "replacement"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            changed_label = subprocess.run(
                ["icacls", str(canonical), "/setintegritylevel", "Low"],
                check=False,
                capture_output=True,
                text=True,
            )
            if changed_label.returncode != 0:
                self.skipTest("icacls cannot create an integrity label")
            namespace_stages: list[str] = []

            with self.assertRaisesRegex(
                OSError,
                "canonical_swap_metadata_mismatch",
            ):
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                    _failpoint=namespace_stages.append,
                )

            self.assertEqual(namespace_stages, [])
            self.assertEqual(canonical.read_bytes(), b"old")
            self.assertEqual(swap.read_bytes(), b"new")
            self.assertFalse(previous.exists())

    def test_metadata_drift_after_first_move_preserves_previous(self) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(
            prefix="wom-cas-metadata-drift-"
        ) as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "swap"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            set_attributes = kernel32.SetFileAttributesW
            set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
            set_attributes.restype = wintypes.BOOL
            file_attribute_hidden = 0x00000002

            def change_old_metadata(stage: str) -> None:
                if stage == "canonical_moved_to_previous" and not set_attributes(
                    str(previous),
                    file_attribute_hidden,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())

            with self.assertRaises(OSError):
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                    _failpoint=change_old_metadata,
                )

            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertEqual(previous.read_bytes(), b"old")

    def test_previous_deletion_is_blocked_until_exact_success_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-delete-race-") as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "swap"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            delete_errors: list[int | None] = []

            def attempt_previous_delete(stage: str) -> None:
                if stage != "canonical_moved_to_previous":
                    return
                try:
                    previous.unlink()
                except OSError as exc:
                    delete_errors.append(getattr(exc, "winerror", None))
                else:
                    delete_errors.append(0)

            archive_services._replace_activity_group_file_with_backup_windows(
                canonical,
                swap,
                previous,
                expected_replaced_bytes=b"old",
                expected_replacement_bytes=b"new",
                max_bytes=1024,
                error_prefix="windows_cas_test",
                _failpoint=attempt_previous_delete,
            )

            self.assertEqual(delete_errors, [32])
            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertFalse(previous.exists())

    def test_posix_delete_unlinks_previous_with_external_handle(
        self,
    ) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(
            prefix="wom-cas-posix-delete-"
        ) as tmp:
            parent = Path(tmp)
            canonical = parent / "canonical"
            swap = parent / "replacement"
            previous = parent / "previous"
            canonical.write_bytes(b"old")
            swap.write_bytes(b"new")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            create_file.restype = wintypes.HANDLE
            device_io_control = kernel32.DeviceIoControl
            device_io_control.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            device_io_control.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            external_handle = create_file(
                str(canonical),
                0,
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,
                0,
                None,
            )
            if external_handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            object_id_created: list[bool] = []

            def mutate_detached_old_object(stage: str) -> None:
                if stage != "previous_delete_marked":
                    return
                output = ctypes.create_string_buffer(64)
                returned = wintypes.DWORD()
                object_id_created.append(
                    bool(
                        device_io_control(
                            external_handle,
                            0x000900C0,
                            None,
                            0,
                            output,
                            len(output),
                            ctypes.byref(returned),
                            None,
                        )
                    )
                )

            try:
                archive_services._replace_activity_group_file_with_backup_windows(
                    canonical,
                    swap,
                    previous,
                    expected_replaced_bytes=b"old",
                    expected_replacement_bytes=b"new",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                    _failpoint=mutate_detached_old_object,
                )

                self.assertEqual(object_id_created, [True])
                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertFalse(previous.exists())
            finally:
                close_handle(external_handle)

    def test_unsupported_posix_delete_preserves_previous_for_retry(
        self,
    ) -> None:
        import ctypes

        with tempfile.TemporaryDirectory(
            prefix="wom-cas-posix-delete-unsupported-"
        ) as tmp:
            root = Path(tmp).resolve()
            canonical = root / "canonical"
            canonical.write_bytes(b"old")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"unsupported-posix-delete"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            swap.write_bytes(b"new")
            real_win_dll = ctypes.WinDLL
            real_kernel32 = real_win_dll(
                "kernel32",
                use_last_error=True,
            )
            real_set_information = (
                real_kernel32.SetFileInformationByHandle
            )
            real_get_information = (
                real_kernel32.GetFileInformationByHandle
            )
            posix_delete_attempts: list[int] = []

            def reject_posix_delete(*args: object) -> object:
                if int(args[1]) == 21:  # FileDispositionInfoEx
                    posix_delete_attempts.append(21)
                    ctypes.set_last_error(50)  # ERROR_NOT_SUPPORTED
                    return 0
                real_set_information.argtypes = None
                real_set_information.restype = ctypes.c_int
                return real_set_information(*args)

            def get_information(*args: object) -> object:
                real_get_information.argtypes = None
                real_get_information.restype = ctypes.c_int
                return real_get_information(*args)

            class Kernel32Proxy:
                SetFileInformationByHandle = staticmethod(
                    reject_posix_delete
                )
                GetFileInformationByHandle = staticmethod(get_information)

                def __getattr__(self, name: str) -> object:
                    return getattr(real_kernel32, name)

            proxy = Kernel32Proxy()

            def win_dll_proxy(name: str, *args: object, **kwargs: object) -> object:
                if name.casefold() == "kernel32":
                    return proxy
                return real_win_dll(name, *args, **kwargs)

            with patch.object(ctypes, "WinDLL", side_effect=win_dll_proxy):
                with self.assertRaisesRegex(
                    OSError,
                    "canonical_swap_posix_delete_unsupported",
                ):
                    archive_services._replace_activity_group_file_with_backup_windows(
                        canonical,
                        swap,
                        previous,
                        expected_replaced_bytes=b"old",
                        expected_replacement_bytes=b"new",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )

                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertEqual(previous.read_bytes(), b"old")
                with self.assertRaisesRegex(
                    OSError,
                    "canonical_swap_posix_delete_unsupported",
                ):
                    archive_services._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )

                self.assertEqual(posix_delete_attempts, [21, 21])
                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertEqual(previous.read_bytes(), b"old")

            self.assertTrue(
                archive_services._replace_regular_file_bytes_compare_and_swap(
                    root,
                    canonical,
                    expected_bytes=b"old",
                    replacement_bytes=b"new",
                    transaction_sha256=transaction_sha256,
                    swap_suffix=".windows-cas-test",
                    max_bytes=1024,
                    error_prefix="windows_cas_test",
                )
            )
            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(previous.exists())

    def test_installed_state_posix_unlinks_with_external_handle(
        self,
    ) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-posix-delete-"
        ) as tmp:
            root = Path(tmp).resolve()
            canonical = root / "canonical"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-posix-delete"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            create_file.restype = wintypes.HANDLE
            close_handle = kernel32.CloseHandle
            external_handle = create_file(
                str(previous),
                0,
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,
                0,
                None,
            )
            if external_handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                self.assertTrue(
                    archive_services._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )
                )
                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertFalse(previous.exists())
            finally:
                close_handle(external_handle)

    def test_installed_state_readonly_residue_cleans_with_posix_delete(
        self,
    ) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-readonly-"
        ) as tmp:
            root = Path(tmp).resolve()
            canonical = root / "canonical"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-readonly"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            set_attributes = kernel32.SetFileAttributesW
            set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
            set_attributes.restype = wintypes.BOOL
            file_attribute_readonly = 0x00000001
            file_attribute_normal = 0x00000080
            for candidate in (canonical, previous):
                if not set_attributes(
                    str(candidate),
                    file_attribute_readonly,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
            try:
                self.assertTrue(
                    archive_services._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )
                )
                self.assertEqual(canonical.read_bytes(), b"new")
                self.assertFalse(swap.exists())
                self.assertFalse(previous.exists())
            finally:
                for candidate in (canonical, previous):
                    if candidate.exists():
                        set_attributes(str(candidate), file_attribute_normal)

    def test_installed_state_drift_before_cleanup_preserves_previous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-drift-"
        ) as tmp:
            root = Path(tmp).resolve()
            parent = root / "zettels"
            parent.mkdir()
            canonical = parent / "z.md"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-drift"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            foreign = b"FOREIGN-CANONICAL"
            original_hold = (
                archive_services._hold_activity_group_evidence_file
            )
            canonical_hold_count = 0

            @contextmanager
            def drift_before_cleanup_hold(
                root_arg: Path,
                path_arg: Path,
                *,
                max_bytes: int,
            ):
                nonlocal canonical_hold_count
                if path_arg == canonical:
                    canonical_hold_count += 1
                    if canonical_hold_count == 2:
                        canonical.write_bytes(foreign)
                with original_hold(
                    root_arg,
                    path_arg,
                    max_bytes=max_bytes,
                ) as held:
                    yield held

            with patch.object(
                archive_services,
                "_hold_activity_group_evidence_file",
                new=drift_before_cleanup_hold,
            ):
                with self.assertRaises(OSError):
                    (
                        archive_services
                        ._replace_regular_file_bytes_compare_and_swap(
                            root,
                            canonical,
                            expected_bytes=b"old",
                            replacement_bytes=b"new",
                            transaction_sha256=transaction_sha256,
                            swap_suffix=".windows-cas-test",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                        )
                    )

            self.assertEqual(canonical_hold_count, 2)
            self.assertEqual(canonical.read_bytes(), foreign)
            self.assertFalse(swap.exists())
            self.assertEqual(previous.read_bytes(), b"old")

    def test_installed_state_cleanup_blocks_concurrent_canonical_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-held-"
        ) as tmp:
            root = Path(tmp).resolve()
            parent = root / "zettels"
            parent.mkdir()
            canonical = parent / "z.md"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-held"
            ).hexdigest()
            _swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            original_delete = (
                archive_services._delete_activity_group_evidence_exact
            )
            write_blocked: list[bool] = []

            def attempt_write_during_cleanup(
                root_arg: Path,
                path_arg: Path,
                **kwargs: object,
            ) -> None:
                try:
                    canonical.write_bytes(b"FOREIGN-CANONICAL")
                except OSError:
                    write_blocked.append(True)
                else:
                    write_blocked.append(False)
                original_delete(root_arg, path_arg, **kwargs)

            with patch.object(
                archive_services,
                "_delete_activity_group_evidence_exact",
                new=attempt_write_during_cleanup,
            ):
                changed = (
                    archive_services
                    ._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )
                )

            self.assertTrue(changed)
            self.assertEqual(write_blocked, [True])
            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(previous.exists())

    def test_installed_state_named_stream_preserves_previous(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-stream-"
        ) as tmp:
            root = Path(tmp).resolve()
            parent = root / "zettels"
            parent.mkdir()
            canonical = parent / "z.md"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-stream"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            named_stream = Path(str(previous) + ":wom_review_private")
            named_stream.write_bytes(b"PRIVATE-ADS-BYTES")

            with self.assertRaisesRegex(
                OSError,
                "canonical_swap_named_stream_unsupported",
            ):
                (
                    archive_services
                    ._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )
                )

            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertEqual(previous.read_bytes(), b"old")
            self.assertEqual(named_stream.read_bytes(), b"PRIVATE-ADS-BYTES")

    def test_installed_state_ntfs_ea_preserves_previous(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="wom-cas-installed-ea-"
        ) as tmp:
            root = Path(tmp).resolve()
            parent = root / "zettels"
            parent.mkdir()
            canonical = parent / "z.md"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"installed-ea"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".windows-cas-test",
                )
            )
            previous.write_bytes(b"old")
            lxmod_value = struct.pack("<I", 0o100600)
            status = self._set_ntfs_ea(
                previous,
                "$LXMOD",
                lxmod_value,
            )
            if status in {0xC0000010, 0xC000004F}:
                self.skipTest("temporary volume does not support EAs")
            self.assertEqual(status, 0)

            with self.assertRaisesRegex(
                OSError,
                "canonical_swap_backup_stream_unsupported",
            ):
                (
                    archive_services
                    ._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".windows-cas-test",
                        max_bytes=1024,
                        error_prefix="windows_cas_test",
                    )
                )

            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertEqual(previous.read_bytes(), b"old")
            self.assertEqual(
                self._read_ntfs_eas(previous),
                [("$LXMOD", lxmod_value)],
            )

    def test_process_exit_at_each_namespace_checkpoint_is_recoverable(
        self,
    ) -> None:
        source_root = Path(archive_services.__file__).resolve().parents[1]
        child = textwrap.dedent(
            r"""
            import os
            import sys
            from pathlib import Path

            sys.path.insert(0, sys.argv[1])
            from wom_kit import archive_services

            canonical, swap, previous = map(Path, sys.argv[2:5])
            target_stage = sys.argv[5]
            exit_code = int(sys.argv[6])

            def hard_exit(stage: str) -> None:
                if stage == target_stage:
                    os._exit(exit_code)

            archive_services._replace_activity_group_file_with_backup_windows(
                canonical,
                swap,
                previous,
                expected_replaced_bytes=b"old",
                expected_replacement_bytes=b"new",
                max_bytes=1024,
                error_prefix="windows_cas_test",
                _failpoint=hard_exit,
            )
            """
        )
        checkpoints = (
            ("canonical_moved_to_previous", 73, "gap"),
            ("replacement_moved_to_canonical", 74, "installed"),
            ("previous_delete_marked", 75, "clean"),
        )
        for stage, exit_code, state in checkpoints:
            with self.subTest(stage=stage):
                with tempfile.TemporaryDirectory(
                    prefix="wom-cas-hard-exit-"
                ) as tmp:
                    root = Path(tmp).resolve()
                    parent = root / "zettels"
                    parent.mkdir()
                    canonical = parent / "z.md"
                    canonical.write_bytes(b"old")
                    transaction_sha256 = "sha256:" + hashlib.sha256(
                        stage.encode("ascii")
                    ).hexdigest()
                    swap, previous = (
                        archive_services.regular_file_canonical_swap_paths(
                            canonical,
                            transaction_sha256,
                            swap_suffix=".windows-cas-test",
                        )
                    )
                    swap.write_bytes(b"new")

                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            child,
                            str(source_root),
                            str(canonical),
                            str(swap),
                            str(previous),
                            stage,
                            str(exit_code),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        completed.returncode,
                        exit_code,
                        completed.stderr,
                    )
                    if state == "gap":
                        self.assertFalse(canonical.exists())
                        self.assertEqual(swap.read_bytes(), b"new")
                        self.assertEqual(previous.read_bytes(), b"old")
                    elif state == "installed":
                        self.assertEqual(canonical.read_bytes(), b"new")
                        self.assertFalse(swap.exists())
                        self.assertEqual(previous.read_bytes(), b"old")
                    else:
                        self.assertEqual(canonical.read_bytes(), b"new")
                        self.assertFalse(swap.exists())
                        self.assertFalse(previous.exists())

                    resumed = (
                        archive_services
                        ._replace_regular_file_bytes_compare_and_swap(
                            root,
                            canonical,
                            expected_bytes=b"old",
                            replacement_bytes=b"new",
                            transaction_sha256=transaction_sha256,
                            swap_suffix=".windows-cas-test",
                            max_bytes=1024,
                            error_prefix="windows_cas_test",
                            allow_already_replacement=(state == "clean"),
                        )
                    )
                    self.assertEqual(resumed, state != "clean")
                    self.assertEqual(canonical.read_bytes(), b"new")
                    self.assertFalse(swap.exists())
                    self.assertFalse(previous.exists())


@unittest.skipIf(os.name == "nt", "POSIX conservative residue policy")
class PosixInterruptedCasResidueTests(unittest.TestCase):
    def test_installed_state_preserves_residue_without_stable_name_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="wom-cas-posix-residue-") as tmp:
            root = Path(tmp).resolve()
            parent = root / "zettels"
            parent.mkdir()
            canonical = parent / "z.md"
            canonical.write_bytes(b"new")
            transaction_sha256 = "sha256:" + hashlib.sha256(
                b"posix-installed-residue"
            ).hexdigest()
            swap, previous = (
                archive_services.regular_file_canonical_swap_paths(
                    canonical,
                    transaction_sha256,
                    swap_suffix=".posix-cas-test",
                )
            )
            previous.write_bytes(b"old")

            with self.assertRaisesRegex(
                OSError,
                "canonical_swap_cleanup_stability_unsupported",
            ):
                (
                    archive_services
                    ._replace_regular_file_bytes_compare_and_swap(
                        root,
                        canonical,
                        expected_bytes=b"old",
                        replacement_bytes=b"new",
                        transaction_sha256=transaction_sha256,
                        swap_suffix=".posix-cas-test",
                        max_bytes=1024,
                        error_prefix="posix_cas_test",
                    )
                )

            self.assertEqual(canonical.read_bytes(), b"new")
            self.assertFalse(swap.exists())
            self.assertEqual(previous.read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
