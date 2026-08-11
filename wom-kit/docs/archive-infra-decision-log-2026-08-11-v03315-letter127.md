# v0.3.315 project-update preview parity

Date: 2026-08-11

## Context

v0.3.314 could report a local target as `ready_for_approval` before checking
whether the target tree collided with an ignored or unsafe filesystem entry.
Approval later ran the missing read-only materialization probe and failed
closed, preserving source and pins but leaving the operator without a safe
inspection or remediation route.

## Decisions

1. Dry-run and approve share one structured materialization planner for every
   locally available exact target. A target not yet fetched reports a deferred
   materialization preflight rather than a verified plan.
2. Public results use stable reason codes, bounded category counts, and opaque
   entry references. Ignored local names, absolute paths, private bytes, and
   private byte hashes stay private.
3. Conflict control is one alias-free CLI-only surface. It may disclose a
   target-tree-derived relative path only behind an explicit local inspection
   boundary.
4. Automatic remediation is limited to separately approved, identity-bound,
   no-replace preservation of a bounded regular ignored untracked file outside
   the source mirror. It never deletes, overwrites, follows a reparse point, or
   automatically retries the update.
5. Unsupported entry kinds and any drift remain fail-closed. A successful
   preservation is followed by a new dry-run and a separate update approval.
6. Current, target, index, and worktree names use one digest-bound canonical
   cross-map: NFKC, case-folding, HFS-ignored characters, Windows
   trailing-space/dot and reserved-name rules, `.git` aliases, and conservative
   8.3-looking names. Exact raw tracked membership wins before canonical
   equality. Ignored aliases and empty ignored descendant directories block
   transitions instead of being reinterpreted as target content.
7. Approval re-verifies HEAD, target-tree identity, current tracked bytes, and
   the exact materialization mapping immediately before the first source-tree
   mutation. The materializer repeats the complete approved source-snapshot
   comparison after planning and immediately before its first path write. If
   that final comparison differs, it performs no source or pin write, preserves
   the changed bytes, releases its owned lock, and requires a fresh dry-run.
   If the later pre-HEAD verifier fails after preparatory state changed, WOM
   performs only a provable bounded self-rollback; uncertain rollback retains
   the owned lock and recovery evidence.
8. A preservation result distinguishes preview truth from final lock truth.
   Terminal observation verifies the private completed case but does not claim
   a current materialization plan. The lock-absent field becomes true only
   after this invocation releases its owned lock and separately verifies a
   safe missing path.
9. Unexpected approved-path exceptions use nullable relocation and write
   fields. They report that writes or relocation may have occurred and require
   recovery; inspection and dry-run exceptions remain verified zero-write
   failures.

## Consequences

The previous `unexpected_worktree_entry_count` remains a Git-nonignored count
for compatibility and is no longer presented as complete filesystem evidence.
Release acceptance now includes a previous-release fixture that asserts
preview/approval parity, privacy-safe inspection, preservation receipt
integrity, and the full update-to-index-health handoff.

The private intent, relocated payload, and completion receipt use bounded
handle-bound reads and exact Windows volume/file identity checks. This proves
`unauthenticated_private_state_internal_consistency` only. It detects a changed
single artifact while the others remain intact, but it is not a MAC,
signature, ACL, authenticated binding, or defense against a process running as
the same local user that coherently rewrites the payload and both receipts.
That coordinated rewrite is outside the v0.3.315 trust boundary.

`operation-control` now routes allowlisted updater statuses instead of treating
all complete outputs as one generic success. Dry-run review, deferred fetch,
preview-only platform, applied-and-restart, no-change, blocked collision, and
unknown status each lead to a different fixed next action without echoing a
private path or blocker message.
