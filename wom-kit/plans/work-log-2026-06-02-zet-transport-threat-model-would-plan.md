# Work Log: v0.2.59 ZET Transport Threat Model And Would-Plan

Date: 2026-06-02
Status: implemented for review

## Goal

Add a conservative ZET transport threat model and a local dry-run would-transport planner without opening real transport.

The planner helps an AI runtime or human operator reason about future `key-sharing`, `radio-frequency`, or `mirroring` risks after a local shared update record passes the existing single-record review preview policy.

## Implemented

- Added service `zet_transport_would_plan`.
- Added CLI `archive zet-transport-plan <archive-root> --record <archive-relative-json> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`.
- Added MCP tool `zet_transport_would_plan`.
- Added focused CLI and MCP tests.
- Updated version metadata to `0.2.59`.
- Added public docs and release notes.

## Safety Decisions

- Dry-run is required.
- The record path must be archive-relative and contained under the archive root.
- Absolute paths, URL-like paths, traversal, UNC paths, NUL bytes, provider URLs, tokens, secrets, and private local paths are blocked by the reused review policy.
- The planner reads one local JSON record only.
- The planner reuses the v0.2.56 single-record review preview policy before producing method-specific planning output.
- Body text is not echoed.
- `would_change` remains empty.
- Closed flags stay false for transport, key creation, radio-frequency access, mirroring payloads, provider calls, queue jobs, workers, neighbor feed updates, trust, import, acceptance, attestation, signature, anchor, projection write, and receipt write.

## Deferred

- Real ZET transport.
- Key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, delivery receipts, queues, workers, neighbor feed updates, recommendation execution, receiver-side renewal writes, trust/import/acceptance, attestation/signature writes, anchors, provider calls, projection writes, payments, blockchain, model training, backpropagation, and full-auto behavior.

## Verification Plan

- Run full WOM-kit unit tests.
- Run strict doctor through both CLI paths.
- Run release readiness, public link, Korean product-language, and privacy hygiene checks.
- Run `git diff --check`.
- Run naming, privacy, release-note link, code-boundary, and safety-boundary scans.
