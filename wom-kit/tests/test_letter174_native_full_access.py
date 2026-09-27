"""Actual Windows visibility events while the real dialog factory is enabled.

Only initial synthetic consent and the archive key/remote provider are injected.
The measured cleanup uses the production native approval implementation.
"""
import ctypes
from ctypes import wintypes
import json
import os
import threading
import unittest

from wom_kit import exact_human_approval_windows as windows
from . import test_activity_cleanup as fixture


@unittest.skipUnless(os.name == "nt", "native Windows visibility observation")
class NativeFullAccessTests(unittest.TestCase):
    def test_real_dialog_factory_full_access_has_no_visible_window(self):
        native_factory = windows._CtypesTaskDialogNative
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
            wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
            callback_type, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        ready, stop = threading.Event(), threading.Event()
        seen, errors = [], []
        def observe():
            @callback_type
            def event(hook, kind, hwnd, object_id, child_id, thread, stamp):
                if hwnd and object_id == 0 and user32.IsWindowVisible(hwnd):
                    seen.append({"event": "visible_top_level_window", "timestamp": int(stamp)})
                    # Unexpected test-owned dialogs must fail/cancel instead of
                    # leaving the unattended acceptance run waiting for input.
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
            hook = user32.SetWinEventHook(0x8002, 0x8002, None, event, os.getpid(), 0, 0)
            if not hook:
                errors.append("native_visibility_hook_unavailable")
                ready.set()
                return
            ready.set()
            message = wintypes.MSG()
            try:
                while not stop.wait(.01):
                    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                        user32.TranslateMessage(ctypes.byref(message))
                        user32.DispatchMessageW(ctypes.byref(message))
            finally:
                user32.UnhookWinEvent(hook)
        worker = threading.Thread(target=observe, daemon=True)
        case = fixture.ActivityCleanupTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        calls = []
        def actual_factory():
            calls.append("production_factory")
            return native_factory()
        case.actual_native_factory = actual_factory
        worker.start()
        self.assertTrue(ready.wait(5))
        self.assertEqual(errors, [])
        try:
            case.test_full_access_official_pipeline_has_zero_additional_dialogs()
        finally:
            stop.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen, [], seen)
        print(json.dumps({"windows_visibility_hook_active": True, "observed_visible_windows": len(seen),
            "production_native_factory_enabled": True, "factory_constructions": len(calls),
            "synthetic_consent_and_remote": True, "customer_acceptance": False}), flush=True)
