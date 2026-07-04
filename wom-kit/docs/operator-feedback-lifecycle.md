# Operator Feedback Lifecycle

Status: v0.3.149 approval-gated metadata checkpoint; runtime discoverability and shipped schema files since v0.3.160; delivery ledger + batched mark-delivered since v0.3.169

WOM now gives operator-generated tool feedback a separate lifecycle surface.

This is for feedback, bug reports, and retrospectives created while an AI
operator is running an archive for a human. Those records are meaningful, but
they are not the user's own knowledge objects. They should not be tracked only
as loose files in user content folders.

## Commands

Preview the policy:

```powershell
archive operator-feedback-plan <archive-root> `
  --dry-run `
  --format json
```

Preview a metadata record:

```powershell
archive operator-feedback-record <archive-root> `
  --feedback-id agent_operator_retro_20260623 `
  --feedback-ref feedback:agent-operator-retro `
  --status delivered `
  --dry-run `
  --format json
```

Approve the metadata write:

```powershell
archive operator-feedback-record <archive-root> `
  --feedback-id agent_operator_retro_20260623 `
  --feedback-ref feedback:agent-operator-retro `
  --status resolved `
  --resolved-in v0.3.149 `
  --approve `
  --reviewed-by person:me `
  --format json
```

Aliases:

```powershell
archive feedback-plan <archive-root> --dry-run
archive ops-feedback-plan <archive-root> --dry-run
archive feedback-record <archive-root> ...
archive feedback-register <archive-root> ...
```

## Delivery Ledger (v0.3.169)

See the whole board at once instead of tracking delivery in your head:

```powershell
archive operator-feedback-ledger <archive-root> `
  --dry-run `
  --format json
```

Aliases: `archive feedback-ledger`, `archive feedback-board`.

The ledger is read-only. It enumerates `ops/feedback/*.yml` and returns counts
by status, a pending list (the `draft` feedback ids that have not been marked
delivered), and the newest delivery-boundary timestamp among delivered records.
It projects only feedback id, status, and safe timestamps — it never reads a
feedback body and never echoes feedback ref values, title values, paths, or
secrets. A malformed or non-mapping record is counted into an `unreadable`
bucket and skipped so one bad file never fails the whole board.

Delivery-boundary honesty: `delivered_at` is stamped only by the
mark-delivered command below. Records that reached `delivered` through the older
`operator-feedback-record --status delivered` path have no `delivered_at`, so
for those the boundary falls back to their `updated_at`. The boundary is the
newest available delivery timestamp — it is not proof that anything was
submitted externally or received by a human.

## Batched Mark-Delivered (v0.3.169)

Instead of hand-editing each record's status one at a time, commit the delivery
boundary in one action:

```powershell
# Preview which draft records would transition; writes nothing.
archive operator-feedback-mark-delivered <archive-root> `
  --dry-run `
  --format json

# Approve the batch: draft -> delivered for every pending record.
archive operator-feedback-mark-delivered <archive-root> `
  --approve `
  --reviewed-by person:me `
  --format json

# Mark only one record.
archive operator-feedback-mark-delivered <archive-root> `
  --approve `
  --reviewed-by person:me `
  --only agent_operator_retro_20260623 `
  --format json
```

Alias: `archive feedback-mark-delivered`.

On approve it marks every pending `draft` record as `delivered`, stamps
`delivered_at`, sets `reviewed_by`, refreshes `updated_at`, and writes one batch
receipt under
`receipts/operator-feedback/delivery-batch.<timestamp>.<batch-digest>.json`
recording the ids, count, reviewer, and a per-batch content digest. The filename
carries that digest so two batches committed in the same wall-clock second cannot
collide and overwrite each other's audit receipt. It reads each record and
preserves every other field verbatim (feedback ref, title, related releases,
resolved_in), re-validates the mutated record against the shipped schema, and
writes atomically per record. It **only** transitions `draft -> delivered` — it
never touches acknowledged/resolved/archived records — and it is idempotent: once
no drafts remain, a re-run marks nothing new and writes no receipt (the boundary
receipt is emitted only when at least one record actually transitioned). A
malformed record in the target set is reported and skipped, never half-writing the
others.

Truth boundary (no overclaim): this is metadata lifecycle only. It performs no
external submission and proves no human receipt. `external_submission_performed`
stays `false`. Here `delivered` means "the operator marked it delivered" — the
same trust level as the existing `--status delivered`, just batched, timestamped,
and receipted.

## Runtime Discovery

Since v0.3.160 the read-only plan command is part of the runtime discovery
chain: `archive runtime-context` lists it in `recommended_first_commands`
(appended fourth entry), `ai_runtime_order` carries step 7
`plan_operator_feedback`, and `available_safe_actions` includes
`run operator-feedback-plan dry-run`.

## Storage

Approved metadata records go under:

```text
ops/feedback/<feedback-id>.yml
```

Receipts go under:

```text
receipts/operator-feedback/
```

## Schemas

Since v0.3.160 the record and receipt shapes ship as real schema files —
`wom-kit/schemas/operator-feedback.schema.json` and
`wom-kit/schemas/operator-feedback-receipt.schema.json` — matching the
unchanged schema-id strings `wom-kit/operator-feedback/v0.1` and
`wom-kit/operator-feedback-receipt/v0.1`.

Since v0.3.169 the record schema gains two optional timestamp properties,
`delivered_at` and `acknowledged_at` (additive, not required, so existing
records still validate), and the batched delivery receipt ships as
`wom-kit/schemas/operator-feedback-delivery-receipt.schema.json`
(`wom-kit/operator-feedback-delivery-receipt/v0.1`).

## Statuses

- `draft`: feedback exists but has not been recorded as delivered.
- `delivered`: the operator marked it delivered. This is a metadata stamp, not
  proof that anything was submitted externally or received by a human — WOM
  performs no external submission (`external_submission_performed` stays
  `false`). It records the operator's own claim of delivery, batched and
  receipted by `operator-feedback-mark-delivered` or set directly by
  `operator-feedback-record --status delivered`.
- `acknowledged`: the project team confirmed receipt.
- `resolved`: a release or decision closed the feedback.
- `archived`: feedback is kept for history and no active action remains.

## Safety Boundary

All of these commands — plan, record, ledger, and mark-delivered:

- do not read feedback bodies,
- do not copy or move feedback body files,
- do not submit feedback externally,
- do not call providers,
- do not check network,
- do not echo feedback ref values,
- do not echo title values,
- do not echo local absolute paths, tokens, or secret values.

The ledger and mark-delivered commands aggregate and mutate status metadata
only; the ledger reads status + id + safe timestamps and writes nothing, and
mark-delivered stamps `delivered_at`/`reviewed_by` without changing any other
field and without claiming external submission.

## Still Future

- Real feedback submission to a project-maintainer channel.
- Inbox migration helpers for existing loose feedback files.
- ~~A feedback status board.~~ Shipped in v0.3.169 as the read-only
  `operator-feedback-ledger` (delivery-status board + pending list) and the
  approval-gated `operator-feedback-mark-delivered` delivery-boundary commit.
- Cross-archive feedback relay receipts.
- Automatic issue or release-note linking.
