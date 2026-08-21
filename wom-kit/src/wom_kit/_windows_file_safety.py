from __future__ import annotations

import os
import stat
from pathlib import Path


def open_regular_rw_descriptor_no_reparse(
    path: Path,
    *,
    create_if_missing: bool,
) -> int:
    """Open one single-link Windows regular file without following reparse data."""

    if os.name != "nt":
        raise OSError("windows_regular_file_open_wrong_platform")
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    try:
        named_info = os.lstat(path)
    except FileNotFoundError:
        if not create_if_missing:
            raise
        named_info = None
    if named_info is not None and (
        not stat.S_ISREG(named_info.st_mode)
        or named_info.st_nlink != 1
        or getattr(named_info, "st_file_attributes", 0) & reparse_flag
    ):
        raise OSError("windows_regular_file_open_unsafe")

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

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
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    generic_read = 0x80000000
    generic_write = 0x40000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    open_always = 4
    file_flag_open_reparse_point = 0x00200000
    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400
    invalid_handle = wintypes.HANDLE(-1).value
    windows_handle = create_file(
        str(path),
        generic_read | generic_write,
        file_share_read | file_share_write,
        None,
        open_always if create_if_missing else open_existing,
        file_flag_open_reparse_point,
        None,
    )
    if windows_handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        information = ByHandleFileInformation()
        if not get_information(windows_handle, ctypes.byref(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        file_index = (
            int(information.nFileIndexHigh) << 32
        ) | int(information.nFileIndexLow)
        if (
            information.dwFileAttributes
            & (file_attribute_directory | file_attribute_reparse_point)
            or information.nNumberOfLinks != 1
            or (
                named_info is not None
                and named_info.st_ino
                and named_info.st_ino != file_index
            )
        ):
            raise OSError("windows_regular_file_open_unsafe")
        descriptor = msvcrt.open_osfhandle(
            int(windows_handle),
            os.O_RDWR | getattr(os, "O_BINARY", 0),
        )
        windows_handle = None
        return descriptor
    finally:
        if windows_handle is not None:
            close_handle(windows_handle)
