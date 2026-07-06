# Decision Log - v0.3.179 Remint Diagnostic-Only Redaction

Date: 2026-07-06
Batch: v0.3.179.
Anchor: v0.3.178 public release.

## Problem

The v0.3.176 body-diff diagnostic was content-free by itself, but the full
`remint-reconcile --format json` plan still carried `current_canonical_text` and detailed
frontmatter value changes. That full payload is appropriate for review, but not for a quick
operator diagnostic transcript.

## Decisions

- **DEC-1 - Keep existing JSON backward-compatible.** Do not remove fields from ordinary
  `--format json`; scripts and reviewers may depend on the full payload.
- **DEC-2 - Add an explicit redacted projection.** `--diagnostic-only --format json` returns a
  smaller dry-run view with drift class, body-change status, `body_diff_diagnostic`,
  blocker/warning context, and frontmatter field names/counts.
- **DEC-3 - Omit body text and frontmatter values.** The projection drops
  `current_canonical_text` and the full `frontmatter_field_changes` list, replacing the latter
  with field names and count only.
- **DEC-4 - Refuse approve.** `--diagnostic-only` is dry-run only. Approval must keep showing
  the current on-disk content so receipt hash recomputation remains human-reviewed.
- **DEC-5 - JSON only.** The redacted surface is for structured operator diagnostics. Text mode
  stays the existing human-review printer.

## Consequences

Operators can run:

```bash
archive remint-reconcile <archive-root> --zettel-id <id> --dry-run --diagnostic-only --format json
```

to inspect the body-diff category without copying canonical body text into the JSON transcript.
The existing review and approval flows remain unchanged.
