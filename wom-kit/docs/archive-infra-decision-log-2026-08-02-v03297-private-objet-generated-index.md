# Decision: Keep private objet rediscovery durable authority separate from its generated index

Date: 2026-08-02
Status: accepted for v0.3.297

## Context

v0.3.296 can append one human-reviewed private objet source-metadata row and
its immutable receipt. That makes the observation durable, but it deliberately
does not create a queryable index or prove that a later generated projection
still represents the same authority.

Letter 105 showed that public-only indexing cannot rediscover an objet from
its reviewed original name. The first safe step is therefore not to expose a
finder. It is to build and validate a private generated layer whose freshness
can be proved without placing private names or digests in public output.

## Decision

v0.3.297 adds exactly four generated tables to the existing
`db/archive-index.sqlite` database. The private manifest and receipts remain
the durable authority; the SQLite rows are disposable and may always be
rebuilt.

The existing `archive index` operation:

1. captures and validates the complete private authority;
2. compiles deterministic aliases and two audience-safe projections;
3. rebuilds inherited public and new private rows in one transaction;
4. proves the exact schema, counts, row digests, and foreign keys;
5. requires unchanged authority snapshot A/B; and
6. writes the fingerprint-bearing singleton last before one final commit.

Windows uses the existing retained mutation guard and persistent lock order:
object manifest, then private metadata. Non-Windows uses exact A/B snapshots
and does not imitate those Win32 guarantees.

The existing `archive index-health --dry-run` operation adds one closed,
content-free private envelope. It uses an opaque `mode=ro` pinned session and
classifies the complete state with a strict eleven-row decision table.

The exact schema boundary rejects every persisted view or trigger that refers
to a private table, including triggers owned by inherited public tables. When
the stored fingerprint equals live authority, health recompiles the projection
from that authority and exact-compares all rows plus the singleton rather than
trusting mutually rewritten stored digests.

The read session opens a WAL-advertising database only when a coherent WAL/SHM
pair already exists. Otherwise it returns closed projection-unavailable
evidence before opening SQLite or consuming private queries and creates no
sidecar to make the check pass.

## Consequences

- Approved private metadata becomes deterministically indexable without
  changing its durable authority.
- A negative lookup still cannot be treated as complete until the generated
  projection is valid and current.
- v0.3.297 exposes no finder, search result, new CLI command, or new MCP tool.
- Output can distinguish missing, invalid, unavailable, stale, empty-current,
  and nonempty-current states without exposing private identifiers or hashes.
- A clean WAL database without its coherent sidecar pair is intentionally
  unavailable to the private reader; health does not create those files or
  silently substitute an immutable snapshot.
- Pre-commit failure preserves the prior snapshot. Post-commit output failure
  returns failure to the caller while fresh health reports the committed
  truth.
- Health is not evidence of objet bytes, provider availability, source
  coverage, external-store completeness, or global privacy cleanliness.

## Follow-up

v0.3.298 may consume aliases and safe projections only when private health is
exact nonempty current. v0.3.299 separately addresses source-reference
coverage versus storage integrity. v0.3.302 retains the inherited public
privacy-cleanup gate.

## Longer record

See:

- `meeting-minutes/2026-07-31-v03297-private-objet-metadata-index-directive.md`;
- `meeting-minutes/2026-08-02-v03297-private-objet-metadata-index-implementation.md`; and
- `meeting-minutes/2026-07-31-letter105-v03296-v03299-release-reslicing-decision.md`.
