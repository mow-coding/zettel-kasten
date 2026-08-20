# Letters 118 and 119: credential continuity and reviewed Notion page recovery

Status: v0.3.311 implementation and operator-contract checkpoint.
This document is not proof of a live credential intake, provider recovery,
pull-request review, CI, tag, GitHub Release, wheel, fresh install, or human
acceptance.

Current v0.4.0 override: `notion-page-recovery` and `notion-recover` are
content-free preview/audit routes only. Approval returns
`compound_exact_human_approval_binding_required` before credential, private
request, provider, or target reads; it starts no provider recovery and writes
no recovery result. The v0.3.311 execution details below are historical
evidence, not current run instructions.

## Current state, without shortcuts

| Layer | Current checkpoint |
| --- | --- |
| Credential and Notion source modules | Present in the isolated v0.3.311 worktree with injected-fake regression tests around the lower-level contracts. |
| Credential workflow composition | Planning, spawned-child intake, authenticated rediscovery, lifecycle selection, and receipt-backed recovery composition exist in source and are connected to release-facing CLI commands. |
| Reviewed-recovery planning | `notion-page-recovery-plan` is a CLI-only, no-write preview over one complete ignored-local reviewed request. |
| Reviewed-recovery execution | `notion-page-recovery` starts a separate worker only after explicit approval and an unchanged plan; a fully verified replay remains secret/provider/write-free. |
| Real secret or provider state | No PAT was received, searched, read, written, adopted, or reissued. No real Windows vault or KeePassXC entry was opened. No Notion request was made. |
| Archive state | No reviewed page set was recovered. No canonical zet, objet, profile, locator, or collaboration state was changed. |
| Release state | No v0.3.311 commit, PR, remote CI, tag, public Release, public wheel, anonymous install, or human acceptance exists yet. |

The v0.3.311 source registers `credential-adopt`, `credential-secure-list`,
`credential-lifecycle`, `notion-page-recovery-plan`, and
`notion-page-recovery`. Use `archive capabilities --machine` or
`archive --help` from the exact installed artifact as executable authority.
Do not treat these source names as proof that an installed v0.3.310 runtime
supports them.

## Why Letter 119 is part of Letter 118

Letter 118 asked WOM to continue using a previously supplied external-service
credential across AI sessions without exposing it. Letter 119 corrected a
critical assumption: a safe-looking credential reference is not evidence that
the secret was ever persisted in an approved store.

That distinction is now explicit:

- legacy metadata discovery can show a safe label, intended provider, purpose,
  store type, and possible locator shape;
- discovery reports `presence: not_checked` and must not claim that a secret
  exists;
- conversation history is temporary working context, not a supported secret
  store and not a product-wide search surface;
- durable credential authority begins only after an exact encrypted-store
  write or exact existing-entry proof, provider identity verification, a
  reviewed workspace anchor, and an authenticated non-secret receipt;
- a newly persisted credential is rediscoverable, but it is not executable
  recovery authority until a human records one active, current default for the
  provider/workspace scope.

`credential-ref-inventory` and `connected-accounts` therefore remain useful
for content-free discovery, but their legacy rows are metadata-only evidence.
They are not persistence receipts.

## Human-only credential intake

### v0.3.317 visible-console and reuse correction

The visible black console is a small WOM-owned security surface, not a generic
terminal. Its copy has two owners. The helper AI must supply a reviewed,
public-safe `task_summary` and `connection_reason` that describe the actual
current work. WOM alone supplies the fixed security notice, including the exact
promise that the entered credential is not sent to the helper AI or chat. WOM
also owns the masked-input, cancellation, storage, and reuse wording. The two
helper sentences and replacement intent are bound into the canonical request
SHA-256; changing either after review blocks before the console opens.

The console uses Windows Unicode APIs (`SetConsoleTitleW`, `WriteConsoleW`, and
`ReadConsoleW`) and explicitly selects UTF-8 console code pages, so Korean copy
does not depend on the launcher terminal's legacy code page. Echo and processed
Ctrl+C handling are disabled during input. Empty Enter and Ctrl+C are
safe cancellations, and the original mode/code pages are restored before the
worker detaches.

Here, “one-use” describes the short approval request and visible input session,
not the saved credential. A successful first enrollment stores one exact
Generic Credential in Windows Credential Manager and verifies an authenticated
local receipt. Later approved recovery uses that exact saved entry through the
receipt-backed broker and does not open the input console again. A repeated
matching `credential-adopt` call may skip the prompt only after the worker
authenticates the receipt, reads the exact saved entry, verifies its secret
fingerprint, and rechecks the currently reviewed Notion anchor. A missing,
unreadable, or fingerprint-mismatched saved entry fails closed and requires an
explicit, separately reviewed `--replace-existing` request. A current-anchor or
provider check failure preserves the saved entry and routes to page, sharing,
and connection review before a no-prompt retry. Account/workspace labels are
not authority and a label-only change never justifies another prompt or
duplicate credential.

### Notion scope identity and legacy receipt evolution

Notion presents two supported identity shapes. An internal integration returns
a bot object with `bot.workspace_id`; WOM hashes that provider value under the
`notion_bot_workspace_id_v1` basis. A person PAT returns a person object and no
workspace ID. Notion's documented PAT contract says one PAT belongs to one user
in one workspace, so WOM uses `notion_pat_token_scope_v1`: the worker derives a
private scope witness from the archive-keyed HMAC fingerprint of the exact
saved PAT, verifies the current person through `/v1/users/me`, and verifies
access to the currently reviewed page. It never substitutes a label, email,
account id, or page UUID for a workspace ID.

That distinction is intentionally conservative. The same saved PAT can be
reused for another reviewed page without another prompt. A different PAT gets
a different witness even if a human knows both tokens belong to the same
workspace. PAT rotation or reconciliation therefore remains a separately
reviewed lifecycle operation; WOM does not silently merge credentials.

New successful intake writes an authenticated v0.2 receipt carrying the basis.
Released v0.3.311-v0.3.316 v0.1 receipts used the reviewed page as their old
scope fingerprint, and they remain byte-immutable. When exactly one compatible
legacy registration exists, WOM authenticates that receipt, reads only its
exact saved Credential Manager entry inside the worker, verifies the secret
HMAC, and performs the current provider/page verification. It may then append
one authenticated local workspace-scope evolution for the same
`credential_id`, backend, and PAT. No input window opens and no credential is
written, deleted, or duplicated.

If the legacy lifecycle contains exactly that one compatible credential, WOM
can move the signed lifecycle authority to the evolved scope. With no
lifecycle, the evolved row still requires a human default decision. Duplicate,
conflicting, tampered, or complex lifecycle/evolution state fails closed before
first publication. If a process stops after the evolution is durable but
before the lifecycle transition, the old broker binding remains unusable and a
retry completes the same idempotent transition.

The v0.3.311 source boundary uses a short-lived, one-use plan. The default
lifetime is five minutes, with a supported range of 30 to 3,600 seconds. The
AI-visible parent process receives only safe labels, a plan digest, and fixed
reason codes.

On Windows, the intended live sequence is split across a public parent process
and a fresh `multiprocessing.spawn` child. The parent validates approval and
the unchanged public plan, then sends only a secret-free invocation. Raw secret
bytes exist only in the child. That child performs the following transaction:

1. Revalidate the unexpired plan digest and the approved local Windows user.
   Claim the request once through an archive-bound, non-reparse authority file
   whose bytes are fully written, synced, atomically published, and exactly
   revalidated on replay.
2. Detach the isolated worker from any inherited console, allocate one separate
   visible Windows console, open only `CONIN$` and `CONOUT$`, and read one line
   with `ENABLE_ECHO_INPUT` disabled. Empty Enter or Ctrl+C cancels. Escape is
   not presented as a cancel key because the real cooked Windows console does
   not reliably wake `ReadConsoleW` for it.
3. Pass the mutable secret buffer directly to one exact Windows Credential
   Manager Generic Credential target; do not use argv, environment variables,
   normal stdin, a plaintext file, chat, a direct clipboard API read, or tool
   output. A deliberate human paste into the separate masked console is
   console input only and is never read by the helper AI.
4. Prove that exact target exists, then verify the provider identity and one
   human-reviewed workspace anchor.
5. Commit one authenticated, non-secret local receipt atomically. Only after
   this commit may WOM issue a durable opaque `credential_id` with
   `persisted: true`.
6. Wipe the mutable secret buffer before the worker exits.

Once the child starts, the parent does not force-terminate it on a timer. The
human must finish or cancel the visible console prompt so the child keeps its normal
buffer-wipe and rollback opportunity. A process crash or power loss can still
interrupt cleanup; the source result therefore does not claim crash-proof
rollback. If the parent loses the child result after process start, it reports
`accepted` and `persisted` as unknown, marks durable state as possibly changed,
and requires reconciliation with the same approved command and plan. Only a
failure proven before process start may claim exact zero live operations.

If the store write, exact presence probe, provider identity, workspace anchor,
or receipt commit fails, the worker attempts exact rollback, returns a fixed
value-free failure, and issues no credential id. Rollback is evidence of an
attempt, not automatic proof of absence: if exact deletion fails, a Windows
entry may remain and must be handled as unresolved local state. A
`persisted: false` failure result alone must not be interpreted as a successful
delete receipt. The high-level source preserves a fixed `rollback_status`, a
separate store-absence proof bit, and a content-free operator action for this
case. There is no parent-console or ordinary-stdin fallback. This is a narrow
OS-native console secret-entry boundary, not a general shell, WOM web UI, or
desktop form. The console closes before the Credential Manager write begins.

There is also a distinct post-commit repair state. If the exact store write and
authenticated receipt commit succeed but immediate authenticated rediscovery
fails, WOM must report failure with `accepted: true` and `persisted: true`,
return no usable credential id, and stop for registry repair. It must not call
that state rolled back or absent.

The corrected source contract follows Microsoft's documented
[console creation](https://learn.microsoft.com/en-us/windows/console/creation-of-a-console),
[console modes](https://learn.microsoft.com/en-us/windows/console/setconsolemode),
and [Credentials Management](https://learn.microsoft.com/en-us/windows/win32/api/wincred/)
interfaces, including exact `CredWriteW`, `CredReadW`, and `CredDeleteW`
operations. The test checkpoint uses injected fakes; it has not performed a
real OS call.

## Credential orchestration commands

| Capability surface | Intended role | Current source status |
| --- | --- | --- |
| Human-only adoption | `credential-adopt --interactive --dry-run` reviews safe helper task/reason copy plus fixed WOM security copy; `--interactive --approve --expected-request-sha256 ...` opens the separate echo-disabled Windows console only for first enrollment or explicit `--replace-existing`. In v0.4.0 a matching existing registration fixed-closes before saved-secret read, provider validation, or registry evolution; caller approval cannot silently reuse it. Metadata alone can never set `persisted: true`. | Parser, spawned worker, Unicode visible-console input, authenticated receipt composition, fixed existing-registration boundary, and privacy projection are implemented and tested with injected dependencies. |
| Authenticated listing | `credential-secure-list` lists unauthenticated local metadata without an OS read; `--verify` reads only the exact archive authentication-key target and verifies receipt/lifecycle MACs. It never enumerates vault entries or reads a provider credential. | Parser, registry, and exact-key verification are implemented. |
| Default lifecycle selection | `credential-lifecycle --dry-run` returns an authenticated plan. In v0.4.0 the legacy `--approve --expected-plan-sha256 ... --reviewed-by ...` writer is fixed closed before archive-key or credential access because a digest and reviewer label are not exact-human write authority. Historical v0.3 receipts remain auditable; WOM still never deletes or revokes credentials automatically. | Read-only planning remains implemented; the approval branch returns `compound_exact_human_approval_binding_required` and writes nothing. |

The exact released artifact remains the final parser authority. No operator
should paste a PAT into any command or AI chat: the approved path accepts it
only inside the separate black Windows console. Authenticated listing and lifecycle planning
must read the exact archive authentication key. Once that key boundary is
entered, a failure reports native/key-read counts as unknown and possibly
nonzero; it never falsely reports exact-zero OS activity. Lifecycle planning
still writes no archive state, while approved lifecycle publication reports
archive-write state conservatively if its final outcome is uncertain.

## Reviewed finite-page recovery

This is separate from the existing `notion-recover` ancestor-structure flow.
The new lane handles a complete human-reviewed list of page bodies. It never
searches a workspace broadly.

The ignored-local request lives under:

```text
profiles/local/notion-page-recovery/<reviewed-private-name>.json
```

The request must bind exactly two reviewed source groups, 577 items and 43
items, for an exact total of 620. Each group includes only opaque public-safe
authority fields: credential id, credential-binding revision, workspace
fingerprint, authenticated scope-receipt SHA-256, `persisted: true`, and
`workspace_evidence_verified: true`. Every item belongs to exactly one group,
and duplicate or malformed page ids block the complete request.

The preview accepts a bounded pilot slice of 1 through 1,000 items and defaults
to five. The offset, slice, request digest, selected ids, and fixed approved
execution capabilities are bound into the deterministic plan digest. Preview
performs zero credential reads, provider calls, and writes, and it does not
echo the request path or page ids. Approval always authorizes credential
reads, read-only provider GETs, and archive evidence writes for the selected
slice; current verified replay evidence is an optimization and is not a
weaker authority promise.

The execution composition requires the unchanged plan digest
and a safe reviewer, resolves only an authenticated receipt-backed default
credential for each exact group, and serializes same-plan execution through a
private lock. The request's `persisted` and workspace-verification fields are
claims during standalone manifest validation; they become executable authority
only when the authenticated registry and credential broker verify them during
execution. The approved `archive_id` is revalidated before live access and
before every durable commit. The credential receipt set, scope revision, and
active/current/default lifecycle state are revalidated before every provider
GET attempt; a concurrent lifecycle change stops the next call without rereading
the secret or calling a provider identity endpoint.

For each approved item, the core:

1. retrieves minimal page metadata;
2. accepts `deleted` only from an accessible 200 response with
   `in_trash: true`;
3. retrieves exact enhanced-Markdown UTF-8 bytes;
4. sends every returned `unknown_block_id` back to the same Markdown endpoint
   and stores each recovered subtree as separate exact bytes;
5. retrieves page metadata again and refuses a mixed snapshot when
   `last_edited_time` changed;
6. stores exact bytes under the existing content-addressed objet layout,
   keeps exactly one central manifest authority row per object id, appends
   page-specific Notion projection rows, and records private itemized resume
   and aggregate receipt evidence.

Every create, replace, and append uses a complete write loop and verifies the
published bytes. A changed archive identity, short/zero-progress write,
post-publication mismatch, malformed complete authority row, or conflicting
pre-existing receipt fails closed. Prior completed calls and commits remain in
the reported operation counts instead of being relabeled as zero.

Replay trusts neither a prior outcome label nor an object filename. It
revalidates the bytes, object manifest, projection row, request digest, and
plan digest. A verified replay performs zero provider calls. The recovery lane
does not create or rewrite a canonical zet, infer an edge, mint a page, or
change Notion.

The spawned recovery parent applies the same honesty boundary. A launch failure
proven before process start has exact-zero operations. EOF, crash, or invalid
IPC after start reports unknown durable archive state and requires the same
approved plan to be reconciled and rerun; it cannot claim that no object,
manifest, projection, resume, or receipt row was written.

## Notion API corrections and limits

The adapter fixes `Notion-Version: 2026-03-11`, the latest version documented
for the selected endpoints at this checkpoint.

- Page metadata uses `GET /v1/pages/{page_id}`.
- Page and unknown-subtree Markdown use the same
  `GET /v1/pages/{page_or_block_id}/markdown` endpoint.
- The official Markdown endpoint defaults `include_transcript` to `false`.
  WOM does not opt in, so meeting-note transcripts are excluded.
- HTTP 404 means the object may not exist **or** may not be shared with the
  connection. WOM reports `not_found_or_not_shared`; it does not invent a
  separate deletion or permission conclusion.
- Every provider GET attempt in one archive shares an archive-local
  interprocess coordinator paced at no more than the documented average of
  three requests per second. Retryable responses use bounded retries and honor
  a safe `Retry-After` value within the run ceiling. Separate archive roots
  that happen to use the same Notion integration are not a connection-wide
  shared coordinator, so the source does not claim that stronger guarantee.

Official references:

- [Retrieve a page as Markdown](https://developers.notion.com/reference/retrieve-page-markdown)
- [Working with Markdown content](https://developers.notion.com/guides/data-apis/working-with-markdown-content)
- [Notion API 2026-03-11 upgrade guide](https://developers.notion.com/guides/get-started/upgrade-guide-2026-03-11)
- [Request limits](https://developers.notion.com/reference/request-limits)
- [Status codes](https://developers.notion.com/reference/status-codes)

## What has not happened

The tests in this source checkpoint use injected fake UIs, stores, credentials,
and HTTP transports. They prove the implemented control flow and privacy
guards, not a live recovery result.

The adapter now validates exact HTTP 200, `object`, requested id, bounded
timestamp/unknown-id shapes, and blocks redirects. The archive-local pacer is
also implemented and tested across processes. Those source tests remain
different from a live provider execution, and the pacer does not coordinate
the same connection across unrelated archive roots.

There has been no real PAT intake or persistence, no credential default
selection, no provider call, no 620-item recovery, no source-archive write, no
canonical zet modification, no UI product change, no MCP writer, no PR/CI/tag/
Release/wheel/fresh-install proof, and no human acceptance. Letters 120 and 121
remain separately queued tasks, in that order, and are outside v0.3.311.
