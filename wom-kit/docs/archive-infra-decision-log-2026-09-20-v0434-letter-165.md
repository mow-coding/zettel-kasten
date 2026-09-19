# Archive infrastructure decision log — 2026-09-20, v0.4.34 (beta letter 165: presenter-bound session grants, legacy identifiers, feedback compose under exact approval)

Executing model: Claude Opus 5 (design v1 and v2, implementation, tests,
docs), solo and sequential, under the user's standing approval to work
through the backlog. The first design was corrected by a bounded read-only
Ultracode review (8 agents, `wf_9b0ff2e8-8a9`, 2026-09-20 04:15–04:35 KST);
the corrected design (`l165_v0434_design_v2`) is what was implemented, with
the three deviations recorded below. No client archive, runtime, workspace or
ledger was read or changed; every fixture is synthetic.

## What the letter established

1. A session permission grant (v0.4.24) was usable by any process that
   presented the three work-session refs: a second conversation of the same
   desktop app wrote eleven times under a limited mode granted elsewhere, and
   neither the claims nor `work-session --action inspect` said so.
2. The pre-WOM Notion identifiers (`ZET<number>` page names, 32-hex page ids)
   kept leaking into new zets, labels and intake filenames without a warning.
3. `operator-feedback-compose --approve` wrote a body and a receipt on the
   strength of `--reviewed-by` alone — no dialog, no claim — while every other
   v0.4 writer asks.
4. The revise path (record draft → body-check → `--intent revise`) was not
   announced where the operator needed it, and the revision-plan quality
   warnings did not say which field or table they meant.

## What the review established

1. The presenter check must live in `resolve_grant` itself, because the
   create-draft session route passes explicit refs; an environment-only check
   would have left that route open.
2. The `permission` row must stay immutable and be bound into the dialog's
   plan digest; a write counter in the registry row would drift the binding
   and need the held lock on every write. `max_writes` is therefore carried
   to v0.4.35 with a lock-free per-grant use ledger.
3. Rows written before v0.4.34 (the two-key shape) cannot be upgraded in
   place; they are refused with a fixed code until the grant is set again.
4. The presenter token is visible in the CLI transcript of the granting
   conversation; the honest claim is that it binds the grant to whoever
   received the approve result, and the fingerprint, the expiry and the
   operator's recover route are the guards against reuse. Only an in-process
   MCP holder gives the strong form.
5. The claim may grow by one optional top-level key; `public_reference` (five
   keys, pinned by twelve schemas) must not.
6. The fingerprint is the first ancestor process outside a fixed
   shell/launcher set, HMAC'd with the archive receipt key; it is evidence,
   never authority, and its absence is recorded, not refused.
7. The legacy-identifier regexes must exclude `_`-joined WOM ids
   (`zet_notion_db3_ZET0637`, `approval_<hex>`), scan body and title only, and
   downgrade for a record that itself came out of the Notion import.
8. The feedback body write routes through the CLI-context binding of the
   broker (not an exact-operation manifest), with a v0.2 receipt that carries
   the claim's five-key reference; the emergency lane under
   `version-update.lock` keeps its text-flag path.

## Decisions

1. **Presenter-bound, time-boxed grant.** `set-permission-mode --approve` for
   `limited` / `allow_all` mints a 32-byte presenter secret before the
   dialog; the row becomes `{mode, operations, presenter_sha256, granted_at,
   expires_at}` (`grant_hours` 1..24, default 8, an optional request key of
   the write and of the v0.4.32 preview, which now returns `would_box`). The
   dialog shows one more line (`유효 시간 N시간 · 이 대화(제시 토큰)에만 적용`).
   The secret is returned exactly once in that approve result
   (`presenter_token`, `presenter_token_returned_once`); a resume or
   re-review reports `presenter_token_available: false`. The conversation
   keeps it in `WOM_WORK_SESSION_PRESENTER`; an MCP-hosted approve returns
   it once through its envelope the same way and also holds it in the
   server process (`presenter_token_held_in_process`) — the implementation
   review established that no MCP tool can consume the holder (every exact
   write through MCP is `exact_human_approval_cli_required`), so a
   strip-only host would have stranded the grant.
2. **Resolution with reasons.** `resolve_grant_outcome` returns the grant or
   one fixed code: `work_session_presenter_missing`,
   `work_session_presenter_mismatch`, `work_session_grant_expired`,
   `work_session_grant_legacy_shape`, `work_session_grant_unavailable`,
   `work_session_grant_warning_review_required`. Every refusal means the
   dialog; a write that presented the refs and was refused carries
   `session_permission_refused {reason_code, dialog_shown: true}`. Expiry is a
   resolve-time refusal, never a state transition; an in-flight writer is
   never interrupted. `grant_still_permits` compares the presenter hash and
   the expiry too.
3. **Presenter evidence in the claim.** A grant-mechanism claim carries the
   optional key `session_presenter` (`wom-kit/exact-human-approval-presenter/v0.1`:
   work_session_ref, presenter_sha256, fingerprint_state,
   process_fingerprint_sha256, presenters_observed_before_this_claim,
   scan_truncated), covered by the MAC; fifteen-key claims stay valid. Results carry
   `exact_human_approval.presenter` and, when another fingerprint already used
   the session, `exact_human_approval.warnings:
   [work_session_second_presenter_observed]`. The claims listing gains
   `mechanism_counts`, `presenter_unknown_count` and per-row
   `presenter_recorded` / `session_presenter`; claims before v0.4.34 stay
   immutable. Earlier presenters are derived from the authenticated claims
   already in the store, never from the registry: only claim files modified
   since the grant's `granted_at` (minus a 5-minute slack) are opened, newest
   first, at most 2,000 of them, and `scan_truncated` says when that bound
   was hit (a claim older than the grant cannot be a presenter of it).
4. **Visibility and guidance.** `work-session` list / inspect rows carry
   `presenter_bound`, `permission_granted_at`, `permission_expires_at`,
   `grant_expired`, `grant_legacy_shape`; the session listing counts
   `non_manual_session_count`, `expired_grant_count`, `legacy_grant_count`.
   `ai-start-here` gains the registry-only `session_permission_attention`
   block (counts, `review_recommended`, the guidance line), a Markdown
   section, a `next_safe_steps` entry and a warning line. The guidance — the
   refs and the token stay in the granting conversation's process; another
   conversation continues a task through handoff/accept — appears in the
   approve result, the help text, the block and the contract.
5. **Deviation: no route-less revoke action.** Design v2 proposed a
   `revoke-permission` human action taking only the app and session refs.
   Every work-session human decision is bound to an actor (app + task route)
   that owns the claim (v0.4.20 invariant); a route-less action would bypass
   it. Operator control is therefore `set-permission-mode manual` in the
   granting conversation, `recover --approve` from any route of the same app
   (a new claim: the grant is cleared and the old conversation loses
   ownership), or the expiry. A lighter per-session revoke is carried.
6. **Warning gate by literal code.** CLI contexts digest their warning set
   (`warning_set_<hex>`); since the implementation review the three fixed
   legacy codes stay literal next to that digest
   (`exact_human_approval_warning_codes`), so the broker refuses any grant
   with `work_session_grant_warning_review_required` for every CLI writer
   (create-draft, mint-zet, mint-zet-batch, zet-revision-write,
   zettel-objet-link) and the result says so; a clean plan keeps its single
   digest code. `create-draft --approve` additionally refuses before any
   dialog (`create_draft_warning_override_required`) until `--allow-warnings`
   is given, on both the environment and the explicit-refs route.
7. **Legacy identifier detector.** One module, `legacy_identifier`:
   `(?<![A-Za-z0-9_])ZET[0-9]{3,4}(?![0-9A-Za-z])` (case-insensitive) and the
   32-hex / 8-4-4-4-12 page-id forms guarded the same way; v0.4.31-shaped
   evidence (counts, body lines, `matched_text_echoed: false`). Surfaces:
   `create-draft --dry-run` (`quality_check.warning_explanations`, bound
   warning `legacy_identifier_in_new_record`, refusal
   `create_draft_warning_override_required` before any dialog), `mint-zet
   --dry-run` (explanation only when matched, so clean plans keep their
   digest), `zet-revision-plan` (top-level warning; the write merges the
   reviewed plan's warnings into its own bound set instead of moving the
   plan digest, so pre-upgrade previews stay valid — a deviation from the
   review's `quality_review_digest`), `zettel-objet-link`
   (`label_legacy_identifier_review`, warn-only, bound), `source-intake`
   (`legacy_identifier_in_source_label`, plan-only). A migrated record gets
   `legacy_identifier_in_migrated_record`. Mapping availability is a
   read-only count of `zet_notion_%` / `zet_import_notion_%` ids in the
   generated index; the guidance names the full WOM id form and the
   `zet:notion:ZET<n>` resolver.
8. **Feedback compose under exact approval.** Operation
   `operator_feedback_body_write` (grantable; Korean copy: `운영자 피드백 편지
   본문 기록` / `본문 기록`). The CLI plans, checks the expected plan digest
   and a `person:` / `human:` reviewer (`feedback_compose_plan_changed`,
   `feedback_compose_reviewer_claim_invalid`) before any dialog, binds the
   request digest and the body digest, warns `feedback_body_revision` /
   `feedback_body_supersession`, and runs the unchanged service writer inside
   the claim. Receipts become v0.2 with an `exact_human_approval` envelope
   (five-key reference + operation); v0.1 receipts stay valid and the body
   check reports `exact_human_approval_reference_present`.
   `operator-feedback-compose` joins the reopened-writer set; the inventory
   counts do not move (the path was already approval-available).
9. **Revise path.** The five-step sequence (record draft → body-check →
   compose `--intent revise --expected-body-sha256` → record update →
   body-check) is announced on every compose result and on the body check's
   `feedback_record_binding_missing` branch. Draft-record creation after a
   created body is opt-in (`--create-draft-record`, sequential and outside
   the claim) — a deviation from design v2, because the existing compose →
   record sequence in the runtime routes and tests must keep working.
10. **Revision-plan explanations.** `quality_review.warning_explanations`
    names the field to fill (`document_type`, allowed values) or the table(s)
    whose parse review is missing (ordinal, header line, row count; cell text
    never echoed).

## Implementation review (2026-09-20, `wf_2ee314e9-7f4`, 6 reviewers + 4 verifiers, read-only)

Applied before the candidate: the explicit-refs create-draft route crashed
after the legacy refusal (an int left the held lane; now a sentinel and one
document); the explicit-refs route now carries `session_permission_refused`
(the CLI passes `resolve_grant_outcome`'s pair to the broker); the literal
legacy codes survive the context digest (decision 6) and `mint-zet-batch`
folds an allowed item's code into the batch set; the verbatim fidelity body
is scanned as written; the migrated-record downgrade keys on the record id
prefix only; intake scans the stored source-map / manifest label too; the
mint `quality_check` shape changes only for flagged plans; the presenter
scan is bounded newest-first from `granted_at` with `scan_truncated` in the
claim and the result, and interrupts propagate; `grant_expired` is computed
at page time so a listing cursor survives the expiry; the draft/intake
privacy gates refuse a pasted `WOM_WORK_SESSION_PRESENTER=` line and the
next-step sentence says exactly that; the MCP envelope returns the token
once (decision 1); compose validates the expected digest shape before
comparing, reports a blocked approve as an approve, reads the persisted
receipt for `exact_human_approval_reference_present`, creates the draft
record on an `already_written` replay too, and the revise-path step 1 names
`--create-draft-record`. Not changed (recorded): a partial compose after a
claim-referencing receipt leaves the claim `started` for the standard
finalize route; the `work-session-permission/v2` schema string is a
constant of the grant projection, not a new document.

## Carried to v0.4.35

`max_writes` with a per-grant use ledger, a per-session revoke action, bulk
revoke, session refs for the always-dialog writers and for compose, the
select-all group for `git-backup-reconcile-plan`, a reviewed re-PUT, the
letter-164 ⑧ delivered-feedback archival and the 8b index participation.
