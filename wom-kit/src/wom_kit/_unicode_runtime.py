"""Lazily adapt one Windows native import without changing search locations.

Windows' native-extension loader can reject an otherwise valid selected file
at MAX_PATH. Only that already selected extension receives an equivalent
extended-length spelling. Python retains module initialization and ownership.
Other modules, search locations, and Unicode normalization are unchanged.
"""

from __future__ import annotations

import importlib
from importlib import machinery, util
import ntpath
import os
import sys
from types import ModuleType


_NAME = "unicodedata2"
_MAX_PATH = 260

# Preserve exact identities across reload. Never relocate an existing hook or
# replace a host's finder with a guessed equivalent.
if "_PATH_FINDER" not in globals():
    _PATH_FINDER = machinery.PathFinder


def _extended_origin(spec: machinery.ModuleSpec) -> str | None:
    """Return a path spelling only for the exact selected long native file."""

    origin = spec.origin
    loader = spec.loader
    if (
        os.name != "nt"
        or type(loader) is not machinery.ExtensionFileLoader
        or not isinstance(origin, str)
        or origin.startswith("\\\\?\\")
    ):
        return None
    # Leave *every* short-path import spelling and loader state to Python.
    # Strict conversion checks apply only after this long-path-only gate.
    if len(origin.encode("utf-16-le")) // 2 < _MAX_PATH:
        return None
    if (
        spec.name != _NAME
        or loader.name != _NAME
        or loader.path != origin
        or spec.submodule_search_locations is not None
        or spec.loader_state is not None
        or not spec.has_location
    ):
        raise ImportError("unicode_runtime_selected_spec_invalid")
    if origin.startswith("\\\\.\\"):
        raise ImportError("unicode_runtime_selected_spec_invalid")
    path = origin
    drive, tail = ntpath.splitdrive(path)
    if not drive or not tail.startswith("\\") or ntpath.normpath(path) != path:
        raise ImportError("unicode_runtime_selected_spec_invalid")
    extended = (
        "\\\\?\\UNC\\" + path[2:]
        if path.startswith("\\\\")
        else "\\\\?\\" + path
    )
    if not os.path.samefile(origin, extended):
        raise ImportError("unicode_runtime_selected_file_changed")
    return extended


class _UnicodeExtensionLoader(machinery.ExtensionFileLoader):
    """Forward standard native loading, without private failure text."""

    def create_module(self, spec):
        try:
            return super().create_module(spec)
        except (ImportError, OSError, ValueError):
            pass
        raise ImportError("unicode_runtime_dependency_unavailable")

    def exec_module(self, module):
        try:
            return super().exec_module(module)
        except (ImportError, OSError, ValueError):
            pass
        raise ImportError("unicode_runtime_dependency_unavailable")


class _UnicodePathFinder:
    """A one-name meta-path protocol implementation, before exact PathFinder."""

    def _is_adjacent(self) -> bool:
        if machinery.PathFinder is not _PATH_FINDER:
            return False
        entries = tuple(sys.meta_path)
        own = [i for i, value in enumerate(entries) if value is self]
        selected = [i for i, value in enumerate(entries) if value is _PATH_FINDER]
        return len(own) == len(selected) == 1 and selected[0] == own[0] + 1

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _NAME or os.name != "nt" or path is not None:
            return None
        if not self._is_adjacent():
            return None
        try:
            # util.find_spec would recurse through this hook. Use only the
            # exact original path finder, at its existing precedence point.
            selected = _PATH_FINDER.find_spec(fullname, path, target)
            if selected is None or not self._is_adjacent():
                return None
            extended = _extended_origin(selected)
            if extended is None:
                # Path-entry finders may be stateful. Do not ask PathFinder a
                # second time after it has already made the ordinary choice.
                return selected
            converted = util.spec_from_file_location(
                _NAME,
                extended,
                loader=_UnicodeExtensionLoader(_NAME, extended),
            )
            if converted is not None:
                return converted
        except (ImportError, OSError, ValueError):
            pass
        # Selection/conversion errors carry no private path or exception chain.
        raise ImportError("unicode_runtime_dependency_unavailable")


if "_FINDER" not in globals():
    _FINDER = _UnicodePathFinder()


def register_unicode_finder() -> None:
    """Register lazily; do not import the native engine or touch any file."""

    if os.name != "nt" or any(value is _FINDER for value in sys.meta_path):
        return
    if machinery.PathFinder is not _PATH_FINDER:
        return
    selected = [i for i, value in enumerate(sys.meta_path) if value is _PATH_FINDER]
    if len(selected) == 1:
        sys.meta_path.insert(selected[0], _FINDER)


def load_unicode() -> ModuleType:
    """Use ordinary import/cache/locking; never fall back to another Unicode."""

    try:
        register_unicode_finder()
        return importlib.import_module(_NAME)
    except (ImportError, OSError, ValueError):
        pass
    # A missing/broken pinned engine must not silently change normalization.
    # Keep private dependency paths and loader exception context out of errors.
    raise ImportError("unicode_runtime_dependency_unavailable")
