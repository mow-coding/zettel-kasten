# Zettel-Kasten and Zet Implementation Research v0.1

Status: research baseline
Date: 2026-05-22

This document maps the product blueprint in `zettelkasten-zet-product-blueprint.md` to existing standards, protocols, open-source systems, and implementation strategies.

The goal is not to copy one project. The goal is to avoid building from scratch when strong reference designs already exist.

## 1. Research Conclusion

The blueprint should be implemented in phases.

Do not begin with full P2P, social networking, or blockchain infrastructure.

The correct first implementation is local and archive-native:

```text
draft zet
-> mint transaction
-> canonical private zet
-> source refs, typed edges, local AI provenance, receipt, hash, index update
```

Then the system can grow outward:

```text
local archive
-> signed archive actions
-> portable workpacks
-> capability-based sharing
-> optional relay/P2P sync
-> collaborative/shared archives
-> standalone zet communication client
```

## 2. Implementation Stack Recommendation

### Phase 1: Local Minting Baseline

Use the current codebase's strengths:

- Markdown + YAML frontmatter for zets.
- JSON/YAML receipts for actions.
- SHA-256 object ids for originals.
- JSON Schema for receipts and manifests.
- SQLite FTS5 for local search.
- Existing `doctor` checks for validation.

Implement:

```text
mint-zettel
  reads inbox draft
  validates checklist
  writes canonical zet
  snapshots draft
  writes mint receipt
  updates index/source map
```

No new network protocol is needed yet.

### Phase 2: Signed Receipts And Archive Identity

Add cryptographic signing around archive actions:

- mint receipts,
- revision receipts,
- import/export receipts,
- share receipts,
- ownership transfer receipts.

Use the existing archive identity and keyring/profile design as the starting point.

Reference models:

- Nostr event signatures for a simple signed event envelope.
- AT Protocol repository commits for signed content-addressed repository state.
- Radicle for Git-backed signed social artifacts.

### Phase 3: Portable Archive Slices

Extend existing workpacks into a stronger export/import package.

Relevant references:

- BagIt for stable file package layout and fixity manifests.
- RO-Crate for machine-readable metadata around research/data artifacts.
- AT Protocol CAR exports and IPFS content addressing for content-addressed package ideas.

Do not require IPFS to use content addressing.

The project already uses `sha256:` object ids, which are enough for the local baseline.

### Phase 4: Capability-Based Sharing

When the future `zet` sharing service begins, access should not be modeled as "just send a URL."

It should be modeled as scoped authority:

```text
who can read what
for what purpose
until when
with what ability to copy, quote, reply, or derive
```

Relevant references:

- UCAN for signed, decentralized, user-controlled authorization.
- DID Core for subject-controlled identifiers and key material.
- W3C Verifiable Credentials for tamper-evident claims and presentations.
- AnySync for encrypted spaces, user-owned keys, and ACL complexity.

### Phase 5: Local-First Collaboration

Only after local minting, receipts, and portable workpacks are stable should shared editing or multi-user workspaces be attempted.

Relevant references:

- Automerge for local-first sync and versioned CRDT documents.
- Yjs for mature collaborative text editor integrations.
- Radicle's collaborative objects for Git-backed social artifacts.

Do not use CRDTs for every archive object by default.

Use CRDTs where real concurrent editing is needed.

### Phase 6: P2P / Relay / Social Transport

The future `zet` service can study:

- Nostr's signed event plus relay model.
- Secure Scuttlebutt's per-identity append-only feed.
- Radicle's P2P Git replication and gossip.
- Briar/SimpleX for private messaging and metadata minimization.
- Matrix/MLS for group communication and encryption lessons.

But the `zettel-kasten` core should not depend on any of these in v0.

## 3. Standards And References By Blueprint Need

### 3.1 Provenance

Need:

```text
Record where a zet came from:
source data, other zets, local AI session, human reviewer, mint action.
```

Reference:

- W3C PROV.

Why it matters:

W3C PROV defines provenance as information about entities, activities, and people involved in producing data, useful for judging quality, reliability, and trustworthiness. It also gives a family of interoperable provenance models and serializations.

Implementation direction:

Do not import RDF/OWL complexity into v0.

Use a small PROV-inspired model:

```yaml
provenance:
  entities:
    - zet:...
    - object:sha256:...
    - ai_session:...
  activities:
    - mint
    - derive
    - revise
  agents:
    - person:...
    - ai_runtime:...
```

Map to W3C PROV later if needed.

Sources:

- [W3C PROV Overview](https://www.w3.org/TR/prov-overview/)
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)

### 3.2 Content Addressing And Integrity

Need:

```text
Verify source originals and minted zets.
Know whether bytes changed.
Avoid provider URL lock-in.
```

Reference:

- IPFS CID model.
- AT Protocol repository data model.
- Existing project object manifest.

Why it matters:

IPFS CIDs show how content can be addressed by the content itself rather than location. AT Protocol repositories use content-addressed graphs and signed commits, with large blobs referenced by content hash and repositories exportable as CAR files.

Implementation direction:

For v0:

```text
sha256 object ids are enough.
```

Add:

```yaml
integrity:
  body_sha256: ...
  envelope_sha256: ...
  canonical_bytes_policy: markdown-frontmatter-v0.1
```

Later:

- add CID/CAR compatibility for package exports,
- use deterministic canonicalization for signed envelopes,
- study AT Protocol's signed repository commits.

Sources:

- [IPFS Content Addressing](https://docs.ipfs.tech/concepts/content-addressing/)
- [AT Protocol Repository Spec](https://atproto.com/specs/repository)

### 3.3 Portable Archive Packages

Need:

```text
Move selected zets, source references, receipts, and metadata between devices or archives.
```

Reference:

- BagIt.
- RO-Crate.
- AT Protocol CAR export.

Why it matters:

BagIt is a practical packaging convention with manifests and payloads for transferring digital content. RO-Crate describes research/data packages with machine-readable metadata. AT Protocol uses CAR files to export content-addressed repository blocks for sync, backup, or migration.

Implementation direction:

Current `workpack` can evolve into:

```text
workpack/
  package.yml
  zettels/
  objects/
  manifests/
  receipts/
  ro-crate-metadata.json   optional later
  bagit.txt                optional later
```

For now, keep workpacks simple and validate with `doctor`.

Sources:

- [IETF RFC 8493 BagIt](https://www.ietf.org/rfc/rfc8493.txt)
- [RO-Crate Specification](https://www.researchobject.org/ro-crate/specification/1.1/introduction.html)
- [AT Protocol Repository Spec](https://atproto.com/specs/repository)

### 3.4 Markdown Knowledge Base And AI Memory

Need:

```text
A human-readable local archive that AI can read, write, search, and connect.
```

Reference:

- Basic Memory.
- Obsidian properties/frontmatter.
- Logseq/Obsidian style graph notes.

Why it matters:

Basic Memory is very close to the local AI memory part: Markdown files, AI-readable/writable memory, SQLite index, MCP tools, relations, and semantic graph. It does not include the full source/original data + mint receipt + sharing lineage model, but it is an excellent implementation reference for the local AI-memory loop.

Implementation direction:

Borrow the pattern:

```text
plain Markdown files
+ local index
+ AI tools
+ graph traversal
+ transparent user-owned memory
```

But add this project's stricter archive controls:

- human minting,
- source_refs,
- object manifests,
- receipts,
- visibility gates,
- no provider URLs as canonical object references.

Sources:

- [Basic Memory: What is Basic Memory](https://docs.basicmemory.com/start-here/what-is-basic-memory)
- [Obsidian Properties](https://obsidian.md/help/properties)

### 3.5 AI Tool Runtime

Need:

```text
Let an AI operate inside the user's archive with controlled tools.
```

Reference:

- Model Context Protocol.
- Basic Memory's MCP usage.

Why it matters:

MCP separates resources, tools, and prompts. That matches the archive control model:

```text
Resources
  readable zets, source maps, manifests, receipts.

Tools
  create draft, mint zet, search, read, inspect, pack workpack.

Prompts
  guided zettel writing and mint review workflows.
```

Implementation direction:

Keep CLI as the stable core.

Then expose safe actions through MCP:

- `create_draft_zettel`,
- `read_zettel`,
- `search_zettels`,
- `mint_zettel` with human approval gate,
- `inspect_sources`,
- `build_context`.

Sources:

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2024-11-05/index)
- [Basic Memory MCP Integration](https://docs.basicmemory.com/start-here/what-is-basic-memory)

### 3.6 Policy And Validation

Need:

```text
Prevent unsafe writes and keep archive rules explicit.
```

Reference:

- JSON Schema.
- Open Policy Agent / Rego.

Why it matters:

JSON Schema can validate receipts, manifests, and envelope shapes. OPA/Rego is a mature model for policy-as-code, but it may be too heavy for v0.

Implementation direction:

For v0:

- continue with YAML rules,
- add JSON Schemas for mint receipts,
- enforce through Python doctor/tests.

Later:

- compile policies to a small internal evaluator,
- consider OPA only if policy complexity grows.

Sources:

- [JSON Schema Specification](https://json-schema.org/specification)
- [Open Policy Agent Docs](https://www.openpolicyagent.org/docs/latest)

### 3.7 Local Search And Indexing

Need:

```text
Fast local search over zets, receipts, source maps, and object metadata.
```

Reference:

- SQLite FTS5.
- Basic Memory's SQLite indexing pattern.

Why it matters:

SQLite FTS5 is built for full-text search over document collections. The existing project already uses SQLite as a rebuildable index, which fits the principle that canonical memory is files/receipts/manifests, while the database is derived.

Implementation direction:

Keep SQLite rebuildable.

Index:

- zet title,
- zet body,
- facets,
- source_refs labels,
- edge targets,
- receipt metadata,
- local AI session summaries.

Sources:

- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- [Basic Memory: How it works](https://docs.basicmemory.com/start-here/what-is-basic-memory)

### 3.8 Identity And Keys

Need:

```text
Archive identity, subject identity, key rotation, trusted counterparties.
```

Reference:

- W3C DID Core.
- Radicle identity documents.
- AT Protocol DID-linked account repository location.

Why it matters:

DID Core separates subject, controller, verification methods, services, and key material. Radicle uses identity documents and signed repository state. AT Protocol uses DIDs to locate account repositories and key material.

Implementation direction:

Do not require global DID adoption in v0.

Use local archive identities first:

```yaml
archive_id: archive:personal:...
subject_id: person:...
public_keys:
  - key_id: ...
    algorithm: ssh-ed25519
    fingerprint: ...
```

Design it so it can map to DID-style identities later.

Sources:

- [W3C DID Core](https://www.w3.org/TR/did-core/)
- [Radicle Protocol Guide](https://radicle.dev/guides/protocol)
- [AT Protocol Repository Spec](https://atproto.com/specs/repository)

### 3.9 Signed Events And Receipts

Need:

```text
Make mint, share, revise, and transfer actions verifiable.
```

Reference:

- Nostr event structure.
- Secure Scuttlebutt append-only feeds.
- Radicle signed Git artifacts.

Why it matters:

Nostr's event shape is a very small signed envelope: id, pubkey, timestamp, kind, tags, content, signature. SSB shows identity feeds as append-only logs, with each message pointing to the previous message. Radicle shows how social artifacts can live in Git and be signed/replicated.

Implementation direction:

For v0 mint receipts:

```yaml
receipt_id: receipt:mint:...
action: mint_zettel
created_at: ...
actor: person:...
archive_id: ...
target_zet: zet_...
input_draft_hash: sha256:...
output_zet_hash: sha256:...
previous_receipt:
signature:
```

Start with unsigned receipts plus hashes.

Then add signatures.

Later, consider append-only receipt chains per archive or per action type.

Sources:

- [Nostr NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md)
- [Secure Scuttlebutt Protocol Guide](https://ssbc.github.io/scuttlebutt-protocol-guide/)
- [Radicle Protocol Guide](https://radicle.dev/guides/protocol)

### 3.10 Capability Sharing

Need:

```text
When sharing zets or source access, model exactly what the recipient may do.
```

Reference:

- UCAN.
- W3C Verifiable Credentials.
- DID capability verification relationships.
- AnySync ACLs and keys.

Why it matters:

UCAN is designed for signed, local-first, user-controlled authorization without a central authority. W3C Verifiable Credentials provide a model for tamper-evident claims and presentations. AnySync shows that encrypted spaces and ACL changes become complex once there are multiple users and multiple devices.

Implementation direction:

For first sharing prototypes, do not build full UCAN.

Use a simple local share policy:

```yaml
permissions:
  read_zet: true
  read_sources: false
  can_copy: true
  can_forward: false
  expires_at: ...
```

Later, map share grants to signed capability objects.

Sources:

- [UCAN](https://ucan.xyz/)
- [W3C Verifiable Credentials 2.0](https://www.w3.org/TR/vc-data-model-2.0/)
- [AnySync Access Control and Encryption](https://sync.any.org/publish-your-docs)

### 3.11 Local-First Collaboration

Need:

```text
Eventually support shared workspaces and multi-user archive composition.
```

Reference:

- Automerge.
- Yjs.
- AnySync.
- Radicle COBs.

Why it matters:

Automerge is strong for local-first data that syncs and remembers change history. Yjs is strong for collaborative text editors with many existing editor bindings. AnySync is a close product reference for encrypted local-first shared spaces. Radicle COBs are a strong reference for signed collaborative artifacts inside a Git-backed system.

Implementation direction:

For `zettel-kasten`, canonical zets should remain durable text files with receipts.

Use CRDTs later only for:

- live collaborative editing sessions,
- shared workspace drafts,
- multi-user comments,
- conflict-prone shared documents.

Do not store every canonical archive record as CRDT from day one.

Sources:

- [Automerge](https://automerge.org/)
- [Yjs Docs](https://beta.yjs.dev/docs/introduction/)
- [Anytype Docs](https://doc.anytype.io/)
- [Radicle Protocol Guide](https://radicle.dev/guides/protocol)

### 3.12 Future Messaging And Social Transport

Need:

```text
Turn shared zets into 1:1 messages, 1:many feeds, and many:many workspaces.
```

Reference:

- Nostr for signed events and relays.
- Briar for direct encrypted device sync and no central server.
- SimpleX for metadata-minimizing messaging without global user identifiers.
- Matrix/MLS for group messaging and E2EE lessons.
- Secure Scuttlebutt for P2P social feeds.

Implementation direction:

Do not choose the transport yet.

Possible strategies:

1. file/workpack exchange,
2. Git-backed sync,
3. Nostr-like relay for discovery/distribution,
4. SimpleX-like pairwise queues for private messaging,
5. Matrix-like rooms for workspaces,
6. custom P2P only after the model proves itself locally.

Sources:

- [Nostr NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md)
- [Briar How It Works](https://briarproject.org/how-it-works/)
- [SimpleX Platform](https://simplex.chat/docs/simplex.html)
- [Matrix Specification](https://spec.matrix.org/)
- [IETF RFC 9420 MLS](https://www.ietf.org/rfc/rfc9420)
- [Secure Scuttlebutt Protocol Guide](https://ssbc.github.io/scuttlebutt-protocol-guide/)

## 4. Recommended First Implementation

Implement a local minting feature before researching transport further.

### 4.1 Files To Add Or Change

Likely files:

```text
ai-archive-kit/specs/zettel.md
ai-archive-kit/specs/zettel-lifecycle.md
ai-archive-kit/specs/zettel-kasten.md
ai-archive-kit/zettel-kasten/actions.yml
ai-archive-kit/zettel-kasten/policies.yml
ai-archive-kit/zettel-kasten/zettel-rules.yml
ai-archive-kit/schemas/mint-receipt.schema.json
ai-archive-kit/cli/archive.py
ai-archive-kit/src/...
ai-archive-kit/tests/...
```

### 4.2 CLI Shape

Preferred user-facing command:

```text
archive mint-zettel <archive> --draft <draft-id-or-path> --reviewed-by <person-id> --approve
```

Potential compatibility alias:

```text
archive promote-zettel ...
```

Internally, both can use one action model:

```text
action_id: mint_zettel
legacy_alias: promote_zettel
```

### 4.3 Mint Receipt Shape

Minimum:

```json
{
  "receipt_id": "receipt:mint:20260522:example",
  "action": "mint_zettel",
  "archive_id": "archive:personal:example",
  "actor": "person:example",
  "reviewed_by": "person:example",
  "created_at": "2026-05-22T00:00:00+09:00",
  "input": {
    "draft_path": "inbox/zet_example.md",
    "draft_sha256": "..."
  },
  "output": {
    "zet_id": "zet_example",
    "canonical_path": "zettels/zet_example.md",
    "body_sha256": "...",
    "envelope_sha256": "..."
  },
  "source_refs": [],
  "edges": [],
  "local_ai_sessions": [],
  "checklist": {
    "version": "zettel-promotion/v0.2",
    "passed": true
  },
  "side_effects": {
    "draft_snapshot_path": "receipts/mint/drafts/zet_example.md",
    "index_updated": true
  }
}
```

### 4.4 Doctor Checks

Add checks:

- canonical minted zets have receipts,
- receipt hashes match draft snapshot and canonical output,
- source refs are valid,
- edges use allowed types,
- local AI session refs are local or imported source records,
- no external AI share URL is treated as local AI provenance,
- provider URLs are not used as canonical object references.

## 5. What Not To Build Yet

Do not build yet:

- P2P networking,
- relay server,
- mobile app,
- group E2EE,
- CRDT shared editor,
- blockchain anchoring,
- DID method,
- UCAN-compatible full authorization,
- Nostr event bridge,
- Matrix bridge.

These are future layers.

The first proof is local:

```text
Can the archive turn a user-supervised AI draft into durable, private, verifiable memory?
```

## 6. Architectural Bet

The core bet is:

```text
If the minting transaction is correct,
then sharing, collaboration, lineage, and Web3-like behavior can be built as layers.
```

If minting is weak, the later `zet` service becomes just another messenger or social app.

Therefore, the next implementation should protect the minting path.

