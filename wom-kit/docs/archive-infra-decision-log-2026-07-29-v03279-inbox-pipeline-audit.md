# Decision Log: v0.3.279 Inbox Pipeline Audit

Date: 2026-07-29
Status: implemented

## Context

Letter 103 showed that location-only AI guidance let a direct Markdown write
to `inbox/` look superficially compliant. v0.3.278 fixed the live command
routing, but historical inbox drafts still needed a human-review signal.

Metadata alone cannot prove which executable wrote a file. In particular, a
known official v0.3.275 unprofiled `create-draft` result has no optional
`draft_creation` block.

## Decision

Add CLI-only:

```text
archive inbox-pipeline-audit <archive-root> --dry-run --format json
```

Classify bounded top-level inbox Markdown frontmatter as:

- `pipeline_shape_consistent`;
- `possible_out_of_pipeline_draft`;
- `insufficient_evidence`.

Use current deterministic `create-draft` output shape only as compatibility
evidence. This is not proof of command execution; no classification proves
which writer ran.

Default findings expose stable ordinals, path SHA-256 values, and content-free
reason codes. They expose no raw path, zettel id, title, actor, source value,
or body text.

Add one aggregate warning to full Doctor for possible cases. Do not run the
whole-inbox audit during unrelated scoped validation.

Extend the read-only AI routing contract to:

```text
wom-kit/ai-command-path-routing/v0.2
```

## Consequences

- Owners receive a visible, repeatable signal for the Letter 103 bypass shape.
- Known official historical output is not falsely rejected merely because
  optional approval metadata is absent.
- Strict Doctor can stop unattended “all healthy” claims when possible cases
  need review.
- No historical draft is changed automatically.
- Any future repair remains a separate approval-gated release.

## Related Documents

- [Inbox Pipeline Audit](inbox-pipeline-audit.md)
- [AI Command-Path Routing](ai-command-path-routing.md)
- [v0.3.279 release note](releases/v0.3.279.md)
