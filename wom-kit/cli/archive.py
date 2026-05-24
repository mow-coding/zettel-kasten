#!/usr/bin/env python3
"""Compatibility wrapper for the packaged archive CLI."""

from __future__ import annotations

import sys
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit.archive_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

