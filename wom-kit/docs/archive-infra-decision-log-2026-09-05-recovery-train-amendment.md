# Decision amendment: recovery outcomes before release claims

Date: 2026-09-05
Status: accepted; implementation in progress

## Context

A full feedback-history reassessment found both real client successes and
regressions hidden by command-level release checks. At reassessment the candidate
rejected benign directory allocation-size changes, prepared a runtime before a
same-version no-op, and used tiny object bytes in its count-scale benchmark.

## Decisions

1. Preserve the six-release order and existing implementation. Do not prioritize
   a visible feature ahead of the foundation it needs to complete safely.
2. Distinguish implemented, development-verified, released, client-executed, and
   independently verified. Keep client lifecycle decisions in the client project.
3. Move common target preview and usable session-scoped Git backup into v0.4.20.
   v0.4.21 real data repairs depend on verified pre- and post-change backups.
4. Keep existing approved manifests, claims, checkpoints, and receipts immutable
   across session migration. Responsibility assignment is not creation provenance
   and never changes past approval authority.
5. Restore omitted local outcomes: source-property backfill, draft discard and
   restore, semantic revision and restore, batch publication/retirement/edges,
   object-link outcomes, and field-scoped revert for every repaired domain.
6. Preserve successful older capture/context/search paths. Withdrawn reports do
   not become new feature requirements. Distinct Notion recovery cohorts retain
   distinct denominators and final outcomes.
7. Use published-wheel user journeys and fault injection as release gates. Keep
   operational Doctor's 180-second target; describe count-scale and deep-byte
   throughput evidence separately rather than claiming equivalence.
8. Limit automatic predecessor recovery to proven released states and reachable
   interruption prefixes. Unknown/tampered evidence remains preserved for review.
9. Measure startup from the public process, not just the command handler. A
   small CLI entrypoint may report a fixed preparation state while loading the
   existing implementation. It grants no authority and must preserve quiet
   modes, JSON stdout, cancellation, and legacy entrypoint compatibility.
   An observational heartbeat child must have no domain arguments or authority,
   inherit no archive locks, close on parent loss, and be joined before progress
   handoff. Keep the existing noninteractive Windows launch policy.
10. Centralize command availability without changing established public action
    identifiers or parsed output defaults. A closed writer is refused before
    private prerequisite inspection. Contended, unavailable, changed and
    unsupported native operations remain different observations; none implies
    permission to repair, seize a lock or mint replacement approval authority.
11. Mutable convenience views are not approved evidence. Reconstruct and detach
    Git execution state through its existing strict bundle decoder, retain exact
    legacy serialization, and recheck factory context before the writer starts.
    Completed predecessor cleanup remains separate from prewrite recovery; only
    authenticated matching evidence, not a phase label alone, permits effects.

## Consequences

The train gains stronger end-to-end acceptance without another approval system,
an indiscriminate reopening of closed commands, or an extra release series.
Public source and synthetic tests can proceed while private client application
remains outside developer authority.

The subprocess boundary follows the [CPython 3.12 subprocess contract](https://docs.python.org/3.12/library/subprocess.html#popen-constructor):
explicit pipes, a minimal valid environment, `close_fds`, no shell, and bounded
child reaping. This is a liveness aid, not another operation runner or an excuse
to call loading progress successful work.

See the [acceptance register](recovery-operations-acceptance.md) and
[conversation record](../../meeting-minutes/2026-09-05-recovery-train-reassessment.md).
