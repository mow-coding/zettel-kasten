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
| LR-01 | v0.4.21 | Draft discard/restore, semantic revision/restore, mint/retire/edge batches work through exact approval | discard-draft, discard-draft-restore, zettel-edge-batch, mint-zet-batch, retire-draft-batch, revert-batch, zet-revision-write and zet-revision-restore-write reopened through exact approval with development evidence (20 new tests; batches take one count-first dialog and every item write re-verifies the batch claim; the revision pair binds its own digest protocol to the dialog; `source-intake-chain` runs record, selection and capture under one approval, 27 new tests); installed/client acceptance pending; **Client verified 2026-09-18** (v0.4.25 success report): `source-intake-chain` ×5 (one approval per original, none under the session mode), `discard-draft --approve` ×3, `zettel-objet-link --approve` ×1, and the letter-159 `mint-zet` defects gone on the client's own archive; letters 157 through 160 reported resolved by the client |
| LR-02 | v0.4.23 | Source-property backfill classifies every mirror page and supports apply/resume/independent comparison/field revert | existing `notion-source-properties` domain revalidated at v0.4.23 (`test_notion_property_backfill`, `test_notion_property_backfill_cli` and the CLI group: 42 tests); client closure unconfirmed |
| LR-03 | v0.4.23 | Identifier-like title proposals and historical title receipts are individually classified; insufficient evidence remains review | existing `zet-title-remap-plan` / `-receipt-audit` / `-recovery-plan` planner revalidated at v0.4.23 (`test_v045_local_locator_title_recovery` and the CLI title-remap group); client writes unconfirmed |
| LR-04 | v0.4.23 | Locator records, occurrence anchors, and markup have separate validated outcomes; existing correct links survive | existing `external-locator-*` and anchor domain revalidated at v0.4.23 (`test_v045_local_locator_title_recovery`, `test_v0420_work_session_git_anchors` and the CLI locator group); client recovery pending |
| LR-05 | v0.4.23 | Already captured objects become linked, awaiting a human target, or no existing target without recapture | existing `objet-rediscovery-plan` and `zettel-objet-link` domain revalidated at v0.4.23 (`test_objet_rediscovery`, `test_v045_local_objet_link_recovery`, the letter 140 link service/CLI/binding tests, the letter 137 fail-closed test and the CLI group); client application pending |
| LR-06 | v0.4.21 | Source properties/title/locator/object links/edges each apply, resume and revert; unrelated later field changes survive | common-writer integration pending |
| LR-07 | v0.4.23 | Filename/metadata finds the actual object and linked zet; paired original/derived intake preserves original bytes; display projection never edits canonical content | existing paired original/derived intake revalidated at v0.4.23 (`test_v03315_objet_capture_batch_derived_text` and the CLI derived/paired group); client reverification pending |
| CF-01 | v0.4.27 | Client follow-ups from the v0.4.25 run: `project-version-update` usage refusals carry `cause_code` / `cause_stage: starting`; a bootstrap installed from a local wheel file is told to reinstall from the public URL; `work_session_permission_operation_not_grantable` reports the refused position and the fixed grantable / always-dialog name lists; intake plans and batch requests accept a UTF-8 byte-order mark and name UTF-16/32 marks; discard previews expose `plan_sha256` at the top level | development verified (9 new tests plus the session, intake, discard and permission cohorts); the index-rebuild block after several intakes is asked back with the client's sequence; installed/client acceptance pending |
| SP-01 | v0.4.24 | A claimed work session carries one human-granted permission mode (manual / limited / allow_all); a permitted write skips the dialog but still publishes its own one-use claim that records the permission mechanism; always-dialog operations (project update, providers, session lifecycle, repairs, overrides) can never be granted; pause, handoff, complete, accept and recover clear the grant; a grant revoked before the claim fails closed | development verified on the synthetic session fixture (8 tests: one dialog per grant, dialogless permitted write with the mechanism in the claim, environment-context grant, stale route and manual still ask, pause clears, revoke fails closed, always-dialog exclusion, modes/MCP/registry); installed/client acceptance pending; **Client verified 2026-09-18** (v0.4.25 success report): register-app → request-init → create → claim → `set-permission-mode limited`, then 11 writes with `approval_mechanism: work_session_permission_mode`, two dialogs in total; letters 160 ⑦ and 161 request 6 reported resolved by the client |
| UF-03 | v0.4.26 | The native approval dialog's "대상 자세히 보기" button opens the read-only paged target list on Windows 11 instead of cancelling the dialog with `exact_human_approval_native_call_failed`; an unconfirmed page stays inert except cancel | development verified on a real Windows 11 task dialog (details, return, approve and cancel; the unfixed handler reproduced the report on the same dialog) and with 3 new fake-dialog tests that fail against v0.4.25; installed/client acceptance pending |
| UF-02 | v0.4.25 | A project update started from the archive root resolves its recorded `parent_of_archive/...` mirror, pin and receipt locations onto the project root in every consumer, so the post-approval snapshot guard passes and `--resume` reopens the transaction; a failure the service raises before any result carries its fixed code and journal stage as `cause_code` / `cause_stage` | development verified: letter 161 ③ and ⑤ reproduced on synthetic fixtures with the released v0.4.18 and v0.4.21 wheels from the archive root (`approved_snapshot_changed` after the dialog; `directory_stability_unavailable` on v0.4.24 resume, 39 s); with the hotfix build the stuck transaction closes with `--resume --abandon-started-approval` (`preapproval_scaffold_cancelled`) and a fresh archive-root approve reaches `updated_restart_required`; 12 new tests; installed/client acceptance pending; **Client verified 2026-09-18** (v0.4.25 success report): `--resume --abandon-started-approval` from the archive root returned `preapproval_scaffold_cancelled` (one started claim abandoned), the recorded intent carried the labelled locations as diagnosed, and a fresh approve to v0.4.25 reached `updated_restart_required` with the pin, source and runtime aligned after restart; letters 161 and 162 reported resolved by the client |
| UF-01 | v0.4.22 | A reviewed project update that fails after the native approval names the refusing fixed gate and the journal stage; a claim left `started` with nothing written can be closed after human review and the reservation released by the ordinary claimless cancellation; a skipped `version` Git probe is never reported as a misconfigured origin; `operation-control` finds the owning project's journal from the archive root; `upgrade-check` announces its scope | development verified on synthetic two-step fixtures (stuck state reproduced with the released v0.4.21 wheel; cause, stage names, abandon, claimless cancellation and a fresh approve verified with the hotfix wheel; 10 new tests); the refusing gate of the client run is unknown until the client's next run reports it; installed/client acceptance pending; **Client verified 2026-09-18** (v0.4.25 success report): the abandon route closed the client's letter-161 claim on v0.4.25 |
| NP-01 | v0.4.22 | Existing native credential components feed one scoped broker; one safe entry supports fresh-process reuse without secret export | partial components; end-to-end pending |
| NP-02 | v0.4.22 | Evidence-built missing-page cohort, workspace separation, five-page canary, raw/body/property/media/parent recovery and ledger | planned integration |
| NP-03 | v0.4.22 | Historical locator recovery cohort, nested pages/media, and markup blockers have separate complete accounting | planned integration |
| NP-04 | v0.4.22 | 404 is not-found-or-not-shared, permanent evidence blockers differ from retryable pending errors, interruption resumes exactly | planned integration |
| OB-01 | v0.4.23 → v0.4.28 | Existing object-store transports use the broker; full authenticated GET size/hash proves remote bytes | slipped from v0.4.23 (2026-09-04 plan) behind the v0.4.22–v0.4.27 hotfix train; **development verified in v0.4.28**: `object-storage-restore --verify-only` runs one signed full GET per WOM-verified remote object through the shared live-transport seam (credential values read only inside the approved write), compares streamed size and sha256 to the object id and records one `remote_verified` / `review_required` receipt per object; the live sender gained a 120 s idle timeout so a silent socket is a retryable transport error; the scoped Windows credential broker of decision 5 stays NP-01 work; installed/client acceptance pending |
| OB-02 | v0.4.23 → v0.4.29 | One approved eligible retention batch offloads with journal/tombstone/receipt and survives every interruption | slipped from v0.4.23 (2026-09-04 plan); **development verified in v0.4.29**: `object-storage-offload` plans only WOM-uploaded, capture-provenance objects with verified local bytes that no inbox draft references or was created from, past the operator's age/size filters (every exclusion counted; an unreadable draft or fidelity receipt blocks the plan); per object a same-run full-GET re-hash, a local re-hash, an execution-bound proof marker, the handle-bound compare-and-delete and one receipt; one manifest projection flips the local location to `offloaded` (kept as the tombstone); a mismatching or absent remote copy is `review_required` with the file kept; a crash after the delete resumes from the marker without a second download; a foreign or torn marker never authorises a removal; bytes that reappear keep their row available; the remote object is never deleted; Doctor `--strict` stays green with `local_object_offloaded` INFO, backup-evidence counts remote-only objects, staged cleanup defers, the resolver and upload planner name the restore; apply is Windows-only by design (18 tests, execution cohort Windows-only); installed/client acceptance pending |
| L163-01 | v0.4.30 | Beta letter 163 core: mint-zet fidelity gate before the claim, started-claim listing/finalize, audit paging, inbox attention on write results, revert-edge under session mode and on inbox drafts, discard inbound-edge count, mint edge-target check, create-draft truncated-reference blocker | **development verified in v0.4.30**: `mint-zet --dry-run` carries `approval_handoff` (json_pointer to `current_source_fidelity_plan_sha256`) and `next_safe_actions`; `--approve` refuses `mint_source_fidelity_plan_sha256_required` / `_mismatch` / `_not_applicable` before any claim; the failure envelope carries `cause_code` / `cause_stage`; `exact-approval-claims` lists the MAC-verified claim store (fixed fields only) and `exact-approval-claim-finalize` closes reviewed started claims as `operator_closed_started_claim_after_review` behind one dialog after a receipt scan, a minimum-age gate and the writer lock; `approval-integrity-audit --kind/--offset` pages one receipt kind (v0.2 result); approved `mint-zet` / `create-draft` / `retire-draft` (and batches) and `work-session create/claim` carry `inbox_attention`; `revert-edge --approve` is unconditional and accepts `inbox/` sources (minted sources resolve by id); `discard-draft --dry-run` reports `inbound_edge_count` with warning `discard_draft_inbound_edges_present`; mint dry-run reports `edge_target_check`; `create-draft` blocks `draft_body_truncated_objet_reference` (17 + 9 + 6 tests); installed/client acceptance pending; carried to v0.4.31: create-draft argument hints, index pre-checks, warning explanation field, preflight cause codes, scratch cleanup, the gating edge-target warning |
| L163-02 | v0.4.31 | Beta letter 163 remainder: create-draft hints, gating edge-target warnings, warning explanations, preflight cause family + existing-transaction shape, index pre-announce | **development verified in v0.4.31**: the AI-runtime blocker adds `ai_draft_assisted_by_required` and a next-step line naming `--assisted-by` / `--supervised-by` / `--creation-mode`; `approval_handoff` arguments carry `omit_when_null` and the CLI refuses the literal `None` (`create_draft_replay_value_null_literal`); mint dry-run warns `edge_target_discarded` / `edge_target_missing` (bound; `--allow-warnings` after review); `quality_check.warning_explanations` names detector, rule, marker counts and body lines for the two body-wording warnings; a `project-version-update` failure without a fixed token records `project_version_update_failure_family_<family>` and the terminal-cleanup gate carries `existing_transaction`; `zettel-edge`, `revert-edge` and `source-intake-chain` dry-runs carry `index_precheck` with the rebuild commands (8 tests); installed/client acceptance pending; carried to v0.4.32: same-generation index participation and the bounded incremental index (verifiers refuted the first design), scratch classification (folder-in-archive question open), record_type registry (not reproduced), session refs for the three always-dialog writers |
| L164-01 | v0.4.32 | Beta letter 164 first half: byte-stream finalize scanner, update-snapshot probe failure kinds, content-free Git backup attention, permission-mode preview | **development verified in v0.4.32**: `exact-approval-claim-finalize` scans every receipt as a byte stream (256 MiB ceiling; `oversize_skipped_*` separated from `unreadable_*`, both named by archive-relative path) so a 3 MB Doctor receipt no longer blocks the close; the `project-version-update` preflight attaches `checks.git_transaction_snapshot.detail` with every probe's fixed `failure_kind` (timeout / probe_budget_exhausted / output_cap_exceeded / ...) or exit code; `ai-start-here`, `backup-evidence` and `work-session` create/claim carry `git_backup_attention` (uncommitted count, last-commit age, ahead/behind, remote-tip age; no path, branch, URL or subject; network never touched; the GitHub lane stays unverified); `work-session --action set-permission-mode --dry-run` previews the grant with the fixed grantable / always-dialog lists and the refusal detail, without a dialog or a session read (15 tests); installed/client acceptance pending; carried to v0.4.33: `object-storage-upload` reopened under exact approval with `writer_unavailable` first, `--local-bytes-only`, `--progress`, byte-external exclusion and store-ref label validation, a select-all group for `git-backup-reconcile-plan`; to v0.4.34: delivered-feedback archival, 8b index participation |
| L168-01 | v0.4.36 | Beta letter 168 ⑥ (and the 2026-09-17 decision): a session grant still opened dialogs for eighteen operation kinds | **development verified in v0.4.36**: the always-dialog set is empty, every kind is grantable, the only dialog-only action is `set-permission-mode` itself (a grant cannot mint or extend itself), the allow_all dialog line names the scope; client acceptance pending: one grant, then update / upload / finalize / archival with no dialog |
| L168-02 | v0.4.36 | Beta letter 168 ① (requests 1-3): the upload writer died after the dialog with `exact_human_approval_state_unknown`, no cause, claim left started | **development verified in v0.4.36**: cause codes travel through the broker allowlist, the exact runner and the upload envelope (`cause_code`, `cause_stage`, `effects_state`, `progress_summary`, `--progress-log`); the manifest-index authority and the credential refs are refused BEFORE the dialog; a failure before the first checkpoint closes the claim as failed (`exact_human_approval_writer_refused`); `registered_store_refs` on `store_setup_missing`; client acceptance pending: the dry-run's `manifest_index_authority` / `credential_refs_present`, then the approved upload |
| L168-03 | v0.4.36 | Beta letters 164 ⑧ / 168 request 8: delivered letters stay in the archive (asked three times) | **development verified in v0.4.36**: `operator-feedback-archive` moves delivered / acknowledged / resolved letters and their body receipts to an operator-designated folder outside the archive (path never echoed), leaves a content-free `archived` stub, writes one receipt naming the claim; body-check reports `archived_stub`, the ledger counts `archived`; client acceptance pending: the 115 letters archived |
| L168-04 | v0.4.36 | Beta letter 168 ③ (request 4): finalize approve repeats the receipt scan | **development verified in v0.4.36**: the receipt inventory fingerprint is bound into the plan digest; the approve re-scans only when it changed |
| L168-05 | v0.4.36 | Beta letter 168 ④ / request 5 and request 9: the preview refuses the approve request shape; the revise path did not say the ref | **development verified in v0.4.36**: the preview accepts `reviewer_claim`, a refusal names the allowed keys; `--create-draft-record` is the default and step 1 names `feedback-body-sha256:<sha>` |
| L167-01 | v0.4.35 | Beta letter 167: `project-version-update` refused the client's v0.4.34 update because the public-history rewrite left the mirror's `origin/main` unable to fast-forward, and reported only "fetch failed / tag missing" | **development verified in v0.4.35**: a failed fetch is diagnosed without stderr (`fetch.rejection_kind` `non_fast_forward` / `remote_unreachable` / `target_tag_missing_on_remote` / `ref_update_rejected`, `remote_reachable`, `target_tag_on_remote`, `origin_main_before_fetch`, `origin_main_remote_sha`, `origin_main_rewritten`); `--affirm-origin-main-rewritten` lets the one fetch replace `refs/remotes/origin/main` (tag ref never forced; before/after ids reported; bound warning `origin_main_rewrite_affirmed`); a refused rewrite names the flag in its blocker and next step (2 tests); client acceptance pending: the update to v0.4.35 through the v0.4.35 bootstrap with the affirmation |
| L165-01 | v0.4.34 | Beta letter 165: presenter-bound session grants, legacy identifier warnings, feedback compose under exact approval, the revise path, revision-plan warning explanations | **development verified in v0.4.34**: a `limited` / `allow_all` grant is minted with a presenter secret and a 1–24 h box before its dialog, returned once (`presenter_token`) and refused with a fixed code when presented without the secret, after expiry or in the pre-v0.4.34 shape (`session_permission_refused` on the result); grant claims carry `session_presenter` (HMAC'd process fingerprint, earlier presenter count) and results warn `work_session_second_presenter_observed`; `work-session` rows and `ai-start-here` (`session_permission_attention`) show the box and the counts; the shared `legacy_identifier` detector warns on create-draft (refusal `create_draft_warning_override_required` until `--allow-warnings`; never under a grant), mint, zet-revision-plan/write, objet-link labels and intake labels with counts and lines only; `operator-feedback-compose --approve` opens the dialog under operation `operator_feedback_body_write` and its receipts (v0.2) name the claim; the five-step revise path is announced and `--create-draft-record` creates the draft record in sequence; `quality_review.warning_explanations` names the field or table (21 tests); installed/client acceptance pending; carried to v0.4.35: `max_writes` ledger, per-session / bulk revoke, session refs for always-dialog writers and compose, select-all, reviewed re-PUT, letter 164 ⑧, 8b |
| L164-02 | v0.4.33 | Beta letter 164 ①③④: `object-storage-upload` reopened under the exact approval contract as preservation PUT + adoption projection | **development verified in v0.4.33**: new module `object_storage_upload_exact` composes the v0.4.13 preservation executor (create-only PUT, same-run full-GET proof, manifest-bound provider-call budget, private ledger) with the formal-adoption `wom_uploaded` projection under the manifest-index authority; the plan reports the writer line first (`provider_unsupported` / `store_setup_missing` / ... before any manifest read), classifies every object with counts, supports `--local-bytes-only` (fail closed on missing local bytes by default), `--max-objects` bounds instead of refusing, no tier gate; execution receipts keep the v0.3 contract (Doctor, backup-evidence and the gating matcher accept them unchanged) and are written after the projection; operation `object_storage_bytes_upload` is always a dialog; the inventory moves to 60 approval-available / 59 fixed-closed (16 tests); installed/client acceptance pending; carried to v0.4.34: session refs for restore/offload/finalize/upload, the select-all group for `git-backup-reconcile-plan`, a reviewed re-PUT operation |
| OB-03 | v0.4.23 → v0.4.28 | Resolver rehydrates verified bytes without overwrite or remote deletion; staging cleanup requires complete preservation proof | slipped from v0.4.23 (2026-09-04 plan); **development verified in v0.4.28**: `object-storage-restore` streams each remote body into a private create-only sink, keeps it only when size and sha256 reproduce the object id, re-hashes it from disk, moves it no-replace into `objects/sha256/`, re-hashes the destination, writes one receipt per object and one manifest projection (adds or reactivates the local location for restored objects only); absent or mismatching remote copies are `review_required` without blocking the batch; interruption resumes without a second download; a foreign local file is a `local_conflict` and is never overwritten; `delete_object` is unreachable from the module; `resolve-objet-ref` reports `remote_verified_local_absent` and names the workflow (21 tests); staged-cleanup semantics for offloaded objects are the v0.4.29 scope; installed/client acceptance pending |
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

### 2026-09-16 v0.4.21 LR-01b/c: the four batches under one approval each

`zettel-edge-batch`, `mint-zet-batch`, `retire-draft-batch` and `revert-batch`
accept `--approve` again: one fresh preflight, one binding over every item's
own single-operation binding, one count-first native dialog with a live
target observer, one authenticated claim that each item write re-verifies
against the batch context before it proves its own binding is approved.
Development evidence and the inventory change (53 available, 62 fixed-closed)
are in the [v0.4.21 implementation record](../../meeting-minutes/2026-09-16-v0421-local-repairs-implementation.md).
Not released; letter 160's 21-dialog and 42-popup measurements stay open
until the client runs the released commands.

### 2026-09-16 v0.4.21 LR-01d: semantic revision and restore reopened

`zet-revision-write` and `zet-revision-restore-write` accept `--approve`
again: the reviewer's digest protocol (expected proposal and current digests,
reviewer marker, revision time) stays as it was and is bound into one exact
human approval whose claim is verified right after the dry-run point against
the same ready-to-apply document the preview produced. Unbound service calls
return the content-free blocked document with `exact_human_approval_required`.
Development evidence and the inventory change (55 available, 60 fixed-closed,
no fixed-closed plan writers left) are in the
[v0.4.21 implementation record](../../meeting-minutes/2026-09-16-v0421-local-repairs-implementation.md).
Not released; issue I14 stays open until the client runs the released
command.

### 2026-09-16 v0.4.21 LR-01e: the intake chain under one approval

`source-intake-chain` plans the source-intake record, the objet-capture
selection and the objet capture of one staged original from projected bytes
(the record's receipt bytes and the selection bytes are known before they are
written), opens one native dialog, and runs the three steps in order under
one authenticated claim that every step re-verifies before it writes. The
dry-run also proves the capture precondition so the first two steps are never
written into a refused capture; a later failure is reported as `partial` with
the written paths and the single-step command that finishes. Development
evidence and the inventory change (56 available, 60 fixed-closed, 30 pending
session paths) are in the
[v0.4.21 implementation record](../../meeting-minutes/2026-09-16-v0421-local-repairs-implementation.md).
Not released; letter 160's three-approvals-per-objet measurement stays open
until the client runs the released command.

### 2026-09-17 v0.4.21 release candidate

Scope decision (Claude Opus 5, high; standing train approval): v0.4.21 ships
LR-01a through LR-01e (the eight reopened writers and the one-approval
intake chain), because those are the client regressions letters 157-160
report; LR-06 session integration of the 30 pending paths and the older
audit rows LR-02 through LR-05 and LR-07 carry to v0.4.22 and later with
their register rows unchanged. The version bump and release documents were
prepared in the work-session branch after the full development cohorts of
each unit passed. This register still records development evidence only:
LR-01 keeps its pending installed/client acceptance until the public
artifact, anonymous download and fresh-venv installation evidence exist,
and no client outcome is claimed by publication.

### 2026-09-17 v0.4.21 pre-merge review corrections

A bounded adversarial review of the release diff (Claude Fable 5.1 with the
user's Ultracode opt-in; three read-only lenses, one skeptic per finding)
confirmed six defects before merge, all corrected in the candidate: the
batch `identity_after_own_write` rule is now proven by the item writer's own
fresh read against the digest of the bytes the batch wrote (a foreign edit
between items is refused), the intake chain lists the capture step's durable
writes when the capture reports failure and writes no chain receipt when
nothing was written, and the packaged Runtime Skill operator contract plus
the revision/discard/batch guides, matrix rows and READMEs no longer describe
the reopened writers as fixed closed. Development evidence: 5 new tests,
full cohort 2,185 OK. Still no client outcome is claimed.

### 2026-09-17 v0.4.21 released

v0.4.21 is public: tag `v0.4.21` on main `70536034`, one wheel
`wom_kit-0.4.21-py3-none-any.whl` (SHA-256
`73f13ff73ca983b5ac196ca5d8f01b818c739becc1b1fc7eb09e8c79f46527db`),
candidate CI 14/14 with no rerun on the merged head, exact-merge installed
verification, anonymous download and two fresh-venv installations recorded
in the [release evidence](../../meeting-minutes/2026-09-17-v0421-release-evidence.md).
This is release acceptance of the artifact and the installed synthetic
journeys only. LR-01's client outcome (letters 157-160 and the letter-160
intake chain), LR-06 session integration of the 30 pending paths, and the
carried rows LR-02 through LR-05 and LR-07 remain open. No feedback letter's
`resolved_in` is set by this release.

### 2026-09-17 letters 161/162: the v0.4.21 update failure (plan addition)

Beta letters 161 and 162 report that the client's reviewed
`project-version-update` to v0.4.21 reached the native dialog, published
its claim and failed about nineteen seconds later with only
`ExactHumanApprovalWorkflowError` / `project_version_update_command_failed`
and no cause, left the claim `started` with the lock and reservation in
place, and that `--resume` failed in preflight, `version` reported a
misconfigured origin under disk contention, `operation-control` from the
archive root returned `operation_not_found`, and `upgrade-check --dry-run`
printed nothing for twenty-three minutes. Row UF-01 is added ahead of the
carried LR rows because no v0.4.21 repair reaches the client until the
update itself works. Diagnosis (Claude Fable 5.1, one bounded read-only
diagnostic workflow of 8 readers, then solo): the failure is raised inside
the approved writer between claim publication and the `approval_bound`
checkpoint, every boundary re-raises `from None`, the claim stays `started`
by the one-use contract, and no supported path could close it. The exact
stuck state was reproduced on a synthetic two-step fixture (an existing
v0.4.20 runtime updating to v0.4.21 from a local bare remote) with the
released wheel; the faithful fixture itself updates cleanly, so the client's
refusing gate is load- or state-specific and is not known from the v0.4.21
diagnostics. Recorded in the
[v0.4.22 hotfix record](../../meeting-minutes/2026-09-17-v0422-update-failure-hotfix.md).

### 2026-09-17 v0.4.22 UF-01 development verified

Hotfix (Claude Fable 5.1, solo): failures after the claim carry a fixed
`cause_code`, `cause_stage` and `cause_code_source: fixed_literal_allowlist`
with chaining still `from None`; the journal names
`materialize-runtime-candidate`, `native-approval`, `post-claim-revalidate`,
`approval-bound` and `durable-write`; `--resume --abandon-started-approval`
finalizes the started claim as `failed` /
`operator_abandoned_before_domain_write` only under journal state `exact`,
phases `lock_backlinked` only and classification `prewrite_exact`, and
discovery treats exactly that code as absence; the `version` Git probe
budget is 45 seconds and exhaustion reports
`project_git_probe_budget_exhausted`; `operation-control` retries once with
the owning project root; `upgrade-check` announces its scope. Evidence: 10
new tests in `test_v0422_update_failure_hotfix.py` plus the approval,
project-update, operation-control and dispatch cohorts; end to end on the
hotfix wheel against the reproduced stuck fixture, a forced writer failure
produced the cause and named stages, the abandon closed the claim, the
following resume returned `preapproval_scaffold_cancelled` (lock and
transaction removed, pin unchanged) and a fresh approve reached
`updated_restart_required` with the pin at the target. Not in scope: the
session-scope pre-approval of letter 161 (awaits the maintainer), the
journal schema, and the carried LR rows.

### 2026-09-17 v0.4.22 release candidate

Scope decision (Claude Fable 5.1; standing train approval): v0.4.22 ships
UF-01 alone, ahead of the carried LR rows, because no v0.4.21 repair reaches
the client until the update itself works. Candidate PR #104 (`c3bfb0be` plus
the CI corrections `cd1d7464`): the `upgrade-check` scope notice is printed
only on a terminal stderr, the cause-allowlist test's unlisted case uses an
out-of-family token, and the Windows shard 4/4 CI budget moves from 45 to 60
minutes after a run was cut at the cap with no failing test. Details in the
[v0.4.22 hotfix record](../../meeting-minutes/2026-09-17-v0422-update-failure-hotfix.md).
### 2026-09-17 v0.4.22 released

v0.4.22 is public: tag `v0.4.22` on main `4a4b1850`, one wheel
`wom_kit-0.4.22-py3-none-any.whl` (SHA-256
`2c6ac4ac9f7d87e73987a40b9344731dd2e19e02bbd9019b692846da63d875d6`),
candidate CI 14/14 on the merged head, exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-17-v0422-release-evidence.md).
This is release acceptance of the artifact and the installed synthetic
journeys only. UF-01's client outcome (letters 161 and 162: the abandon and
resume on the client's reserved project, then one reviewed update) remains
open, and no feedback letter's `resolved_in` is set by this release. The
carried rows are in the v0.4.23 candidate (PR #105).

### 2026-09-17 v0.4.23 U1: binary originals as the fidelity source (letter 160 ②)

Development verified (Claude Fable 5.1, solo): `create-draft` with a binary
objet as `--fidelity-source-object-id` previews and approves in
`faithful_summary` and `sanitized_derivative` on a second comparison basis,
`bytes` (raw digest as normalized digest, no newline transformation, no
source text or locator stored); `verbatim` still requires UTF-8 text and
names the two accepting modes in its next safe action. Every basis check
(plan builder, private receipt shape, mint-time verifier and evidence id,
approval integrity) accepts both bases with consistency; both draft receipt
schemas relax the basis const to the two-value enum without changing ids;
text receipts keep their bytes. Evidence: 6 new tests in
`test_v0423_binary_fidelity_source.py` and a 112-test fidelity/integrity
regression cohort. Recorded in the
[v0.4.23 implementation record](../../meeting-minutes/2026-09-17-v0423-carried-work-implementation.md);
installed/client acceptance pending.

### 2026-09-17 v0.4.23 U2: letter 160 ④ reproduction attempt

On Windows PowerShell 5.1 with the letter's exact wrapper shape
(`function Approve([scriptblock]$cmd){ & $cmd > $out 2>&1 }`) and the
v0.4.22 hotfix wheel, an AI-authored `create-draft --approve` replay reached
the native approval dialog both directly and inside the wrapper; the human
route returned the same fixed-closed answer both ways. Not reproduced; no
code change. A command re-quoted through a second shell layer does lose its
quotes and is refused as `cli_arguments_invalid`, which is the nearest
wrapper-only refusal and is not the letter's shape. Since v0.4.20 a blocked
text-mode `--approve` prints its reason codes, so the client's next
occurrence is self-diagnosing. Recorded in the
[v0.4.23 implementation record](../../meeting-minutes/2026-09-17-v0423-carried-work-implementation.md).

### 2026-09-17 v0.4.23 U3 (LR-06a): create-draft session integration

Development verified (Claude Fable 5.1, solo): `create-draft` with
`--client-app-ref`, `--task-route-ref` and `--work-session-ref` runs under
the held session lane, freezes the claimed session's content-free scope
digest into the reviewed fidelity plan and the native dialog, re-verifies it
after the dialog, records the operation as pending then completed on the
actor, and writes the binding into the draft receipt; sessionless
create-draft and every existing plan digest are unchanged. The reusable
`work_session_native_write` module is the template for the other native
single writers. Coverage: 6 integrated, 29 pending, 20 exempt of 56.
Evidence: 4 tests in `test_v0423_create_draft_session.py`; regression cohort
recorded in the
[v0.4.23 implementation record](../../meeting-minutes/2026-09-17-v0423-carried-work-implementation.md).
LR-06 remains open for the 29 pending paths; installed/client acceptance
pending.

### 2026-09-17 v0.4.23 U4: carried rows LR-02 through LR-05 and LR-07 revalidated

Development revalidation (Claude Fable 5.1, solo) of the existing domains
behind the carried rows, on the v0.4.23 tree with the U1 and U3 changes
applied: the domain cohort (`test_notion_property_backfill`,
`test_notion_property_backfill_cli`, `test_v045_local_locator_title_recovery`,
`test_v0420_work_session_git_anchors`, `test_objet_rediscovery`,
`test_v045_local_objet_link_recovery`, the letter 140 `zettel-objet-link`
service/CLI/binding tests, the letter 137 objet-link fail-closed test and
`test_v03315_objet_capture_batch_derived_text`: 173 tests) and the matching
`test_cli` groups (source properties, property backfill, title remap,
external locator, objet link, objet rediscovery, derived text, paired intake:
66 tests) pass. No behaviour was changed by this pass; the rows now name the
commands and evidence that implement them and keep their client-closure
state, which only a client run can change. Recorded in the
[v0.4.23 implementation record](../../meeting-minutes/2026-09-17-v0423-carried-work-implementation.md).

### 2026-09-18 v0.4.23 released

v0.4.23 is public: tag `v0.4.23` on main `ad0738f3`, one wheel
`wom_kit-0.4.23-py3-none-any.whl` (SHA-256
`f90e72402b5dfac51658ed332308b18e43a10a78349a3cca71f0f820580d818c`),
candidate CI 14/14 on the merged head, exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-18-v0423-release-evidence.md).
This is release acceptance of the artifact and the installed synthetic
journeys only: letter 160 ② (binary fidelity source), LR-06a (the
session-bound create-draft) and the revalidated rows LR-02 through LR-05
and LR-07 remain open for client closure, letter 160 ④ stays unreproduced,
and no feedback letter's `resolved_in` is set by this release. v0.4.24
starts with the session permission modes the user decided on.

### 2026-09-18 v0.4.24 SP-01: session permission modes development verified

Decision (the user, 2026-09-17; Claude Fable 5.1, solo after one bounded
read-only code map): per-work-session permission modes like the Codex and
Claude desktop apps, built as the first v0.4.24 unit, with the client reply
waiting until v0.4.24 is public. The grant is one exact human decision on the
claimed session (`work-session --action set-permission-mode --approve`),
stored as one optional session-row key, cleared with the claim, and enforced
at the broker's single choke point from the caller's retained refs
(`WOM_CLIENT_APP_REF`, `WOM_TASK_ROUTE_REF`, `WOM_WORK_SESSION_REF`, or a
command's explicit session refs). A permitted write mints its claim with the
`work_session_permission_mode` mechanism and results carry
`approval_mechanism` / `live_dialog_shown`; the five-key receipt reference is
unchanged. Project updates and credential writes always ask (the user's
unanswered question defaulted to my recommendation). Evidence:
`tests/test_v0424_session_permission_modes.py` (8 tests) plus the session
and approval regression cohort recorded in the
[v0.4.24 implementation record](../../meeting-minutes/2026-09-18-v0424-session-permission-modes-implementation.md).

### 2026-09-18 v0.4.24 released

v0.4.24 is public: tag `v0.4.24` on main `17ab3940`, one wheel
`wom_kit-0.4.24-py3-none-any.whl` (SHA-256
`44f964abc601f2d858e84586f112f4d65f1ab58dd3a88f708b8f8c89b23367b0`),
candidate CI 14/14 on the merged head, exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-18-v0424-release-evidence.md).
This is release acceptance of the artifact and the installed synthetic
journeys only: SP-01 (session permission modes) stays open for client
closure — the client grants a mode on its own claimed session and observes
a permitted write run without a dialog while its receipt still names a
claim — and no feedback letter's `resolved_in` is set by this release.

### 2026-09-18 v0.4.25 UF-02: archive-root update and resume failure reproduced and fixed

The client's 2026-09-18 report (v0.4.24 bootstrap, three `--resume` runs
dying in `project-preflight` with no cause; dry-run pointing back at
`--resume`) was reproduced solo on synthetic fixtures after one bounded
read-only workflow (8 agents) had localised the failure window to the
transaction reopen. The decisive difference from the v0.4.22 reproduction
was the positional root: the client runs every command from the archive
root, so preflight recorded `parent_of_archive/.zettel-kasten/...` locations
that six consumers joined literally onto the project root. Facts: the
released v0.4.18 wheel from the archive root fails after the dialog with
`project_version_update_approved_snapshot_changed` (pin specs re-resolved to
a missing path); the released v0.4.21 wheel reproduces letter 161 ③ exactly
(dry-run `ready_for_approval`, approve dies after the dialog, 154 s); the
released v0.4.24 wheel's `--resume --abandon-started-approval` on that state
raises `project_version_update_directory_stability_unavailable` in
`_project_update_reopen_durable_state` (mirror path
`<project>/parent_of_archive/.zettel-kasten/source`), 39 s, from either
root. With the hotfix build: the same command returns
`preapproval_scaffold_cancelled` in one run, and a fresh approve from the
archive root reaches `updated_restart_required`. Decision: ship as hotfix
v0.4.25 with the consumer-side resolver (recorded bytes unchanged) and the
direct-cause projection; the labelled public `files_written` form and the
pre-dialog `failed_rollback_incomplete` text blocker are deferred. Record:
[v0.4.25 hotfix minutes](../../meeting-minutes/2026-09-18-v0425-archive-root-update-hotfix.md).

### 2026-09-18 v0.4.25 released

v0.4.25 is public: tag `v0.4.25` on main `815819d7`, one wheel
`wom_kit-0.4.25-py3-none-any.whl` (SHA-256
`3fb76fb590b94a891136e126e6ac536300cab9370dba9eb95794a40bd8d82256`),
candidate CI 14/14 after one unrelated Windows-shard rerun, exact-merge
installed verification, anonymous download, two fresh-venv installations,
and the public wheel's own run of the letter-161 recovery sequence on the
synthetic fixture (`preapproval_scaffold_cancelled`, then
`updated_restart_required` from the archive root), recorded in the
[release evidence](../../meeting-minutes/2026-09-18-v0425-release-evidence.md).
This is release acceptance of the artifact and the synthetic journeys only:
UF-02 and letter 161 ③/⑤ close only when the client's own run from its
archive root reaches `preapproval_scaffold_cancelled` and then
`updated_restart_required`; no feedback letter's `resolved_in` is set by
this release.

### 2026-09-18 v0.4.26 UF-03: target-details page navigation reproduced and fixed

The user reported that the approval dialog's "대상 자세히 보기" button did
nothing for the client's operator and confused the AI client. Reproduced
solo on a real Windows 11 (26200) task dialog with synthetic labels and a
traced callback: the click built the details page and sent the navigation
call, the dialog delivered the page's construction notice inside that call
but posted `TDN_NAVIGATED` afterwards, and the v0.4.20 handler raised
`exact_human_approval_native_call_failed` and cancelled the dialog before
the confirmation could arrive. With the fix the same dialog opened the page,
returned, and approved or cancelled as before. Decision: the confirmation
is still required before any page is trusted, but its lateness is not a
failure; only destruction during a pending navigation is. Observed and
deferred: the dialog is owned by the foreground window at start time and
hides with it. Record:
[v0.4.26 hotfix minutes](../../meeting-minutes/2026-09-18-v0426-target-details-hotfix.md).

### 2026-09-18 v0.4.26 released; client verification of v0.4.25

v0.4.26 is public: tag `v0.4.26` on main `e998852d`, one wheel
`wom_kit-0.4.26-py3-none-any.whl` (SHA-256
`fc61406459927608dcd75981485211b65434224fc232994ff61b3e3bdb2e4043`),
candidate CI 14/14, exact-merge installed verification, anonymous download
and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-18-v0426-release-evidence.md).
UF-03 stays open for client closure (the operator presses "대상 자세히 보기"
and sees the list page instead of a closed dialog).

The same day the client reported its v0.4.25 run
(`.wom-scratch/analysis/wom-update-20260918/reply-to-devs-v0425-success-report.md`
in the client workspace, read only): the archive-root recovery and update
succeeded, the session permission mode cut eleven writes to two dialogs, the
intake chain, draft discard, object link and mint checks ran on the client's
archive, and the client stated that letters 157 through 162 may be closed.
`resolved_in` is the client project's field and is set there; rows SP-01,
UF-01, UF-02 and LR-01 above now carry the client verification. The report
also lists the follow-ups carried to v0.4.27: a fixed code for the
command's own usage refusals (the reply draft's approve command had omitted
`--affirm-external-writers-quiescent`, a maintainer error), a public-URL
reinstall hint for a bootstrap installed from a local wheel file, the
refused position and grantable names in a permission refusal, a UTF-8
byte-order mark in intake plans, a top-level `plan_sha256` in the discard
previews, and the "대상 자세히 보기" failure that v0.4.26 fixes. The
index-rebuild block after several intakes needs the client's exact sequence
and is asked back rather than changed blindly.

### 2026-09-18 v0.4.27 CF-01: client follow-ups implemented

Scope decided by the user ("그 회신 바탕으로 우리는 또 우리 할 거 하고 있으면
되는거잖아"): the five message and input requests of the v0.4.25 success
report are implemented as one small release, the "대상 자세히 보기" fix is
already v0.4.26, and the index-rebuild block after several intakes is asked
back with the client's exact sequence (the chain already checks the index
authority at planning time, so the observed block needs the dry-run result
of the blocked chain and the prior chains' `index_marked_dirty` facts
before any change). Every addition is content-free: positions and fixed
names, never the refused request value; the usage token is the command's
own literal. Record:
[v0.4.27 minutes](../../meeting-minutes/2026-09-18-v0427-client-followups.md).

### 2026-09-19 v0.4.27 released

v0.4.27 is public: tag `v0.4.27` on main `d39df7b0`, one wheel
`wom_kit-0.4.27-py3-none-any.whl` (SHA-256
`8abc91c8d3d5ca50a787b2e476b82206a908fa2eda7fb9aa407fc18328a25096`),
candidate CI 14/14 on the first run, exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-19-v0427-release-evidence.md).
CF-01 stays open for client closure; the reply draft now points the client
at v0.4.27 with the corrected approve command and answers each item of the
v0.4.25 report, and asks back for the index-rebuild sequence.

### 2026-09-19 v0.4.28 released (OB-01, OB-03 public)

v0.4.28 is public: tag `v0.4.28` on main `4a78cd7c`, one wheel
`wom_kit-0.4.28-py3-none-any.whl` (SHA-256
`50777719c2cdf9d81980de32aaad28a6c02ca6c0ebc945da2c9f82a51df4b8a6`),
candidate CI 14/14 after one correction commit, exact-merge installed
verification, anonymous download and two fresh-venv installations recorded
in the [release evidence](../../meeting-minutes/2026-09-19-v0428-release-evidence.md).
OB-01 and OB-03 are now installable from the public artifact; they stay
open for installed/client acceptance, and OB-02 (offload) follows as
v0.4.29 from the same decision log. The reply draft to the client is
refreshed to v0.4.28 with the restore section and the letter-163 answers.

### 2026-09-19 v0.4.29 released (OB-02 public)

v0.4.29 is public: tag `v0.4.29` on main `424bfd81`, one wheel
`wom_kit-0.4.29-py3-none-any.whl` (SHA-256
`679123d06ed671c6c04e3f7ec94da65351ad36a8cd75ad997a67c0f9e0d33bbe`),
candidate CI 14/14 after one test-only correction commit, exact-merge installed
verification, anonymous download and two fresh-venv installations recorded
in the [release evidence](../../meeting-minutes/2026-09-19-v0429-release-evidence.md).
OB-02 is now installable from the public artifact and stays open for
installed/client acceptance; the client is asked to run one restore
(`--verify-only`) before the first offload on the same archive.

### 2026-09-19 v0.4.30 letter 163 core implemented

Scope decided by the user ("베타테스터 클라이언트들한테 새로이 편지 온거 부터 해서.
밀린거 작업 다 알아서 처리하고 있어라"): the client's 2026-09-19 final report
(letter 163) is split into a v0.4.30 core (mint-zet gate first, then the
started-claim store, the audit cap, inbox attention on write results, the
edge and draft frictions) and a v0.4.31 remainder (create-draft hints, index
pre-checks, warning explanation, preflight cause codes, scratch cleanup, the
gating edge-target warning). Items ①, ③(a)(b) and ④(a)(b) were already
answered by v0.4.26/v0.4.27. Two adversarial reviews of the design changed
it: the receipt scan is generic (every JSON under the receipt roots, so batch
item envelopes count), finalize runs under the writer lock with a minimum
claim age, the failure code is not the abandon code, write evidence is
declared "receipts only", the discard plan echoes no raw edge types, the MCP
create-draft attach site was dropped (that path is fail-closed), and the
batch approve loop reuses the dry-run's fidelity digest. Record:
[v0.4.30 minutes](../../meeting-minutes/2026-09-19-v0430-letter-163.md),
[decision log](archive-infra-decision-log-2026-09-19-v0430-letter-163.md).

### 2026-09-19 v0.4.30 released (letter 163 core public)

v0.4.30 is public: tag `v0.4.30` on main `6ff9fb89`, one wheel
`wom_kit-0.4.30-py3-none-any.whl` (SHA-256
`2fe2d46fe62d8ae0cd46dd86b75bd4fb74ce8cd0ea0df3665e424f9d70c936e1`),
candidate CI 14/14 after two test-only correction commits and one flake
rerun, exact-merge installed verification, anonymous download and two
fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-19-v0430-release-evidence.md).
L163-01 is now installable from the public artifact and stays open for the
client's own runs; by the user's decision the client receives one reply
covering v0.4.28 through v0.4.30 now that all three are public.

### 2026-09-19 v0.4.31 letter 163 remainder implemented

Scope: the five letter-163 items carried from v0.4.30 that survive review —
create-draft hints (⑦a/c), the gating half of the edge-target check (11),
explanations for `internal_status_consistency_review_required` and
`tool_execution_trace_review_required` (⑪), always-present cause codes and
the existing-transaction shape for `project-version-update` (②/6), and the
index fact announced by edge, revert-edge and intake-chain dry-runs (⑧, unit
8a). Two adversarial verdicts refuted the first v0.4.31 design; the
incremental index (8b/8c: seal/generation contract, a lock deadlock, CRLF row
mismatch), the scratch classifier (out-of-archive folder, schema pins) and
the record_type registry (not reproduced in source) are carried to v0.4.32
with the client questions recorded. The client received one reply covering
v0.4.28–v0.4.30 on 2026-09-19 (sent by the user). Record:
[v0.4.31 minutes](../../meeting-minutes/2026-09-19-v0431-letter-163-remainder.md),
[decision log](archive-infra-decision-log-2026-09-19-v0431-letter-163-remainder.md).

### 2026-09-19 v0.4.32 letter 164 first half implemented

Scope: the four bounded read-side items of beta letter 164 — the finalize
receipt scanner reads bytes instead of parsing JSON and separates oversize
from unreadable (②); the update snapshot names each failed Git probe and its
fixed failure kind (⑤); session start, backup evidence and work-session
create/claim expose the local Git backup gap as counts and ages only (⑥);
and `set-permission-mode --dry-run` previews a grant without a dialog (⑦).
The upload writer (①/③/④) is a v0.4.33 design with adversarial review; the
delivered-feedback archival (⑧) and the 8b index participation that ⑨
confirms are v0.4.34. The one-approval commit+push route already exists as
`git-backup-reconcile-plan --approve`; a select-all convenience is a v0.4.33
candidate. Record:
[v0.4.32 minutes](../../meeting-minutes/2026-09-19-v0432-letter-164.md),
[decision log](archive-infra-decision-log-2026-09-19-v0432-letter-164.md).

### 2026-09-20 v0.4.33 upload reopened (letter 164 ①③④ implemented)

Scope: `object-storage-upload` reopened under the exact approval contract. A
bounded read-only Ultracode review (8 agents) refuted the first design — the
v0.4.13 preservation route already was an exact-approval live PUT writer —
so the implemented writer composes that route with the formal-adoption
projection instead of adding a third writer: writer line first, a counts-only
classification, `--local-bytes-only`, no tier gate, create-only PUT with a
same-run full-GET proof, one manifest projection under the index authority,
receipts after the projection. Session refs, the select-all group for
`git-backup-reconcile-plan` and a reviewed re-PUT move to v0.4.34. Record:
[v0.4.33 minutes](../../meeting-minutes/2026-09-20-v0433-upload-exact.md),
[decision log](archive-infra-decision-log-2026-09-20-v0433-upload-exact.md).

### 2026-09-21 v0.4.36 letter 168 (grants without dialogs, upload cause, archival)

Scope: the 2026-09-17 decision restored (no operation kind keeps its own
dialog under a grant; the grant action is the only dialog-only action); the
upload writer names its cause and refuses its two silent gates before the
dialog; a proven-no-effects failure closes its claim; delivered letters leave
the archive through `operator-feedback-archive`; finalize skips an unchanged
re-scan; the preview accepts the approve request; compose creates the draft
record by default. Record: [v0.4.36 minutes](../../meeting-minutes/2026-09-21-v0436-letter-168.md),
[decision log](archive-infra-decision-log-2026-09-21-v0436-letter-168.md).

### 2026-09-20 v0.4.35 letter 167 hotfix (rewritten origin main)

Scope: the public-history rewrite broke the client's update path (the mirror's
`origin/main` cannot fast-forward). v0.4.35 diagnoses a failed fetch with a
fixed rejection kind and the remote's own tag/main observation, and accepts a
rewritten `main` only under `--affirm-origin-main-rewritten` (forced main
refspec for that one fetch, tag ref never forced, affirmation bound into the
approval). Record: [v0.4.35 minutes](../../meeting-minutes/2026-09-20-v0435-letter-167.md),
[decision log](archive-infra-decision-log-2026-09-20-v0435-letter-167.md).

### 2026-09-20 v0.4.34 letter 165 implemented (presenter-bound grants)

Scope: the whole of beta letter 165. A session grant is presenter-bound and
time-boxed (secret returned once, fixed refusal codes, presenter evidence in
every grant claim, second-presenter warning, registry-only attention block);
one legacy-identifier detector warns on every new-record surface and is never
covered by a grant; the feedback body write asks the dialog and its receipts
name the claim; the revise path is announced; revision-plan warnings explain
themselves. Three deviations from the reviewed design are recorded (no
route-less revoke, warning gate by code at the caller, opt-in draft record).
Record: [v0.4.34 minutes](../../meeting-minutes/2026-09-20-v0434-letter-165.md),
[decision log](archive-infra-decision-log-2026-09-20-v0434-letter-165.md).

### 2026-09-19 v0.4.31 released (letter 163 remainder public)

v0.4.31 is public: tag `v0.4.31` on main `ff9fed87`, one wheel
`wom_kit-0.4.31-py3-none-any.whl` (SHA-256
`7a3e2e76ed03253e996dfa455f657a62f18651a31a403be054dc98c1f628decb`),
candidate CI 14/14 on the first attempt after one correction commit,
exact-merge installed verification, anonymous download and two fresh-venv
installations recorded in the
[release evidence](../../meeting-minutes/2026-09-19-v0431-release-evidence.md).
L163-02 is now installable from the public artifact and stays open for the
client's own runs; the client is told about it together with v0.4.32 in
the next reply.

### 2026-09-20 v0.4.32 released (letter 164 first half public)

v0.4.32 is public: tag `v0.4.32` on main `3ee73588`, one wheel
`wom_kit-0.4.32-py3-none-any.whl` (SHA-256
`272211f9ce1264fb711bbf96cd0ba92d518534438d2f4224fd128f42c37a7503`),
candidate CI 14/14 (first attempt, no reruns), exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-20-v0432-release-evidence.md).
L164-01 is now installable from the public artifact and stays open for the
client's own runs; the client receives one reply covering v0.4.31 and
v0.4.32 (the letter-164 reply draft), sent by the user.

### 2026-09-20 v0.4.33 released (upload writer reopened public)

v0.4.33 is public: tag `v0.4.33` on main `088cceae`, one wheel
`wom_kit-0.4.33-py3-none-any.whl` (SHA-256
`f08a56b3861a103b1cf1ec0cbd2a3bfb1d271669621d23a22007626baf7914cb`),
candidate CI 14/14 (first attempt, no reruns), exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-20-v0433-release-evidence.md).
L164-02 is now installable from the public artifact and stays open for the
client's own runs; the client receives one reply covering v0.4.32, v0.4.33 and
v0.4.34 (the letters 164+165 reply draft), sent by the user.

### 2026-09-20 v0.4.34 released (letter 165 public)

v0.4.34 is public: tag `v0.4.34` on main `3b0dc70d`, one wheel
`wom_kit-0.4.34-py3-none-any.whl` (SHA-256
`fa9f6b2cdeff88a3fb07e70fa51d4a632f7e4ba9e971ae65b5f1dcfae3f0b49e`),
candidate CI 14/14 (first attempt, no reruns), exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-20-v0434-release-evidence.md).
L165-01 is now installable from the public artifact and stays open for the
client's own runs; the client receives one reply covering v0.4.32, v0.4.33 and
v0.4.34 (the letters 164+165 reply draft), sent by the user.

### 2026-09-20 v0.4.35 released (letter 167 hotfix public)

v0.4.35 is public: tag `v0.4.35` on main `5858db1a`, one wheel
`wom_kit-0.4.35-py3-none-any.whl` (SHA-256
`a9fe67eef113fdc731357152f22178cf312affc7ead2c3a02652b33a7f7d48ec`),
candidate CI 14/14 (attempt 1 after one test-only correction: the approve-path test gained the Windows-only skip every approve-path CLI test carries), exact-merge installed verification,
anonymous download and two fresh-venv installations recorded in the
[release evidence](../../meeting-minutes/2026-09-20-v0435-release-evidence.md).
L167-01 is now installable from the public artifact and stays open for the
client's own run (the v0.4.35 bootstrap, the dry-run naming the rewrite, the
approved update under `--affirm-origin-main-rewritten`); the letter 167 reply
draft is sent by the user.

### 2026-09-21 v0.4.36 released (session grants, upload diagnostics, feedback archival)

v0.4.36 is public: tag `v0.4.36` on merge `a1cce66d`, one wheel
`wom_kit-0.4.36-py3-none-any.whl`, 3340372 bytes, SHA-256
`df925a87dc45cab4f228726b91ba9f481797049ae4291ebca77dc1dfa0f99941`.
Candidate CI passed 14/14. Exact-tag Windows verification used the unmodified
checker and preserved this wheel; the earlier local timeout remains failed.
Anonymous public download matched. The [release evidence](../../meeting-minutes/2026-09-21-v0436-release-evidence.md)
records source, artifact and installation checks with their actual boundaries.
L168-01 through L168-05 stay open for the customer's own run. Publication does
not establish that a customer upload succeeded or that all session-granted
operations completed without dialogs. New project/session-close feedback is
separate follow-up, and no future feature version is promised. The reply file
is delivered to the user for sending.
