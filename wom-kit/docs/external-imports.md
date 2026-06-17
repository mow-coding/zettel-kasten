# External Imports

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
archive import-external --approve --reviewed-by ...
inbox drafts + import receipt
```

## Notion Export

Export Notion pages as Markdown, then run:

```text
archive import-external <archive> --source notion --export <notion-export-folder> --dry-run
```

Apply after review:

```text
archive import-external <archive> --source notion --export <notion-export-folder> --approve --reviewed-by person:me
```

Each Markdown or text file becomes one draft zettel in `inbox/`.

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

