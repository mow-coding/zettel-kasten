# Decision Log: Digest-Bound Content-Change Review

Date: 2026-07-13
Decision: accepted for v0.3.230

## Context

Reconcile already classified content drift and required a named reviewer plus
an explicit content-change acknowledgment. It did not, however, give the human
a structured evidence order, and an approval was not cryptographically tied to
the exact bytes that person had reviewed. A file or receipt could change after
the dry-run while remaining in the broad `content_change` class, making an old
acknowledgment appear applicable to new evidence.

## Decision

- Return a content-free `human_review_plan` whenever either reconcile command
  classifies a result as `content_change`.
- Order evidence by role and expose only archive-relative paths, presence,
  SHA-256 values, changed field/ref names, and fixed instructions.
- Require the human to choose `intentional_change`, `unintentional_change`, or
  `uncertain`; never infer approval from a classifier or another target.
- Hash the technical plan evidence as `review_plan_sha256`.
- Require `--reviewed-plan-sha256` for content-change approval, recompute it
  from current evidence before writing, and fail closed on any mismatch.
- Record the reviewed digest in in-place provenance and the immutable audit
  receipt. Preserve `--strip-bom` in every generated command when requested.
- Leave `format_drift` approval compatible and keep all MCP/provider surfaces
  unchanged.

## Consequences

A human can now review sensitive content locally without copying it into a
diagnostic transcript, and WOM-kit can prove that the approved evidence did not
change between dry-run and apply. The digest does not decide whether content is
correct; the named human remains responsible for that judgment. Existing
content-change scripts must add the digest produced by their reviewed dry-run.
