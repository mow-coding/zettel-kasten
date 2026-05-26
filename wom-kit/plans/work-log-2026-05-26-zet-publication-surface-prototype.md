# ZET Publication Surface Prototype Work Log

Date: 2026-05-26
Status: documentation and sanitized example

## Context

This change records a UX insight from a real AI-assisted archive workflow, without publishing the user's private conversation, credentials, provider tokens, local paths, or personal archive contents.

The source workflow was:

```text
desktop AI conversation
-> AI-generated session summary
-> human review
-> private archive-oriented post
-> WordPress.com private blog publication
-> mobile/web browsing and search
```

## What Changed

Added:

- `docs/zet-publication-surface-prototype.ko.md`
- `examples/zet-publication-surface/README.ko.md`
- `examples/zet-publication-surface/zet-publication-envelope.example.json`
- `examples/zet-publication-surface/wordpress-title.example.txt`
- `examples/zet-publication-surface/wordpress-post.safe-html.example.html`
- `examples/zet-publication-surface/wordpress-publish.example.ps1`

Updated:

- `docs/public-documentation-map.ko.md`

## Product Insight

The WordPress archive workflow is useful as a prototype for a future `ZET` publication surface.

It shows that users can understand:

```text
AI conversation
-> reviewed archive summary
-> readable publication surface
-> later search and rereading
```

The important product boundary is:

```text
posting is not minting
external URL is not canonical zet identity
provider post is projection, not archive memory
```

This supports the existing WOM principle:

```text
private archive first
sharing/projection as a separate explicit action
```

## Safety Boundary

The example is intentionally sanitized:

- no real WordPress site URL,
- no OAuth token,
- no client secret,
- no local filesystem path,
- no raw AI conversation,
- no private source object,
- no real receipt from a personal archive.

The example PowerShell helper defaults to dry-run behavior and requires `-Approve` before a provider call.

## Next Step

A future implementation slice could add a local-only projection preview command:

```text
archive projection-plan <archive-root>
  --zet <zet-id-or-path>
  --surface wordpress_private_blog
  --dry-run
  --format json
```

That command should preview:

- projection body,
- target surface,
- scope/redaction gate,
- receipt preview,
- provider call plan.

It should not call WordPress, write receipts, mint zets, delegate capabilities, attest foreign blocks, or anchor anything unless a later explicit approval path is designed.
