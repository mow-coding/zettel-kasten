# Archive Infra Decision Log - v0.3.257 Strict Revision Boundary

Date: 2026-07-17

Status: accepted for v0.3.257 implementation and release

## Context

v0.3.256 established a fail-closed content boundary for ordinary zettel reads.
The follow-up audit found revision and restore workflows that still read and
fingerprinted raw bytes before complete schema, identity, archive, and lifecycle
validation. A first combined repair also changed mutation infrastructure and
was stopped when independent review found Linux/Docker and hard-exit regressions.

## Decision

1. v0.3.257 is restricted to revision and restore validation ordering.
2. Approval YAML rejects duplicate/non-string keys and accepts only a bounded,
   acyclic JSON value tree (with the existing ISO timestamp normalization),
   while tolerant import/capture parsing remains unchanged.
3. A zettel snapshot returns bytes only after a bounded regular-file read,
   stable opened-generation checks, UTF-8/frontmatter parsing, schema validation,
   and exact id/archive/status checks.
4. Revision and restore plans, writes, recovery, receipt verification, history
   audit, and restore materialization may derive hashes or equality only from
   that successful snapshot.
5. Rejected zettel evidence is represented by fixed blockers and null/false
   evidence fields. Private content is never included in the result.
6. Publisher, lock, canonical replacement, rollback, and recovery algorithms
   are not redesigned in this release. Recoverable mutation infrastructure is a
   separate batch with a separate review contract.

## Consequences

- Valid revision/restore behavior and public schemas remain compatible.
- Ambiguous or invalid zettels stop earlier and may no longer produce the hash
  operators previously saw for those bytes.
- Restore materialization validates before creating its scratch directory, so
  a rejected source does not leave a new empty working directory.
- The smaller diff can be tested and reviewed without inheriting the unproven
  cross-platform mutation helpers from the combined checkpoint.

## Verification Contract

- Regressions must prove rejected bytes never reach SHA-256 derivation and
  produce no plan/state/equality evidence.
- Existing revision and restore plan, apply, recovery, receipt, and audit tests
  must remain green.
- An independent reviewer must find no unresolved P0/P1 within this scoped diff.
- Full tests, resource synchronization, release-readiness checks, wheel install,
  tag/release publication, and public reinstall must pass before completion.
