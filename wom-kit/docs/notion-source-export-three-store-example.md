# Notion Source Export Three-Store Example

Status: worked example for the human artifact store contract

This example shows how to separate a changing Notion workspace into WOM's
three storage roles without treating Notion as the canonical WOM archive.

## Scenario

A user has a Notion workspace that evolved over time:

```text
Notion DB 1.0: loose pages and uploads
Notion DB 2.0: structured project database
Notion DB 3.0: reviewed project dashboard plus linked attachments
```

The user exports or retrieves the workspace outside WOM-kit. The export process
may produce:

- content-addressed binaries with sha256 values,
- a retrieval ledger with sha256 and byte-size fields,
- an attachment catalog,
- a deep crawl tree,
- page/block snapshot JSON such as `recordMap` or `blocks`,
- Markdown/CSV/HTML pages for human review,
- operator notes about what changed between DB versions.

## Three Stores

### Raw Data Store

Raw data is the original source material or its content-addressed copy.

Examples:

- exported attachment binaries,
- content-addressed blob files,
- original Markdown/CSV/HTML export files,
- page/block snapshot JSON that preserves provider structure,
- raw retrieval ledgers that prove which external objects were present.

These are objets or source-export inputs. They are not canonical zets by
themselves, and they are not human-facing summaries.

### Human Artifact Store

Human artifacts are readable working materials that help a person understand
the export.

Examples:

- a review report for DB 1.0 -> DB 2.0 -> DB 3.0,
- a page-level checklist,
- a migration dashboard,
- a handoff note explaining which projects matter,
- a human-readable attachment catalog.

These may live in Notion, Markdown, Joplin, Obsidian, or another user-facing
surface. They are useful, but they do not replace source maps, manifests,
receipts, or canonical WOM archive records.

### System/AI Artifact Store

System/AI artifacts are machine-oriented evidence and control records.

Examples:

- source maps,
- object manifests,
- source-intake plans,
- project-intake decision receipts,
- capture receipts,
- derived-text records,
- indexes,
- sha256 commitments,
- validation reports.

These records should stay in WOM-controlled files unless an adapter explicitly
mirrors them elsewhere with receipts.

## Current Safe Preview Path

Use the human artifact store planner to declare Notion's role:

```bash
archive human-artifact-store <archive-root> \
  --surface-kind notion \
  --role source_export \
  --surface-ref backup-workspace \
  --dry-run \
  --format json
```

Use the prehashed ledger preview when the export already has sha256 and byte
counts:

```bash
archive prehashed-objet-ledger <archive-root> \
  --ledger retrieval-ledger.jsonl \
  --ledger deep-ledger.jsonl \
  --ledger workspace-dl-ledger.jsonl \
  --store-kind notion_source_export \
  --mime-field mime \
  --dry-run \
  --format json
```

`--ledger` may be repeated. WOM-kit dedupes sha256 values across all provided
ledgers in one run. Rows whose sha256 field is null or empty, such as
`via: aid-dedup` rows that point to an object already represented elsewhere, are
counted as skipped rows rather than invalid rows. Malformed non-empty sha values
still count as invalid.

If the ledger includes a safe MIME field, keep it with `--mime-field mime`.
That lets later `derive-text coverage` classify textual candidates without
falling back to `application/octet-stream`.

After reviewing the dry-run, stop. In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before reading the private
ledger/archive target or writing. It appends no external manifest record or
receipt and does not read blob bytes, copy objects, call Notion, upload, sync,
draft, mint, or clean.

MCP exposes only the read-only preview as `prehashed_objet_ledger_preview`.

## Page Snapshot JSON

Notion page/block JSON is a provider page snapshot. It is not a minted `zet`,
not a receipt, and not automatically a derived text body.

Use this model:

```text
recordMap / blocks JSON -> source/original objet
extracted readable block text -> derived text record
human-reviewed conclusion -> draft or minted zet
```

If the snapshot bytes are already in an externally verified
content-addressed store, include them in the prehashed-ledger dry-run with a
safe `--store-ref` label. `prehashed-objet-ledger` and `objet-capture` approval
are fixed fail-closed in v0.4.0 and write nothing.

See [Notion Page Snapshot Model](notion-page-snapshot-model.md).

## Current Boundary

Today, `objet-capture` and the prehashed-ledger route retain their dry-run
validation only. Neither route may register, copy, or materialize bytes in
v0.4.0.

Recommended order:

- keep the external source-export ledger as raw evidence,
- preview it with `prehashed-objet-ledger --dry-run`,
- stop after human review because approval returns
  `compound_exact_human_approval_binding_required`,
- use project-intake and source-intake receipts for human-reviewed context,
- use `objet-capture --dry-run` only to preview staged-byte handling.
