"""Legacy identifier detection for new WOM records (v0.4.34, beta letter 165 [B]).

A migrated Notion workspace leaves two kinds of pre-WOM identifiers behind:
the sequential ``ZET<number>`` page names and the 32-hex Notion page ids.
Both keep leaking into new zets, labels and intake filenames because they are
what the operator remembers, and nothing in WOM said so. This module is the
one detector the writers share; every surface reports it the v0.4.31 way —
fixed code, category, detector, rule, counts and body line numbers — and
never echoes the matched text.

The detector is deliberately narrow: an identifier joined with ``_`` is part
of a WOM id (``zet_notion_db3_ZET0637``, ``approval_<hex>``) and is not
flagged; the bare page name and the bare page id are.
"""

from __future__ import annotations

import re
from typing import Any

ZET_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])ZET[0-9]{3,4}(?![0-9A-Za-z])", re.IGNORECASE)
NOTION_PAGE_ID_RE = re.compile(
    r"(?<![0-9A-Fa-f_])(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"(?![0-9A-Fa-f-])",
    re.IGNORECASE,
)
CATEGORY = "legacy_identifier"
DETECTOR = "legacy_identifier_scan"
RULE = "bare_zet_number_or_notion_page_id_outside_a_wom_id"
CODE_NEW_RECORD = "legacy_identifier_in_new_record"
CODE_MIGRATED_RECORD = "legacy_identifier_in_migrated_record"
CODE_LABEL_REVIEW = "label_legacy_identifier_review"
CODE_SOURCE_LABEL = "legacy_identifier_in_source_label"
GUIDANCE = (
    "Reference a migrated zet by its full WOM id (for example zet_notion_db3_ZET0637) or by its "
    "title; never write the bare ZET number or a Notion page id into a new body, title or label."
)
MAPPING_NEXT_STEPS = (
    "archive zettel-edge <archive-root> --source <zet-id> --target zet:notion:ZET<n> --dry-run --format json "
    "resolves a bare ZET number to its WOM id (exact resolver; the current index is required).",
    "archive search <archive-root> \"<32-hex page id>\" --count-total --format json finds the migrated zet "
    "that preserved a Notion page id.",
)
_MAX_LINES = 32


def _lines(text: str, pattern: re.Pattern[str]) -> tuple[int, list[int], bool]:
    count = 0
    lines: set[int] = set()
    for match in pattern.finditer(text):
        count += 1
        lines.add(text.count("\n", 0, match.start()) + 1)
    ordered = sorted(lines)
    return count, ordered[:_MAX_LINES], len(ordered) > _MAX_LINES


def legacy_identifier_scan(body: str | None, *, title: str | None = None) -> dict[str, Any]:
    """Content-free evidence: counts and 1-based body lines, never the text."""

    body_text = body if type(body) is str else ""
    title_text = title if type(title) is str else ""
    zet_count, zet_lines, zet_truncated = _lines(body_text, ZET_NUMBER_RE)
    page_count, page_lines, page_truncated = _lines(body_text, NOTION_PAGE_ID_RE)
    title_zet = len(ZET_NUMBER_RE.findall(title_text))
    title_page = len(NOTION_PAGE_ID_RE.findall(title_text))
    return {
        "category": CATEGORY,
        "detector": DETECTOR,
        "rule": RULE,
        "zet_number_count": zet_count + title_zet,
        "zet_number_body_lines": zet_lines,
        "zet_number_in_title": title_zet > 0,
        "notion_page_id_count": page_count + title_page,
        "notion_page_id_body_lines": page_lines,
        "notion_page_id_in_title": title_page > 0,
        "lines_truncated": zet_truncated or page_truncated,
        "body_line_count": body_text.count("\n") + 1 if body_text else 0,
        "matched_text_echoed": False,
    }


def legacy_identifier_present(body: str | None, *, title: str | None = None) -> bool:
    evidence = legacy_identifier_scan(body, title=title)
    return evidence["zet_number_count"] > 0 or evidence["notion_page_id_count"] > 0


def legacy_identifier_explanation(
    body: str | None, *, title: str | None = None, migrated_record: bool = False,
    mapping_available: bool | None = None,
) -> dict[str, Any] | None:
    """The v0.4.31-shaped explanation entry, or None when nothing matched.

    ``migrated_record`` downgrades the code to the informational one: a zet
    that itself came out of the Notion import may legitimately carry its
    own old name. ``mapping_available`` says whether the archive index can
    resolve the old identifiers (migrated zets are indexed).
    """

    evidence = legacy_identifier_scan(body, title=title)
    if evidence["zet_number_count"] == 0 and evidence["notion_page_id_count"] == 0:
        return None
    return {
        "code": CODE_MIGRATED_RECORD if migrated_record else CODE_NEW_RECORD,
        **evidence,
        "mapping_available": mapping_available,
        "guidance": GUIDANCE,
        "next_safe_actions": list(MAPPING_NEXT_STEPS) if mapping_available else [],
    }


def label_legacy_identifier_present(value: Any) -> bool:
    """For labels and filenames: a single-line scan, no line evidence."""

    if type(value) is not str or not value:
        return False
    return bool(ZET_NUMBER_RE.search(value) or NOTION_PAGE_ID_RE.search(value))


__all__ = [
    "CODE_LABEL_REVIEW", "CODE_MIGRATED_RECORD", "CODE_NEW_RECORD", "CODE_SOURCE_LABEL", "GUIDANCE",
    "MAPPING_NEXT_STEPS", "NOTION_PAGE_ID_RE", "ZET_NUMBER_RE", "label_legacy_identifier_present",
    "legacy_identifier_explanation", "legacy_identifier_present", "legacy_identifier_scan",
]
