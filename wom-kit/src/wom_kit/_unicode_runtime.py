"""Load the pinned Unicode engine without changing global import/search paths.

Windows' native-extension loader can reject an otherwise valid selected file
at MAX_PATH. Only that already selected extension receives an equivalent
extended-length spelling. This is not a dependency finder or Unicode fallback.
"""

from __future__ import annotations

import importlib
from importlib import _bootstrap, machinery, util
import ntpath
import os
import sys
from types import ModuleType


_NAME = "unicodedata2"
_MAX_PATH = 260


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


def load_unicode() -> ModuleType:
    """Share one standard-initialized module, or fail without changing Unicode."""

    try:
        # CPython 3.10/3.12's existing import protocol owns the module lock,
        # _initializing flag, publication, and error cleanup. Do not hand-roll
        # sys.modules publication: ordinary imports must not see a partial
        # module or initialize a second copy. These private hooks are covered
        # by the supported-version CI and guarded before use.
        lock_manager = getattr(_bootstrap, "_ModuleLockManager", None)
        load = getattr(_bootstrap, "_load", None)
        if not callable(lock_manager) or not callable(load):
            raise ImportError("unicode_runtime_import_protocol_unavailable")
        with lock_manager(_NAME):
            # Recheck under the *same* lock used by an ordinary raw import.
            # import_module also preserves the standard explicit-None block.
            if _NAME in sys.modules:
                return importlib.import_module(_NAME)
            spec = util.find_spec(_NAME)
            if spec is None or spec.name != _NAME:
                raise ImportError("unicode_runtime_dependency_unavailable")
            extended = _extended_origin(spec)
            if extended is None:
                return importlib.import_module(_NAME)
            spec = util.spec_from_file_location(
                _NAME,
                extended,
                loader=machinery.ExtensionFileLoader(_NAME, extended),
            )
            if spec is None:
                raise ImportError("unicode_runtime_selected_spec_invalid")
            return load(spec)
    except (ImportError, OSError, ValueError):
        pass
    # A missing/broken pinned engine must not silently change normalization.
    # Keep private dependency paths and loader exception context out of errors.
    raise ImportError("unicode_runtime_dependency_unavailable")
