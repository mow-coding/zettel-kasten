"""Ephemeral native-only target views, never an approval or public document.

Callers supply labels only from evidence already bound by their exact plan.
This module does not inspect files, infer relationships, or grant write authority.
Native Task Dialog uses plain text, so Markdown ranges and incomplete markers
are displayed literally without changing the canonical source bytes.
"""

from __future__ import annotations

import re
from collections import Counter


TARGET_COLLECTION_PAGE_SIZE = 20
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_KINDS = {"zet": "zet", "draft": "초안", "objet": "오브제"}


def _safe_text(value: object) -> str | None:
    # Reuse the approval boundary's complete-input sensitive-shape filter.
    # The deferred import keeps the native boundary and view model acyclic.
    from .exact_human_approval_windows import exact_human_approval_safe_content_preview

    return exact_human_approval_safe_content_preview(value, truncate=True)


class _LocalOnly:
    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("target_collection_preview_immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("target_collection_preview_immutable")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("target_collection_preview_local_only")


class TargetCollectionItem(_LocalOnly):
    """One exact identity with optional sanitized, already-bound local labels."""

    __slots__ = ("identity_sha256", "kind", "title", "filename")

    def __init__(
        self,
        *,
        identity_sha256: str,
        kind: str,
        title: str | None = None,
        filename: str | None = None,
    ) -> None:
        if (
            type(identity_sha256) is not str
            or _SHA256.fullmatch(identity_sha256) is None
            or type(kind) is not str
            or kind not in _KINDS
        ):
            raise ValueError("target_collection_preview_invalid")
        safe_filename = (
            _safe_text(filename)
            if type(filename) is str and not any(mark in filename for mark in ("/", "\\"))
            else None
        )
        object.__setattr__(self, "identity_sha256", identity_sha256)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "title", _safe_text(title))
        object.__setattr__(self, "filename", safe_filename)

    def __repr__(self) -> str:
        return "<TargetCollectionItem values=local-only>"


class TargetCollectionPreview(_LocalOnly):
    """Count-first collection, or one edge with its two bound endpoints.

The exact identity is retained even when every human label is omitted. Only
colliding display names receive a short digest; a unique title is not cluttered
with internal identifiers. Page methods deliberately return native-only text.
"""

    __slots__ = ("_items", "_names", "_relation_meaning", "_reason", "_is_edge")

    def __init__(
        self,
        *,
        items: tuple[TargetCollectionItem, ...],
        relation_meaning: str | None = None,
        reason: str | None = None,
    ) -> None:
        if (
            type(items) is not tuple
            or not items
            or any(type(item) is not TargetCollectionItem for item in items)
            or len({item.identity_sha256 for item in items}) != len(items)
            or (relation_meaning is not None and len(items) != 2)
            or (reason is not None and relation_meaning is None)
        ):
            raise ValueError("target_collection_preview_invalid")
        labels = tuple(
            item.title or item.filename or f"{_KINDS[item.kind]} · 미리보기 생략"
            for item in items
        )
        counts = Counter(labels)
        peers_by_label: dict[str, list[str]] = {}
        for item, label in zip(items, labels):
            peers_by_label.setdefault(label, []).append(item.identity_sha256[7:])
        widths: dict[str, int] = {}
        for label, peers in peers_by_label.items():
            if counts[label] > 1:
                width = 8
                while len({digest[:width] for digest in peers}) != len(peers):
                    width += 1
                widths[label] = width
        names = []
        for item, label in zip(items, labels):
            if counts[label] > 1:
                width = widths[label]
                label = f"{label} · {item.identity_sha256[7:7 + width]}"
            names.append(label)
        object.__setattr__(self, "_items", items)
        object.__setattr__(self, "_names", tuple(names))
        object.__setattr__(self, "_is_edge", relation_meaning is not None)
        object.__setattr__(self, "_relation_meaning", _safe_text(relation_meaning))
        object.__setattr__(self, "_reason", _safe_text(reason))

    @property
    def count(self) -> int:
        return len(self._items)

    @property
    def page_count(self) -> int:
        return (self.count + TARGET_COLLECTION_PAGE_SIZE - 1) // TARGET_COLLECTION_PAGE_SIZE

    def native_main_text(self) -> str:
        if not self._is_edge:
            return f"대상 {self.count:,}개"
        return (
            f"{self._names[0]} → {self._names[1]}\n"
            f"관계 의미: {self._relation_meaning or '미리보기 생략'}\n"
            f"근거: {self._reason or '미리보기 생략'}"
        )

    def native_page_text(self, page_index: int) -> str:
        if type(page_index) is not int or not 0 <= page_index < self.page_count:
            raise ValueError("target_collection_preview_page_invalid")
        start = page_index * TARGET_COLLECTION_PAGE_SIZE
        rows = self._names[start:start + TARGET_COLLECTION_PAGE_SIZE]
        return "\n".join(f"{start + offset + 1}. {name}" for offset, name in enumerate(rows))

    def __repr__(self) -> str:
        return f"<TargetCollectionPreview count={self.count} values=local-only>"
