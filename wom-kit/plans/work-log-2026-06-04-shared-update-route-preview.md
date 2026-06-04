# Work Log: v0.3.1 Shared Update Route Preview

Date: 2026-06-04
Status: implemented for release

## Goal

Add a narrow read-only receiver-side route preview for one local shared update record.

The preview should answer only this question:

```text
After the shared update record passes the existing metadata-only review gate,
which route could a human consider next: delegate, attest, anchor, or none?
```

## Implemented

- Added CLI `shared-update-route-preview`.
- Added service `shared_update_route_preview`.
- Reused `zet_shared_update_record_review_preview` before route selection.
- Returned route pointer fields for `delegate`, `attest`, `anchor`, and `none`.
- Returned `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`.
- Kept the route preview dry-run only with `would_change: []`.
- Added hardening so free-form or hostile proposed-action metadata is not echoed as a route.
- Added regression coverage for dry-run enforcement, unsafe record paths, hostile metadata, free-form proposed actions, and route-token selection.
- Updated public docs, version metadata, repository-root shim metadata, release note, capability matrix, and runtime skill guidance.

## Safety Boundary

The new preview does not create trust, import, acceptance, attestations, signatures, anchors, public proof, provider sync, projection, feed updates, receipts, real ZET transport, queues/workers, wallet/key custody, payment/staking/consensus/blockchain/token behavior, model training, backpropagation, or full-auto behavior.

Body text, local absolute paths, provider URLs, tokens, secrets, private source locations, and unsafe free-form route metadata are not echoed.

MCP exposes no shared-update route write/apply/approve tool and no new shared-update route MCP tool for this boundary.

## Verification Plan

- Run full WOM-kit unit tests.
- Run strict doctor through both CLI paths.
- Run release readiness and hygiene tools.
- Run `git diff --check`.
- Run route-preview regression and hostile-metadata checks.
