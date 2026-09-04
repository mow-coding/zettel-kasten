"""Cross-platform launch flags for invisible noninteractive child processes.

WOM uses native UI for the decisions that require a human.  Those approval
windows must stay visible.  Git, Docker, Python runtime probes, and other
captured or discarded child processes are different: on Windows, launching a
console executable without an explicit flag can flash a black console window.

Callers opt in by passing :func:`noninteractive_creationflags` to
``subprocess.run`` or ``subprocess.Popen``.  Keeping the opt-in explicit makes
it difficult to accidentally hide an interactive approval or credential UI.
"""

from __future__ import annotations

import os
import subprocess


# CPython exposes subprocess.CREATE_NO_WINDOW on Windows.  Keep the documented
# Win32 value as a fallback so an alternate compatible runtime cannot silently
# regress to a visible console.
WINDOWS_CREATE_NO_WINDOW = int(
    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
)
_IS_WINDOWS = os.name == "nt"


def noninteractive_creationflags(existing: int = 0) -> int:
    """Return launch flags that never create a console for background work.

    ``existing`` lets containment-sensitive callers preserve flags such as
    ``CREATE_NEW_PROCESS_GROUP`` or ``CREATE_SUSPENDED``.  On non-Windows
    systems the value is unchanged; ordinary callers pass zero, which is the
    only portable value accepted by :mod:`subprocess`.

    This helper is intentionally *not* a default subprocess wrapper.  Native
    approval and secure-input UI stay visible because only explicitly
    noninteractive call sites opt in.
    """

    if isinstance(existing, bool) or not isinstance(existing, int) or existing < 0:
        raise ValueError("noninteractive_creationflags_invalid")
    if not _IS_WINDOWS:
        return existing
    return existing | WINDOWS_CREATE_NO_WINDOW
