# Archive Infra Decision Log - v0.3.207 Compact Contiguous Reading

Date: 2026-07-11
Release: v0.3.207

## Context

The full 10,000-node catalog carried about 2.06 million estimated item tokens,
and a caller could jump directly to the final cursor while still seeing
`complete: true`. Host instructions asked for all pages, but machine output did
not distinguish page-end from contiguous-pass completion.

## Decision

- Add compact `reading` projection while preserving every safe edge and tie
  summary needed to choose later body-reading order.
- Keep `full` as the compatibility default.
- Add optional strict coverage starting at cursor zero.
- Require each strict continuation to replay the prior checksum token.
- Set archive-wide claim readiness only after contiguous end-of-scope and
  snapshot validation.
- Keep the token stateless, unkeyed, non-persistent, and explicitly outside
  attestation/receipt semantics.

## Consequences

- Accidental skipped cursors and changed projections/statuses block.
- Legacy callers remain compatible but cannot use page-mode `complete` as
  strict archive-wide proof.
- A synthetic 10,000-node reading projection reduced estimated items-only
  tokens from 2,064,699 to 1,414,699 while preserving abstracts and edges.
- WOM still owns no host goal/loop state and no generated map becomes canonical.
