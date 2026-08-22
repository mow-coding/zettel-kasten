# Archive infrastructure decision — R2 formal adoption as receipts plus one projection

Date: 2026-08-23
Status: implemented and synthetically verified; live acceptance pending

## Context

The legacy R2 adopter issued a HEAD and then rewrote the entire central object
manifest once per object. At 19,055 mapped objects this made the local mutation
path quadratic and left the public approval mode closed. Duplicate manifest
definitions also required a rule-based review boundary rather than an unsafe
same-digest auto-merge.

## Decision

- Extend `object-storage-adopt-existing` with an explicit
  `--formal-adoption` mode.
- Bind the exact key map, source projection, receipt effects, final manifest
  location projection, aggregate counts, and classification digests to one
  native-approved `ExactOperationManifest`.
- Record one immutable HEAD evidence receipt and common checkpoint per mapped
  object.
- Require writer-side and independent presence/size HEAD evidence. Never claim
  a content hash or original provider upload timestamp from HEAD.
- Make zero provider PUT calls in formal adoption.
- Add all eligible non-conflicting locations through one locked atomic central
  manifest rewrite. Keep per-object central rewrites at zero.
- Classify duplicate definitions into fingerprinted evidence batches. Human
  judgments may defer or preserve distinct metadata definitions; neither action
  auto-merges or auto-adopts conflicts.
- Carry the locked 23,580/22,431/1,149/3,374/597/560 accounting and source,
  key-map, and conflict-batch digests into the common final operation receipt.
- Reuse the verified common checkpoint linearization rather than introducing a
  domain-specific journal.

## Consequences

The formal-adoption path is resumable, exact, privacy-safe, and linear in local
manifest work. A provider mismatch cannot create a gating manifest location.
The 1,149 conflicting definitions remain explicit review debt rather than being
silently normalized.

Presence+size adoption is intentionally weaker than whole-object checksum
verification. The emergency bytes-preservation path supplies HEAD plus full GET
rehash for local-only bytes; formal adoption preserves the historical 158 GB
cost boundary and records its narrower evidence honestly.

Live provider and Basoon completion evidence remains pending release,
installation, native approval, and authorized application.

