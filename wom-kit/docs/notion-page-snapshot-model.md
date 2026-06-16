# Notion Page Snapshot Model

Status: v0.3.16 model baseline
Date: 2026-06-14

This document answers a narrow but important import question:

```text
When a Notion export or retrieval contains page/block JSON, what is it in WOM?
```

## Short Answer

A provider page snapshot is a source/original objet.

For Notion, that may include JSON shaped like `recordMap`, `blocks`, page
properties, database row metadata, parent-child links, provider ids,
timestamps, attachment refs, or crawl tree entries.

It is not automatically:

- a minted `zet`,
- a human-reviewed conclusion,
- a derived text body,
- a source map,
- a receipt,
- an object manifest.

It is provider/workspace evidence. If the user wants to preserve it as part of
the archive, it should receive an `object_id` through a manifest path.

## Layering Rule

Use this layering model:

```text
Notion export / retrieval
-> page snapshot JSON as source/original objet
-> extracted readable block text as derived text
-> human-reviewed note or conclusion as draft/minted zet
```

The page snapshot JSON preserves the provider structure. The derived text
record preserves readable text extracted from that structure. The zet records a
human-approved interpretation, summary, decision, or memory.

These layers can point to each other, but they should not be collapsed.

## What Counts As A Page Snapshot

Examples:

- one exported page JSON file,
- one Notion API page/block tree response saved as JSON,
- a `recordMap` style object containing page and block records,
- database row metadata plus page property values,
- a crawl output that records page ids, block ids, parent links, and attachment
  references,
- a provider snapshot bundle that can be hashed and addressed.

These snapshots may contain private content. Do not commit them to the public
repository unless they are tiny fake examples.

## Current Registration Paths

There are two safe current paths, depending on where the bytes live.

### Externally Verified Store

If an external export process already produced sha256 and byte-size values,
register the snapshot through the prehashed ledger path:

```bash
archive prehashed-objet-ledger <archive-root> \
  --ledger notion-page-snapshots.jsonl \
  --store-kind notion_source_export \
  --store-ref notion-export-20260614 \
  --mime-field mime \
  --dry-run \
  --format json
```

After review:

```bash
archive prehashed-objet-ledger <archive-root> \
  --ledger notion-page-snapshots.jsonl \
  --store-kind notion_source_export \
  --store-ref notion-export-20260614 \
  --mime-field mime \
  --approve \
  --reviewed-by person:me \
  --format json
```

This appends manifest records for externally verified object ids. It does not
read the JSON bytes, copy files, call Notion, upload, draft, mint, or clean.
If the ledger has MIME values, `--mime-field mime` keeps page snapshots and
textual export rows classifiable for later derived-text coverage.

### WOM-Verified Staged File

If the JSON file is staged under an archive-controlled staging area and WOM-kit
is allowed to hash and copy it, use the local `objet-capture` path instead.

That path verifies bytes from the staged file before writing a local content
addressed copy and manifest record.

## Derived Text From Page Snapshots

Do not treat raw page snapshot JSON as the derived text body.

If a parser extracts readable block text from the snapshot, register that text
as derived text against the page snapshot `object_id` or against the broader
source-export object id:

```bash
archive derive-text capture <archive-root> \
  --text-file extracted-page-text.txt \
  --source-object-id sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --derivation-kind parser \
  --tool-name notion-block-text-extractor \
  --tool-version 1.0.0 \
  --review-status unreviewed \
  --dry-run \
  --format json
```

The derived text record can later support drafting, search, review, and minting.
It still does not replace the original page snapshot.

## `store-ref` Meaning

In prehashed ledger records:

```text
object_id  -> what bytes are being identified
store_kind -> what storage family supplied the external ledger
store_ref  -> which reviewed external store label contains those bytes
```

`store_ref` is a safe binding label. It should be stable enough for the archive
operator to find the external byte store again, but it must not be a raw local
absolute path, private URL, account id, token, email address, or secret.

Examples of safe labels:

```text
notion-export-20260614
notion-page-snapshots-20260614
retrieval-ledger-batch-001
workspace-export-reviewed-a
```

`store_ref` does not prove byte availability by itself. Today, WOM-kit records
the manifest reference and receipt. Future provider adapters may add explicit
byte materialization or availability checks, but v0.3.16 does not.

## Public/Private Boundary

Keep these out of the public repository:

- real page snapshot JSON,
- real workspace/page titles if private,
- local absolute paths,
- private provider URLs,
- tokens or API responses containing secrets,
- raw attachment binaries.

Public docs should use fake hashes, fake page names, and safe store labels.

## Future Work

Future versions may add:

- a page-snapshot manifest schema,
- provider-specific safe refs for page ids and block ids,
- Notion API or export adapters,
- external store byte verification,
- page-snapshot to derived-text extraction helpers,
- delta snapshots between workspace versions.

None of those are implemented in v0.3.16.
