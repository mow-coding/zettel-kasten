# Letters 098-111 Integrated Completion

Status: implemented for WOM-kit v0.3.300

This checkpoint finishes the source-confirmed public implementation work that
remained after Letters 098-110 and incorporates Letter 111 in the same release
train. It deliberately avoids one-letter micro-releases.

## What Is Implemented

### Safer operator feedback

`operator-feedback-record` now distinguishes `create` from `update`.
Creation can never overwrite an existing id. Updating requires the exact
current record SHA-256 and cannot change the original feedback reference.
A per-id operating-system lock and atomic create-if-absent close same-id
multi-process races. Updates preserve omitted title, related-release, and
delivery/acknowledgment timestamps instead of erasing lifecycle evidence.

### Archive-root path authority

Relative paths for `objet-capture --selection`,
`project-intake-plan --staged-folder`, and
`project-intake-unpack-queue --staged-folder` resolve from the archive root,
not the shell's current directory. Absolute-path compatibility remains.

### Bounded batch Objet capture

`objet-capture-batch` validates a complete archive-local request before source
bytes are opened. It accepts up to 2,000 reviewed items and titles up to 2,000
characters, produces one deterministic selection and plan hash, and reuses the
existing capture engine. Its guarantee is bounded per-item convergence with
safe replay, not transaction-wide atomicity.

### Provider-neutral external locators

The external-locator command family records multiple typed human-reviewed
coordinates without reflecting their private values in command output.
Recovery plans expose only safe digest identities and never claim that a
stored locator proves current remote reachability. Every addition has an
exact prior-state revert path.

### Relation candidates and durable judgment

The relation-candidate planner uses local frontmatter coordinates and reads no
body. A human must decide whether to accept or reject each candidate and, on
acceptance, must name the edge type. Rejections become durable suppression
evidence. Accepted edges pass through the mature edge writer and are re-read
after writing.

The semantics guide keeps these concepts separate:

- `continues`: next installment in the same thought or work, including the
  next week of the same course;
- `sequence`: next reviewed step in a generic administrative, operational, or
  life-event process;
- recurring program instance: recurrence alone does not prove continuation;
- third-party Principal: archive owner and subject are not silently merged,
  and a reviewed actor is registered before becoming an edge target;
- format variant: alternate rendition of the same intellectual content after
  human confirmation.

`sequence` is now an active directed base edge type. Like `format_variant`, it
is never inferred or batch-written: one human reviews and approves each pair.
A stale vendored `types.yml` can adopt only a named base type with repeated
`--link-type` options. The same exact receipt can later drive a partial revert,
but only while every selected record is unchanged and unused.

Third-party Principal records live in `principals/*.yml`; the owner remains in
`archive.yml`. `principal-register-plan`, `principal-register`,
`principal-list`, `principal-unregister-plan`, and `principal-unregister`
provide a digest-bound lifecycle. Unregistration blocks while an edge still
targets the Principal. `archive index` projects both owner and registered
third parties into the disposable SQLite `principals` table.

A recurring program uses `facets.recurring_series` as a shared coordinate, not
an automatically created relation. Multiple zets from one occurrence use
`activity_group` only after the reviewed event-anchor zet exists. Private
Notion recovery joins use exact `facets.source_page_id`; a similarly named
mirror-zettel field is never a substitute because it can silently drop rows.

### Reviewed markup normalization

The markup command family supports explicit `preserve` or reviewed
`normalize` policy. Normalization removes migration-only empty markers and
wrappers while preserving visible text and compatible inline HTML. Unknown
semantic tags always block.

Reference tags such as file, media, mention, and synced-ref require a reviewed
archive-local binding manifest. Each exact tag SHA-256 must point to an
already-existing active external locator or source-zettel edge. Replacement
Markdown contains only a digest-based WOM URI, never the private source
coordinate.

Before the first canonical mutation, the writer preserves both exact before
and after bytes and publishes a transaction journal. A stopped run can be
resumed or rolled back with a new deterministic recovery plan and explicit
approval. A completed run can be reverted to the exact prior bytes from its
receipt.

### Derived project bytecode repair

The bytecode repair command family inspects only the verified project-local
source mirror and only the runtime package. It refuses tracked, linked,
reparse, or special bytecode entries. Approval deletes verified untracked
`.pyc`/`.pyo` bytes and then empty `__pycache__` directories without modifying
source files.

### Faster complete CI

Pull-request tests are assigned to deterministic, complete, unique shards
across Ubuntu Python 3.12, Ubuntu Python 3.10, and Windows Python 3.12. The
two pytest-native Windows authority modules run once rather than once per
shard. One stable `Required CI` job aggregates every gate and shard.

## Commands

```text
external-locator-plan
external-locator-record
external-locator-recovery-plan
external-locator-revert
relation-semantics-guide
relation-candidate-plan
relation-candidate-decide
principal-register-plan
principal-register
principal-list
principal-unregister-plan
principal-unregister
markup-style-guide
markup-normalization-plan
markup-normalization
markup-normalization-recovery
markup-normalization-revert
objet-capture-batch
project-bytecode-repair-plan
project-bytecode-repair
migrate --target base-link-types --link-type <type> [--revert]
```

Every modifying command is CLI-only, requires explicit human review, and
revalidates a fresh plan under the relevant lock before writing.
Repeated base-link-type adoption/revert cycles advance a validated receipt
generation, so the second cycle cannot collide with the first cycle's
deterministic receipt paths.

## Honest Remaining Boundaries

- External host adoption and provider-specific live recovery remain external
  integration work.
- No private client corpus was opened or modified while building this public
  implementation. Scale checks use synthetic 508-item and 3,514-zettel data.
- The reported edge-count discrepancy still needs a sanitized reproduction
  before source code can determine whether it is a product bug, stale index,
  or client-specific data condition.
- A green local suite is engineering evidence. Real-use validation begins only
  after the integrated release is installed and independently exercised.
