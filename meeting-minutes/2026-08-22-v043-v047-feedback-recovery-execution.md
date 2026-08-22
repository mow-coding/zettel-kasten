# WOM v0.4.3-v0.4.7 feedback recovery execution minutes

Date: 2026-08-22 (Asia/Seoul)

## User intent

The user directed the development repository to implement the complete recovery
plan derived from all beta feedback through Letter 144.  The required standard
is an efficient sequence of small, outcome-complete releases rather than more
read-only plans or safety surfaces that leave historical data unrepaired.

## Feedback authority

- Letter 142 is an independent Codex-session report.
- Letters 141, 143, and 144 are one Claude-session correction lineage.
- Letters 141 and 143 are superseded evidence, not separate current requests.
- Letter 144 is the corrected current report.  Its current ledger status is
  `delivered`, while `external_submission_performed` remains false; internal
  lifecycle state must not be presented as proof of external submission.

## Corrected starting state

- Public development repository: `mow-coding/zettel-kasten`, public, current
  `origin/main` at `592f45232dad9cdc815910a27865fe1ee90c630e`.
- Basoon archive: clean `main`, no ahead/behind divergence from `origin/main`,
  starting commit `8973ab96150e2c6ced87eaa8b05ae5de3cf8ee0d`.
- The prior Git backlog was manually committed and pushed.  This removes the
  immediate unbacked-worktree incident but does not fix WOM's large-tree
  `git-backup-plan` stall or the absence of an exact commit/push writer.
- The existing dirty Letter 138 prototype remains audit-only.  Implementation
  starts from a fresh `origin/main` worktree and must independently validate any
  useful idea before reuse.
- Independent source re-check corrected an early implementation assumption:
  `objets/notion-preservation/2026-06-07-db3-full-mirror/pages.raw.jsonl`
  contains only 3,605 Database 3.0 pages.  Letter 138's complete 11,585-page
  evidence set is the sharded
  `objets/notion-preservation/block-mirror/*/*.json` mirror (11,585 files,
  925,127,334 bytes at the starting snapshot).  A 3,605-page backfill must
  never be reported as the complete Letter 138 recovery.
- The 11,585 block-mirror files have two source shapes: 4,034 expose a direct
  `object_record`, while 7,551 expose the older `recordMap` envelope.  Of the
  latter, 7,441 have a root properties dictionary and 110 do not.  A recovery
  that reads only `object_record` would therefore silently omit most pages.
- A deliberately simple raw-type census currently observes 51 populated-email
  pages, 917 populated-URL pages, and 3,439 populated-date pages.  Letter 138
  reports 51, 904, and 2,810.  The URL difference of 13 and date difference of
  629 must be decomposed and the client's semantic counting rule reproduced;
  the implementation must not force the data to match either count.  No write
  can be approved until the manifest records the source-shape provenance and
  explains the acceptance classification.
- Canonical matching is based on the canonical zet's `source_page_id`, with
  only dashed/compact UUID normalization.  Legacy `recordMap` property bytes
  are preserved as opaque source evidence when name/type semantics cannot be
  recovered without guessing.

## v0.4.3 implementation progress

- `ExactOperationManifest v1` is integrated with target/source/effect digests,
  a fixed archive-wide writer lock, fsynced hash-chained checkpoints,
  idempotent resume, content-free final receipts, independent verification,
  and field-scoped revert.
- The Windows Git capped runner now drains stdout and stderr concurrently, so a
  large tree cannot deadlock merely because one pipe fills first.
- The exact-human same-claim resume guard now receives the rehydrated,
  authenticated claim and can recompute the exact execution authority before
  touching a checkpoint.
- `project-version-update` is reopened behind the existing exact-human broker.
  The durable v0.2 update receipt now contains the exact approval reference;
  the update, rollback, receipt, and replay test suite passes.
- Draft-only same-ID feedback revision is implemented with CAS evidence.
  Delivered or later records remain immutable and require a new superseding
  feedback id.

## Release sequence

1. v0.4.3: shared exact-operation execution, Git/update/feedback revision, and
   actual local-mirror Letter 138 backfill with verification and revert.
2. v0.4.4: R2 byte preservation, remote verification, and evidence
   reconciliation.
3. v0.4.5: locator, 508 captured-Objet linking, and scoped rollback recovery.
4. v0.4.6: Windows credential continuity, 620-page Notion recovery, and markup
   blocker-class recovery.
5. v0.4.7: relation quality, canonical hygiene, artifact lifecycle, legacy
   coordination cleanup, and final feedback-ledger reconciliation.

## Completion rule

A feature is not complete merely because code, a contract, or a dry-run exists.
Each release must pass source tests and privacy gates, be packaged and released,
be installed through the supported project update, execute against the intended
real data, produce durable receipts, pass an independent re-read, and finish
with a verified remote Git backup.  Feedback records receive `resolved_in` only
after that chain is complete.

## Safety and privacy boundaries

- Real Basoon content, credentials, URLs, and user-profile paths remain private.
- Public tests and documentation use synthetic values only.
- The 173 work-marker titles, 335 quarantine records, and 1,149 conflicting R2
  definitions are never auto-deleted or auto-merged.
- Existing unrelated worktrees and client data are preserved.
