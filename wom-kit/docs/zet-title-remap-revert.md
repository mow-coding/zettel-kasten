# Approved zet Title Remap Revert

Status: v0.3.276 approval-gated completed-title compensation and hard-exit recovery

Use this command only for one clean, immutable title-remap receipt whose exact
prior-byte compensation has been reviewed.

## Two-Step Command

Preview the unchanged source receipt and plan digest:

```powershell
archive zet-title-remap-revert <archive-root> `
  --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json `
  --expected-receipt-sha256 sha256:<reviewed-receipt-digest> `
  --expected-plan-digest sha256:<reviewed-revert-plan-digest> `
  --max-items 500 `
  --dry-run `
  --format json
```

Approve only the same exact receipt and plan:

```powershell
archive zet-title-remap-revert <archive-root> `
  --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json `
  --expected-receipt-sha256 sha256:<reviewed-receipt-digest> `
  --expected-plan-digest sha256:<reviewed-revert-plan-digest> `
  --max-items 500 `
  --approve `
  --reviewed-by person:<reviewer-id> `
  --affirm-title-reversions-reviewed `
  --affirm-archive-quiescent `
  --format json
```

Alias: `title-remap-revert`.

Approval requires the exact source-receipt SHA-256, exact current revert-plan
digest, a safe reviewer id, explicit review of every title reversion, and an
explicit statement that archive writers are quiescent.

## Exact Compensation Boundary

The command reruns the complete receipt/journal/lock audit and complete
revert plan. After exclusively taking the common title-remap write lock, it
runs that same plan again while recognizing only its own exact lock binding.
Any receipt, participant, snapshot, audit, or plan drift blocks before the
transaction journal or canonical files are written.

For every participant the writer restores only the complete prior bytes
already preserved under:

```text
objects/sha256/<first-two-hex>/<64-hex>
```

It does not synthesize an old title or reserialize the file. Therefore BOM
state, newline convention, every prior frontmatter byte, body bytes, and
`updated_at` return to the exact source-receipt before-file hash.

## Immutable Compensation Receipt

The original apply receipt is never edited or deleted. A separate create-new
receipt is written under:

```text
receipts/revisions/title-remap/reverts/
  <source-receipt-digest>.zet-title-remap-revert.json
```

The revert receipt binds the source receipt, original proposal/plan/write-plan
digests, planner version, pre-revert complete history-audit digest, reviewed
revert-plan digest, reviewer affirmations, and the original private hash-only
participant rows. The archive-wide audit independently recomputes the revert
plan binding. The receipt stores no title or body text.

A verified unchanged replay returns `already_reverted` and writes nothing.

## Failure And Hard Exit

Before the first canonical write, WOM publishes a private hash-only revert
transaction journal and holds the common title-remap write lock.

A caught runtime or final-receipt failure restores every attempted canonical
file to its exact applied bytes, removes only evidence owned by that
invocation after verification, and returns `failed_rolled_back` when the
rollback is complete.

A process kill or power interruption may leave:

- some participants at applied hashes and some at prior hashes;
- one private `.revert.transaction.json`;
- the common `.title-remap.write.lock`;
- no final revert receipt.

`zet-title-remap-receipt-audit --dry-run` classifies these as `prepared`,
`partially_reverted`, `fully_reverted_receipt_missing`, `divergent`, or
`stale_completed`. Preserve all evidence. Since v0.3.275 the separate
read-only `zet-title-remap-revert-recovery-plan --dry-run` command maps a
complete retained revert case to one fixed decision. Since v0.3.276 the
separate `zet-title-remap-revert-recover` command can execute its non-forensic
actions after fresh review; `manual_forensic_hold` remains non-executable.

## Privacy Boundary

CLI output does not echo title text/hash/length, body text, zet ids or paths,
source proposal SHA-256, reviewer id, receipt/journal/lock/snapshot paths,
provider values, secrets, or absolute local paths. The command calls no
provider or model and has no MCP method.

## History Model

The source receipt remains immutable and the new receipt records a separate
compensating operation. This follows the same narrow history-preserving idea
as `git revert` and the current-state revalidation rule in the compensating
transaction pattern:

- https://git-scm.com/docs/git-revert.html
- https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction

See also:

- [zet Title Remap Completed-Receipt Revert Plan](zet-title-remap-revert-plan.md)
- [zet Title Remap Revert Recovery Plan](zet-title-remap-revert-recovery-plan.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [Approved zet Title Remap Write](zet-title-remap-write.md)
