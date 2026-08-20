# External Imports

Status: dry-run-only in v0.4.0. `import-external` approval fails with
`compound_exact_human_approval_binding_required` before archive/export read or
mutation and writes no inbox draft or import receipt. Approval examples below
are historical v0.3 behavior, not current run instructions.

External import brings records from existing systems into the archive as governed inbox drafts.

Phase 9 supports:

```text
notion
google_drive
```

## Safety Model

The first implementation does not call Notion or Google Drive APIs directly.

Instead, it imports from:

```text
an exported folder
a JSON/YAML manifest that points at exported files
```

This keeps OAuth tokens, browser cookies, API keys, and service account keys outside archive files.

The flow is:

```text
external system export
archive import-external --dry-run
human review
stop: v0.4.0 approval is fixed fail-closed
no inbox draft or import receipt
```

## Notion Export

Export Notion pages as Markdown, then run:

```text
archive import-external <archive> --source notion --export <notion-export-folder> --dry-run
```

After review, keep the operation in dry-run. An approval request returns
`compound_exact_human_approval_binding_required` before reading the private
export/archive target or writing. Historical v0.3 runs could create one draft
per Markdown/text file; v0.4.0 creates none.

## Notion Manifest Title Fallback

From v0.3.285, a new Notion item in a JSON or YAML manifest can use one
same-item `index` value as its imported draft title when the item's resolved
primary title is identifier-shaped.

For example:

```json
{
  "source_system": "notion",
  "items": [
    {
      "external_id": "0123456789abcdef0123456789abcdef",
      "title": "0123456789abcdef0123456789abcdef",
      "index": "Project launch notes",
      "path": "project-launch.md"
    }
  ]
}
```

The precedence is deliberately narrow:

1. Resolve the normal primary title first.
2. If it is a human-readable title, keep it. A human title always wins.
3. Only when that title is a 16-or-more-character hexadecimal identifier
   after spaces, dots, underscores, and hyphens are removed, consider the
   exact lowercase top-level `index` key on the same item.
4. Use the fallback only when its value is a string and passes the existing
   title normalization, whitespace, specificity, identifier, 500-character,
   local-path, provider-locator, and secret-like metadata checks.

A present but unsafe exact `index` blocks that item with a fixed content-free
reason code. The rejected value is not copied into the item-derived CLI
projection, item warning/error text, draft, or receipt item projection.
File-backed and inline-content manifest items use the same resolver. For an
explicit identifier-shaped primary title, a path-backed item runs this gate
before path resolution or file I/O. Unsupported, missing/unsafe,
unreadable/undecodable, and empty item-file failures report content-free
reason text without the item path or filename. Item paths must be strictly
export-relative: POSIX absolute, UNC, Windows drive-absolute or drive-relative,
parent-traversing, and resolver-failure paths all fail before a file read.
Discovery derives the stored relative path from the same guarded resolved
root/path pair, rather than resolving the item again after reading it.

For a blocked fallback, every user-derived item identity field in the public
preview and receipt preview is replaced by
`<withheld:private_metadata_alias>`. This closes aliases through the primary
title, effective `external_id`, raw `id`, source path, source URL, content
hash, zettel id, and target path. Numeric and other scalar item ids are
compared through the same effective string form that the importer uses.

`facets.source_page_id` remains private even when another public field has the
same value. Such aliases are withheld from previews and receipts. If a
`source_page_id` would become either an explicit or deterministic generated
zettel id and therefore a public filename, the Notion item blocks with
`source_page_id_aliases_public_target_path` before any draft or receipt is
written. Once a blocked target path is withheld, WOM does not probe that raw
path for an existence conflict.

This alias boundary covers the seven item identity fields (`external_id`,
`title`, `source_path`, `source_url`, `sha256`, `zettel_id`, and
`target_path`) plus generated target-path safety. It is not a byte-global
coincidence scrubber. Independently supplied operational/provenance metadata,
including the `--export` path, target archive id, and `--reviewed-by` value,
keeps the existing truthful import/receipt contract even if an operator
deliberately supplies text that happens to equal a protected item value.
Treat those CLI values as intentional receipt metadata.

This fallback does not interpret:

```text
Index
properties.index
properties.Index
rich-text arrays
pages.index.jsonl
```

It does not apply to Google Drive items or directory-only Markdown imports. It
does not create `facets.index`, add `source_index_path`, consult
`source_page_id`, call Notion, read a provider mirror, improve the generated
search index, or rewrite any existing inbox or canonical zet.

An approved import uses one frozen discovery projection for planning and
writes inside that single call. This prevents a manifest edit during that
call from changing a title beneath the already selected zettel id and receipt
path. It does **not** make a later separately approved CLI invocation
digest-bound to an earlier dry-run. Run the approved invocation only after
reviewing the current preview and source export.

## Google Drive Export

For Google Drive, v1 expects files exported to Markdown or text. A manifest can preserve Drive metadata:

```json
{
  "source_system": "google_drive",
  "items": [
    {
      "external_id": "gdrive:file:example",
      "title": "Example",
      "path": "example.txt",
      "url": "https://drive.google.com/file/d/example/view"
    }
  ]
}
```

Then run:

```text
archive import-external <archive> --source google_drive --export <manifest.json> --dry-run
```

## What Gets Written

Approved import writes:

```text
inbox/zet_import_<source>_<hash>.md
receipts/import/<source>_<fingerprint>.external-import.json
```

The draft frontmatter records:

```text
source_system
external_id
source_path
source_url
sha256
source_refs, when the manifest supplies explicit safe object refs
```

The receipt records the reviewed import batch and the paths created.

When the v0.3.285 Notion fallback is selected, the safe `index` string becomes
the new draft's ordinary title. The importer does not persist a separate index
facet or source-index field.

## Source Ref Preservation

From v0.3.105, approved imports preserve explicit safe object refs from manifest
metadata into the imported draft's `source_refs`.

Accepted manifest fields:

```text
object_id
source_object_id
approved_object_id
target_object_id
objet_ref
source_refs[] with object_id or objet_ref values
```

Dry-run output reports `source_ref_count` and `source_refs_preserved`, but does
not echo the object id values in the batch preview.

The importer does not treat the imported text body hash as an object ref, does
not turn provider URLs into object refs, reads no object bytes, and calls no providers.

## MCP Boundary

MCP exposes only:

```text
external_import_plan
```

MCP does not expose an external import apply tool.

Future live API import should be a separate opt-in network-enabled provider phase.

