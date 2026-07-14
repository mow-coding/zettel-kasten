# Archive Infrastructure Decision Log

Date: 2026-07-14
Release: v0.3.239
Decision: Add one approval-gated exact-byte canonical restore writer after the
read-only plan and chronological event-chain gates.

## Context

v0.3.237 proved that separately recovered complete old zet bytes match one
receipt's before state. v0.3.238 changed revision history to a chronological
event chain so a legitimate restore such as `A -> B -> A` would not be
misclassified as a hash cycle. The remaining unsafe gap was manual copying:
there was no approved writer, durable restore receipt, or interruption
recovery path.

## Decision

- Add CLI-only `zet-revision-restore-write`; add no MCP write duplicate.
- Require dry-run and approval to be separate. Bind the selected receipt SHA,
  current state, recovered proposal file and semantic hashes, restore-plan
  digest, history audit digest, event time, and fixed change summary into a
  second write-plan digest.
- Require a safe reviewer, full restore review, abstract/body-pair review, and
  changed-edge review when applicable.
- Reuse the ordinary revision writer's per-canonical exclusive lock so the two
  writers cannot mutate one canonical zet concurrently.
- Atomically write the recovered proposal bytes exactly, preserving its YAML,
  BOM, newline, ordering, body, frontmatter, and historical `updated_at`.
- Store the restore event time in a separate immutable restore receipt in the
  existing canonical revision receipt directory.
- Audit ordinary and restore receipts and locks as one chronological event
  chain; treat restore review as abstract-freshness evidence.
- Roll back exact previous bytes on handled runtime failure. On forced process
  interruption, let an exact approved rerun resume before writing, finalize a
  missing receipt, or clean a verified completed lock.
- Require later ordinary revision events to be newer than the latest receipt
  event, not merely newer than a restored historical `updated_at`.

## Consequences

WOM now has a complete local correction and exact recovery loop without
inventing content from hashes or asking the operator to hand-edit canonical
memory. The private source receipt remains immutable, outputs remain
content-free, and the archive-wide audit stays
`O(receipt_files log receipt_files + revision_chains + lock_files)`.

This proves exact reviewed local application only. It does not prove truth,
backup existence, external replication, legal rights, or AI understanding.
