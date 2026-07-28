# Archive Infrastructure Decision Log: v0.3.275 Title Revert Recovery Plan

Date: 2026-07-28
Status: accepted and implemented

## Context

v0.3.274 can safely compensate one completed title-remap receipt and retains a
private revert journal plus the common title lock after a hard exit. Its audit
can distinguish an unstarted revert, a partial revert, complete canonical
restoration without a receipt, divergent evidence, and verified completion
with stale transaction evidence.

The older title recovery planner and executor were designed for interrupted
uncommitted apply transactions. Reusing their rollback direction for a
reviewed compensation would be unsafe and semantically wrong.

## Decision

Add a separate CLI-only, read-only
`zet-title-remap-revert-recovery-plan`.

- Require `--dry-run`; never provide an approve mode in this release.
- Reuse the complete bounded apply/revert evidence audit.
- Select only `operation: revert` journals.
- Map every complete state to one fixed content-free decision.
- Continue a partial reviewed revert only toward verified prior bytes.
- Treat a fully restored batch without its compensation receipt as a future
  receipt-finalization case.
- Treat exact verified completion residue as a future cleanup-only case.
- Treat invalid, divergent, unverified-receipt, unsafe-snapshot, and unsafe-lock
  evidence as `manual_forensic_hold`.
- Report a missing common lock as a future reacquisition requirement.
- Keep every action non-executable in v0.3.275 with
  `execution_implemented: false` and `safe_to_execute_now: false`.
- Keep the older apply recovery planner and executor closed to revert cases.

## Consequences

An operator can now understand the one safe future direction for a retained
title-revert journal without hand-editing evidence or accidentally invoking
the apply recovery executor. The plan digest and case SHA-256 can become the
approval boundary of a later dedicated executor.

No canonical zet, receipt, journal, lock, snapshot, or manifest is written,
deleted, finalized, resumed, or repaired in this release.

## Standards Basis

- Git revert preserves the original committed history and records a distinct
  compensating operation:
  https://git-scm.com/docs/git-revert.html
- The compensating transaction pattern requires current-state checks,
  idempotent steps, resumability, and end-to-end audit:
  https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction
