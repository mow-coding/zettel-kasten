# Recovery and operations acceptance register

Updated: 2026-09-08
Status: accepted implementation register; not a client-resolution ledger

## Evidence contract

Track each requirement through `implemented`, `development_verified`,
`released`, `client_executed`, and `independently_verified`. Public release
evidence never substitutes for a private recovery receipt, independent source
or provider check, or the required remote backup. Expected counts in historical
reports are observations, not mutation targets. Recompute the live set, bind the
reviewed manifest, and stop if that bound set subsequently changes.

The register contains only non-sensitive requirement identifiers and synthetic
acceptance contracts. Private source material and client outcome evidence stay
in their original private custody. The developer does not update their lifecycle.

## Ordered implementation and acceptance

| Ref | Release | Required complete outcome | Current train state |
| --- | --- | --- | --- |
| RT-01 | v0.4.19 | Runtime and source directory allocation-size changes do not imply byte drift; real file/membership/identity/reparse changes still fail | development verified and released; client execution independently pending |
| RT-02 | v0.4.19 | Trusted healthy same-version runtime terminates before candidate download/build; damaged state repairs atomically | released with installed public workflow evidence; original local timeout retained separately from successful supplement; client execution independently pending |
| RT-03 | v0.4.19 | Actual released interruption states resume or safely abandon with exact evidence; unknown states are preserved | development verified and released; client execution independently pending |
| RT-04 | v0.4.19 | Four-state checks, command availability, requested modes, index readiness, and actual dispatch agree | development verified and released; client execution independently pending |
| RT-05 | v0.4.19 | Operational Doctor <=180 s, initial status <=2 s, heartbeat <=10 s; count and byte-scale evidence distinguished; no background console flashes | released with supported-platform candidate and installed observations; count/mixed evidence and failed observations retained separately; client execution independently pending |
| WS-01 | v0.4.20 | Opaque app/workstream/session identity, CAS claims, one cancellable OS writer lock, consistent generation reads, and context handoff | public CLI/MCP lifecycle implemented with development evidence; released in v0.4.20 (public wheel, anonymous download and fresh-venv installation verified); client outcome pending |
| WS-02 | v0.4.20 | New writes carry session binding; old approved operations resume without rewriting their authority | batch/record intake and Git have scoped CLI/MCP source evidence; intake original review and unrelated-app continuation development verified; title apply/original review/resume now has CLI/MCP development evidence (25 recovery plus 30 adapter/transport tests and independent review); canonical document before/after transition observation development verified (21 recovery plus one MCP projection test, independent read-only review); authenticated whole-document Git ownership for completed title recoveries development verified (7 tests over a real repository; HEAD preimage, worktree postimage, index, original authentication); session-scoped title revert development verified (compensation as a bound apply over the observed post subset; 3 tests); all-writer/effect coverage unfinished |
| WS-03 | v0.4.20 | Local-only count-first target preview with 20-item pages and safe title/filename/short-ID fallback | preview and paging components implemented; session decisions and local recovery writers (legacy and session-scoped apply) show the count-first paged preview with a live target-binding observer; other writer families and installed acceptance pending |
| WS-04 | v0.4.20 | Complete cursor pagination and exact selected/excluded Git coverage; selected-session non-force commit/push plus independent remote-ref proof | pagination and authenticated receipt/metadata selective Git source journeys verified; canonical zettel documents changed by completed session title recoveries are now selected with HEAD/index/worktree proof (scope v3); generic ownership of other outputs, responsibility integration and installed/release acceptance pending |
| LR-01 | v0.4.21 | Draft discard/restore, semantic revision/restore, mint/retire/edge batches work through exact approval | discard-draft and discard-draft-restore reopened through exact approval with development evidence (6 new tests, receipts carry the approval reference); revision/restore and the batches pending |
| LR-02 | v0.4.21 | Source-property backfill classifies every mirror page and supports apply/resume/independent comparison/field revert | older domain exists; client closure unconfirmed |
| LR-03 | v0.4.21 | Identifier-like title proposals and historical title receipts are individually classified; insufficient evidence remains review | older planner exists; client writes unconfirmed |
| LR-04 | v0.4.21 | Locator records, occurrence anchors, and markup have separate validated outcomes; existing correct links survive | older partial result; recovery pending |
| LR-05 | v0.4.21 | Already captured objects become linked, awaiting a human target, or no existing target without recapture | classification/application pending |
| LR-06 | v0.4.21 | Source properties/title/locator/object links/edges each apply, resume and revert; unrelated later field changes survive | common-writer integration pending |
| LR-07 | v0.4.21 | Filename/metadata finds the actual object and linked zet; paired original/derived intake preserves original bytes; display projection never edits canonical content | preserve and reverify existing paths |
| NP-01 | v0.4.22 | Existing native credential components feed one scoped broker; one safe entry supports fresh-process reuse without secret export | partial components; end-to-end pending |
| NP-02 | v0.4.22 | Evidence-built missing-page cohort, workspace separation, five-page canary, raw/body/property/media/parent recovery and ledger | planned integration |
| NP-03 | v0.4.22 | Historical locator recovery cohort, nested pages/media, and markup blockers have separate complete accounting | planned integration |
| NP-04 | v0.4.22 | 404 is not-found-or-not-shared, permanent evidence blockers differ from retryable pending errors, interruption resumes exactly | planned integration |
| OB-01 | v0.4.23 | Existing object-store transports use the broker; full authenticated GET size/hash proves remote bytes | existing lower transport; general workflow pending |
| OB-02 | v0.4.23 | One approved eligible retention batch offloads with journal/tombstone/receipt and survives every interruption | planned |
| OB-03 | v0.4.23 | Resolver rehydrates verified bytes without overwrite or remote deletion; staging cleanup requires complete preservation proof | planned |
| QC-01 | v0.4.24 | Indexed relation candidates include readable evidence; human accept/reject links bidirectionally to actual edges | partial candidate/reject path; completion pending |
| QC-02 | v0.4.24 | Session-owned and registered external artifacts retain current/superseded/preservation state and exact cleanup responsibility | planned integration |
| QC-03 | v0.4.24 | Historical human-approval/source evidence has explicit review, reapproval, withdrawal or correction without rewriting old receipts | planned |
| QC-04 | v0.4.24 | Title/quarantine/legacy-edge/semantic-format drift and nested Git history are classified before exact retirement | planned |
| QC-05 | v0.4.24 | Final session backup and all feedback outcomes are evidence-backed; drafts and corrected report lineages stay distinct | client-run closure pending |

## Preservation and non-goals

The RT rows reflect the [published v0.4.19 evidence](../../meeting-minutes/2026-09-06-v0419-release-evidence.md)
and its completed evidence merge. Earlier pending entries in the chronological
log below remain historical. WS source checkpoints are detailed in the
[writer coverage record](archive-infra-decision-log-2026-09-05-v0420-writer-coverage.md).
None of these developer statuses updates a client feedback lifecycle.

- Preserve confirmed single publication/capture/link/edge workflows and the
  existing source-intake/capture batches; do not describe them as absent.
- Preserve paired original/derived capture, overview reads, search, saved views,
  operational context, event/sequence semantics, and safe staging checks whose
  client success has been reported. Revalidate them instead of replacing them.
- Confirmed duplicate-row removal is a regression invariant, not a second
  destructive recovery job. Historical row counts are not current baselines.
- Withdrawn search-absence and corrected source-loss measurements do not create
  new mandatory full-text search or bulk rewrite features.
- IMAP, Tiro, unrelated provider work, and public Git history rewriting remain
  separate explicit backlog/decision items; this train does not close them.

## Cross-release verification

Run supported public CLI and launcher journeys from a real candidate wheel:
update/create/publish/search/revise/revert, paired intake/capture/link/revert,
and receipt-backed staging retirement. Do not mock the runtime builder,
verifier, or writer whose behavior is being claimed. Synthetic approval input
may be controlled without bypassing the production approval broker.

Faults include file/ref/CAS drift, same-session claim conflict, concurrent
writers, disk-full, process termination, output loss, old approval resume in a
new version, and foreign-operation authority substitution. Target preview
fixtures cover 1, 2, 5 and 1,000 items, paging, cancel, approval, duplicate
titles, Korean range/Markdown display, and sensitive-value suppression.

Independent review, all supported-platform CI, public privacy/resources,
exact-head merge/tag, anonymous wheel download/hash, clean installation and
new-process validation precede release evidence. Completed feature/evidence
branches and worktrees are cleaned only after their work is preserved and
verified. Client execution waits for that public result; developer access never
substitutes for client authority.

## Execution log

### 2026-09-05 restart

Preserved the existing integration candidate, recorded the accepted amendment,
and split runtime and Doctor corrections into disjoint file ownership. Live
repository checks still showed public v0.4.18, no open PR, and no open secret
alert. This entry records implementation start, not test, release, or client
completion.

### 2026-09-05 integration correction checkpoint

The implementation record now includes the timeout-versus-corruption review,
shared capability/provenance and index-readiness corrections, historical
approval exposure annotations, and the actual no-op-followed-by-preview
failure. The historical count fixture passed; the expanded fixture did not
complete inside its bounded investigation window and is retained solely for
synthetic profiling. Neither full CI nor release/client completion is claimed.

### 2026-09-08 original continuation checkpoint

The user approved completing the pending intake original-review extension and
correcting the unrelated-app registration blocker in the existing worktree.
Only the two extra whole-registry current-owner comparisons were removed;
the existing claimed-binding guard, actor/pending checks, original evidence,
domain preimages, registry CAS and original bundle formats are retained.

Development verification passed 45 focused tests in three serial cohorts:
eight private original-review cases, nine actual public/registry journeys, and
28 current-scope/Git/CAS regressions. All exited 0 with no skips. Public journeys
register an unrelated app after A's retained-original interruption, then
continue batch, record and Git through CLI/MCP. Actual pause remains a refusal.
Git checks use isolated real commit/push/ref/blob evidence; source custody and
generic document ownership are not inferred from metadata backup.

Independent read-only review found no actionable defect. Exact selectors,
durations, frozen source hashes and retained earlier evidence are in the
[implementation record](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).
The previous 101 routing/transport passes are reused, not counted as rerun.
This closes the bounded development unit, not WS-02 all-writer acceptance,
v0.4.20 installed/platform/release acceptance or any client feedback outcome.

### 2026-09-15 canonical document transition checkpoint

The title recovery session control gains an optional whole-document image
extension: actual canonical zettel preimages are read under the existing held
writer lock, postimages are predicted with the existing field replacement
function, and only digests, sizes and exact target references are retained,
bound by the scope digest. The existing file CAS compares both its observed
input and replacement bytes against these images; original review rejects a
changed whole preimage even when the title field still matches. Controls
without images keep their exact historical shape and receive no inferred
evidence. Completion reports `whole_document_transition_verified` and
`whole_document_count` separately and still reports
`whole_document_ownership_verified` false.

Development verification passed 21 tests in one serial run (four isolated
observation cases, five actual session admission/drift/original-review/
old-shape cases, and 12 existing local-recovery regressions) plus one MCP
public projection test. Independent read-only review of the codec, writer
comparison and compatibility boundaries found no actionable defect. Exact
selectors, durations and frozen source hashes are in the
[implementation record](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).
This closes the bounded observation unit only. Authenticated Git producer
integration (original HEAD/index bytes versus approved preimage, current file
versus approved postimage) is the next unit; WS-02/WS-04 whole-document
ownership, scoped revert and installed/release acceptance remain unfinished.

### 2026-09-16 letters 159/160 writer-defect checkpoint (plan addition)

Beta-tester letters 159 and 160 arrived after the 2026-09-05 audit. They
report two defects created by WOM's own writers on v0.4.18: zettel-edge
rewrote drafts without the blank separator line and mint-zet then refused
them, and linking the declared fidelity source object as an asset made
mint-zet report private authority exposure. Both are corrected inside the
v0.4.20 train as a bounded unit with no new command or approval system:
exact body preservation in edge write/revert, separator normalization in the
mint verifier, a one-row asset exemption, truthful blocked responses for
create-draft and zettel-edge, and the selection file path from the exact
objet-capture-selection. Development verified (5 new tests, 185 regression
tests). Client execution depends on the next release and their pin update.

Plan addition recorded for v0.4.21 LR-01: letter 160 measured 42 approval
popups for three drafts because each intake runs record → selection →
capture as three approvals; the batch reopening must include one approval
plan for that intake chain. Letter 160 ④ (create-draft --approve behaving
differently under a PowerShell scriptblock wrapper) remains unreproduced.

### 2026-09-16 v0.4.20 release candidate

The version bump and release documents for v0.4.20 were prepared in the
work-session branch after independent review of the bounded units. This
register still records development evidence only: WS-01 through WS-04 keep
their pending installed/platform/release acceptance until the public
artifact, anonymous download and fresh-venv installation evidence exist,
and no client outcome is claimed by publication.

### 2026-09-16 v0.4.20 released

v0.4.20 is public: tag `v0.4.20` on main `25a46efb`, one wheel
`wom_kit-0.4.20-py3-none-any.whl` (SHA-256
`42d6553f1f49ef2cdc03a0990974c4c00ad9a3a629123e888cb5b6e4a293d9e8`),
candidate CI 14/14, exact-merge installed verification, anonymous download
and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-16-v0420-release-evidence.md).
This is release acceptance of the artifact and the installed synthetic
journeys only. WS-02 all-writer coverage (21 pending paths), WS-03 and
WS-04 installed acceptance for the remaining writer families, and every
client feedback outcome remain open. No feedback letter's `resolved_in` is
set by this release.

### 2026-09-16 v0.4.21 LR-01a: discard-draft and restore reopened

Both writers accept `--approve` again, only through operation-specific exact
human approval: fresh private preflight, digest comparison, binding from the
fresh plan, native dialog, authenticated one-use claim re-verified under the
per-draft lock, approval reference embedded in the receipt. Development
evidence and the exact inventory change (49 available, 66 fixed-closed) are in
the [v0.4.21 implementation record](../../meeting-minutes/2026-09-16-v0421-local-repairs-implementation.md).
Not released; letters 157-160 stay open until the client runs the released
command.
