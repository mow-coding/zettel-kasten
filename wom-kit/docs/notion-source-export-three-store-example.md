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
- Markdown/CSV/HTML pages for human review,
- operator notes about what changed between DB versions.

## Three Stores

### Raw Data Store

Raw data is the original source material or its content-addressed copy.

Examples:

- exported attachment binaries,
- content-addressed blob files,
- original Markdown/CSV/HTML export files,
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
  --store-kind notion_source_export \
  --dry-run \
  --format json
```

This second command only checks ledger shape and counts. It does not read blob
bytes, register object manifests, call Notion, upload, sync, draft, mint, or
clean.

## Current Boundary

Today, `objet-capture` still verifies bytes from staged local files. It does
not yet import an already-hashed external content-addressed store without
rehashing. A future no-rehash path needs a separate approval-gated manifest
registration command with its own receipts.

Until that exists:

- keep the external source-export ledger as raw evidence,
- preview it with `prehashed-objet-ledger --dry-run`,
- use project-intake and source-intake receipts for human-reviewed context,
- use `objet-capture` only when WOM-kit is allowed to verify staged bytes.
