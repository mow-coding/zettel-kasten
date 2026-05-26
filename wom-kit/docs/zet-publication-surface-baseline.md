# ZET Publication Surface Baseline

Date: 2026-05-26

## Summary

v0.2.45 records the first public baseline for user-selected publication surfaces around ZET.

The core WOM archive remains no-UI and local-first. A zet is still canonical archive memory only after human-supervised minting inside the archive. A publication surface is an outside projection of selected content, not the canonical identity of the zet itself.

WordPress is documented here as one possible user-selected surface because many people already understand posting there. v0.2.45 does not publish to WordPress, call provider APIs, create projection receipts, or add a projection-plan CLI/MCP command.

## Model

```text
canonical archive memory -> selected projection envelope -> user-selected surface
```

The surface can be a blog, static site, feed, newsletter, collaboration tool, or future ZET sharing interface.

The important distinction is:

- minting creates or promotes canonical archive memory,
- posting publishes a projection somewhere outside the canonical archive,
- a surface locator points to the outside projection,
- the zet identity stays in the archive.

## No-UI Core

WOM-kit should not require its own social UI to be useful. The local archive, CLI, MCP read-only checks, receipts, schemas, and docs form the core.

A user can later choose a surface that fits their workflow. That surface may be:

- a WordPress site,
- a static website,
- a private team workspace,
- an RSS/feed layer,
- a future ZET transport surface.

The chosen surface does not become the source of truth.

## Example Envelope

The example files under `wom-kit/examples/zet-publication-surface/` are sanitized placeholders. They show what a future projection envelope might carry without storing secrets, tokens, raw conversations, private source filenames, provider URLs, or local absolute paths.

The example includes:

- a safe projection envelope,
- a possible WordPress title,
- a possible WOM Safe HTML-compatible post body.

All URLs use `https://example.invalid/...`.

## Future Safe Order

The expected future sequence is:

```text
minted zet
-> block header preview
-> publication surface selection
-> projection-plan dry-run
-> scope gate
-> human approval
-> projection receipt preview
-> provider-specific publisher in a later release
```

v0.2.45 stops at documentation and sanitized examples.

## Non-Goals

v0.2.45 does not:

- call providers,
- publish to WordPress,
- create projection receipts,
- implement projection-plan CLI or MCP,
- trust, import, accept, attest, sign, mint, anchor, or transport anything,
- implement ZET transport,
- introduce Redis, backpropagation, model training, full-auto execution, payments, staking, consensus, blockchain, WOM coin, or token mechanics.
