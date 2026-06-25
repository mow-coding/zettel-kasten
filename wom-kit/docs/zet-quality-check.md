# zet Quality Check

Status: v0.3.145 read-only zet quality checkpoint

`archive zet-quality-check` inspects one draft or canonical zet before it is
treated as durable canonical memory.

It is a local, read-only safety gate for real-use feedback where long projects
mix original material, OCR/parsing work, meeting notes, strategy notes, and
external-facing reports.

## Command

```powershell
archive zet-quality-check <archive-root> `
  --path inbox/example.md `
  --dry-run `
  --format json
```

Alias:

```powershell
archive zettel-quality-check <archive-root> --path inbox/example.md --dry-run --format json
```

## What It Checks

- Project entity rules from optional `zet-quality-rules.yml`.
- Missing or unknown `document_type`.
- Missing or unknown `audience`.
- OCR/parsing metadata that appears to be in the canonical body.
- Markdown tables without reviewed structure or row/source mapping metadata.
- Correction hints without structured `correction_events`.
- Incomplete source acquisition, verification, or rights metadata.
- Derived artifacts without source zettel/source receipt links or sync status.
- Internal working-context residue in external-facing zets or reports.
- Basic viewer-readiness signals such as YAML frontmatter and Markdown tables.

## Project Entity Rules

Archives may add a local project file:

```yaml
entity_terms:
  - id: project_entity_rule
    canonical: APPROVED_CANONICAL_ENTITY
    forbidden:
      - DO_NOT_USE_ALIAS
    severity: blocker
```

When a blocker-severity entity rule matches, `zet-quality-check` reports the
safe rule id and counts. It does not echo the matched term, body text, source
values, provider URLs, local absolute paths, tokens, or secret values.

`mint-zet --dry-run` includes the same `quality_check` summary. It blocks only
for blocker-severity quality issues.

## Suggested Frontmatter

These fields are optional in v0.3.145, but they make the quality gate more
useful:

```yaml
document_type: source_outline
audience: private_self
parse_review:
  table_structure_reviewed: true
  row_mapping: receipts/parse/example.json
correction_events:
  - event_id: correction:example
    status: applied
    applies_to:
      - zettel_body
source_refs:
  - type: external_citation
    value: https://example.org/public-source
    role: citation
    acquired_at: 2026-06-25
    acquired_by: person:me
    acquisition_method: web_review
    verification_status: reviewed
    public_report_allowed: needs_review
    rights_status: unknown
derived_artifacts:
  - artifact_ref: report:example
    source_zettels:
      - zet_example_source_outline
    sync_status: needs_review
```

## Safety Boundary

The command:

- reads one selected zet,
- writes nothing,
- calls no providers,
- does not create revision candidates,
- does not sync external reports,
- does not rewrite frontmatter,
- does not read original object bytes,
- does not echo matched entity terms, body text, source-ref values, provider
  URLs, local absolute paths, tokens, or secret values.

## Still Future

- UI for table structure review and row-level image mapping.
- Automatic revision-candidate creation for already minted zets.
- Full dependency graph from zets to external reports.
- Automatic report staleness detection.
- Audience-aware report rendering.
- Frontmatter-hiding viewer UI.
- Archive status dashboard for draft/canonical/revision/retire states.
