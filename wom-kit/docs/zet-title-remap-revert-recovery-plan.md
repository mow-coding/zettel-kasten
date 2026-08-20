# zet Title Remap Revert Recovery Plan

Current v0.4.0 boundary: this recovery plan remains read-only. A recommended
action grants no executor authority; `zet-title-remap-revert-recover` approval
fails before private target read or mutation with
`compound_exact_human_approval_binding_required`.

Status: v0.3.276 read-only hard-exit title-revert recovery decision and approved-executor handoff

Use this command when v0.3.274 or later leaves a private
`.revert.transaction.json` and the common title-remap lock after a process
kill, machine shutdown, or power interruption:

```powershell
archive zet-title-remap-revert-recovery-plan <archive-root> `
  --dry-run `
  --max-receipts 5000 `
  --max-journals 100 `
  --max-cases 100 `
  --format json
```

Alias:

```powershell
archive title-remap-revert-recovery-plan <archive-root> --dry-run --format json
```

`--dry-run` is mandatory. The command calls the complete bounded title
apply/revert receipt, journal, snapshot, canonical-hash, and common-lock audit.
It writes and deletes nothing.

## Fixed Decisions

| Observed revert evidence | Recommended action |
|---|---|
| every participant remains at its applied hash | `cleanup_unstarted_title_revert_transaction_evidence` |
| participants are split between applied and verified prior hashes | `resume_title_revert_forward_and_finalize_receipt` |
| every participant reached its verified prior hash but the compensation receipt is absent | `finalize_title_revert_receipt` |
| the exact compensation receipt is verified but journal cleanup was interrupted | `cleanup_verified_completed_title_revert_evidence` |
| a participant, source/revert receipt, snapshot, journal, or common lock cannot be safely verified | `manual_forensic_hold` |

A partial revert moves only in the already reviewed compensation direction:
remaining applied participants would later be restored from complete verified
prior-byte snapshots. It never rolls already restored participants back to the
applied title merely to recreate the pre-revert batch.

This plan does not itself grant write authority. Since v0.3.276 every
non-forensic fixed action reports `execution_implemented: true`, while
`safe_to_execute_now` remains false until the separate executor rebinds the
complete plan, exact case, action, and fresh human approval.

## Apply/Reverse Separation

The older `zet-title-remap-recovery-plan` and
`zet-title-remap-recover` commands handle interrupted uncommitted apply
transactions. They must not execute a revert journal. v0.3.274 made the older
planner return `manual_forensic_hold` for every `operation: revert` case.

This dedicated plan selects only revert cases. If it sees an apply journal, it
reports `apply_recovery_required_elsewhere` or a warning and directs the
operator to the older apply recovery route. It never silently changes the
operation.

## Lock And Evidence Rules

The common title-remap lock should bind the exact retained revert journal. A
missing lock is reported as a later lock-reacquisition requirement, not
silently recreated by this read-only command. An orphaned, malformed, or
ambiguous lock is `manual_forensic_hold`.

Preserve:

- the immutable source apply receipt;
- any compensation receipt already present;
- the private revert journal;
- the common title-remap lock;
- every prior-byte snapshot and object-manifest record;
- every canonical participant in its current state.

Do not hand-copy snapshots, synthesize a compensation receipt, or delete
evidence to make the audit green.

## Complete-Plan Boundary

If the source audit or returned case set is incomplete, the plan is blocked.
The complete `plan_digest` binds every returned content-free case and its fixed
decision. The v0.3.276 executor reruns the complete audit and plan, binds one
exact case SHA-256 plus this plan digest and action, requires fresh human
review and archive quiescence, and revalidates all private evidence before
writing.

## Privacy Boundary

Output may include only archive identity, audit/plan digests, a content-free
journal SHA-256 handle, operation/state/action codes, counts, and boolean
future requirements. It does not echo title text/hash/length, body text, zet
ids or paths, reviewer id, proposal SHA-256, receipt/journal/lock/snapshot
paths, provider values, secrets, or absolute local paths.

The command calls no provider or model, reads no secret store or environment
credential, and has no MCP method.

## Current Execution Boundary

Since v0.3.276, pass one reviewed non-forensic case to the separate
`zet-title-remap-revert-recover` command. Do not pass these cases to the older
`zet-title-remap-recover`, which remains dedicated to interrupted apply
transactions.

The approved revert recovery executor can continue only toward verified prior
bytes, finalize the deterministic compensation receipt, or clean exact
transaction residue. `manual_forensic_hold` remains non-executable.

See also:

- [Approved zet Title Remap Revert](zet-title-remap-revert.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [zet Title Remap Recovery Plan](zet-title-remap-recovery-plan.md)
- [zet Title Remap Recover](zet-title-remap-recover.md)
- [zet Title Remap Revert Recover](zet-title-remap-revert-recover.md)
