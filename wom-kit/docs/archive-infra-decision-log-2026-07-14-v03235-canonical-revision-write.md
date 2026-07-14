# Archive Infrastructure Decision Log: v0.3.235 Canonical Revision Write

Date: 2026-07-14
Decision: accepted for v0.3.235

## Context

v0.3.234 moved ordinary correction before mutation by binding one complete
private proposal to the exact current canonical zet. It deliberately stopped
before writing, so direct canonical editing was still not an acceptable normal
workflow.

## Decision

- Add CLI-only `zet-revision-write`; do not expose canonical mutation through
  MCP.
- Require the four exact hashes from `zet-revision-plan`.
- Add a separate write dry-run that binds writer-managed `updated_at`, the
  deterministic candidate file, and the fixed change summary into a second
  `write_plan` digest.
- Require that second digest, a safe reviewer id, complete-revision review, and
  abstract/body-pair review at approval. Require a separate edge affirmation
  when edges change.
- Key one private write-ahead lock to canonical identity, not proposal
  identity, so distinct plans for one zet cannot enter the write section
  concurrently. Re-run the original revision plan after acquiring that lock
  and immediately before mutation.
- Replace one canonical file atomically, verify it, and create one immutable
  digest-named receipt with text-free before/after evidence.
- Roll back exact canonical bytes and remove a partial receipt on ordinary
  runtime failure.
- Keep enough text-free evidence in the private write lock to finish a missing
  receipt after a process interruption without rewriting the canonical file.
- Register the receipt's reviewed abstract/body pair as abstract-freshness
  evidence.

## Consequences

WOM now has an ordinary correction path from private proposal through human
review to a durable local history record. The write is idempotent by receipt
and fails closed on stale bytes or stale approval. It still does not establish
truth, external sync, backup, or model understanding, and it does not replace
receipt audit/revert work that may be added in a later safety rung.
