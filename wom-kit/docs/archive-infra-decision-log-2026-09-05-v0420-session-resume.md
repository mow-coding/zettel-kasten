# Session resume preserves original human authority

## Context

Session ownership preparation must not invalidate older approvals or require a
person to reconstruct hashes, reviewer strings and checkpoint identifiers after
a process exits. A stored manifest alone is not evidence that anyone approved
it. The existing broker authenticates claims against the full original context.

## Decisions

1. Reuse the existing archive OS lock, native broker, authenticated claim,
   exact runner, checkpoint and terminal receipt. Do not add a competing lease
   or a new approval system.
2. Acquire the archive lock before planning and native review. A waiting caller
   can cancel; acquisition requires fresh state observation before approval.
3. Save the exact prepared payload and original content-free context in the
   ignored private registry after approval and before claim publication. The
   reviewer claim remains a claim, not Windows identity attestation. Preserve
   the original values; do not infer them from hashes or new session metadata.
4. Pure prepared payloads retain their old byte format. A missing context is a
   blocker, not permission to upgrade or overwrite an existing payload. Even a
   self-consistently rehashed context must match its existing authenticated claim.
5. Resume a started claim with a real checkpoint through the existing strict
   checkpoint validator. A reachable started-before-first-checkpoint cut is a
   different branch: require the exact current predecessor, absent immutable
   target and absent final receipt before beginning the original exact runner.
   Report this preimage evidence separately; do not claim a nonexistent chain
   was validated or manufacture old success evidence.
6. An authenticated succeeded claim never reopens the domain writer. Recheck
   the existing terminal receipt, claim MAC and immutable target independently.
   Later unrelated registry generations do not change historical authority.
7. Retain ancestor directories throughout registry and historical generation
   reads. On POSIX read relative to the retained descriptor; on Windows retain
   the existing no-delete-sharing handles. Unavailable observations are not
   empty registries. Count pending entries toward bounded directory scans too.
8. Show app/workstream labels only through the existing memory-only target
   collection. Persist opaque references and label digests in public evidence,
   not duplicate titles in receipts or JSON. Reobserve the exact registry before
   approval; sensitive previews may be omitted without losing target identity.

## Evidence and remaining integration

The combined execution/preview group passed 37 tests and 37 subtests. After
additional original-reviewer substitution and ambiguous-claim cases, all 13
execution tests passed. These use real claims, filesystem writes, checkpoints
and MAC verification with synthetic native/key input only. All three genuine
child-exit/fresh-process-resume tests then passed in 79.16 seconds, covering
started-before-checkpoint, post-publication and succeeded-before-output cuts.
The parent independently reacquired the OS lock and verified the original
claim, terminal MAC and disk generation. POSIX-specific
retained-parent race tests still require Linux execution.

This is an internal integration checkpoint, not a public release. Public CLI
and MCP routing, app installation attachment, task-scoped payload discovery,
all-writer scope enforcement and installed-wheel session journeys remain open.
No private client archive, credential, provider or feedback ledger was changed.

See [integration minutes](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).
