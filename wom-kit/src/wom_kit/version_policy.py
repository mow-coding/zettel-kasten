"""Shareable exact stable WOM version-label policy."""

from __future__ import annotations

import re


MAX_STABLE_VERSION_LABEL_LENGTH = 64
STABLE_VERSION_TAG_RE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
    re.ASCII,
)
RELEASE_VERSION_TAG_RE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:b([1-9][0-9]*))?$",
    re.ASCII,
)


def normalize_version_label(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > MAX_STABLE_VERSION_LABEL_LENGTH:
        return None
    normalized = value.strip().lstrip("\ufeff").strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]
    return normalized or None


def stable_version_value(
    value: str | None,
    *,
    include_prefix: bool = False,
) -> str | None:
    """Return only a public, exact stable WOM version label.

    Version files, ownership manifests, and local Git metadata are untrusted
    local inputs. Arbitrary payloads stay inside fail-closed decisions and are
    never projected into shareable results.
    """

    normalized = normalize_version_label(value)
    if normalized is None:
        return None
    label = f"v{normalized}"
    if STABLE_VERSION_TAG_RE.fullmatch(label) is None:
        return None
    return label if include_prefix else normalized


def release_version_value(value: str | None, *, include_prefix: bool = False) -> str | None:
    """Accept stable or explicit canonical PEP 440 beta labels, never aliases."""
    if value is not None and not isinstance(value, str):
        return None
    normalized = normalize_version_label(value)
    if normalized is None or RELEASE_VERSION_TAG_RE.fullmatch("v" + normalized) is None:
        return None
    return "v" + normalized if include_prefix else normalized


def release_sort_key(value: str | None) -> tuple[int, int, int, str] | None:
    normalized = release_version_value(value)
    if normalized is None:
        return None
    match = RELEASE_VERSION_TAG_RE.fullmatch("v" + normalized)
    beta = match.group(4)
    # Stable sorts after all betas of the same target; beta 10 follows beta 9.
    suffix = "~" if beta is None else f"b{len(beta):02d}:{beta}"
    return tuple(int(match.group(i)) for i in (1, 2, 3)) + (suffix,)
