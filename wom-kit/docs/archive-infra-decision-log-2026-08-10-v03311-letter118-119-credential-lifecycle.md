# Archive infrastructure decision log: Letters 118 and 119 credential lifecycle

Date: 2026-08-10

Status: accepted v0.3.311 implementation and release-scope decision. This
record does not claim a live credential intake,
provider execution, canonical archive change, PR, CI, tag, GitHub Release,
wheel, fresh install, or human acceptance.

## Context

Letter 118 reported two connected gaps. WOM could list historical credential
reference metadata but could not prove that the corresponding secret existed,
bind it to provider/account/workspace/purpose authority, and reuse it safely in
a later AI session. It also lacked bounded, itemized recovery for a complete
reviewed set of 620 Notion page bodies; the existing `notion-recover` lane
recovers ancestor structure instead.

Letter 119 corrected the prerequisite. A safe-looking reference, a remembered
conversation, or an earlier intent to use a password manager is not evidence
that a secret was persisted. A metadata-only adoption receipt would therefore
create false authority.

## Decision

1. Keep legacy metadata discovery separate from persistence proof. Discovery
   may return safe labels and candidate counts with `presence: not_checked`,
   but it may not claim a credential exists or is reusable.
2. Treat credential continuity as a provider-neutral authority layer. A
   credential becomes durable only after a human-only, expiring, one-use local
   intake or exact existing-store proof, exact encrypted-store presence,
   provider identity verification, a reviewed workspace anchor, and atomic
   authenticated receipt publication.
3. On Windows, receive a secret only through the OS-native masked CredUI
   boundary inside a fresh spawned child process. The public parent validates
   approval and an unchanged plan but never receives raw secret bytes. Do not
   accept the secret through normal agent stdin, argv, environment, plaintext
   files, chat, clipboard, or tool output. Use an exact Generic Credential
   target and wipe the mutable secret buffer before the worker exits.
4. If store, presence, identity, workspace, or receipt publication fails,
   attempt exact rollback, issue no credential id, and return only fixed
   value-free public status. Treat rollback deletion failure as unresolved
   local state: `persisted: false` alone is not proof that the store entry is
   absent. Preserve the fixed rollback outcome and a separate absence-proof
   bit for operator review. Do not force-terminate a started intake child; a
   crash or power loss remains an explicit non-guaranteed cleanup boundary.
   Before process start, launch failure may prove exact zero. After start, lost
   IPC must leave `accepted`/`persisted` and durable state unknown and require
   reconciliation with the same approved command and plan.
5. Make next-session registry authority depend on authenticated receipt and
   lifecycle evidence. Rediscovery alone does not make a credential executable.
   A human must select one active/current/default credential for each exact
   provider/workspace scope. If receipt commit succeeds but immediate
   authenticated rediscovery fails, preserve `accepted: true` and
   `persisted: true`, expose no usable credential id, and require registry
   repair instead of claiming rollback.
6. Compare duplicate valid credentials only through non-secret fingerprints.
   Mark non-default entries `legacy_valid` or `revocation_pending`; never delete
   a store entry or revoke a provider credential automatically.
7. Bind reviewed Notion recovery to one complete ignored-local request. Preserve
   the two source groups as 577 and 43 items, total 620, with exact group/item
   membership and receipt-backed credential scope. Do not discover or search a
   workspace broadly.
8. Use Notion API version `2026-03-11`. Retrieve page metadata and enhanced
   Markdown read-only, return every unknown block id to the same Markdown
   endpoint, exclude transcripts, pace at no more than three requests per
   second, and use bounded retry/resume behavior.
9. Report a 404 as `not_found_or_not_shared`. Report `deleted` only when an
   accessible 200 metadata response explicitly says `in_trash: true`.
10. Preserve recovered Markdown bytes as content-addressed objets and existing
    retrieval-ledger evidence. Do not create or rewrite canonical zets, infer
    edges, mint pages, write to Notion, or expose a live MCP writer.
11. Bind every approved recovery plan to the same explicit live capability
    envelope: credential reads, read-only provider GETs, and archive evidence
    writes may occur for the selected slice. Treat verified replay as an
    optimization, not a weaker approval promise.
12. Reuse the existing zero-byte central object-manifest lock and keep exactly
    one authority row per object id. Per-page recovery provenance belongs in
    the projection ledger; conflicting or duplicate authority fails closed.
13. Bind the one-time intake claim to the exact archive-local claims root. Hold
    and revalidate non-reparse parent authority, write and sync the complete
    private marker, publish it atomically, and accept replay only from exact
    canonical marker evidence.
14. Revalidate the approved archive identity and authenticated credential
    lifecycle before each provider attempt and before every durable recovery
    commit. A concurrent archive or default/revision change stops the next
    operation without hiding work already completed.
15. Treat short writes and post-publication mismatch as fixed durable-write
    failures. Treat OS archive-key access as possibly nonzero once authenticated
    listing or lifecycle enters that boundary; never project a later failure as
    exact-zero native or key-read activity.

## Release-facing CLI decision

The v0.3.311 source registers these CLI surfaces:

- `credential-adopt` for safe request planning and Windows-native approval;
- `credential-secure-list` for unauthenticated metadata or exact-key receipt
  authentication;
- `credential-lifecycle` for digest-bound human default selection;
- `notion-page-recovery-plan` for a no-secret/no-provider/no-write preview; and
- `notion-page-recovery` for the unchanged approved slice in a spawned worker.

The complete Letter 118 request gate is fixed at two groups, 577 plus 43 items.
`--max-items` and `--offset` select a bounded pilot or continuation without
weakening the complete request. The exact installed `archive --help` and
`archive capabilities --machine` output remains executable authority; an older
v0.3.310 installation does not gain these commands from documentation alone.

## Authority and safety boundary

Legacy `profiles/local/credential-refs.local.yml` metadata can describe where a
secret may have been intended to live. It is not a secret-presence probe,
authenticated intake receipt, or executable scope binding. The authenticated
ignored-local intake registry and lifecycle decision are separate authority.

The reviewed page request may contain private ids locally, but public output is
aggregate-only. It must not echo page ids, exact credential/backend refs,
provider payloads or URLs, titles, bodies, e-mail addresses, cursors, request
paths, tokens, or secrets.

No code or test may use a historical conversation-wide secret search as a
normal workflow. Development and regression tests use injected fake UI,
credential-store, broker, and HTTP adapters. They are not live evidence.

## Evidence and consequences

The isolated worktree contains source primitives and injected regression tests
for tolerant legacy metadata discovery, exact adoption evidence, human-only
atomic intake and rollback, Windows CredUI/CredMan calls, authenticated receipt
rediscovery, human default selection, receipt-backed Notion broker use, fixed
Notion 2026-03-11 HTTP projection, 577 + 43 request arithmetic, exact Markdown
byte capture, ambiguous 404 handling, archive-local interprocess rate pacing,
exact response identity, no redirects, retry, resume,
crash repair, archive/credential authority revalidation, complete-write and
post-publication verification, and replay verification. A high-level source composition now
places secret-bearing intake in a spawned child and uses an authenticated
receipt committer before rediscovery.

The current coordinator covers concurrent processes using the same archive
root; it does not claim to coordinate one Notion integration across different
archive roots. Exact page and page-Markdown identity is now validated in
source. Neither fact is evidence that a real provider execution occurred.

No actual PAT, OS-vault entry, KeePassXC entry, provider account, workspace, or
page was opened during this implementation checkpoint. No 620-item run or
canonical archive change occurred. Packaged resources, release-gate tests,
commit/PR/CI, tag, public artifact, fresh installation, and human acceptance
remain separate evidence gates until each is completed.

## Standards references

- [Notion: Retrieve a page as Markdown](https://developers.notion.com/reference/retrieve-page-markdown)
- [Notion: Working with Markdown content](https://developers.notion.com/guides/data-apis/working-with-markdown-content)
- [Notion API 2026-03-11 upgrade guide](https://developers.notion.com/guides/get-started/upgrade-guide-2026-03-11)
- [Notion request limits](https://developers.notion.com/reference/request-limits)
- [Notion status codes](https://developers.notion.com/reference/status-codes)
- [Microsoft: CredUIPromptForCredentialsW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforcredentialsw)
- [Microsoft: Credentials Management functions](https://learn.microsoft.com/en-us/windows/win32/api/wincred/)

See `docs/letter118-119-credential-continuity-and-notion-page-recovery.md` for
the longer architecture and operator contract.
