# WOM Product Roadmap

Status: v0.4.0 current roadmap checkpoint
Historical baseline: v0.3.115 public roadmap baseline
Updated: 2026-08-20

This document is a public orientation map for the WOM version line. It explains
what each pre-1.0 minor line is meant to prove.

It is not a promise that future features already exist. Release notes and the
capability matrix remain the source of truth for what the current code can do.

## Roadmap Snapshot

| Version line | Phase | Main question | Public meaning |
| --- | --- | --- | --- |
| `v0.1.x` | Idea and protocol language | Can the worldview be named clearly? | Historical concept and vocabulary work. |
| `v0.2.x` | Local implementation | Can WOM write, read, validate, and document a local archive safely? | Historical local-first implementation baseline. |
| `v0.3.x` | WOM real-use feedback | Can real archives migrate, mint, connect, retire, recover, and inspect at scale? | Historical field-test and safety-hardening line. |
| `v0.4.x` | Human-control layer | Can a non-developer approve an exact local operation without bypassing receipts and safety gates? | Current line. v0.4.0 implements the native exact-human TaskDialog foundation; it is not a complete custom control application. |
| `v0.5.x` | ZET real-use feedback | Can people test ZET communication patterns without corrupting private archives or leaking private material? | Planned ZET sharing and communication feedback phase. |

## How To Read v0.3.x

The `v0.3.x` line is not random feature growth. It is the real-use feedback line
for WOM as a private, local archive system.

Typical `v0.3.x` work includes:

- making archive migration and import safer,
- making minting and retirement repeatable,
- turning source material into reviewed zets without leaking private source
  locators,
- building preview and approval gates before live adapters,
- adding rollback, doctor, validation, and release-hygiene checks,
- improving scale behavior when real archives become large.

The line should stay conservative: local-first, receipt-backed, privacy-aware,
and clear about what remains only planned.

## v0.4.x Current Direction

The `v0.4.x` line connects a human-control layer to the existing WOM core.
v0.4.0 begins with a native Windows TaskDialog for supported exact single
operations, an authenticated durable `started` claim before the writer, writer
revalidation, and workflow-only finalization. Compound or otherwise unbound
writes remain fixed fail-closed.

This does not mean replacing the CLI, receipts, validation, or safety gates. The
UI should read and operate through those existing boundaries so a beginner can
use WOM without memorizing every command, while the archive remains auditable.

Later `v0.4.x` work may make more review and status surfaces beginner-readable,
but the current release must not be described as a complete custom UI.

Good `v0.4.x` signals include:

- PC-first local operation,
- readable queue and review surfaces,
- visible receipt and doctor status,
- safer onboarding for archives, credentials, objets, and provider plans,
- no hidden write path that bypasses exact-human, CLI, or MCP safety contracts.

## v0.5.x Direction

The `v0.5.x` line should begin ZET real-use feedback only after the WOM archive
and UI/control layer are stable enough.

ZET feedback should test communication patterns, not basic archive confusion.
That means the project should be able to separate:

- "the user could not operate the tool",
- "the private archive boundary was unsafe",
- "the ZET communication model itself needs design changes."

In this roadmap, `v0.5.x` is the place for real feedback about ZET as messaging,
feed/SNS, or collaboration patterns. It is not a claim that production ZET
transport, recommendation services, wallets, tokens, provider sync, or public
blockchain mechanics exist today.

## Phase Gates

The v0.3.x field-test record remains historical evidence. It does not reactivate
an approval route that v0.4.0 now closes for lack of an exact operation binding.

Before entering `v0.5.x`, the UI/control layer should make normal WOM operation
clear enough that ZET feedback is about sharing and communication behavior, not
about command-line friction.

Across all lines, public releases should keep the same safety posture:

- say what is implemented,
- say what is only planned,
- avoid leaking private archives, secrets, local paths, provider URLs, or
  unrelated personal context,
- keep release notes beginner-readable.
