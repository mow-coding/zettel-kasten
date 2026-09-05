"""Immutable read-only projection pages; cursors never grant write authority.

A cursor is a canonical, content-free continuation identifier with an integrity
checksum, not a secret MAC or proof that earlier pages were read. The collector
must independently establish a complete, consistent metadata generation before
building a pager. A new process must collect/revalidate that generation again.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


PAGINATION_SCHEMA = "wom-kit/snapshot-pagination/v1"
CURSOR_SCHEMA = "wom-kit/snapshot-cursor/v1"
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CURSOR_KEYS = frozenset({
    "schema", "snapshot_sha256", "query_sha256", "offset", "page_size", "integrity_sha256",
})


class SnapshotPaginationError(ValueError):
    _CODES = frozenset({
        "snapshot_pagination_input_invalid",
        "snapshot_pagination_cursor_invalid",
        "snapshot_pagination_query_changed",
        "snapshot_pagination_generation_changed",
    })

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "snapshot_pagination_input_invalid"
        super().__init__(self.code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise SnapshotPaginationError("snapshot_pagination_input_invalid") from None


def content_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _require_sha(value: Any) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise SnapshotPaginationError("snapshot_pagination_input_invalid")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key] = value
    return result


def _decode_cursor(cursor: Any) -> dict[str, Any]:
    try:
        if type(cursor) is not str or not 1 <= len(cursor) <= 2048:
            raise ValueError("shape")
        if re.fullmatch(r"[A-Za-z0-9_-]+", cursor) is None:
            raise ValueError("encoding")
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        if type(value) is not dict or set(value) != _CURSOR_KEYS:
            raise ValueError("fields")
        if value["schema"] != CURSOR_SCHEMA or _canonical(value) != raw:
            raise ValueError("canonical")
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != cursor:
            raise ValueError("encoding")
        for name in ("snapshot_sha256", "query_sha256", "integrity_sha256"):
            _require_sha(value[name])
        for name in ("offset", "page_size"):
            if type(value[name]) is not int or not 1 <= value[name] <= 2**63 - 1:
                raise ValueError("integer")
        expected = content_sha256({key: entry for key, entry in value.items() if key != "integrity_sha256"})
        if value["integrity_sha256"] != expected:
            raise ValueError("integrity")
        return value
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        raise SnapshotPaginationError("snapshot_pagination_cursor_invalid") from None


@dataclass(frozen=True)
class SnapshotPager:
    """One fully captured projection; individual pages require no repeated scan."""

    _rows: tuple[bytes, ...]
    generation_sha256: str
    query_sha256: str
    snapshot_sha256: str

    @classmethod
    def build(
        cls,
        items: Iterable[Mapping[str, Any]],
        *,
        generation_sha256: str,
        query_sha256: str,
    ) -> SnapshotPager:
        generation = _require_sha(generation_sha256)
        query = _require_sha(query_sha256)
        rows: list[bytes] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise SnapshotPaginationError("snapshot_pagination_input_invalid")
            rows.append(_canonical(dict(item)))
        frozen = tuple(rows)
        snapshot = content_sha256({
            "schema": PAGINATION_SCHEMA,
            "generation_sha256": generation,
            "query_sha256": query,
            "row_sha256": ["sha256:" + hashlib.sha256(row).hexdigest() for row in frozen],
        })
        return cls(frozen, generation, query, snapshot)

    def page(self, *, page_size: int, cursor: str | None = None) -> dict[str, Any]:
        if type(page_size) is not int or not 1 <= page_size <= 2**63 - 1:
            raise SnapshotPaginationError("snapshot_pagination_input_invalid")
        offset = 0
        if cursor is not None:
            payload = _decode_cursor(cursor)
            if payload["query_sha256"] != self.query_sha256 or payload["page_size"] != page_size:
                raise SnapshotPaginationError("snapshot_pagination_query_changed")
            if payload["snapshot_sha256"] != self.snapshot_sha256:
                raise SnapshotPaginationError("snapshot_pagination_generation_changed")
            offset = payload["offset"]
            if offset >= len(self._rows) or offset % page_size:
                raise SnapshotPaginationError("snapshot_pagination_cursor_invalid")
        end = min(offset + page_size, len(self._rows))
        next_cursor = None
        if end < len(self._rows):
            payload = {
                "schema": CURSOR_SCHEMA,
                "snapshot_sha256": self.snapshot_sha256,
                "query_sha256": self.query_sha256,
                "offset": end,
                "page_size": page_size,
            }
            payload["integrity_sha256"] = content_sha256(payload)
            next_cursor = base64.urlsafe_b64encode(_canonical(payload)).decode("ascii").rstrip("=")
        return {
            "items": [json.loads(row) for row in self._rows[offset:end]],
            "pagination": {
                "schema": PAGINATION_SCHEMA,
                "state": "complete",
                "snapshot_sha256": self.snapshot_sha256,
                "generation_sha256": self.generation_sha256,
                "query_sha256": self.query_sha256,
                "page_size": page_size,
                "offset": offset,
                "total_count": len(self._rows),
                "observed_count": len(self._rows),
                "returned_count": end - offset,
                "remaining_count": len(self._rows) - end,
                "next_cursor": next_cursor,
                "has_more": end < len(self._rows),
                "complete_listing": offset == 0 and end == len(self._rows),
                "cursor_is_authority": False,
                "prior_pages_read_proven": False,
            },
        }
