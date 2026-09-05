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
9. One app installation can host simultaneous tasks. Require an explicit
   opaque task route beneath the existing app selector, never a newest/current
   default. New task decisions bind its archive/app/route digest in existing
   manifest evidence. Legacy approvals keep their original bytes and resume
   path; do not add a current route to an old approval.
10. Keep original pending and last-completed selectors in the same private
    actor CAS image. After verified completion, atomically retain the original
    completed pointer while releasing the pending gate. Output loss after that
    save must still find the same receipt. Optional-field omission by old
    callers preserves completion pointers; explicit null cannot erase them.
11. A completed pointer is not proof. Completed-only resume rejects a started
    claim and can only verify an original succeeded claim, terminal MAC,
    receipt and immutable target. Pending registry work cannot fall through to
    an older completed human decision. Fresh writes independently check the
    caller's selected session and actual current claimed binding.
12. Persist the pending selector after the native decision and original bundle
    save, before authenticated claim publication. Revalidate the original
    source/context/manifest/predecessor and OS lock after the callback. A cut
    before claim publication is not approved work; a native re-review path is
    required before this branch can become a complete public recovery flow.

## Original claim composition amendment

New task claims retain their original human-create manifest/context selector
inside the existing private registry intent. Pending and completed continuation
authenticate that original receipt and its app, task route and session. A
private selector or a rehashed intent alone is not sufficient. Completed
continuation is read-only and must separately prove current claimed ownership;
a later pause does not erase the verified historical commit.

Old intents without the optional origin retain their exact bytes and existing
low-level observation. The task facade does not retroactively assign them an
original human route. A copied completed selector from another route is refused.
No new approval protocol, claim token input or duplicate claim is introduced.

## Original pre-claim re-review amendment

An explicitly requested re-review may redisplay only the original pending
human decision whose authenticated claim is genuinely absent. Failed, corrupt
or ambiguous claims are blockers, not absence. An existing claim uses original
resume and does not reopen the approval window. No new manifest, reviewer,
label, task route or approval identifier is accepted by this recovery path.

Presence discovery must finish its key consumer before the broker is invoked.
After the native decision, rescan for claims and revalidate the original
actor, bundle, predecessor and target before entering claim publication. Keep
publication checks independent of nested key consumers. Continue through the
existing runner and terminal verification, preserving original authority.

The source-level re-review cohort passed twelve tests in an independent root
run, including genuine pre-claim and post-claim process exits. Public routing
and the installed package journey remain separate, unfinished acceptance gates.

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

The later task lifecycle/ownership integration passed 19 tests in 51.081
seconds, including an actual exit after final actor save and a new process
recovering its original completed receipt without rewriting bytes. Independent
review found and helped correct same-app cross-route pointer substitution and
old-image optional-field migration. These are source-level regression results,
not installed-wheel or client completion evidence.

This is an internal integration checkpoint, not a public release. Public CLI
and MCP routing, app installation attachment, task-scoped payload discovery,
all-writer scope enforcement and installed-wheel session journeys remain open.
No private client archive, credential, provider or feedback ledger was changed.

See [integration minutes](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).
