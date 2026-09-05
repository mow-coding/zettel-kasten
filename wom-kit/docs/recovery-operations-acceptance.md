# Recovery and operations acceptance register

Updated: 2026-09-05
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
| RT-01 | v0.4.19 | Runtime and source directory allocation-size changes do not imply byte drift; real file/membership/identity/reparse changes still fail | corrected; focused development tests passed; full CI pending |
| RT-02 | v0.4.19 | Trusted healthy same-version runtime terminates before candidate download/build; damaged state repairs atomically | actual-wheel no-op/follow-on preview diagnostic passed; four real closeout fault tests passed; final candidate verification pending |
| RT-03 | v0.4.19 | Actual released interruption states resume or safely abandon with exact evidence; unknown states are preserved | candidate, full verification pending |
| RT-04 | v0.4.19 | Four-state checks, command availability, requested modes, index readiness, and actual dispatch agree | focused development tests and bounded independent review passed; installed candidate/full CI pending |
| RT-05 | v0.4.19 | Operational Doctor <=180 s, initial status <=2 s, heartbeat <=10 s; count and byte-scale evidence distinguished; no background console flashes | count and mixed local measurements passed on separate runs; first mixed operational failure retained; directory identity/startup fixes and independent focused review passed; exact final CI/installed-wheel pending |
| WS-01 | v0.4.20 | Opaque app/workstream/session identity, CAS claims, one cancellable OS writer lock, consistent generation reads, and context handoff | planned |
| WS-02 | v0.4.20 | New writes carry session binding; old approved operations resume without rewriting their authority | planned |
| WS-03 | v0.4.20 | Local-only count-first target preview with 20-item pages and safe title/filename/short-ID fallback | planned |
| WS-04 | v0.4.20 | Complete cursor pagination and exact selected/excluded Git coverage; selected-session non-force commit/push plus independent remote-ref proof | planned |
| LR-01 | v0.4.21 | Draft discard/restore, semantic revision/restore, mint/retire/edge batches work through exact approval | planned |
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
