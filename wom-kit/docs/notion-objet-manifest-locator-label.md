# Notion Objet Manifest Locator Label

Status: v0.4.0 dry-run-only manifest locator label preview

`archive notion-objet-manifest-locator-label --dry-run` previews one reviewed,
non-secret Notion locator fingerprint for an existing object manifest record.
In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before private manifest or
target reads and adds nothing.

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

Alias:

```text
notion-objet-locator-label
```

## Historical Write Layout

v0.3 approved mode used this layout. v0.4.0 creates neither file:

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

This preview is CLI-only. MCP exposes no write tool for it. Approval reads no
private target and writes no manifest row or receipt.

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
`archive notion-objet-link-rewrite-plan --dry-run`, then only
`archive notion-objet-link-convert --target-mode embed_edge --dry-run` to
preview the conversion. In v0.4.0 conversion approval returns
`compound_exact_human_approval_binding_required` before private target read or
mutation and writes no edge or receipt. A separately reviewed single
`zettel-edge` retains its operation-specific exact-human path. Body rewrite
remains separate future work.
