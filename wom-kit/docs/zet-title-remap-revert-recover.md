# zet Title Remap Revert Recover

Historical status: v0.3.276 approval-gated single-case interrupted title-revert recovery

Current v0.4.0 boundary: the recovery plan and executor dry-run remain
available. Approval returns `compound_exact_human_approval_binding_required`
before private target read or mutation and changes no canonical,
compensation receipt, journal, lock, or recovery guard. Later executor details
are historical v0.3 semantics only.

## Boundary

This CLI-only command executes one fixed action from a complete
`zet-title-remap-revert-recovery-plan`. It does not choose a recovery
direction or accept a private journal, receipt, snapshot, canonical path, zet
id, or title from the command line.

It handles only a retained `operation: revert` transaction. The older
`zet-title-remap-recover` remains the separate executor for interrupted,
uncommitted title applies.

## Preview

```powershell
archive zet-title-remap-revert-recover <archive-root> `
  --case-sha256 sha256:<revert-journal-bytes-digest> `
  --expected-plan-digest sha256:<complete-plan-digest> `
  --expected-action <fixed-action> `
  --dry-run `
  --format json
```

Alias:

```powershell
archive title-remap-revert-recover <archive-root> ... --dry-run
```

Preview reruns the complete bounded plan and writes nothing. It succeeds only
when exactly one case SHA exists, the complete plan digest is unchanged, the
fixed action matches, and the action is executable.

## Current v0.4.0 Approval Boundary

Do not continue past preview. Approval is fixed fail-closed with
`compound_exact_human_approval_binding_required`; historical reviewer,
recovery-review, and archive-quiescence affirmations do not grant current
authority.

Approval requires a safe reviewer id and both affirmations. Archive quiescence
means the original revert process has stopped and no editor, title writer, or
other recovery executor is active.

## Executable Actions

| Fixed action | Approved behavior |
|---|---|
| `cleanup_unstarted_title_revert_transaction_evidence` | Reverify that every participant remains at its applied bytes, then remove only the matching common lock and revert journal. No compensation receipt is created. |
| `resume_title_revert_forward_and_finalize_receipt` | Restore only participants still at verified applied bytes to their complete verified prior-byte snapshots, verify the whole batch at prior bytes, append the deterministic compensation receipt, then remove matching transaction evidence. |
| `finalize_title_revert_receipt` | Reverify that every participant already reached its prior bytes, append the deterministic compensation receipt, then remove matching transaction evidence. |
| `cleanup_verified_completed_title_revert_evidence` | Reverify and preserve the exact existing compensation receipt byte-for-byte, then remove only matching transaction residue. |

`manual_forensic_hold` is never executable.

## Serialization And Revalidation

An approved run:

1. acquires the same cross-platform non-blocking recovery guard used by the
   interrupted-apply recovery executor;
2. regenerates the complete revert recovery plan under that guard;
3. locates exactly one private revert journal by its content-free case SHA-256;
4. verifies the immutable source apply receipt and its journal binding;
5. rejects an invalid present common lock or a lock belonging to another case,
   and exclusively reacquires only a genuinely missing lock;
6. verifies the complete prior-byte snapshot manifest and every participant;
7. verifies each remaining participant immediately before and after a
   safe-direction restore;
8. verifies the whole final participant state and the deterministic
   compensation receipt;
9. removes the matching common lock first and the journal second.

The lock is removed first intentionally. If journal cleanup then fails, the
retained journal and verified completed receipt form a fresh
`stale_completed` case whose missing lock can be safely reacquired.

## Interruption And Retry

The executor never moves a successfully restored participant back to applied
bytes merely to recreate an earlier batch state. A hard exit or caught
failure retains the private evidence that still exists. Generate a fresh plan,
review the new state/action/digest, and provide a new approval before retrying.

A stale case, plan digest, or fixed action is rejected. This includes the
normal transition from a partial restore to
`fully_reverted_receipt_missing` after the last canonical write succeeds but
the process exits before receipt creation.

## Approval Evidence Boundary

The final compensation receipt is reconstructed exactly from the original
revert journal. It preserves the original compensation authorization and does
not rewrite the original `reviewed_by` or human affirmations.

v0.3.276 requires a new recovery reviewer and affirmations before execution,
but does not append a second recovery-approval receipt. The privacy-safe result
reports
`new_recovery_approval_persisted_in_separate_receipt: false`. Persisting that
new authorization as a separate immutable audit artifact is a later
audit-hardening boundary; it is not silently claimed in this release.

## Privacy

Output may include only archive identity, content-free case and plan digests,
fixed state/action/blocker codes, counts, and write/cleanup booleans. It never
echoes title text/hash/length, body text, zet ids/paths, proposal SHA, private
evidence paths, reviewer ids, provider values, secrets, or absolute local
paths.

The command calls no provider or model, reads no secret store or environment
credential, and exposes no MCP method.

See also:

- [zet Title Remap Revert Recovery Plan](zet-title-remap-revert-recovery-plan.md)
- [Approved zet Title Remap Revert](zet-title-remap-revert.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [zet Title Remap Recover](zet-title-remap-recover.md)
