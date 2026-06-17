# Notion Objet Manifest Locator Label

Status: v0.3.100 approval-gated manifest locator label write checkpoint

`archive notion-objet-manifest-locator-label` adds one reviewed, non-secret
Notion locator fingerprint to one existing object manifest record.

It exists for this gap:

```text
zettel body contains a Notion locator fingerprint
object manifest knows the object came from Notion
object manifest does not preserve the locator fingerprint
notion-objet-link-index therefore reports 0 manifest matches
```

The command does not store or print the Notion URL. It stores only the
reviewed `sha256:` locator fingerprint or its 64-character hex value.

## Command

Preview:

```powershell
archive notion-objet-manifest-locator-label <archive-root> `
  --object-id sha256:<64 lowercase hex characters> `
  --locator-fingerprint sha256:<64 lowercase hex characters> `
  --dry-run `
  --format json
```

Approve:

```powershell
archive notion-objet-manifest-locator-label <archive-root> `
  --object-id sha256:<64 lowercase hex characters> `
  --locator-fingerprint sha256:<64 lowercase hex characters> `
  --approve `
  --reviewed-by person:reviewer `
  --format json
```

Alias:

```text
notion-objet-locator-label
```

## What It Writes

Approved mode rewrites only:

```text
objects/manifests/files.jsonl
receipts/objects/notion-locator-labels/*.notion-objet-manifest-locator-label.json
```

If the manifest record has no locator field yet, WOM-kit adds:

```json
{
  "provenance": {
    "provider_locator_sha256": "<64 lowercase hex characters>"
  }
}
```

If a different `provider_locator_sha256` already exists, WOM-kit preserves it
and adds a list field:

```json
{
  "provenance": {
    "provider_locator_sha256_values": [
      "<existing 64 lowercase hex characters>",
      "<new 64 lowercase hex characters>"
    ]
  }
}
```

This lets `notion-objet-link-index` and `notion-objet-link-plan` find manifest
candidates without storing provider locator text.

## Safety Boundary

This command is CLI-only. MCP exposes no write tool for it.

It does not:

- read zettel bodies,
- rewrite zettel bodies,
- write `embed` edges,
- call Notion or any provider,
- start OAuth,
- read real source exports,
- read object bytes,
- write candidate records,
- upload or download media,
- create provider URLs.

Output avoids provider URLs, provider locator text, zettel body text, zettel
titles, frontmatter values, page titles, absolute local paths, account ids,
emails, tokens, and secret values.

## Relationship To Other Notion Objet Tools

Use this after a human has reviewed the selected object and locator
fingerprint.

Then run:

```text
archive notion-objet-link-index <archive-root> --dry-run
archive notion-objet-link-plan <archive-root> --path <zet.md> --dry-run
```

Once the manifest match appears, use
`archive notion-objet-link-rewrite-plan`, then
`archive notion-objet-link-convert --target-mode embed_edge` for a reviewed
`embed` edge write. Body rewrite remains separate future work.
