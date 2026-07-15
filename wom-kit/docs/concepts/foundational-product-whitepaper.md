# Foundational Product Whitepaper: WOM, zettel-kasten, zet, and ZET

Status: public product planning baseline
Date: 2026-05-23
Updated: 2026-07-15
Version context: v0.2.7 planning document

This document is the detailed public product philosophy for WOM, `zettel-kasten`, `zet`, and `ZET`.

`WOM` means `Widesider of Modernity`: the ambition to widen the horizon humans can perceive at the frontier of modernity.

`zettel-kasten` is the historical root and archive method. `zet` is the unit document minted inside it. `ZET` is the future zettel-kasten-based communication layer.

It explains the product idea before implementation details: what the system is, why it exists, what it assumes about humans and AI, and how the same structure can support private archives, HITL workflows, AI-agent harnesses, messaging, social feeds, and collaboration.

## 1. Core Thesis

AI does not only need better prompts.

AI needs durable memory that it can inspect, cite, verify, revise, and act on.

Humans also need memory that does not disappear into scattered chats, folders, cloud drives, screenshots, and SaaS silos.

`zettel-kasten` is a local-first, subject-owned archive system for this memory.

`zet` is the text-centered unit that turns source material, AI conversation, and user judgment into durable archive memory.

The future `ZET` communication layer lets selected zets move between people, organizations, devices, agents, and archives without making a central platform the canonical owner of the user's memory.

The root model is:

```text
source/original data
+ metadata
+ minted zets
+ receipts
+ shareable envelopes
```

This is not only a note-taking idea.

It is a memory infrastructure idea.

### 1.1 Artifact Primacy, Not Entity Certainty

WOM adopts the auditable operating discipline of an ontology system without
treating entity resolution as the purpose of human memory. A person is not a
stable master-data table. Meanings, beliefs, names, categories, and priorities
can drift with time and context. Yesterday's use of a word and today's use may
need to remain distinct even when their labels match.

The primary evidence is the durable, time-situated artifact. Revisions and
contradictions stay traceable. A `canonical` zet is the subject's current
archive record, not an objective-truth certificate. Nodes, ties, edges, search
indexes, embeddings, and graphs are regenerable aids for reading and routing.
They must not silently merge matching labels, erase ambiguity, or become a
hidden authority over the artifacts.

AI may spend tokens and use current model capability to infer context across
those artifacts at reading time. That inference is replaceable. The artifacts,
their provenance, and their chronology are the durable layer.

## 2. The Problem

Most current tools divide memory into incompatible fragments.

Files live in local folders, Google Drive, Notion, Slack, GitHub, email, screenshots, phone galleries, and chat logs.

AI conversations often create useful insight, but the insight stays inside transient chat history. It is rarely converted into durable records with source references, authority, review status, and revision history.

Cloud apps often make the application the center:

```text
app first
user memory second
AI as a feature inside the app
```

This project reverses that order:

```text
user archive first
AI as an operator over that archive
apps as optional surfaces
sharing as deliberate projection
```

The problem is not that people lack places to store files.

The problem is that people lack a durable, inspectable, AI-native memory layer that can connect original data, interpretation, decisions, and future action.

## 3. The Subject-Owned Archive

Every subject can own an archive.

A subject may be:

- a person,
- a family,
- a team,
- a company,
- a project,
- an institution,
- a delegated agent identity,
- or another bounded actor that can hold memory and authority.

The first-run archive can therefore be personal or organizational.

This matters because the system should work on:

- a personal laptop,
- a company workstation,
- a shared tablet,
- a family archive server,
- a team workspace machine,
- or an AI-operated environment.

The archive is not just a folder.

It is a structured memory boundary:

```text
who owns this memory?
what source material does it cite?
which zets are canonical?
who approved them?
what changed over time?
what can be shared?
what must remain private?
```

## 4. Human Data Primitives

The project starts from a human-facing model of data.

Humans create and perceive data through three primitive forms:

```text
text / language
sound
image
```

These are not file extensions.

They are conceptual primitives.

Speech may become text through transcription, but the original sound remains sound.

Music or noise may be analyzed, labeled, or converted into notation, but the original acoustic signal remains sound.

An image may be captioned, OCR'd, embedded, or described by AI, but the original image remains image.

A screenshot of a spreadsheet may be converted into table text, but the screenshot itself remains an image source object. The extracted table is a derived record.

This matters because `zet` is always text.

`zet` is the interpreted map, not the raw territory.

It can cite, explain, summarize, quote, connect, or decide based on source material, but it should not pretend to be the source material itself.

## 5. Original Data And Derived Text

The archive must not flatten all text-like artifacts into one category.

Recommended authority ladder:

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

Examples:

- `.txt`, `.md`, `.hwp`, `.hwpx`, `.docx`, `.xlsx`, and similar files may contain born-digital editable text.
- PDF text extracted by a parser is derived from a source object.
- OCR from a screenshot or scanned PDF is model-dependent derived text.
- Speech-to-text from an audio recording is derived text.
- A human-reviewed correction of OCR is stronger than raw OCR but still derived from a source object.
- A minted `zet` is not raw evidence. It is approved archive memory that may cite evidence.

This distinction is crucial because AI tools will improve.

If OCR quality improves later, the system should be able to regenerate the OCR layer without overwriting the original object or confusing derived text with original text.

## 6. What `zet` Is

A `zet` is always text.

More precisely, a `zet` is:

```text
v0.2 Markdown-compatible document body
long-term WOM Safe HTML Profile rendering/interchange target
+ metadata envelope
+ source references
+ relationships
+ provenance
+ lifecycle state
+ authority record
+ integrity information
```

The body should be readable by a human.

The envelope should be inspectable by software.

The long-term format direction matters because WOM should not force every future user into one official app. The local zettel-kasten runtime is AI/CLI/MCP first, while future `ZET` surfaces may be galleries, feeds, media viewers, workspaces, dashboards, or domain-specific SaaS products. Markdown remains useful for authoring and import compatibility, but the canonical/interchange/rendering target should converge toward a security-conscious WOM Safe HTML Profile rather than arbitrary HTML.

A `zet` may:

- summarize a source,
- explain an idea,
- interpret a document,
- connect multiple sources,
- preserve an AI-assisted conclusion,
- record a decision,
- cite a local file,
- cite an object store item,
- cite a Notion page,
- cite a Google Drive document,
- cite an external URL,
- or become a shareable text object.

A `zet` is not:

- a random file attachment,
- a raw screenshot,
- a database row only machines can read,
- a social media post by default,
- or a central-server object by default.

It is the smallest durable unit of interpreted archive memory.

## 7. Minting

Minting means private archive issuance.

It does not mean public posting.

It does not mean blockchain publication.

It does not mean sharing.

Minting is the act of turning a draft `zet` into a canonical private archive record.

Default flow:

```text
source material
-> AI/user conversation
-> draft zet
-> review gate
-> minted private zet
-> receipt
-> optional later share action
```

Before minting, the draft can be freely edited.

After minting, the `zet` becomes durable memory. It can still be corrected or superseded, but those changes should leave history.

This gives the archive an important property:

```text
thinking can stay fluid before minting
memory becomes accountable after minting
```

## 8. HITL And AI-Agent Harness

The default mode is HITL: human-in-the-loop.

In the default model:

```text
AI may inspect allowed context.
AI may draft.
AI may propose links, tags, source refs, and summaries.
Human reviews.
Human mints.
Human approves sharing.
```

But the same architecture can support stronger delegation.

The important abstraction is the authority slot.

The authority slot may be occupied by:

- a human user,
- an organization role,
- a supervised AI agent,
- a policy-bound autonomous AI agent,
- or a chain of agents operating under a scoped permission profile.

This gives three practical authority modes:

```text
basic
  AI drafts only. Human mints and shares.

auto_review
  AI may prepare candidates and run checks.
  Human still controls canonical minting and external sharing.

full_authority
  AI may mint, revise, route, or share inside an explicitly bounded scope.
  Every action must create receipts and remain revocable/auditable.
```

This is why `zettel-kasten` can become both:

```text
human-centered AI archive
AI-agent operating harness
```

The same receipt system that protects a human user's memory also makes autonomous agent behavior auditable.

If a human is present, the system supports deliberation.

If a human delegates authority, the system becomes an operating substrate for agents.

The difference is not a different product.

The difference is the authority mode attached to the same archive and zet lifecycle.

## 9. Local AI Conversation Provenance

AI conversation provenance should mean the AI conversation inside the user's `zettel-kasten` runtime environment.

This matters because a local or controlled runtime may have permission to inspect the archive, local folders, provider exports, object manifests, and source maps.

External AI chat URLs are not equivalent provenance.

They may be cited as external references, imported snapshots, or source objects after review, but they should not pretend to be the same as a controlled local archive session.

Recommended rule:

```text
local archive AI session
  -> creation provenance

external AI chat link
  -> external reference unless imported, snapshotted, reviewed, and bound
```

## 10. Storage Model

Object storage is not only for media.

Original source files belong in a source/object layer when they are used as evidence.

This includes:

- `.hwp`,
- `.hwpx`,
- `.docx`,
- `.xlsx`,
- `.pdf`,
- `.txt`,
- `.md`,
- `.csv`,
- screenshots,
- audio,
- video,
- exports from Notion,
- exports from Google Drive,
- provider snapshots,
- and other original or captured files.

Recommended split:

```text
Git repository
  zets
  metadata
  schemas
  receipts
  manifests
  public-safe specs

Object store / local object store
  source files
  media
  binary documents
  large exports
  immutable snapshots

Search/index layer
  extracted text
  OCR text
  embeddings if used
  graph index

Provider bindings
  Notion
  Google Drive
  GitHub
  object storage
  local filesystem
```

A `.md` file can be a source object or a minted `zet` depending on its role.

Role matters more than extension.

The search/index layer is a rebuildable acceleration layer, not a canonical
ontology. Entity candidates, embeddings, and graph projections may help an AI
choose what to read first, but they do not authorize automatic identity merges
or replace chronological artifact evidence.

## 11. Provider-Aware Archive

The user should be able to say things naturally:

```text
Load this local folder into my zettel-kasten.
Make a zet from this document.
Use this Google Drive file as source material.
Map this Notion page into my archive.
Mint the summary we just created.
Share this zet with this person.
```

The system should translate those requests into explicit operations:

```text
scan source
bind provider
copy or snapshot source
extract derived text
draft zet
show review
mint zet
write receipt
update index
offer optional share
```

Provider integration must preserve provenance.

For example, a Google Drive or Notion item can be:

- referenced by URL,
- imported as an export,
- snapshotted into object storage,
- represented in a source map,
- or cited by a minted `zet`.

Those choices are different and should be recorded.

## 12. Private Archive First

The base system assumes the external `zet` sharing service does not exist.

This is intentional.

The first product is not a social network.

The first product is a trustworthy private archive.

Default:

```text
minted zet = private
```

External sharing must be a separate action:

```text
mint != share
mint != publish
mint != post
```

This protects thought before performance.

It lets the archive become memory before it becomes communication.

## 13. ZET Sharing

The future `ZET` service is a sharing and communication layer built from the archive model.

The same `zet` abstraction can produce different social forms depending on topology:

```text
1:1 ZET relation
  -> messenger

1:many ZET relation
  -> SNS feed, channel, newsletter-like stream

many:many ZET relation
  -> collaboration workspace
```

The key point is that these are not separate product categories at the data-model level.

They are different relationship graphs over the same unit:

```text
text zet
+ metadata envelope
+ source access policy
+ share envelope
+ recipient scope
+ receipts
```

Sharing may attach:

- text only,
- copied source artifacts,
- access links,
- scoped capabilities,
- redacted derivatives,
- expiration policy,
- recipient permissions,
- or workspace rules.

The private archive should not casually leak its originals.

Sharing should usually create a share envelope or workpack distinct from the private canonical `zet`.

## 14. Web3-Like Without Token Hype

This project is Web3-like in an infrastructural sense.

It does not need coins or a public blockchain to express the important idea.

The important principles are:

- subject-owned identity,
- user-owned data,
- portable records,
- verifiable actions,
- relationship-scoped sharing,
- local-first operation,
- optional peer-to-peer transport,
- optional relays,
- no central platform as the only source of truth.

Relationship-scoped sharing also means that `delegate` is not a public-link default. A future delegate capability should be counterparty-bound or one-time claimable, then bound to the recipient through attestation. The issuer should not need a central server to remember whom it contacted, and the recipient should not need a central server to prove where the foreign `zet` came from.

This model can later bridge to optional settlement, licensing, token-gated access, or smart contracts. Those layers should remain optional: payment may grant access or license rights, but it should not silently rewrite authorship, provenance, or archive ownership.

The public repository is the protocol/reference chain:

```text
source code
+ specs
+ schemas
+ release tags
+ upgrade notes
```

Users may follow the newest chain or remain on an older release.

Same major version should imply expected compatibility.

Different major versions may need migration or bridges.

This is the practical meaning of versioned `ZET` systems "tuning to the same frequency."

## 15. Composable Archives

A zettel-kasten can produce zets.

Selected zets can be shared.

Shared zets can compose into a new archive.

That new archive may be:

- jointly owned,
- delegated,
- spun out,
- inherited,
- transferred,
- forked,
- or merged.

Examples:

- a personal archive creates selected zets for a family archive,
- two people create a shared archive,
- a team creates a project archive,
- a company spins out a business unit archive,
- an organization transfers a workpack to another subject,
- an agent creates a task archive under full authority and returns receipts.

This is one of the strongest product ideas:

```text
archives create zets
zets can create archives
archives can be composed, shared, transferred, and governed
```

## 16. Why This Matters For AX

AX here means AI Transformation.

Most AI adoption attaches a chatbot to an existing workflow.

This project starts lower in the stack.

It asks:

```text
What memory substrate does AI need in order to work responsibly?
```

The answer is not only vector search.

AI needs:

- original sources,
- derived text,
- provenance,
- human or delegated authority,
- receipts,
- versioning,
- revision history,
- local permissions,
- share boundaries,
- and durable zets.

Without this, AI output remains difficult to trust.

With it, AI can become an archive operator, research assistant, memory curator, collaboration agent, and workflow executor.

## 17. User Experience Principle

The system should be powerful without requiring the user to think like an infrastructure engineer.

Target experience:

```text
install with one command
connect providers step by step
talk to an AI that can access allowed local context
ask naturally
review what matters
mint durable zets
share deliberately
delegate carefully
audit later
```

The product should feel like:

```text
my device
my archive
my AI operator
my zets
my rules
```

not like:

```text
another central app owns my memory
```

## 18. Open Source Philosophy

The blueprint, schemas, reference implementation, research notes, implementation plans, and public-safe work logs should be open.

Real user archives should remain private.

Public:

- product philosophy,
- protocol design,
- schemas,
- fake examples,
- reference implementation,
- research references,
- implementation plans,
- public-safe release notes.

Private:

- real zets,
- real source maps,
- real files,
- provider tokens,
- private AI conversations,
- personal paths,
- sensitive receipts.

This distinction lets the project be public and collaborative without turning personal memory into public data.

## 19. Non-Goals

This project is not trying to be:

- a generic note app,
- a cloud drive clone,
- a chatbot wrapper,
- a token project,
- a public SNS clone,
- a replacement for every collaboration tool immediately,
- a deterministic global knowledge graph that treats entity resolution as
  objective truth,
- an automatic identity-merging system that erases temporal ambiguity,
- or a system that forces everyone to use zettel-kasten before using `zet`.

`ZET` should eventually work as a standalone messenger/collaboration/SNS layer for people who do not want the full archive system.

But the deeper architecture comes from zettel-kasten.

## 20. Implementation Order

The implementation should proceed in this order:

```text
1. local archive structure
2. source/object model
3. provider bindings
4. draft zet format
5. mint transaction
6. mint receipt
7. text provenance hierarchy
8. search and graph index
9. authority modes
10. share envelope / workpack
11. capability-based sharing
12. local-first collaboration
13. optional P2P or relay transport
14. standalone zet client
15. agent harness mode
```

The social layer should not come first.

Trustworthy private memory should come first.

## 21. Success Criteria

The project is working when a user can:

- install the system with minimal setup friction,
- connect local folders and selected providers,
- ask an AI to inspect allowed sources,
- draft a `zet` through conversation,
- see source references and provenance,
- mint the `zet` into a private archive,
- revise it with history,
- preserve contradictions or changed meanings without silently merging them,
- use maps and graphs as reading aids without treating them as truth,
- search it later,
- share it deliberately,
- delegate bounded authority to agents,
- and audit what happened.

The long-term ambition is simple:

```text
important context should not evaporate
private memory should become durable
AI should operate over accountable memory
artifacts should outlive replaceable inference
human change should remain visible instead of being normalized away
sharing should be chosen, scoped, and verifiable
```
