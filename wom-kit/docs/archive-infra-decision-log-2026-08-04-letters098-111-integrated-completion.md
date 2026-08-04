# Decision: Complete Letters 098-111 In One Integrated Release Train

Date: 2026-08-04

## Context

The remaining beta feedback had accumulated faster than repeated
one-feature release, audit, and tester-contact loops could close it. The
engineering standard must remain strict, but strictness does not require
repeating the same release ceremony for every letter.

## Decision

Implement all source-confirmed public work from Letters 098-111 on one branch
and ship it as one release:

- use focused tests while developing;
- keep every write bounded, review-gated, digest-bound, and recoverable;
- run the full cross-platform release gate once after the integrated change is
  complete;
- ask beta testers for one consolidated real-use pass only after the public
  wheel is installed and verified.

Letter-specific private corpora and external-host actions are not pulled into
the public repository. Unknown or unreproduced client state remains an
explicit evidence boundary.

## Consequences

- Test confidence is preserved while duplicate CI and release work is reduced.
- New workflows share one implementation module and common content-free,
  locking, snapshot, receipt, and plan-hash conventions.
- Batch capture promises per-item convergence rather than false atomicity.
- Reference markup is never silently discarded: it either binds to reviewed
  durable identity or blocks.
- The same course's next week is `continues`; a generic process's next step is
  `sequence`. Both remain single-edge human decisions.
- Non-owner actors use registered Principal records. Adoption does not replace
  archive ownership, and an in-use Principal cannot be removed.
- Vendored base link types support selected adoption and exact receipt-bound
  partial revert while the adopted record remains unchanged and unused.
  Valid revert receipts advance a deterministic adoption generation so a later
  re-adopt and second revert cannot collide with the first receipt pair.
- Recurrence stays a coordinate, event grouping requires an existing anchor,
  and private Notion joins use `facets.source_page_id`, never a mirror alias.
- The first beta contact after this decision covers the whole integrated
  release, not an intermediate subset.

Longer implementation guide:
[`letters098-111-completion.md`](letters098-111-completion.md).
