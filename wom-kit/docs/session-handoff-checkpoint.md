# Session Handoff Checkpoint

Status: implemented for v0.3.250

An AI chat can end while useful decisions still exist only in the conversation.
WOM cannot inspect a host application's private chat history by itself, so it
must not pretend that every important thought was saved. This checkpoint gives
the current AI or human a small, explicit closing procedure.

It binds three things:

1. the exact current bytes of `ops/operational-context.yml`,
2. the approval receipt that covers that operating record, and
3. a content-free inventory snapshot of AI artifacts in WOM's allowlisted
   scratch and staging folders.

The reviewer then confirms that the current conversation was checked and that
important decisions, corrections, unfinished work, and generated artifacts
have a durable home in WOM.

## Closing A Session

First inspect the current state:

```powershell
archive session-handoff-checkpoint <archive-root> --dry-run --format json
```

Common states are:

- `needs_durable_capture`: update the operational context or resolve unreviewed
  AI artifacts first.
- `needs_conversation_review`: archive evidence is ready, but the current
  conversation still needs a deliberate review.
- `would_write`: conversation review was confirmed and the exact state can be
  approved.
- `current_verified`: an existing checkpoint still matches current evidence.

After reviewing the conversation and moving important context into reviewed
zets, receipts, meeting records, objets, or operational context, preview the
confirmation:

```powershell
archive session-handoff-checkpoint <archive-root> `
  --confirm-chat-reviewed `
  --dry-run `
  --format json
```

Copy the returned `state_digest` into the approval call:

```powershell
archive session-handoff-checkpoint <archive-root> `
  --confirm-chat-reviewed `
  --expected-state-digest sha256:<64-lowercase-hex> `
  --approve `
  --reviewed-by person:me `
  --format json
```

Approval writes one content-addressed receipt under
`receipts/session-handoffs/`. It does not write or rewrite a zet.

## What Makes A Checkpoint Stale

A checkpoint stops being current when:

- the operational context bytes change,
- its matching approval receipt is missing or no longer covers the current
  record,
- the allowlisted AI artifact inventory changes,
- an unreviewed AI artifact appears, or
- the inventory exceeds the bounded 1,000-item inspection.

The state digest makes a preview stale-safe. Approval refuses a digest from an
older dry-run.

## Honest Boundary

WOM does not read the host chat transcript, understand whether every sentence
was important, or preserve raw chat automatically. `--confirm-chat-reviewed`
is an explicit reviewer attestation, not an automated semantic guarantee.

The artifact inventory reads file names and metadata only. It does not read or
echo AI artifact bodies, local absolute paths, provider URLs, or secrets. The
command calls no model, provider, network, object store, database, or credential
store.

`ready_for_context_reset` means the bounded archive evidence and reviewer
confirmation are current at checkpoint time. Any important decision made later
in the still-open chat requires another checkpoint.

This is a session-memory boundary, not remote backup proof. Use the separate
local-sovereignty and backup-evidence surfaces for GitHub, object storage, and
external map backup claims.
