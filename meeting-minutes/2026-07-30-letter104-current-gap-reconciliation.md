# Letter 104 Current-Gap Reconciliation

Date: 2026-07-30

Source letter:
`WOM-전달-20260730-104-v0.3.286-요청대조-미구현5건-버전스큐-단일본.md`

The source letter was reread in full from the beta archive. The beta archive
was treated as read-only: no WOM command was run there and no file was
changed.

## User Intent

The user asked whether Letter 104 had already been delivered, required an
actual reread rather than an assumed acknowledgement, and asked the WOM team
to include its unfinished work in the ongoing careful release train.

The letter had been delivered earlier. The reread established that it is
partly addressed but not resolved as a whole.

## Current Status By Request

| Letter 104 item | Current status | Evidence boundary |
|---|---|---|
| Weekly `continues` judgment | open | The current vocabulary still limits `continues` to a direct same-work/same-thread follow-on and excludes a generic ordered step. There is no weekly-course ruling. |
| Activate `sequence` | open | `sequence` remains provisional with no active edge type. v0.3.290 strengthens endpoint-type enforcement but deliberately does not activate it. |
| Register a third-party non-event Principal | open | Principal SQLite storage remains planned and there is no third-party registration plan/write/receipt lifecycle. |
| Restore lost Notion source URLs | partial | v0.3.277 audits the loss. v0.3.287 validates private `source_page_id` plus occurrence-ordinal evidence and blocks mismatched counts. There is no restoration writer, receipt, or recovery. |
| Recurring instance relationship | open | No accepted recurrence vocabulary or writer exists. |
| Mirror join trap documentation | partial | `source_page_id` is documented as the join authority, but the explicit warning not to join on the mirror's `zettel` field is absent. |
| Global CLI versus project-pin skew | partial in v0.3.291 | v0.3.291 adds honest runtime alignment and a verified one-invocation `version` bridge. It intentionally does not change a global Python installation and does not bridge write commands. |
| `base-link-types` revert or partial adoption | open | Current adoption is append-only for all missing base types. It has dry-run, approval, receipt, and failure rollback, but no later revert and no selected-type adoption. |
| Event anchor prerequisite | partial | The anchor contract is enforced and documented, but the actual create-draft, mint, then membership-plan command order is not presented as one prerequisite flow. |
| AI write-command routing | implemented in new templates, adoption open | v0.3.278 routes draft, edge, source, and objet actions through official commands. It does not rewrite an existing archive's old `AGENTS.md`. |
| `ai-start-here` self-reference and official search | implemented in new templates, adoption open | New templates start with `ai-start-here` and require `archive search --count-total`; existing archives need a readiness/adoption path. |
| Out-of-pipeline inbox draft detection | implemented in v0.3.279 | `inbox_pipeline_audit` and Doctor report possible unmanaged drafts without automatically rewriting them. |
| Reuse an existing objet and detect duplicate unmanaged bytes | partial | Official capture deduplicates identical content inside its managed flow. Pre-intake cross-path full-hash discovery and a Doctor signal for unmanaged duplicate bytes do not exist. |
| Feedback lifecycle routing | partial | `operator-feedback-plan` recommends `operator-feedback-record`, but the authoritative write-route/adoption guidance remains incomplete and overlaps Letter 105's v0.3.293 task. |

## Exact Answers To The Five Immediate Questions

1. A weekly number transition alone is not enough for `continues`. Use it only
   after a human confirms a direct continuation of the same work or argument.
   A generic N-week to N+1-week order belongs to the future `sequence`
   contract.
2. Historical provider URLs are not preserved as WOM canonical truth. Recovery
   must join surviving private `source_page_id` evidence to a reviewed local
   mirror. The writer is still missing.
3. Yes. Occurrence alignment must precede restoration. The 105 count-mismatch
   zets are correctly blocked by the v0.3.287 evidence plan.
4. No. Current `base-link-types` adoption has neither later revert nor
   selected-type partial adoption.
5. v0.3.291 is not the complete global-tool answer. It diagnoses the skew and
   can run verified project source for read-only `version`, but it neither
   updates the installed global tool nor routes the missing write commands.

## Ordered Follow-Up After Letter 105

Keep the already assigned v0.3.292 through v0.3.299 Letter 105 train. Start
Letter 104 follow-up at v0.3.300 in small reviewable slices:

1. installed-tool provenance and safe alignment plan;
2. manager-specific global-tool update lifecycle with restart/rollback truth;
3. weekly `continues` ruling plus mirror-join and event-anchor prerequisite
   documentation;
4. read-only cross-path objet duplicate preflight;
5. Doctor signal for managed-scope unmanaged duplicate bytes;
6. selected-type base-link adoption plan/write;
7. receipt-bound base-link revert/recovery;
8. manual-review-only `sequence` activation on the v0.3.290 endpoint gate;
9. non-event Principal registration plan, then a separate writer;
10. evidence-bound source URL restoration plan, writer, and recovery;
11. recurrence semantics and manual relationship activation.

Exact version allocation may split a lifecycle further when adversarial review
shows that plan, write, revert, and recovery cannot safely share one release.
