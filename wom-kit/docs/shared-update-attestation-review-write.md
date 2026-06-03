# Shared Update Attestation Review Write

Status: v0.3.0 CLI-only approval-gated write

## Purpose

This command records the first narrow v0.3.0 receiver-side write boundary.

It lets a human/operator record a local review decision for a shared update record that already passes:

```text
archive shared-update-record-review --dry-run
```

The command writes only:

```text
shared-updates/attestation-reviews/<case-id>.json
receipts/shared-updates/<case-id>.shared-update-attestation-review.json
```

The case id is derived from the source shared update record hash. The write refuses overwrite/replay in this release.

## CLI

```bash
archive shared-update-attestation-review <archive-root> --record <archive-relative-json> --decision <attest|needs_more_review|reject> --reviewed-by <safe-actor-id> --approve --format json
```

`--approve` is required. Without it, the command returns `ok: false` and writes nothing.

`--reviewed-by` is required with `--approve` and must be a safe non-secret actor id such as `person:reviewer`.

## Decision Meaning

Supported decisions:

- `attest`
- `needs_more_review`
- `reject`

In v0.3.0, `attest` means only:

```text
a local human review decision was recorded
```

It does not mean the shared update is trusted, imported, accepted, signed, anchored, published, transported, projected, or proven publicly.

## Safety Boundary

The command reuses `zet_shared_update_record_review_preview` before writing. If that preview blocks, this write blocks.

The write stores safe metadata only:

- lifecycle action,
- source shared update record path,
- source shared update record SHA-256,
- receiver archive id,
- reviewer id,
- decision,
- policy reused from the preview,
- timestamp,
- record and receipt refs/hashes.

It must not echo or persist:

- shared update body text,
- review note body text,
- local absolute paths,
- provider URLs,
- raw tokens,
- secrets,
- private source locations.

## Closed Scope

This command does not implement:

- real ZET transport,
- key creation,
- key-sharing registry,
- radio-frequency access,
- mirroring payload or delivery,
- neighbor feed update,
- automatic renewal,
- trust graph mutation,
- import,
- acceptance,
- anchor/apply,
- signature,
- public proof anchoring,
- DID/wallet/key custody,
- provider calls,
- WordPress publishing,
- projection write or projection receipt,
- queues/workers,
- payment, staking, consensus, blockchain, token, or system token behavior,
- model training, backpropagation, or full-auto execution.

## MCP Boundary

MCP exposes no write/apply/approve tool for this boundary.

MCP may still use read-only preview tools:

```text
zet_shared_update_record_review_preview
zet_shared_update_record_review_index
```

## Upgrade

No private archive migration is required.

