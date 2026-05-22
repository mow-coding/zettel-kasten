# Zettel Spec v0.2 Draft

A zettel is the canonical human-readable record unit.

The file format is Markdown with YAML frontmatter.

AI may draft zettels in `inbox/`, but canonical records in `zettels/` require explicit human promotion unless an archive changes that policy.

See also:

```text
specs/zettel-lifecycle.md
zettel-kasten/zettel-rules.yml
```

## Required Frontmatter Fields

```yaml
id: zet_20260519_example
title: Example zettel
created_at: 2026-05-19T00:00:00+09:00
updated_at: 2026-05-19T00:00:00+09:00
archive_id: archive:personal:example
status: canonical
kind: permanent_note
facets: {}
assets: []
edges: []
provenance: {}
visibility: {}
promotion: {}
```

## Status Values

```text
draft
canonical
archived
redacted
```

## Kind Values

`kind` explains what sort of zettel this is.

Recommended values:

```text
fleeting_capture
source_note
permanent_note
record_note
decision_note
meeting_minutes
object_summary
project_note
```

For beginners:

```text
status = where this note is in the lifecycle
kind = what kind of note this is
```

Example:

```yaml
status: draft
kind: fleeting_capture
```

```yaml
status: canonical
kind: record_note
```

## Facets

Facets are stable filter axes for AI retrieval.

```yaml
facets:
  domain: education
  institution: Seoul Example University
  activity_group: course
  record_type: class_note
  school_year: "2025"
  term: spring
```

## Assets

Zettels reference original files by object identity only.

```yaml
assets:
  - object_id: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    role: source_scan
    label: Fake transcript scan
```

Never store B2, R2, S3, Google Drive, or local absolute provider URLs directly inside a zettel.

## Edges

Edges are typed relationships.

```yaml
edges:
  - type: derived_from
    target: zet_20260519_source
    visibility: private_source
```

Suggested edge types:

```text
references
derived_from
shared_with
copied_to
mounted_by
transferred_to
inherited_by
supersedes
redacts
summarizes
applies_to
handover_to
merged_into
forked_from
```

## Provenance

Provenance records where the zettel came from and how it moved.

```yaml
provenance:
  created_by: person:example
  created_in: archive:personal:example
  source: user_conversation
  derived_from: []
```

## Visibility

Visibility records who may see this zettel or its sources.

```yaml
visibility:
  scope: private
  allowed_archives: []
  source_visibility: private
```

## Promotion

Promotion records how a draft became canonical.

```yaml
promotion:
  stage: promoted
  reviewed_by: person:example
  reviewed_at: 2026-05-19T12:30:00+09:00
  checklist_version: zettel-promotion/v0.2
```

AI may prepare a promotion candidate, but the user decides what becomes canonical durable memory.

## Promotion Checklist

A zettel may move from `inbox/` to `zettels/` only after explicit human approval.

Before promotion, check:

```text
1. One clear purpose.
2. Understandable title.
3. Body makes sense outside the original chat.
4. Claims are sourced or marked as personal interpretation.
5. Original files use object_id, not provider URL.
6. Facets are stable enough for retrieval.
7. Edges use allowed link types.
8. Visibility is explicit.
9. Provenance is present.
10. Sensitive content has been reviewed.
```

Idea notes should usually contain one idea. Record notes should usually contain one event, source, object, decision, or meeting.

## Revision Rule

Canonical zettels can be corrected, but meaning-changing edits should preserve history.

Use one of these when a canonical zettel changes meaning:

```text
receipt
superseding zettel
explicit revision note
```
