# Closed Command Tracker

Status: v0.4.44 candidate (2026-09-25)

Owner direction (2026-09-24): a closed command that no customer path needs is
removed outright; a closed command customers need is restored first. Every
release report states the counts below and what changed since the last one.

## Counts

| Release | Approval available | Fixed closed | Reopened this release | Removed this release |
|---|---|---|---|---|
| v0.4.39 | 63 | 59 | 0 | 0 |
| v0.4.40 | 92 | 20 | 27 writers + 2 new batch commands | 12 |
| v0.4.41 | 106 | 8 | `legacy-coordination-cleanup --destination` (retire by moving, letters 142/148/156); `notion-page-recovery` (letters 116-118, 142/148/156); `onboard` and `init --approve` (new-user entry, letter 102); `runtime-skill-install` / `-uninstall` with `--archive-root` (letters 100-105); `relation-candidate-decide --decision accept` (letter 108); `import-external` (letter 141); `credential-lifecycle` (letter 119); `prehashed-objet-ledger` (letters 038-039, 164, 168); `notion-objet-link-convert` (feature request 34); `tiro-lossless-recovery-fetch-run` (feature request 13); `add-source`; `imap-mailbox-adapter-manifest-write`; new `notion-page-trash` (owner idea 2026-09-24) | 0 |
| v0.4.42 | 107 | 8 | new `imap-mailbox-message-fetch` (whole messages with attachments, replacing the header scan's purpose) | 0 |
| v0.4.43 | 107 | 8 | none (project update approval hotfix, letter 20260925-173) | 0 |
| v0.4.44 | 103 | 6 | `notion-recover` revived (parent locations, adopted credential) | 18 IMAP planning commands superseded by `imap-mailbox-message-fetch` |

The counts are the `archive capabilities --machine` inventory (approval-available and
fixed-closed canonical paths). The v0.4.40 decisions and evidence are in the
[closed-writer triage decision log](archive-infra-decision-log-2026-09-24-closed-writer-triage.md).

## Still closed in v0.4.44

Letters are the beta-feedback numbers that asked for or were blocked by the
command. "Next step" is the design work that has to land before the approval
path can open; an approval alone would not make these usable.

| Command | Letters | Why it is still closed | Next step |
|---|---|---|---|
| `delegate-zet` | owner design 2026-05-23 (one-use claimable license) | The "share" step of the ZET flow; removed on 2026-09-24 by mistake and restored as a closed preview | ZET sharing design (v0.5) |
| `transfer-ownership` | owner design 2026-05-22 | Composite-archive inheritance/split/transfer | ZET ownership design (v0.5) |
| `quarantine-foreign-block` | owner design 2026-05-25 | Receiving checkpoint for foreign blocks | With the ZET sharing design |
| `record-quarantine-decision` | owner design 2026-05-25 | Receiving checkpoint decision record | With the ZET sharing design |
| `github-repo` | onboarding spec 2026-06-05 | Planning tool the onboarding spec shows first | Onboarding extension (`onboard` is open since v0.4.41) |
| `operation-control` | none | Cancelling a running operation is not supported (`operation_cancel_not_supported`); `--action status`, `wait` and `recovery-plan` stay available | Operation cancel design when requested |
| `migrate` (targets other than `notion-source-properties`) | owner concern 2026-06-06 (safe upgrade) | Conditional scope; one target is open | Per-target design when requested |

## Notion trash cleanup (v0.4.41)

`notion-page-trash` moves verified-recovered pages to the Notion trash (never a
permanent delete) and `--restore` moves the pages it trashed back. Only pages
whose recovered objet bytes, manifest and projection rows verify qualify; a
page edited in the minute its recovery completed or later is skipped; each
PATCH is journaled so a rerun resumes; no extra dialog is added under a valid
session grant. The Notion token needs the "Update content" capability; without
it the first PATCH is refused and the run stops.
