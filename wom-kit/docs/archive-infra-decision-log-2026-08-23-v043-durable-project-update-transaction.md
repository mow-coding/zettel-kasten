# v0.4.3 durable project update transaction

Date: 2026-08-23

Status: accepted architecture; service integration and full CI remain pending.

Related minutes:

- `meeting-minutes/2026-08-23-v043-integration-and-release-readiness.md`
- `meeting-minutes/2026-08-23-v043-same-computer-client-runtime-scope.md`

## Context

`project-version-update` must prepare a complete project-local WOM runtime,
receive one exact native human approval, survive process or power loss, and
never make a shared `archive.exe` on `PATH` the project's active runtime.

The pre-v0.4.3 updater still had three unsafe phase boundaries:

- post-approval Git could resolve a mutable executable through `PATH`;
- post-approval runtime materialization could execute Python or obtain bytes;
- a receipt embedding the newly created approval id could not be an exact
  preapproval postimage.

## Decision

Use one two-stage transaction with this fixed order:

1. reserve a transaction reference and timestamp;
2. acquire the exclusive project update lock bound to the reservation;
3. use one held trusted Git executable and finish all transport work;
4. build, execute, verify, recursively flush, and seal a complete runtime
   candidate inside the transaction;
5. seal exact bindings, component preimages and postimages, the private Git
   binding, the runtime candidate inventory, and a deterministic static update
   receipt;
6. bind the immutable intent back to the unchanged reservation lock;
7. request one native digest-bound human approval;
8. perform only local, static, no-copy/no-child/no-network domain changes;
9. verify all component postimages and record `domain_committed`;
10. durably finalize the approval claim as `succeeded`;
11. append content-free succeeded-claim evidence, mark ready to unlock, remove
    the exact lock, verify durable absence, and complete the journal.

The static project update receipt contains the reserved transaction reference
and timestamp plus the exact domain-operation manifest and target-set digests.
Those domain digests deliberately exclude the receipt evidence component, so
the receipt can be built in one deterministic pass without hashing itself.
The final native approval context is a separate digest that additionally binds
the sealed transaction intent, static receipt, runtime candidate, and trusted
Git runner. The receipt does not contain that final self-referential approval
digest, the dynamic approval id, or the claim MAC. Dynamic claim values are
represented only by content-free digests in the hash-chained transaction
journal after the authenticated claim is durably succeeded.

## Recovery

- A crash while the claim is `started` reopens the same claim and resumes from
  an exact transaction checkpoint without a second native approval.
- A crash after the claim becomes `succeeded` uses a separate tail-recovery
  path. It does not display native approval and does not re-enter the domain
  writer; it only authenticates the succeeded claim and finishes the bounded
  journal/unlock tail.
- Partial or unknown runtime candidates, ambiguous promotions, torn journals,
  changed locks, and unknown component states remain locked for manual review.
- Automatic rollback or cleanup is allowed only for exact-owned, exact-matching
  fields or trees whose recovery evidence remains durable.

## Consequences

- Normal cancellation leaves no persistent domain effect and removes only
  exact-owned preapproval candidate/control-scaffold state after verified
  cleanup. A transient empty runtime parent may be created before approval to
  bind same-volume and no-replace promotion authority; public evidence reports
  that control write separately and never describes it as installed runtime
  content or activation.
- A successful project update changes only the selected project's runtime and
  pin. Other projects and the shared `archive.exe` remain unchanged.
- The project update receipt and approval evidence are independently verifiable
  without storing absolute paths, credentials, reviewer text, or archive body
  content in public output.
- v0.4.3 remains unreleased until service integration, hard-exit recovery
  tests, full Windows and Ubuntu CI, wheel verification, and the planned
  Letter 138 drill complete.

## Local Git command boundary

The held Git executable is not sufficient by itself. After resolution, the
runner admits only the local plumbing subcommands used by the sealed updater.
Transport-like alternate surfaces such as `remote update` and
`archive --remote`, checkout-like porcelain, repository filters/textconv, and
write-capable config/hash-object variants fail closed. The approved updater
continues to materialize already verified blobs directly and uses only bounded
local ref/index plumbing after the one-way transport boundary closes.
Except for a direct executable version probe, every invocation must also use
the updater's exact fixed global-option prologue and one absolute working root;
callers cannot inject alternate `-c`, `-C`, `--git-dir`, `--work-tree`, or
namespace authority.
