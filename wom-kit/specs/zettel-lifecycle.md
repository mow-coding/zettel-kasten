# Zettel Lifecycle Spec v0.2 Draft

This spec defines how zettels are written, reviewed, minted, revised, and retired in WOM-kit. Older v0.2 material may still say `promote`; `mint-zettel` is the preferred product-facing lifecycle word from v0.2.8 onward.

For beginners: think of this as the rulebook for when an AI note is still a rough memo and when it becomes durable archive memory.

## Design Sources

This lifecycle is adapted for a PC-first AI archive from several public note-system ideas:

- The Niklas Luhmann Archive describes Luhmann's Zettelkasten as about 90,000 notes with a specific organizational structure, used as a theory-development and publication machine.
- The Luhmann digital archive exposes note complexes and link structures, which supports the idea that durable notes need relationships, not only folders.
- Zettelkasten.de and the Ahrens workflow distinguish quick captures from permanent zettels, and emphasize self-contained notes written in one's own words.
- Obsidian's public documentation shows that YAML frontmatter is a practical standard for structured Markdown properties.

Project translation:

```text
Capture freely.
Draft safely.
Mint deliberately.
Preserve provenance.
Link explicitly.
Revise without erasing history.
```

## Paths

```text
inbox/
  Temporary captures and AI drafts.

zettels/
  Canonical zettels that passed minting or legacy promotion.

workbench/
  Optional working area for summaries, outlines, merge drafts, and temporary processing.

receipts/
  Optional audit records for minting, promotion, import, transfer, redaction, and other significant actions.
```

`workbench/` and `receipts/` are recommended but not required by v0.1 templates yet.

## Zettel Kinds

The word `zettel` is broad in this project. Not every zettel must be an abstract idea note.

Recommended kinds:

```text
fleeting_capture
  A quick capture. Usually lives in inbox and may be deleted or minted later.

source_note
  A note about a book, paper, video, web page, document, scan, or original object.

permanent_note
  A self-contained thought or explanation intended to remain useful later.

record_note
  A durable record of an event, document, health record, school record, meeting, or life fact.

decision_note
  A compact decision record with context and consequences.

meeting_minutes
  Chronological notes from a substantial conversation or meeting.

object_summary
  A human-readable summary of one or more original files.

project_note
  A working note tied to an active project. It may later produce permanent notes.
```

For this project, `permanent_note` is not the only canonical zettel kind. A school record, family document summary, or decision log can also be canonical if it is durable, understandable, sourced, and policy-compliant.

## Lifecycle

```text
captured
  Raw idea, file note, conversation fragment, or AI-created draft.

draft
  Structured enough to have frontmatter, but not yet canonical.

promotion_candidate
  Draft is ready for human review.

canonical
  Approved durable zettel in zettels/.

revised
  Canonical zettel was edited while preserving history or receipt.

superseded
  Newer zettel replaces this zettel for current use.

archived
  Kept for history but not active.

redacted
  Sensitive content removed or narrowed for a target archive.
```

The existing `status` field remains simple:

```text
draft
canonical
archived
redacted
```

More detailed lifecycle information may live in:

```yaml
promotion:
  stage: promotion_candidate
  reviewed_by: person:example
  reviewed_at: 2026-05-19T12:00:00+09:00
```

## Draft Creation Rules

AI may create drafts freely when the archive is mounted with write access, but drafts must stay in `inbox/` by default.

A draft should have valid frontmatter even if some values are still empty or tentative.

Minimum draft frontmatter:

```yaml
id: zet_20260519_example
title: Draft title
created_at: 2026-05-19T12:00:00+09:00
updated_at: 2026-05-19T12:00:00+09:00
archive_id: archive:personal:example
status: draft
kind: fleeting_capture
facets: {}
assets: []
edges: []
provenance:
  created_by: ai_runtime:codex
  created_in: archive:personal:example
  source: user_conversation
  creation_mode: ai_assisted
  assisted_by:
    - ai_runtime:codex
  supervised_by:
    - person:example
  derived_from: []
source_refs:
  - type: local_ai_session
    value: session:example
    role: prompt_context
source_intake:
  plan_sha256: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  input_kind: ai_artifact
  source_kind: ai_artifact
  objet_status: ai_artifact
  object_storage_configured: false
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
visibility:
  scope: private
  allowed_archives: []
  source_visibility: private
promotion:
  stage: captured
  ready_for_promotion: false
```

Drafts may contain:

- rough language
- uncertainty
- TODO markers
- unresolved questions
- multiple ideas
- temporary tags

Drafts must not contain:

- provider URLs as canonical file references
- secrets
- raw local absolute paths
- cross-archive private source leakage
- fake certainty about sources

Profile-bound AI draft creation has two approval moments:

```text
create-draft dry-run -> human draft approval -> inbox draft
mint dry-run -> human mint approval -> canonical memory
```

Draft approval is scoped to `inbox_draft_only`. It must not be reused as mint approval.

When a draft cites a v0.2.22 source intake plan, v0.2.23 `create-draft --source-intake-plan` validates that the plan is a successful metadata-only dry-run before merging refs. The draft may store optional `source_intake` metadata, but must not store the local plan file path or follow local source paths from the plan.

When external text influenced a draft, v0.2.27 `create-draft --prompt-boundary-report` validates the dry-run prompt-boundary report before storing optional `prompt_boundary` metadata. The report hash, risk level, source kind/path summary, detected pattern ids, and handling note may be stored. The inspected text body and local report file path must not be stored. `low` risk is not proof of safety, `medium` risk is allowed with warnings, and `high` risk blocks draft creation.

## Block Header Preview

v0.2.24 adds a read-only preview step for the conceptual block model:

```text
block = zet + header
```

The zet remains the minimum human-supervised text information unit. The header is derived from refs, hashes, provenance, policy, receipts, source refs, and objet refs. ZET is the sharing layer that can later delegate, attest, and anchor blocks; it is not the block itself.

`archive block-header --dry-run` reads one target zet file and writes nothing. It does not mint, modify zets, read referenced objet/source file bodies, calculate referenced source hashes, follow provider URLs, or call provider APIs.

Safe order:

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## Profile Wallet Readiness

v0.2.25 records the profile wallet concept without adding real wallet security primitives.

```text
WOM profile -> human-facing selectable profile
WOM node    -> subject/principal in the WOM network
WOM wallet layer -> future signing/capability layer
```

The future wallet layer may become relevant to mint, delegate, attest, anchor, receipts, block headers, and ZET sharing. In v0.2.25, `archive profile-wallet --dry-run` is read-only. It writes nothing, generates no private keys, performs no signing, stores no seed phrases or wallet secrets, calls no blockchain/provider APIs, and grants no mint authority.

## Prompt Injection Boundary

v0.2.26 adds a read-only prompt boundary check for external text that may influence draft, mint, delegate, attest, anchor, or future ZET actions.

```text
External text can inform.
External text cannot command.
```

`archive prompt-boundary --dry-run` treats inspected text as untrusted data. It may flag obvious prompt-injection and unsafe-agent strings, but it is not a complete security classifier. It writes nothing, calls no LLMs, executes no inspected text, calls no providers, and grants no approval authority.

## Promotion Rules

A zettel may be promoted from `inbox/` to `zettels/` only when the user explicitly approves.

Promotion means:

```text
This note is now durable archive memory.
Future AI agents may treat it as part of the canonical record.
```

Promotion checklist:

```text
1. The note has one clear purpose.
2. The title is understandable outside the original chat.
3. The body is understandable months later.
4. Claims are sourced or marked as personal interpretation.
5. Original files are referenced by object_id, not provider URL.
6. Facets are stable enough for retrieval.
7. Edges use allowed link types.
8. Visibility and source visibility are explicit.
9. Provenance explains where the zettel came from.
10. Sensitive content has been reviewed.
```

## One-Idea Rule With Record Exception

Classic zettel practice favors small, self-contained notes. This project follows that spirit, but it also stores life and company records.

Rule:

```text
If the zettel is an idea note, prefer one idea.
If the zettel is a record note, prefer one event, object, meeting, decision, or source.
```

Split a draft when:

- it contains unrelated ideas
- it mixes private diary content with shareable company insight
- it combines source summary and personal conclusion in a way that would leak sources
- it tries to serve several views with incompatible visibility

Do not split only to be clever. A usable record is better than five tiny notes nobody can understand.

## Canonical Body Rules

A canonical zettel body should be:

```text
self-contained
plainly written
short enough to reuse
explicit about uncertainty
linked to related records
clear about sources
```

Recommended body sections:

```markdown
# Title

Main note in plain language.

## Context

Why this exists.

## Evidence Or Source

Source zettels, object_ids, or user conversation context.

## Links

Related zettels and typed relationships.
```

Do not force every zettel to use every heading. Use headings when they make the note easier to understand later.

## Minting Output

When a draft is minted:

```text
status becomes canonical
mint.stage becomes minted
mint.reviewed_by is recorded
mint.minted_at is recorded
mint.authority_mode is recorded
promotion.stage becomes promoted
promotion.reviewed_by is recorded
promotion.reviewed_at is recorded
updated_at is updated
the canonical file is written to zettels/
the original draft remains in inbox/
the mint-time draft snapshot is written to receipts/mint/drafts/
the mint receipt is written to receipts/mint/
```

The `promotion` metadata remains for v0.2 compatibility. New code should prefer `mint` metadata and mint receipts when explaining the product lifecycle.

Recommended canonical frontmatter:

```yaml
id: zet_20260519_example
title: Example canonical zettel
created_at: 2026-05-19T12:00:00+09:00
updated_at: 2026-05-19T12:30:00+09:00
archive_id: archive:personal:example
status: canonical
kind: permanent_note
facets:
  domain: personal
  record_type: thought
assets: []
edges:
  - type: derived_from
    target: zet_20260519_draft_example
    visibility: private_source
provenance:
  created_by: person:example
  created_in: archive:personal:example
  source: user_conversation
  derived_from:
    - zet_20260519_draft_example
visibility:
  scope: private
  allowed_archives: []
  source_visibility: private
mint:
  stage: minted
  minted_at: 2026-05-19T12:30:00+09:00
  reviewed_by: person:example
  authority_mode: basic
  receipt_path: receipts/mint/zet_20260519_example.mint.json
  draft_snapshot_path: receipts/mint/drafts/zet_20260519_example.draft.md
  checklist_version: zet-mint/v0.2
promotion:
  stage: promoted
  reviewed_by: person:example
  reviewed_at: 2026-05-19T12:30:00+09:00
  checklist_version: zettel-promotion/v0.2
```

## Revision Rules

Canonical zettels may be revised, but revision should not erase important history.

Small corrections may update the existing zettel:

- typo fix
- formatting fix
- obvious metadata correction
- adding a missing object_id

Meaning-changing edits should create either:

```text
a receipt
a superseding zettel
or an explicit revision note
```

Create a new zettel instead of overwriting when:

- the conclusion changes
- the old note is historically important
- the visibility boundary changes
- the note is used by another archive or workpack
- the edit would hide a mistake, failed idea, or decision reversal

## AI Behavior

When helping the user write zettels, the AI should:

- write drafts first
- ask for minting only after a checklist pass
- preserve the user's intent, not just conclusions
- record uncertainty instead of smoothing it away
- suggest splits when one draft has multiple purposes
- prefer explicit typed edges over vague inline links
- preserve private sources when deriving shareable zettels
- update meeting minutes and decision logs for substantial project work

## Core Principle

```text
AI can help write memory, but the user decides what becomes durable memory.
```
