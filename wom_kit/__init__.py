"""Source checkout shim for the WOM-kit Python package.

The real package lives in ``wom-kit/src/wom_kit``. This shim lets
``python -m wom_kit.archive_cli`` work from the repository root before an
editable install.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)

_SOURCE_PACKAGE = Path(__file__).resolve().parents[1] / "wom-kit" / "src" / "wom_kit"
if _SOURCE_PACKAGE.is_dir():
    __path__.append(str(_SOURCE_PACKAGE))

__version__ = "0.2.58"
