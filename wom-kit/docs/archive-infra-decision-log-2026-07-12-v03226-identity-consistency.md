# Decision Log: Archive Identity Consistency And Reviewed Repair

Date: 2026-07-12
Decision: accepted for v0.3.226

## Context

A real archive can retain template or stale duplicate metadata across
`archive.yml` and `archive-identity.yml`. Returning whichever value a function
happens to read first makes an AI operator appear confident while the archive
still contains two conflicting declarations.

## Decision

- `archive.yml principal` is the archive principal declaration.
- `archive-identity.yml` is the identity and ownership core.
- Duplicated principal metadata must agree and is diagnosed in quick runtime
  context, AI start-here, and Doctor.
- New archive initialization must replace template identity id/display values
  with the reviewed archive and principal values.
- Different principal or archive identities are never automatically repaired.
- A same-principal display mismatch or missing/template identity id may be
  proposed by a content-free dry-run.
- Approval must bind the exact archive, current identity, and proposed identity
  SHA-256 digests and include attributed human review plus explicit affirmation.
- Approval edits only `archive-identity.yml`; it writes a value-free receipt
  after digest verification and rolls back exact bytes on handled failure.

## Consequences

AI operators receive one consistent warning and one safe next command without
a full archive scan. Archives are not migrated automatically. YAML formatting
may normalize during an approved repair, and forced termination remains beyond
the in-process rollback guarantee.
