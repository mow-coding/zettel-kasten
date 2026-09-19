# Archive infrastructure decision log — 2026-09-19, v0.4.30 (beta letter 163)

Executing model: Claude Opus 5 (implementation, tests, docs, bump, release),
under the user's standing approval to work through the backlog without
re-asking. Read-only design and two adversarial verifications ran as one
bounded Ultracode workflow (9 agents); their findings are folded into the
decisions below. No client archive, runtime, workspace or ledger was read or
changed; the client's letter was read from its feedback ledger only.

## Context

Letter 163 (2026-09-19) reports a successful v0.4.25 update and ~60 writes
under the session permission mode, then the defect that cost the client a
day: `mint-zet --approve` of a source-fidelity draft failed eight times with
`mint_service_failed` because the required
`--expected-source-fidelity-plan-sha256` was checked only inside the approved
writer, the dry-run never named it, the envelope hid the cause, and every
attempt left a `started` claim. The archive now holds 27 such claims with no
listing or closing command; `approval-integrity-audit` cannot complete on
8,600 mint receipts.

## Decisions

1. **Order.** v0.4.30 = the letter's core (⑤ mint gate first, ⑥ claim store,
   ⑥ audit cap, ⑫ inbox attention, ③c/[G] revert-edge, ④c discard inbound
   edges, 11 edge-target check, ⑩ truncated reference); v0.4.31 = ⑦ create-draft
   hints, ⑧ index pre-checks/incremental index, ⑪ warning explanation, ② preflight
   cause codes and transaction status, 18 scratch cleanup, and the gating half
   of 11. ①, ③(a)(b), ④(a)(b) are already public in v0.4.26/v0.4.27.
2. **Mint gate before the claim.** The CLI compares the argument with the
   preview's `current_source_fidelity_plan_sha256` before
   `_execute_exact_human_approved_write`; fixed codes
   `mint_source_fidelity_plan_sha256_required` / `_mismatch` /
   `_not_applicable` replace the free-text service message (the service raises
   the same codes so the writer stays a TOCTOU re-check). The dry-run gains
   `approval_handoff` and `next_safe_actions`; `object_id_only` names body
   lines, never the matched text; a hand-edited fidelity body is the warning
   `draft_body_changed_since_approval` (enters the binding basis, so
   `--allow-warnings` is required — intended and documented).
3. **Claim store.** A read-only listing (`exact-approval-claims`) that projects
   fixed fields after MAC verification, and a reviewed finalize
   (`exact-approval-claim-finalize`) with its own always-dialog operation kind.
   Review changes adopted: the receipt scan reads every `*.json` under
   `receipts/` and `.zettel-kasten/receipts/version-updates` leniently (batch
   item envelopes and future shapes count; an unreadable file fails closed);
   the writer runs under `exact_operation_writer_lock` and re-scans inside the
   lock; a minimum claim age (30 minutes, `--min-age-minutes 0` is a bound
   warning) protects writers that do not take the lock; the failure code is
   `operator_closed_started_claim_after_review`, never the abandon code, so
   resume discovery cannot treat a closed claim as absence; write evidence is
   declared `receipts_only` in the plan, the dialog copy and the receipt; a
   closed claim whose receipt is missing is backfilled by the next run;
   `project_version_update` claims are routed to their abandon path.
   Rejected: per-operation "no domain write" claims (unprovable for writers
   that leave no receipt).
4. **Audit paging, not a time filter.** `--kind` + `--offset` page one
   receipt kind in name order (v0.2 result with a `page` block); the unpaged
   v0.1 document and its single global cap are byte-identical.
5. **Inbox attention.** The `ai-start-here` block is attached after the
   broker returns (outside the claim window) to approved mint/create/retire
   results, their batches and the work-session create/claim envelope; a
   counting failure degrades to `status: unavailable`. The MCP create-draft
   site was dropped because that path is fail-closed by design.
6. **Edges and drafts.** `revert-edge --approve` is unconditional
   (`--exact-local` is a no-op; the conditional scope count drops to 10) and
   accepts `inbox/` sources, resolving a minted source by id; the discard plan
   reports `inbound_edge_count` / `inbound_edge_scan` and warns, but never the
   sources' ids or raw edge types (review finding); the mint dry-run reports
   `edge_target_check` without a gating warning (deferred: warnings enter the
   binding basis and would force `--allow-warnings` on existing automation).
7. **Batch fidelity.** The approve loop reuses the fidelity digest each item's
   dry-run bound instead of re-running the dry-run; the per-item mint binding
   (which hashes the source-fidelity projection) is part of the batch target
   the dialog approved, so a changed draft still refuses. OSError item
   blockers become fixed tokens.

## Carried to v0.4.31

Create-draft argument hints (⑦), index pre-checks and incremental index (⑧),
`internal_status_consistency_review_required` explanation (⑪), preflight
cause codes and transaction status (②), scratch cleanup (18), the gating
edge-target warning, and the session-ref exposure of the three always-dialog
writers added since v0.4.28 (coverage rows pending, target v0.4.31).
