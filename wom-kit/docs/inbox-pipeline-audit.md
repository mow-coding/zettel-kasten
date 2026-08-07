# Inbox Pipeline Audit

Status: implemented in v0.3.279; startup and publication-readiness visibility
added in v0.3.305

## Purpose

WOM routes AI-assisted draft creation through `archive create-draft`.
Historical guidance once said only that AI drafts belong in `inbox/`. An AI
could therefore write Markdown directly to that directory while believing it
had followed the rule.

v0.3.279 adds a conservative read-only signal:

```powershell
archive inbox-pipeline-audit <archive-root> `
  --dry-run `
  --format json
```

Alias:

```text
draft-pipeline-audit
```

The result schema is:

```text
wom-kit/inbox-pipeline-audit/v0.1
```

From v0.3.305, the same bounded frontmatter-only audit is summarized by every
`archive ai-start-here` result as `inbox_attention`. It reports the unpublished
draft count, oldest safely parseable draft age, possible current-pipeline shape
bypasses, and drafts missing an explicit safe abstract or non-empty facets. The
session-start summary returns no title, id, path, body, actor, or source value.
The detailed audit remains the review route; startup visibility is not repair
permission.

## Honest Evidence Classes

The audit does not claim that metadata can prove which process wrote a file.
It uses three evidence classes.

### `pipeline_shape_consistent`

The AI-declared draft has the deterministic structural shape currently emitted
by `archive create-draft`:

- bounded readable frontmatter;
- `status: draft`;
- a safe non-empty `id`;
- exact top-level `inbox/<id>.md` path shape;
- `promotion.stage: captured`;
- `promotion.ready_for_promotion: false`;
- non-empty provenance `created_by`, `created_in`, and `source`;
- a non-empty `assisted_by` list.

This means only that the shape is compatible. A direct writer could copy the
same shape, so this is not proof that WOM executed the command.

### `possible_out_of_pipeline_draft`

The draft declares `provenance.creation_mode` as `ai_assisted` or
`ai_generated`, but one or more current deterministic output facts conflict.
The result returns content-free reason codes such as:

```text
path_not_current_create_draft_shape
promotion_stage_not_captured
assisted_by_missing
```

This is a human-review signal, not an accusation or a repair authorization.

### `insufficient_evidence`

The file is historical, non-AI, ambiguous, symlinked, malformed, unreadable,
or otherwise lacks enough safe metadata for either class. WOM reports that
uncertainty rather than guessing.

## `draft_creation` Boundary

`draft_creation` is optional in the frontmatter schema. The known beta archive
contains an official unprofiled v0.3.275 `archive create-draft` result without
that block. Therefore absence of `draft_creation` is neutral.

When the block is present, the audit checks its current shape:

- non-empty `approved_by`;
- `approval_scope: inbox_draft_only`;
- lowercase 64-character `approved_body_sha256`.

An invalid present block can contribute to a possible-case classification.
Because older official CLI forms could still produce partial optional approval
metadata, that block alone is not authoritative. If it is the only mismatch,
the audit returns `insufficient_evidence`; it accompanies a possible case only
when a deterministic path, promotion, status, provenance, or AI-assistance
shape also conflicts.

## Privacy And Bounds

The audit:

- scans only top-level `inbox/*.md`;
- accepts at most 5,000 drafts;
- reads at most 256 KiB of frontmatter bytes per file;
- stops at the closing frontmatter fence on a valid draft;
- returns at most 500 findings;
- returns path SHA-256 values rather than raw paths;
- does not return zettel ids, titles, actors, source values, or body text;
- records when malformed frontmatter may have caused body bytes to be crossed;
- calls no provider, model, network, index, database, credential store, or Git.

`--max-findings` limits only returned content-free findings. The aggregate
classification still covers every draft within the `--max-drafts` bound. If
the draft population exceeds that bound, the command blocks before scanning
and does not publish a partial classification as complete.

## Doctor Signal

Full `archive doctor` runs the same bounded audit after zettel validation.

- Possible cases produce one aggregate
  `possible_out_of_pipeline_inbox_draft` warning.
- Insufficient-only results produce an informational diagnostic.
- A bounded audit failure produces one `inbox_pipeline_audit_incomplete`
  warning.
- No private draft path is placed in the new aggregate diagnostic.

Because possible cases are warnings, `archive doctor --strict` exits non-zero
until the owner reviews the signal. Scoped validation does not scan unrelated
inbox files.

## No Repair In v0.3.279

This release does not:

- rewrite frontmatter;
- rename a `.draft.md` file;
- add a missing field;
- delete or retire a draft;
- mint or promote anything;
- create a repair receipt.

Do not modify a historical draft merely to make the audit green. Any later
repair must be a separate preview, human approval, exact replay, and receipt
workflow.

## Creation-Time Guard In v0.3.305

The official `create-draft` AI route now blocks before writing when an
`ai_assisted` or `ai_generated` draft lacks an explicit publication-safe
abstract or has empty facets. It also checks bounded inbox frontmatter and
blocks an AI-created same-normalized-title duplicate so the existing unminted
draft can be revised in place. Human-owned rough drafts remain possible and
receive a visible same-title warning rather than an automatic semantic merge.

An arbitrary filesystem writer can still bypass a CLI; WOM does not claim to
be an operating-system access-control service. The runtime skill, archive
templates, creation-time guard, and session-start audit form the four explicit
defense layers.
