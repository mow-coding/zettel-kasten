# Decision Log: Receipt-Backed Session Handoff Checkpoint

Date: 2026-07-15
Status: implemented for v0.3.250

## Decision

Use the existing approved operational context as the semantic AI handoff, then
add one bounded checkpoint receipt that binds its current bytes, its approval
receipt, the AI artifact inventory state, and an explicit conversation-review
attestation.

## Context

WOM already had mission/state rehydration and AI artifact inventory surfaces,
but no command proved that they had been reviewed together before a chat reset.
Creating another free-form handoff document would duplicate operational context
and make the next AI read more competing sources.

## Consequences

- A session checkpoint writes no new semantic knowledge and does not replace
  zets, meeting records, objets, or operational context.
- Approval requires a fresh state digest and an explicit reviewer.
- Current operational context bytes must match an approval receipt.
- Unreviewed or truncated AI artifact inventory blocks approval.
- Any later change to the bound archive evidence makes the checkpoint stale.
- WOM never claims that it read or understood the host application's chat.
- New operational-context writes use exact UTF-8 bytes so their receipt hash
  matches the on-disk file; legacy newline-normalized receipts remain readable.
