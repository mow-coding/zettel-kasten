"""WOM-kit package for local-first zet archives."""

__version__ = "0.4.47b21"

from ._unicode_runtime import register_unicode_finder as _register_unicode_finder

_register_unicode_finder()
