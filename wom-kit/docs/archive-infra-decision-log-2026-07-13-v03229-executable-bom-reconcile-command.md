# Decision Log: Executable BOM Reconcile Command

Date: 2026-07-13
Decision: accepted for v0.3.229

## Context

The v0.3.228 actionable full-Doctor result successfully retained a
`zettel_has_bom` finding and its suggested command. The finding path already
identified the canonical zet, but the command still contained `--zettel-id
<id>`. That forced a human or AI to copy or infer an identifier before even
running the read-only classifier, weakening the promise that a completed Doctor
result is directly actionable.

## Decision

- Build the BOM reconcile selector from the id parsed from canonical
  frontmatter, not from the filename.
- Accept the id only through the existing safe zet-id grammar.
- Emit the complete redacted diagnostic dry-run when the id is valid.
- Keep the finding and hint but omit `suggested_command` when the id is missing
  or unsafe. Never emit an unresolved placeholder or shell-unsafe selector.
- Preserve the existing `--diagnostic-only` boundary in AI-facing results.
  Before approval, require a separate review-visible dry-run without that flag.
- Keep the existing classifier and approval gates unchanged: `format_drift`
  requires format review, while `content_change` requires explicit human
  content review and acknowledgment before approval.
- Treat BOM `remint-reconcile` and retired-draft receipt
  `retire-draft-reconcile` as independent decisions with separate blockers,
  classifications, reviewers, and receipts.

## Consequences

A completed full-Doctor handoff can now provide a copyable, read-only BOM
classifier without another broad scan or manual id substitution. The change
does not approve, apply, or broaden any write. Unsafe identity metadata reduces
the output rather than producing a plausible but untrustworthy command.
