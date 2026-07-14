# Archive Infrastructure Decision Log: v0.3.234 Canonical Revision Plan

Date: 2026-07-14
Decision: accepted for v0.3.234

## Context

v0.3.231 through v0.3.233 established explicit first-read readiness,
publication-time abstract review, and later abstract/body freshness evidence.
WOM still lacked an ordinary path for intentionally correcting canonical
knowledge before editing the canonical file.

`remint-reconcile` must remain a recovery and receipt-repair surface for drift
that already happened. It must not become the recommended authoring workflow.

## Decision

- Add one single-zet read-only `zet-revision-plan` before an approved writer.
- Require a complete private Markdown proposal under
  `.wom-scratch/revisions/`.
- Bind current bytes, proposal bytes, normalized proposal semantics, change
  categories, and pending abstract/body review evidence into one plan digest.
- Freeze archive/zet identity, creation metadata, mint/promotion/revision
  metadata, and original creator metadata.
- Reuse the current publication safety checks for explicit abstract, private
  body locators, allowed edges, required provenance/visibility, and local
  quality blockers.
- Return no private content or actual id/path value.
- Ship no canonical writer in this release. The writer is a separate safety
  rung and must replay every binding before an atomic write and immutable
  receipt.

## Consequences

The normal correction path now starts before canonical mutation, but does not
yet complete it. Operators gain a safe review packet without being encouraged
to edit canonical files manually. The next release can implement the writer
against a stable tested plan instead of combining two new trust boundaries at
once.
