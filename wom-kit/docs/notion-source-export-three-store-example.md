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

If the dry-run is reviewed and the external store should be declared as a WOM
objet source, approve the manifest registration with a safe store label:

```bash
archive prehashed-objet-ledger <archive-root> \
  --ledger retrieval-ledger.jsonl \
  --store-kind notion_source_export \
  --store-ref notion-export-20260613 \
  --approve \
  --reviewed-by person:me \
  --format json
```

Approved mode appends external records to `objects/manifests/files.jsonl` and
writes a receipt under `receipts/prehashed-objet-ledger/`. It still does not
read blob bytes, copy objects, call Notion, upload, sync, draft, mint, or clean.

MCP exposes only the read-only preview as `prehashed_objet_ledger_preview`.

## Current Boundary

Today, `objet-capture` still verifies bytes from staged local files. The
prehashed ledger path is separate: it can register externally verified object
IDs in the manifest without re-reading blob bytes, but it does not prove,
copy, or materialize those bytes inside the archive.

Recommended order:

- keep the external source-export ledger as raw evidence,
- preview it with `prehashed-objet-ledger --dry-run`,
- approve it with `--approve --reviewed-by <actor> --store-ref <safe-label>`
  only after human review,
- use project-intake and source-intake receipts for human-reviewed context,
- use `objet-capture` only when WOM-kit is allowed to verify staged bytes and
  store local content-addressed copies.
