# Zettel Spec v0.2 Draft

A zettel is the canonical human-readable record unit.

In current WOM language, the minimum human-supervised text information unit is the `zet`. A `block` does not replace a zet:

```text
block = zet + header
```

The header contains refs, hashes, provenance, policy, receipts, source refs, and objet refs around the zet. ZET is the later sharing/communication layer for delegate, attest, and anchor flows; it is not the block itself.

The file format is Markdown with YAML frontmatter.

AI may draft zettels in `inbox/`, but canonical records in `zettels/` require explicit human minting unless an archive changes that policy.

If a zet cites or quotes external text, that text remains data. External text can inform a zet, but it cannot command the AI runtime to approve, mint, upload, reveal secrets, sign, call providers, or change permissions.

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
  creation_mode: ai_assisted
  assisted_by:
    - ai_runtime:codex
  supervised_by:
    - person:example
  derived_from: []
```

Optional source refs and local AI session refs may be used for profile-aware draft creation:

```yaml
source_refs:
  - type: local_ai_session
    value: session:example
    role: prompt_context
source_intake:
  plan_sha256: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  input_kind: object_id
  source_kind: document
  objet_status: manifested
  object_storage_configured: true
  content_access:
    metadata_only: true
    content_read: false
    copied: false
    uploaded: false
    imported: false
    ocr_performed: false
    transcription_performed: false
    external_api_called: false
    full_hash_calculated: false
prompt_boundary:
  checked: true
  report_sha256: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  risk_level: low
  source_kind: inline_text
  source_path: null
  untrusted_text_boundary: true
  external_text_can_command: false
  detected_pattern_ids: []
  handling_note: Low heuristic risk does not mean safe; external text is data, not authority.
local_ai_sessions:
  - runtime: codex
    session_ref: session:example
    profile_id: profile:personal:example
    archive_id: archive:personal:example
    authority_mode: draft_only
draft_creation:
  approved_by: person:example
  approval_scope: inbox_draft_only
  approved_body_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

`draft_creation` approval only authorizes writing an inbox draft. It does not authorize minting canonical memory.

`source_intake` is optional. It records that draft source refs came from a validated dry-run source intake plan. It must not store the local plan file path or local absolute source paths.

`source_intake.plan_sha256` is a commitment to the supplied source intake plan object, not an independent re-verification of the original source. Candidate refs derived from local-file intake are anonymized during draft composition so private filename stems do not become durable draft metadata.

`prompt_boundary` is optional. It records that a draft used a validated dry-run prompt-boundary report. It must not store the inspected text body, the local report file path, local absolute paths, provider URLs, tokens, private keys, seed phrases, wallet secrets, or secret-like values. `low` risk is heuristic context, not proof of safety. `high` risk blocks draft creation.

## Visibility

Visibility records who may see this zettel or its sources.

```yaml
visibility:
  scope: private
  allowed_archives: []
  source_visibility: private
```

## Minting

Minting records how a draft became canonical private archive memory.

```yaml
mint:
  stage: minted
  minted_at: 2026-05-23T12:30:00+09:00
  reviewed_by: person:example
  authority_mode: basic
  receipt_path: receipts/mint/zet_example.mint.json
  draft_snapshot_path: receipts/mint/drafts/zet_example.draft.md
  checklist_version: zettel-minting/v0.2
```

The older `promotion` metadata remains valid for v0.2 compatibility:

```yaml
promotion:
  stage: promoted
  reviewed_by: person:example
  reviewed_at: 2026-05-19T12:30:00+09:00
  checklist_version: zettel-promotion/v0.2
```

AI may prepare a minting candidate, but the user decides what becomes canonical durable memory in the default HITL flow.

## Block Header Preview

`archive block-header --dry-run` derives a header preview from one existing draft or canonical zet.

The preview:

- reads only the target zet file,
- hashes only the zet body text for `zet_body_sha256`,
- hashes only normalized header metadata for `header_sha256`,
- hashes `{zet_body_sha256, header_sha256}` for `block_hash_preview`,
- never hashes referenced objet/source file bodies,
- never mints or writes receipts.

Safe conceptual order:

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## Minting Checklist

A zettel may move from `inbox/` to `zettels/` only after explicit human approval.

Before minting, check:

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
