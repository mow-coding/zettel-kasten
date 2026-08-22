# v0.4.4 R2 formal adoption implementation — 2026-08-23

## Scope and safety boundary

The user-approved v0.4.4 plan requires two results beyond emergency byte
preservation:

1. query the 19,055 known R2 keys with real provider HEAD evidence and formally
   adopt only verified, non-conflicting Objet definitions;
2. classify the 1,149 duplicate-definition groups by evidence rule and leave
   ambiguous metadata decisions at a human review boundary.

Development stayed in the dedicated `codex/v044-r2` worktree. No Basoon file,
provider object, credential value, release, or installed runtime was changed.
The only real-data access was aggregate read-only planning.

## Implemented product behavior

- `object-storage-adopt-existing --formal-adoption` extends the existing command
  family; no top-level command was added.
- A validated exact key map is hashed and bound to the common
  `ExactOperationManifest`.
- Every mapped object gets one deterministic receipt target and item checkpoint.
  The writer performs a privacy-safe HEAD presence/size query before recording
  evidence, and the independent verifier performs a second HEAD.
- Provider absence, provider unavailability, and size mismatch fail closed
  before a formal manifest location is added. The formal-adoption path never
  calls PUT.
- Receipt fields explicitly say that presence+size is not a content hash and
  that the provider's original upload time is unknown.
- Eligible locations are projected into `objects/manifests/files.jsonl` in one
  locked, atomic pass. The old per-object full-manifest rewrite is not used.
- Resume uses the common append-only checkpoint chain and a private deterministic
  control document. Receipts are create-or-match immutable. Revert removes only
  operation-owned receipt/location fields.
- Conflict groups are fingerprinted by their complete evidence-rule set.
  Optional JSONL batch judgments accept only `defer_review` and
  `keep_definitions_distinct`. Neither decision merges definitions nor formally
  adopts a conflict group.
- A source and packaged JSON Schema validate formal-adoption receipts.

## Durable evidence binding

The branch incorporated the common optional `operation_evidence` contract.
Every formal-adoption manifest and its final common receipt bind these named
counts:

- manifest rows;
- unique objects;
- conflicting definitions;
- emergency byte-preservation candidates;
- planned remote queries;
- planned formal adoptions;
- existing formal adoptions to reverify;
- strict manifest-scope remote-key evidence;
- official deduplicated WOM upload evidence.

The same durable document binds the source-inventory, exact-key-map, and
conflict-batch-set SHA-256 values. Legacy exact manifests that omit
`operation_evidence` keep their prior bytes and digest contract.

## Actual read-only evidence

The actual aggregate plan reproduced:

- 23,580 manifest rows;
- 22,431 unique objects;
- 19,055 exact key-map/remote-query targets;
- 17,348 pending formal-adoption targets;
- 558 existing exact-key formal adoptions to reverify;
- 1,149 conflict groups;
- 3,374 emergency byte-preservation candidates;
- 597 strict manifest-scope verified-key objects;
- 560 official deduplicated WOM-upload evidence objects;
- zero mapped keys missing from the manifest.

The 1,149 conflict groups formed four deterministic evidence batches of 37, 2,
1,001, and 109 groups. Automatic merge and conflict formal adoption remained
zero.

Read-only planning made zero provider calls and zero writes. It completed in
22.888 seconds with a 237.47 MiB measured peak while constructing the 19,056
item exact manifest.

## Checkpoint scale and verification

The verified common checkpoint linearization commits were incorporated instead
of reimplementing them. At the exact R2 scale of 19,056 effects and 57,168
checkpoints, the synthetic benchmark:

- completed;
- used exactly two full checkpoint-file scans;
- created one checkpoint-directory durability sync;
- produced first status in 0.015 seconds;
- kept the maximum progress gap at 4.032 seconds;
- completed in 213.203 seconds at 268.139 checkpoints/second.

The deliberately chosen 180-second benchmark bound was missed. This is not
hidden: the algorithm is linear and the durability/progress gates passed, but
the measured Windows fsync workload took about 3 minutes 33 seconds. Provider
HEAD latency remains unmeasured until release, supported installation, native
approval, and the authorized live acceptance run.

Focused verification passed:

- 29 common exact/checkpoint tests with 16 subtests;
- 28 R2 preservation/adoption/resource tests with 164 subtests;
- adapter, mismatch-before-write, immutable receipt, one-pass manifest,
  independent HEAD, control reload, CLI dry-run privacy, and packaged schema
  coverage.

## Remaining evidence boundary

Code and synthetic execution are complete for this slice. It is not yet a live
v0.4.4 recovery result. Remaining blockers are intentionally external:

1. merge into the release integration branch;
2. release/package/install verification;
3. native approval of the exact 19,055-target manifest;
4. live R2 HEAD execution and independent provider verification;
5. supported Basoon manifest projection;
6. final receipt inspection and remote Git backup.

No feedback letter is resolved by this development-only result.

