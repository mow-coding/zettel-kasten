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
- A deliberately simple semantic typed census observes 51 populated-email
  pages, 917 populated-URL pages, and 3,439 populated-date pages.  Letter 138's
  51/904/2,810 values were reproduced exactly and identified as a historical
  probe rather than the semantic source total: the 2026-08-20 command searched
  only the first 40,000 characters of each raw JSON file and required the exact
  Korean property names `이메일`, `URL`, and `날짜`.
- For URL, the historical head probe's 904 consists of 901 semantic matches
  and 3 raw-regex false positives.  Three additional exact-name matches occur
  after character 40,000, and 13 populated URL properties use another name,
  producing the semantic total 917.  For date, 17 exact-name matches occur
  after character 40,000 and 612 populated date properties use another name,
  producing 3,439.  Full-file raw regex totals are 51/907/2,827.  These source
  properties are in direct `object_record` files; normalized source page ids
  have no duplicates.
- The implementation therefore preserves 51/904/2,810 as content-free
  historical-probe provenance, not as a value to force during recovery.  The
  write gate is the complete 11,585-file/source-shape accounting and exact
  source-id mapping, with explicit reason counts for all exclusions.
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
- A live read-only Basoon version inspection confirms the project mirror is a
  clean, integrity-verified annotated v0.4.0 checkout with configured origin;
  its latest fetched tag is v0.4.2 and the project pin is v0.4.0.  The Windows
  PATH diagnostic sees one candidate and no shadow.  A source-built v0.4.3
  updater dry-run toward the already-fetched v0.4.2 tag completed in 10.75
  seconds with `ready_for_approval`, verified tag/commit evidence, and zero
  files written.  The same path will be repeated for v0.4.3 only after its
  release artifact exists.
- Draft-only same-ID feedback revision is implemented with CAS evidence.
  Delivered or later records remain immutable and require a new superseding
  feedback id.
- A first actual-scale read-only `git-backup-plan` run against the clean Basoon
  archive exceeded an external 180-second hard timeout.  Direct measurements
  show the five main Git projections each complete in 0.139-0.347 seconds; the
  dominant defect is the repeated whole-archive `_archive_attribute_preflight`
  walk through ignored scratch and Objet trees.  v0.4.3 is not releasable until
  that walk is replaced by a bounded, cached projection and the existing Git
  command family exposes the two-second first-status/ten-second heartbeat
  contract.
- The first complete Letter 138 actual-scale plan read 925 MB across all 11,585
  mirror files in about 3 minutes 40 seconds.  Source-shape gates, historical
  probe provenance, and populated-type omission accounting all passed.
  However, it exposed a P1 classification defect: one 10 KB BOM Markdown file
  with no `source_page_id` token was counted as an invalid canonical target and
  globally changed all 11,585 source pages to review.  A malformed file that
  cannot be a Notion target must instead be separately accounted as
  `bom_non_candidate_no_source_page_id`; only malformed/unreadable files that
  contain, or may contain, a source-page token can block the mapping.  The
  planner must also publish its first status before acquisition rather than
  after the multi-minute mirror read.
- After the P1 and performance fixes, the actual read-only plan completed in
  240.563 seconds.  First status was at 0.000 seconds and the maximum progress
  publication gap was 1.109 seconds.  A bounded four-worker canonical scan
  finished in 30.17 seconds, the one-pass 925 MB mirror scan in 174.27 seconds,
  the indexed join in 33.66 seconds, and finalization in 0.72 seconds.
- Final accounting is exact: 8,566 pages map to backfill effects, 2,882 have no
  canonical target, and 137 require review, totaling 11,585.  The review set is
  110 legacy roots with no properties and 27 typed-indeterminate cases.
  Direct/legacy source shapes remain 4,034/7,551, with 7,441/110 legacy
  property-present/absent.  All 11,585 normalized source ids are unique, with
  zero duplicate or invalid ids, zero unexplained populated property/type
  omissions, one separately accounted BOM non-candidate, and zero writes.
- Re-testing after the first Git planner optimization reduced initial
  preflight/projection to 6.89 seconds, confirming that Git itself is not the
  remaining bottleneck.  The run then stayed in `context_initial` for more than
  70 seconds and was deliberately interrupted.  Basoon has 54,542 receipt
  files totaling 131,235,335 bytes; simple metadata enumeration takes only
  1.843 seconds, while the old planner opens and hashes every receipt before
  and after the plan.  Tracked receipt contents are already bound by the Git
  tree/index projection, and changed/untracked receipts by changed-content
  observation.  The planner will therefore cache one bounded metadata
  inventory and perform a final identity/CAS recheck rather than rehashing 131
  MB across 54,542 generic historical files twice.
- The revised implementation completed the same real Basoon read-only plan in
  31.72 seconds, down from more than 180 seconds.  It published the first state
  at 0.0 seconds and heartbeats no more than five seconds apart.  The archive
  had zero changes.  The remaining anonymous-transport blockers are expected
  for the private remote and belong to the stored-credential v0.4.3 writer
  verification, not to planner performance.
- The stored-credential read-only route then completed against the actual
  private Basoon remote in 32.02 seconds with `plan_ready`, zero changes, no
  blockers, a present remote ref, and an `equal` local/remote relation.  It
  reused the configured credential helper without prompting or exposing a
  credential, remote URL, or path.
- Independent pre-release review found three Letter 138 release blockers that
  must be closed rather than waived.  The runtime parser accepted 10,001
  properties while the public schema caps the array at 10,000; the parser will
  now classify an over-cap page for review so an approved run cannot emit a
  schema-invalid canonical file.  The approved planning/writer path also needs
  the same content-free progress stream as the read-only plan, and an
  indeterminate native-approval result must preserve
  `effects_state: unknown`, require reconciliation, and prohibit automatic
  retry instead of collapsing to a generic message.
- The same review measured an O(n-squared) defect in the shared checkpoint
  store: every appended row re-read the entire growing JSONL before and after
  the fsynced append.  A complete 8,566-effect run produces 25,698 rows and an
  approximately 17.4 MB final checkpoint, but the old algorithm can read about
  447 GB cumulatively.  v0.4.3 is therefore blocked on an append-compatible,
  crash-durable, fail-closed implementation whose total work is linear in the
  final checkpoint size, plus an actual 8,566-effect benchmark and the existing
  tamper, resume, and concurrent-writer regressions.
- The checkpoint blocker is now implemented and integrated.  The legacy JSONL
  format remains byte-compatible, each append validates only a bounded tail,
  every row is file-fsynced, and the complete hash chain is read once at start
  or resume and once before the final receipt.  The final actual-file synthetic
  benchmark processed 8,566 effects and 25,698 durable rows in 53.391 seconds,
  with two full scans, one creation-time directory fsync, first status at zero,
  and a maximum progress gap of 1.375 seconds.  Focused integration reruns pass
  54 tests, and the changed Python tree compiles cleanly.  Independent review
  remains in progress before release acceptance.
- Independent review then found two additional P1s before release: progress
  events still recomputed all completed fields for every item, leaving the full
  apply path quadratic, and POSIX directory fsync failure for the first
  checkpoint name was not distinguished from success.  Both are corrected.
  Completed-field progress now uses an O(1) state counter, durable name sync is
  fail-closed, and targeted regression coverage passes 56 tests.  The repeated
  8,566-effect / 25,698-checkpoint benchmark now finishes in 40.797 seconds
  while retaining two full scans, one creation sync, first engine status at
  zero, and a 1.407-second maximum progress gap.
- The review also bounded two P2 residuals rather than hiding them.  A Windows
  process that ignores the archive lock and restores both checkpoint length
  and timestamp can evade the next O(1) append guard, but the final full-chain
  scan still prohibits a result receipt.  The common benchmark's immediate
  status measures apply-engine entry, so each public writer must separately
  pass a CLI-start-to-first-output end-to-end gate before release.
- Letter 138 review found that the 2,882 unresolved classification and its set
  digests were returned after the generic final receipt had already been
  finalized.  A field write could therefore have a durable completion receipt
  while the complete-source accounting remained only in volatile CLI output.
  The common manifest now accepts one optional, strictly content-free
  `operation_evidence` document containing only bounded named counts and
  SHA-256 digests.  It is manifest- and approval-bound and is copied into the
  stable result/final receipt.  Legacy manifests omit the field and retain
  their prior hash contract.  Manifest/evidence tamper, reflective shapes, and
  durable receipt round-trip tests pass together with the common Git writer
  regressions.
- The separate v0.4.3 release-preparation branch now contains the version,
  package, release-note, upgrade, capability, and resource changes.  Its initial
  161 release/capability/root checks and a further 35 approval-inventory checks
  pass.  It remains separate until both new writers are integrated, because
  their final command inventory must be measured from code rather than guessed.
- Privacy inspection finds zero current tracked files containing the operator's
  personal Windows user name.  Eighteen tracked files contain only generic
  `C:\\Users\\...` documentation or test examples.  Historical Git search finds
  five commits that once added or removed the personal user name; rewriting
  public history would invalidate existing clones and therefore requires an
  explicit later hygiene decision rather than being folded into this release.

## v0.4.4 R2 evidence lock

- The current adoption evidence has 23,580 manifest rows and 22,431 unique
  Objet identities.  The 1,149-row difference is exactly the set of duplicate
  definition groups and remains a conflict population, not an auto-merge
  target.
- There are 4,525 local-location rows: 1,149 belong to those conflict groups
  and 3,376 are unique local-only definitions.  Two of the latter already have
  remote evidence, leaving exactly 3,374 emergency byte-preservation targets.
- The existing SigV4 HEAD/GET verification spine is reused.  Emergency PUT is
  content-addressed and produces an immutable `bytes_preserved` receipt; it is
  deliberately distinct from formal adoption.  Per-item progress is
  append-only and the aggregate projection is built once, avoiding a central
  manifest rewrite after every object.
- On the separate v0.4.4 branch, the adapter/writer and 72 focused/common
  tests now pass.  The existing `object-storage-adopt-existing` family gains a
  `--preserve-local-only` route; it uses a content-addressed key, HEAD plus
  complete GET rehash, mismatch-without-PUT fail-close behavior, common exact
  checkpoints/resume, and immutable `bytes_preserved` receipts.  It performs
  zero formal adoption or central manifest updates.
- An actual Basoon read-only run reproduced all locked counts: 23,580 rows,
  22,431 unique Objet, 1,149 conflicts, 3,374 preservation targets, 597 strict
  remote-key evidence rows, and 560 official deduplicated evidence rows.  The
  classification sum is complete; first status was immediate, cold runtime
  about 45 seconds and cached runtime about 11 seconds.  It made no provider,
  credential, remote, or Basoon write.  Live HEAD/PUT remains an explicit
  post-v0.4.4-release acceptance blocker.
- This v0.4.4 slice is committed separately as product commit `1a57848c` and
  evidence-record commit `eb25d048`.  It deliberately does not claim the
  existing 19,055 remote objects formally adopted, does not auto-decide the
  1,149 conflict groups, and identifies two legacy WOM-evidence rows without a
  remote key for receipt-based recovery or review during formal adoption.

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

## User-requested pause checkpoint

The user asked to stop immediately because the current Codex usage allowance
was exhausted and to resume next week. All active subagents were interrupted.
No release, installation, native approval, Basoon data write, provider call,
feedback resolution, or remote backup write was started as part of the pause.

- Integration remains on `codex/v0.4.3-recovery` at `8759f640`, with the
  linear checkpoint implementation committed and its focused tests passing.
- The Letter 138 implementation remains intentionally uncommitted in the
  dedicated `codex/v043-letter138` worktree. Its modified and untracked files
  are preserved in place; do not clean or reset that worktree on resume.
- The exact Git writer remains intentionally uncommitted in the dedicated
  `codex/v043-git-backup` worktree. Its modified and untracked files are
  preserved in place; do not clean or reset that worktree on resume.
- Release preparation is safely committed on `codex/v043-release-prep` through
  `155c7b0f` and its worktree is clean.
- v0.4.4 R2 read-only product/evidence commits remain separately preserved as
  `1a57848c` and `eb25d048`; they have not been released or applied.

Resume in this order: restore the interrupted independent checkpoint review;
finish, test, and commit Letter 138 and the Git writer in their existing
worktrees; integrate those commits; measure the final command inventory; then
integrate release preparation and run the full v0.4.3 release gates. Only
after a green public release and supported Basoon installation may the native
approval and real Letter 138 recovery sequence begin.

### Pause cancelled by the user

The user immediately cancelled the pause and directed work to continue from
the preserved checkpoint. The three interrupted tasks were resumed in their
existing worktrees: independent checkpoint review, Letter 138 writer closure,
and exact Git writer closure. The pause caused no reset, cleanup, release,
installation, provider action, or Basoon data write.

## Safety and privacy boundaries

- Real Basoon content, credentials, URLs, and user-profile paths remain private.
- Public tests and documentation use synthetic values only.
- The 173 work-marker titles, 335 quarantine records, and 1,149 conflicting R2
  definitions are never auto-deleted or auto-merged.
- Existing unrelated worktrees and client data are preserved.
