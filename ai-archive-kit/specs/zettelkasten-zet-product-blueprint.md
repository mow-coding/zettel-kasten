# Zettel-Kasten and Zet Product Blueprint v0.1

Status: planning baseline
Date: 2026-05-22

This document consolidates the product philosophy and concept model for `zettel-kasten`, `zet`, and the future `zet` sharing service.

It is not a runtime specification yet. It is the blueprint that implementation specs, schemas, CLI commands, tests, and future UI should align with.

For the longer public philosophy narrative, see:

- `ai-archive-kit/docs/concepts/foundational-product-whitepaper.md`
- `ai-archive-kit/docs/concepts/foundational-product-whitepaper.ko.md`

## 1. One-Sentence Definition

`zettel-kasten` is a subject-owned private archive made of source/original data, metadata, and minted `zet` documents.

`zet` is a Markdown-like text document plus metadata envelope, created by a user or under user-supervised AI collaboration, then minted into the private archive.

The future `zet` sharing service is a separate layer that lets minted zets move between subjects and compose into messages, feeds, workspaces, and new archives.

## 2. Product Philosophy

Every subject should be able to maintain its own independent archive.

The archive is not merely a folder, note app, cloud drive, or chat history. It is the subject's durable memory system.

The subject may be:

- a person,
- a project,
- a couple or relationship,
- a family,
- a child archive operated by guardians and later transferred,
- a team,
- a company,
- a business unit,
- a delegated archive,
- a future AI-assisted operational subject.

The first user experience should still be simple:

```text
zettel init
-> create my private zettel-kasten
```

But the internal model must not collapse:

```text
user == archive == device
```

Instead, it must keep these concepts separate:

- subject identity,
- archive identity,
- owner identity,
- operator identity,
- device/install identity,
- AI/runtime identity.

## 3. Core Composition

The system is built from three core layers:

```text
zettel-kasten
  = source/original data
  + metadata
  + zets
```

### 3.1 Source / Original Data

Source data is the raw or near-raw material the archive is based on.

Examples:

- text files,
- photos,
- screenshots,
- audio recordings,
- videos,
- PDFs,
- spreadsheets,
- code,
- exported chat transcripts,
- Notion pages,
- Google Drive documents,
- external web pages,
- object storage files.

Source data is not automatically a `zet`.

Source data may physically live in:

- local disk,
- external SSD,
- GitHub,
- object storage,
- Notion,
- Google Drive,
- Google Photos,
- a website,
- another archive,
- a workpack.

### 3.2 Metadata

Metadata makes source data and zets computable, searchable, governable, and verifiable.

Examples:

- object identity,
- archive identity,
- source bindings,
- object manifests,
- content hashes,
- provenance,
- timestamps,
- visibility,
- permissions,
- typed edges,
- receipts,
- lineage events,
- search indexes,
- local runtime session references.

Metadata is the map around the archive's materials.

### 3.3 Zets

A `zet` is a text document.

The easiest user mental model is:

```text
zet ~= Markdown document
```

But conceptually every `zet` is:

```text
human-readable text body
+ machine-readable metadata envelope
```

A `zet` may summarize, interpret, explain, quote, transcribe, index, or point to source material.

A `zet` is not:

- a raw media file,
- a binary attachment,
- a generic file transfer packet,
- an external social post by default.

## 4. Zet Definition

A `zet` is the basic interpreted map unit of a `zettel-kasten`.

It may be:

- directly written by the user,
- drafted by AI under user supervision,
- refined through user-AI conversation,
- derived from source data,
- derived from other zets,
- linked into larger archive structures.

The body is always text.

The envelope records context, source references, relationships, authority, visibility, and lifecycle.

## 5. Human Data Primitive Model

The project uses the following human-facing data primitives as a conceptual guide:

```text
text/language
sound
image
```

Speech may become text through transcription, but the original sound remains sound.

Images may be captioned or OCR'd, but the original image remains image.

Files are storage formats, not the deepest conceptual unit.

This matters because `zet` is always in the text/language layer. It can refer to sound and image originals, but it does not become those originals.

## 6. The Metadata Envelope

The user should experience a `zet` as a document first.

The system should manage an envelope that can be inspected when needed.

The default UX principle is:

```text
read/write as document;
inspect as envelope.
```

Minimum conceptual envelope fields:

```yaml
id: zet_...
title: ...
created_at: ...
updated_at: ...
archive_id: archive:...
subject_id: subject:...
status: draft | canonical | archived | redacted
kind: source_note | permanent_note | record_note | decision_note | meeting_minutes | object_summary | project_note
facets: {}
source_refs: []
assets: []
edges: []
provenance: {}
visibility: {}
authority: {}
mint: {}
integrity: {}
```

The implementation may use:

- Markdown with YAML frontmatter,
- Markdown plus adjacent JSON/YAML envelope,
- SQLite records plus Markdown export,
- or a package format later.

The concept remains the same:

```text
zet = text + envelope
```

## 7. Source References

A `zet` may refer to source/original data.

Source references must distinguish internal archive-safe references from external references.

### 7.1 Internal Source References

Internal originals should be referenced through archive-safe identities.

Examples:

```yaml
source_refs:
  - ref_id: source_ref_001
    kind: original_object
    object_id: sha256:...
    role: source_audio
```

The current project already follows this rule:

```text
canonical zettels reference original files by object_id;
provider URLs live in manifests/bindings, not as canonical file paths inside zets.
```

### 7.2 External Source References

Some sources are genuinely external:

- public web URLs,
- Notion pages,
- Google Drive documents,
- external AI chat exports,
- third-party documents.

These should be represented carefully.

Safe rule:

```text
If the external URL is the source itself, record it as an external source reference.
If the URL is only a provider location for a file the archive owns, convert it to a source binding/object manifest record instead.
```

Where possible, important external sources should be imported, snapshotted, hashed, or summarized so future readers are not dependent on a mutable external URL.

## 8. AI Conversation Provenance

AI conversation provenance means the local AI conversation inside the user's `zettel-kasten` runtime environment.

This is important because the local runtime may have controlled access to the user's archive and device.

External AI share URLs are not canonical creation provenance.

Rule:

```text
Local zettel-kasten AI session
  -> may be zet creation provenance.

External AI chat URL
  -> external source/reference at most,
     and only after import/snapshot/review if it matters.
```

This prevents the archive from pretending that an uncontrolled external chat had the same authority, access, or context as the local archive runtime.

## 9. Authority Model

The default rule is:

```text
AI may draft.
The user mints.
The user approves sharing.
```

Future authority modes may exist:

```text
basic
  AI drafts only.

auto_review
  AI may create drafts or private candidates,
  but sharing and canonical minting require review gates.

full_authority
  AI may mint/share within an explicitly bounded scope,
  with receipts, audit logs, and revocation boundaries.
```

The system must distinguish:

- created_by,
- assisted_by,
- supervised_by,
- reviewed_by,
- issued_by_subject,
- executed_by_agent,
- authority_mode.

This is necessary for human-authored zets, AI-assisted zets, organization-issued zets, and future agent-to-agent harness workflows.

## 10. Lifecycle

The lifecycle is:

```text
captured
-> draft
-> promotion_candidate
-> minted/canonical
-> revised | superseded | archived | redacted
```

Existing implementation vocabulary uses:

```text
promotion
canonical
```

Product vocabulary may use:

```text
minting
minted zet
```

These should map as:

```text
promote_zettel action ~= mint zet action
canonical zettel ~= minted zet
```

The vocabulary can be refined in code later, but the product meaning is clear:

```text
minting = private archive issuance
```

## 11. Minting

Minting is the act of turning a draft `zet` into an official private record inside the subject's `zettel-kasten`.

Minting is not:

- external sharing,
- SNS posting,
- publishing to a feed,
- sending to another person.

The correct flow is:

```text
AI/user drafts zet
-> user reviews
-> user mints
-> zettel-kasten receives canonical private zet
-> optional later share action may be offered
```

### 11.1 Draft Handling

When a draft is minted, the recommended policy is:

```text
inbox draft
-> canonical zet in zettels/
-> mint receipt in receipts/mint/
-> draft snapshot preserved under receipts/mint/drafts/
```

This keeps `inbox/` clean while preserving the pre-mint artifact.

### 11.2 Mint Transaction Outputs

A mint transaction should create or update:

1. canonical zet document,
2. metadata envelope/frontmatter,
3. source references,
4. typed edges to source zets or related zets,
5. local AI conversation provenance,
6. visibility state,
7. authority/supervision record,
8. mint receipt,
9. integrity fingerprint/hash,
10. search index and graph updates,
11. source map updates when needed.

### 11.3 Mint Receipt

A mint receipt should record:

- receipt id,
- action id,
- archive id,
- source draft id/path/hash,
- minted zet id/path/hash,
- reviewed_by,
- reviewed_at,
- authority mode,
- checklist result,
- source refs included,
- edges included,
- local AI session references,
- warnings,
- side effects.

## 12. Revision

Before minting, the draft is fluid and freely editable.

After minting, the `zet` is durable archive memory.

Small corrections may update the same zet with history:

- typo fix,
- formatting fix,
- obvious metadata correction,
- missing object id.

Meaning-changing edits should create:

- a revision receipt,
- a superseding zet,
- or an explicit revision note.

Shared or externally exported zets should not be silently overwritten.

## 13. Private Archive First

The base `zettel-kasten` system must be designed as if the external `zet` sharing service does not exist.

This prevents social behavior from distorting private thinking.

Default:

```text
minted zet = private
```

External sharing is always a separate action:

```text
share/export/publish != mint
```

## 14. Future Zet Sharing Service

The future `zet` sharing service is built on top of private minted zets.

It lets a user deliberately share a selected zet, or a derived/redacted shareable zet, with another subject.

Depending on relationship topology:

```text
1:1
  messenger-like behavior

1:many
  SNS/feed/channel behavior

many:many
  collaboration/workspace behavior
```

The same underlying object should not be casually leaked from the private archive.

Sharing should usually create a share package or share envelope that is distinct from the private minted zet.

### 14.1 Sharing Lifecycle Terminology

The preferred terminology candidate for future `zet` sharing is:

```text
mint -> delegate -> attest -> anchor
```

Meaning:

- `mint`: issue a `zet` as canonical private archive memory.
- `delegate`: give a scoped capability to a specific subject, group, archive, agent, or workspace.
- `attest`: verify a foreign `zet` and record evidence of its issuer, hash, protocol profile, and delegated condition.
- `anchor`: place an attested foreign `zet` into the recipient archive's meaning network without erasing its foreign provenance.

This vocabulary intentionally avoids ordinary SaaS verbs such as `download`, `share`, and `save` as the core philosophy. Future implementation may still use plain helper words in UI copy where clarity requires it, but the protocol-level concept model should align with minting, delegation, attestation, and anchoring.

### 14.2 Delegation Capability Model

`delegate` must not default to one public key or public link that any actor can reuse.

The preferred model is an attestation-bound delegation capability:

```text
issuer mints zet
-> issuer creates delegate capability
-> recipient claims or receives the capability
-> recipient attests the delegated zet
-> capability becomes bound to that recipient identity
-> optional later anchor places the foreign zet in local meaning
```

Delegation should support at least these future target policies:

```text
counterparty_bound
  The capability is issued to a known subject/archive/key/fingerprint.

claimable_once
  The capability can be claimed once by an initially unknown recipient.
  After claim and attestation, it becomes bound and spent.

group_bound
  A group/workspace capability may exist, but should still be decomposable
  into member-level or role-level proofs where sensitive access is involved.

public_link
  Explicit opt-in only. This must not be the default sharing model.
```

The reason is philosophical as much as technical:

```text
No central server should be the only party that knows who met whom.
The issuer should keep evidence of whom it delegated to.
The recipient should keep evidence of whom it received from.
```

For real implementation, delegate receipts should eventually include:

- delegate id,
- nonce or one-time claim id,
- issuer archive/subject identity,
- target policy,
- target archive/subject/key when known,
- counterparty fingerprint when known,
- scope,
- expiry/revocation policy,
- delegated zet ids and hashes,
- source access or copy policy,
- required attestation policy,
- optional settlement condition.

If the recipient never returns an attestation or acknowledgement, the issuer may only know that a capability was issued, not that it was used. A future relay, shared ledger, or public blockchain can make usage observation stronger, but the core local-first protocol should not require one.

### 14.3 Optional Settlement And Blockchain Extension

The core system should remain usable without coins, tokens, payment, or public blockchain infrastructure.

However, the delegation capability model should leave room for optional financial or contractual layers:

```text
free delegation
paid delegation
token-gated delegation
licensed delegation
institutional delegation
smart-contract-settled delegation
```

The settlement layer must be explicit and separate from authorship/provenance:

```text
payment may grant access/capability/license;
payment does not silently rewrite who minted the zet.
```

This keeps `zet` usable as private communication, messenger, SNS, and collaboration infrastructure while leaving a clean bridge toward future blockchain, licensing, or knowledge-market experiments.

## 15. Sharing Payload Policies

Because a `zet` body is always text, sharing a zet may carry different source access policies:

```text
text_only
  only the zet text/envelope is shared.

copy
  source copies or derived artifacts are bundled.

access_grant
  recipient receives permission or a link/capability to access source data.

hybrid
  text and small supporting artifacts are copied;
  large/sensitive sources remain permissioned references.
```

Sharing must pass scope and trust gates:

```text
scope gate
  What exactly is included/excluded?

trust gate
  Who is the counterparty and what key/fingerprint/identity verifies them?
```

## 16. Composable Archives

Shared or detached zets can compose into new independent zettel-kastens.

This is one of the central ideas of the system.

Examples:

```text
personal archive + personal archive
-> relationship archive

relationship archive
-> family archive

family archive selected history
-> child archive
-> later ownership transfer to child

personal/project archive
-> company archive

company archive + acquired company archive
-> merger archive

company archive selected unit
-> spin-out archive
```

A composed archive needs:

- archive identity,
- owner/operator model,
- scope manifest,
- lineage receipts,
- provenance preservation,
- ownership transfer rules,
- trust gates,
- redaction policies.

## 17. Storage And Infrastructure Model

The conceptual model is not decided by file size alone.

Use these roles:

```text
GitHub
  versioned map, specs, zets, metadata, receipts, source maps, collaboration ledger.

Object storage
  large media and original objects.

Local PC / SSD
  primary user operating environment and local-first working state.

SQLite
  rebuildable index for search, graph queries, and local retrieval.

Provider bindings
  safe references to external provider locations and credentials.

Keyring/local profiles
  secrets and local-only paths.
```

Important:

```text
Storage is not just where a file lives.
Storage is a promise about who can verify, read, mutate, derive, and share it.
```

## 18. UX Principles

### 18.1 One-Command Start

The user wants `zettel-kasten` to be installable and usable with a simple command.

Target feeling:

```text
install once
mount my archive
talk with AI
draft zets naturally
mint what matters
```

### 18.2 Document-First Reading

Users should not feel like they are editing protocol packets.

Default view:

- title,
- body,
- basic status.

Inspectable view:

- sources,
- provenance,
- permissions,
- envelope,
- receipts,
- edges,
- signatures/fingerprints.

### 18.3 Human Review Before Durability

Core message:

```text
AI can help write memory,
but the user decides what becomes durable memory.
```

### 18.4 Sharing Is Deliberate

The private archive must not become performative social media by accident.

The system may ask:

```text
Would you like to share this externally?
```

But only after minting, and only as a separate action.

## 19. Non-Goals For The Next Implementation Slice

The next implementation should not try to build the entire future sharing service.

Avoid in the first slice:

- full P2P networking,
- mobile app,
- public SNS feed,
- decentralized identity network,
- group encryption,
- real-time collaboration,
- global search,
- blockchain consensus,
- automatic external AI import.

First prove:

```text
draft zet
-> mint
-> canonical private zet
-> receipt
-> source/edge/provenance integrity
```

## 20. Implementation Baseline

The current codebase already has useful pieces:

- `inbox/` for drafts,
- `zettels/` for canonical zettels,
- Markdown + YAML frontmatter,
- object manifests,
- typed edges,
- provenance fields,
- visibility fields,
- promotion rules,
- doctor checks,
- workpacks,
- archive identity,
- archive lineage,
- transfer receipts.

The next likely implementation should align existing `promotion` behavior with product-level `minting` language.

Possible next action:

```text
archive mint-zettel <archive> --draft <path-or-id> --reviewed-by <person> --approve
```

This may initially be implemented as a clearer alias or extension of existing promotion concepts.

## 21. Open Implementation Questions

Only these questions remain relevant before coding:

1. Should the first implementation be spec-only or include a local `mint-zettel` CLI path?
2. Should the public CLI vocabulary use `mint-zettel`, keep `promote-zettel`, or support both with one internal action?
3. What is the minimal mint receipt schema for v0.1?

These are implementation-scope questions, not product-philosophy questions.

## 22. Glossary

`archive`
: A subject-owned memory system.

`subject`
: The person, family, team, company, project, or other entity the archive belongs to or represents.

`source/original data`
: Raw or near-raw materials, such as files, media, documents, pages, recordings, or external records.

`metadata`
: Structured information that makes records searchable, verifiable, governable, and linkable.

`zet`
: A Markdown-like text document plus metadata envelope, used as the archive's human-readable interpreted map unit.

`draft zet`
: A working text object that may be AI-assisted and freely edited before minting.

`minted zet`
: A user-approved canonical private zet inside the zettel-kasten.

`minting`
: Private archive issuance: the act of making a draft zet into durable archive memory.

`source_ref`
: A reference from a zet to source/original material.

`edge`
: A typed arrow between zets, objects, archives, or other entities.

`receipt`
: A durable audit record of a meaningful archive action.

`workpack`
: A portable archive slice for sharing, derivation, transfer, or collaboration.

`zet sharing service`
: A future protocol/client layer for sharing minted or derived zets between subjects.
