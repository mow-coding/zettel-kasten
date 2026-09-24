# Closed Command Tracker

Status: v0.4.40 candidate (2026-09-25)

Owner direction (2026-09-24): a closed command that no customer path needs is
removed outright; a closed command customers need is restored first. Every
release report states the counts below and what changed since the last one.

## Counts

| Release | Approval available | Fixed closed | Reopened this release | Removed this release |
|---|---|---|---|---|
| v0.4.39 | 63 | 59 | 0 | 0 |
| v0.4.40 | 92 | 19 (+1 conditional scope) | 27 writers + 2 new batch commands | 12 |

The v0.4.40 decisions and evidence are in the
[closed-writer triage decision log](archive-infra-decision-log-2026-09-24-closed-writer-triage.md).

## Still closed in v0.4.40

Letters are the beta-feedback numbers that asked for or were blocked by the
command. "Next step" is the design work that has to land before the approval
path can open; an approval alone would not make these usable.

| Command | Letters | Why it is still closed | Next step |
|---|---|---|---|
| `delegate-zet` | owner design 2026-05-23 (one-use claimable license) | The "share" step of the ZET flow; removed on 2026-09-24 by mistake and restored as a closed preview | ZET sharing design (v0.5) |
| `transfer-ownership` | owner design 2026-05-22 | Composite-archive inheritance/split/transfer | ZET ownership design (v0.5) |
| `quarantine-foreign-block` | owner design 2026-05-25 | Receiving checkpoint for foreign blocks | With the ZET sharing design |
| `record-quarantine-decision` | owner design 2026-05-25 | Receiving checkpoint decision record | With the ZET sharing design |
| `github-repo` | onboarding spec 2026-06-05 | Planning tool the onboarding spec shows first | With the new-user entry (`onboard`) |
| `legacy-coordination-cleanup` | 142, 148, 156 (blocked three times) | The customer asked for a narrow contract that names the retired structure and preserves before removal; the current writer cannot express that | Preserve-then-remove contract bound to the exact file list |
| `notion-page-recovery` | 116-118, 142, 148, 156 | No request builder (0 request files could be produced); stored-credential reuse not proven | Request builder from existing ledgers, proven credential reuse, then exact approval |
| `notion-recover` | 156 (dry-run and capability disagreed) | Wraps the page-recovery binding | Reopen with notion-page-recovery |
| `onboard` | 102 | A new archive has no claim store yet, so the approval has nowhere to be recorded | New-user entry design |
| `runtime-skill-install` | 100-105 | Writes outside any archive | Install target and approval record design |
| `runtime-skill-uninstall` | none | Pairs with install | With install |
| `credential-lifecycle` | 119 | No adopted credential existed to manage | Redesign on top of `credential-adopt` records |
| `prehashed-objet-ledger` | 038-039, 164, 168 | Whether hash-only registration stays, and one store-label scheme | Decide with the store-label unification |
| `import-external` | 141 (blocked; earlier used for 437 notes) | Needs an exact manifest for bulk draft creation | Exact bulk-draft manifest |
| `add-source` | earlier IMAP context | Useful only with the external-source chain | With the IMAP chain |
| `imap-mailbox-adapter-manifest-write` | earlier letters | Part of the IMAP chain | IMAP chain design |
| `imap-mailbox-header-metadata-scan` | earlier letters | Headers alone do not meet the request to keep full messages and attachments | IMAP chain design |
| `notion-objet-link-convert` | feature request 34 | The source map is empty, so nothing can be converted | Mapping path first |
| `tiro-lossless-recovery-fetch-run` | feature request 13 | Depends on the credential chain | With credential reuse |
| `relation-candidate-decide` (accept) | 108 | Accepting writes an edge and a judgment record together; not in the 58-writer triage | One approval binding both effects |
| `migrate` (targets other than `notion-source-properties`) | owner concern 2026-06-06 (safe upgrade) | Conditional scope; one target is open | Per-target design when requested |

## Planned after recovery

Moving verified-recovered pages to the Notion trash (never a permanent delete)
is planned after Notion recovery works: only pages whose objet bytes and
recovery receipts are proven qualify, the run is resumable, and no extra
dialog is added under a valid session grant.
