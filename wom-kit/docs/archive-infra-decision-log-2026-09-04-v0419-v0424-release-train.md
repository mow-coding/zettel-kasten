# Decision Log — v0.4.19-v0.4.24 Recovery And Operations Train

Date: 2026-09-04
Status: accepted

## Context

Repeated client reports showed that release availability, runtime state,
diagnostic readiness, actual dispatch, archive ownership, credential reuse,
provider recovery, and cleanup could contradict one another. Combining every
repair in one release would make unrelated external failures block completed
local safety work.

## Decisions

1. Ship six ordered, independently testable releases from v0.4.19 through
   v0.4.24. Each release must leave one usable operating result, not only a new
   inspection command.
2. Establish one truth source before adding more writers: v0.4.19 separates
   `passed`, `failed`, `not_reached`, and `unavailable` observations and makes
   capability, preview, dispatch, runtime, and Doctor surfaces agree.
3. Bind every new writer after v0.4.20 to opaque app, workstream, and session
   references. Keep display labels in an ignored private registry and serialize
   all archive writes with the existing OS lock.
4. Keep approval target previews local-only. The main dialog shows a count;
   paged detail shows comprehensible titles or safe fallbacks without placing
   those values in public evidence.
5. Reuse secrets only through a Windows credential broker scoped to the exact
   archive, provider, account or workspace, and bucket. Never pass secrets by
   chat, command arguments, environment, files, logs, receipts, or screenshots.
6. A local object may be offloaded only after a complete remote GET reproduces
   its object digest and every retention and filesystem-safety predicate passes.
   WOM never automatically deletes the remote object.
7. Historical artifacts receive an approved responsibility assignment, never
   invented creation provenance.
8. Publishing code does not resolve beta feedback. Resolution requires a
   client-run receipt and an independent check of the real result.

## Consequences

- External Notion or R2 failures cannot delay an already complete runtime or
  session-safety release.
- A person sees meaningful choices while WOM performs counting, hashing,
  pagination, checkpoint selection, and resume mechanics.
- Public evidence remains useful without leaking private labels or provider
  scope values.
- Release cleanup and the client-validation boundary are explicit completion
  criteria rather than optional follow-up work.

