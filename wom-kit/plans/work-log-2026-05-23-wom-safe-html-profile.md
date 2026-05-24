# Work Log: v0.2.14 WOM Safe HTML Profile

Date: 2026-05-23

Status: public-safe work log

## Context

The user corrected and refined the product language around three terms:

```text
WOM = the whole system / worldview / open infrastructure
zet = the unit document minted inside a zettel-kasten
ZET = the zettel-kasten-based communication layer / service / protocol
```

The user also emphasized that `zet` should not be written as a title-case product word. `zet` stays lowercase when it means the minted document. `ZET` stays uppercase when it means the communication layer that can become messenger, SNS/feed, or collaboration.

## Design Shift

Earlier v0.2 documents treated the practical `zet` body as Markdown-compatible text plus metadata. That remains valid for authoring and import compatibility.

The new clarification is that Markdown-only should not be treated as the permanent ceiling.

The reason is product-level, not cosmetic:

- the current zettel-kasten is AI runtime / CLI / MCP centered,
- that is powerful for AI-assisted local memory work,
- but it is not a full UI/UX surface for every human workflow,
- WOM should let users and developers build their own zettel-kasten and `ZET`-based SaaS layers,
- those future SaaS layers may need galleries, feeds, workspaces, media viewers, dashboards, and domain-specific renderers.

Therefore, the long-term canonical/interchange/rendering target should be a security-conscious HTML profile rather than Markdown-only storage.

## Decision

Add WOM Safe HTML Profile as a public design baseline.

The phrase does not mean arbitrary HTML.

It means a governed profile that should eventually define:

- allowed semantic elements and attributes,
- blocked unsafe elements and attributes,
- deterministic AI-readable text extraction,
- source object references by `object_id`, hash, or manifest ref,
- accessibility requirements,
- deterministic replay and hashing expectations,
- safe CSS/presentation hooks,
- a clear boundary between canonical archive memory and interactive SaaS/view layers.

## Compatibility

This batch intentionally does not migrate existing zets or change CLI/MCP behavior.

v0.2 compatibility stays:

```text
authoring/import format = Markdown-compatible zets
long-term target = WOM Safe HTML Profile
```

Future batches may add a validator or Markdown-to-WOM-Safe-HTML dry-run, but this work log records only the documentation/spec baseline.

## Files Updated

Public-facing updates include:

- `README.md`
- `README.ko.md`
- `CHANGELOG.md`
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `CITATION.cff`
- `wom-kit/README.md`
- `wom-kit/docs/concepts/wom-safe-html-profile.md`
- `wom-kit/docs/concepts/wom-safe-html-profile.ko.md`
- `wom-kit/docs/concepts/naming-and-terminology.md`
- `wom-kit/docs/concepts/naming-and-terminology.ko.md`
- `wom-kit/docs/concepts/product-philosophy.md`
- `wom-kit/docs/concepts/product-philosophy.ko.md`
- `wom-kit/docs/concepts/foundational-product-whitepaper.md`
- `wom-kit/docs/concepts/foundational-product-whitepaper.ko.md`
- `wom-kit/docs/concepts/zet-sharing-lifecycle.md`
- `wom-kit/docs/concepts/zet-sharing-lifecycle.ko.md`
- `wom-kit/docs/public-documentation-map.md`
- `wom-kit/docs/public-documentation-map.ko.md`
- `wom-kit/docs/releases/v0.2.14.md`
- `wom-kit/specs/zettelkasten-zet-product-blueprint.md`
- `wom-kit/specs/zettelkasten-zet-implementation-research.md`

## Explicit Non-Goals

This batch does not implement:

- Markdown-to-HTML conversion,
- WOM Safe HTML validation,
- HTML migration,
- UI,
- custom SaaS scaffolding,
- live sharing,
- P2P transport,
- external provider API sync.
