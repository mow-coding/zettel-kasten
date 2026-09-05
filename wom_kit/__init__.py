"""Source checkout shim for the WOM-kit Python package.

The real package lives in ``wom-kit/src/wom_kit``. This shim lets
``python -m wom_kit.archive_cli`` work from the repository root before an
editable install.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


_SOURCE_PACKAGE = Path(__file__).resolve().parents[1] / "wom-kit" / "src" / "wom_kit"
_extended_path = list(extend_path(__path__, __name__))
if _SOURCE_PACKAGE.is_dir():
    _source_text = str(_SOURCE_PACKAGE)
    __path__ = [
        _source_text,
        *(entry for entry in _extended_path if entry != _source_text),
    ]
else:
    __path__ = _extended_path

__version__ = "0.4.19"
