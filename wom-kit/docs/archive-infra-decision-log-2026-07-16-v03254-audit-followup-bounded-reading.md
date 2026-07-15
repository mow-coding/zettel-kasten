# Archive Infra Decision Log - v0.3.254 Audit Follow-Up And Bounded Reading

Date: 2026-07-16
Status: accepted for v0.3.254 after development-session re-review

## Context

An independent Claude Opus 4.8 audit of v0.3.253 found one stale safety-facing
upload description, several doctrine-to-behavior regression gaps, a bounded
handoff claim that needed clearer scope, missing raw-byte preservation evidence
for transcoded text inputs, and no bounded continuation contract for one large
zet body.

The first implementation attempt happened in the wrong client-support session.
Its uncommitted diff was therefore treated only as a candidate and reviewed
again in the WOM development session.

## Decision

Adopt the candidate selectively, with these development-session corrections:

1. Preserve the default full-body `read-zettel` contract.
2. Add opt-in Unicode code-point JSON pages. Cursor zero returns the complete
   decoded-body hash; every nonzero cursor requires that exact hash.
3. Reject a changed body before returning a continuation page.
4. Treat a consistent object-manifest identity for changed pre-normalization
   text bytes as preservation coverage, not as current byte-availability proof.
5. Keep AI artifact discovery restricted to its existing allowlist, but state
   that limitation in results and new handoff receipts.
6. Preserve compatibility with existing valid handoff receipts.
7. Keep the accepted v0.3.203 node-first decision text intact. Record the
   current public terminology resolution as a dated follow-up instead of
   rewriting the historical decision.
8. Add behavioral regressions for stale indexes, matching titles, and MOW local
   namespaces without adding a new generated map or MOW dependency.

## Rejected Alternatives

- Do not scan the whole archive for every possible AI-generated file.
- Do not recreate or automatically capture original transcript bytes from
  normalized derived text.
- Do not add an opaque stateful continuation-token subsystem for one zet body.
- Do not rename schemas, command names, output keys, receipts, or historical
  release records to resolve the public `node` terminology boundary.
- Do not treat documentation phrase checks as behavioral proof.

## Consequences

- Hosts can bound one large body read while retaining version integrity.
- Existing full-body clients require no change.
- Old archives may receive a new read-only warning when exact transcoded input
  bytes have no manifested objet identity; this is a review queue, not an
  automatic migration.
- Session handoff readiness remains useful but cannot be presented as an
  archive-wide absence claim.
- Audit provenance remains visible without transferring implementation or
  release authority to the reviewer.
