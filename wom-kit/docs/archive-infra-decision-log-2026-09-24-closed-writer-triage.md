# Archive Infra Decision Log: Closed-Writer Triage (2026-09-24)

Status: owner decision recorded; groups 1-5a, the title-remap reclassification, group 6 (in progress) and the removals implemented for v0.4.40.

## Decision (owner, 2026-09-24)

v0.4.0 closed 58 compound-approval writers until each had an
operation-specific exact human approval. A read-only triage matched every one
against the parser, the capability matrix and the beta letters. The owner
accepted the recommendation as a whole and chose customer-impact order:

| Recommendation | Count | Commands |
|---|---|---|
| Reopen under exact approval | 30 | activity-group-membership-write / -removal-write / -recover / -removal-recover, ai-scratch-gc, zet-catalog-pass-cleanup, derive-text capture, external-locator-deactivate, identity-reconcile, markup-normalization / -recovery / -revert, notion-page-recovery and notion-recover (after a request builder and proven credential reuse), objet-source-metadata-write, onboard, principal-register / -unregister, project-bytecode-repair, project-version-update-collision, remint-reconcile, retire-draft-reconcile, repair-gitignore, restore-drill, runtime-skill-install / -uninstall, saved-view-write / -revert, zet-revision-restore-proposal-from-snapshot, zettel-objet-link-revert |
| Replace by an open path | 8 | credential-keepassxc-write → credential-adopt; external-locator-revert → external-locator-record --revert-recovery; notion-ancestor-fetch-adapter-run → notion-recover; notion-objet-manifest-locator-label → external-locator-record; object-storage-wom-location-reconcile → object-storage-adopt-existing; scan-source → source-intake-batch; tiro-lossless-recovery-capture → source-intake-chain; zet-abstract-backfill-write → zet-revision-write |
| Retire | 11 | delegate-zet, transfer-ownership, quarantine-foreign-block, record-quarantine-decision, github-repo, objet-capture-enable, object-storage-upload-evidence, zet-abstract-backfill-recover, zet-abstract-backfill-revert, zet-title-remap-recover, zet-title-remap-revert-recover |
| Needs design first | 9 | add-source, credential-lifecycle, imap-mailbox-adapter-manifest-write, imap-mailbox-header-metadata-scan, import-external, legacy-coordination-cleanup, notion-objet-link-convert, prehashed-objet-ledger, tiro-lossless-recovery-fetch-run |

Reopen order: (1) receipt reconcile, (2) AI scratch cleanup, (3) markup
normalization and objet-link revert, (4) activity groups and principals,
(5) new-user entry (onboard, runtime skill, restore drill), (6) the rest.
Every reopened writer uses the existing broker: one native dialog, or none
under a valid limited/allow_all session grant (2026-09-17 decision); no new
dialog exclusion is added.

Facts found during the triage that shaped the order: `activity-cleanup`
refuses in-archive roots, so it cannot replace `ai-scratch-gc`; the Windows
setup script's `-ApproveOnboarding` calls the closed `onboard`; the closed
`restore-drill` leaves `--require-restore-drill` preflights unsatisfiable.

## Group 1: Receipt Reconcile (v0.4.40)

Letters 147, 148 and 156 reported 3,345 mint and 3,346 retired-draft receipt
mismatches, mostly an `assets` field added after mint by an ordinary objet link,
with the only repair writer closed.

- `remint-reconcile` / `retire-draft-reconcile --approve` and the new
  `remint-reconcile-batch` / `retire-draft-reconcile-batch` run under the
  operations `remint_reconcile` / `retire_draft_reconcile`.
- The batch dry-run lists every drifted receipt, its `format_drift` /
  `content_change` class and the changed fields. One approval covers the list.
- Each item's evidence digest (zet id, drift class, review-plan digest, current
  bytes of every receipt ref) is bound into the approval and re-derived inside
  the writer immediately before that item writes; a moved item fails as
  `receipt_reconcile_item_changed_after_approval`.
- The apply writers refuse without a private token that only the batch
  service builds after reauthenticating the claim.
- A single-zet `content_change` approve keeps its `--content-changed-ack`
  requirement and is refused before any dialog without it.
- Audit receipts and the batch receipt carry the approval reference;
  mint receipts are repaired first, then retired-draft receipts, because the
  latter point at the former.

Evidence: `wom-kit/tests/test_receipt_reconcile_exact.py` (synthetic archive,
injected dialog and key).

## Group 2: Scratch Cleanup (v0.4.40)

The triage table reopened `ai-scratch-gc`, while the earlier letter-173 D
decision had said to extend `activity-cleanup` instead. Asked once, the owner
chose both (2026-09-24): `activity-cleanup` grows to in-archive AI scratch for
bulk activity-scope cleanup, and `ai-scratch-gc` reopens as the small tool that
deletes only what one zet explicitly references.

- `ai-scratch-gc --approve` binds the mint-time cleanup projection (every
  candidate's path, SHA-256 and size) as operation `ai_scratch_gc`, re-derives
  it immediately before deleting, refuses any change as
  `scratch_cleanup_approval_binding_changed`, and writes a receipt that
  carries the approval reference. A zet with no ready candidate opens no dialog.
- `zet-catalog-pass-cleanup --approve` binds the one SHA-verified catalog-pass
  artifact as operation `zet_catalog_pass_cleanup`; the command gained a
  JSON-only `--format` so refusals are machine-readable.

Evidence: `wom-kit/tests/test_scratch_cleanup_exact.py`.

## Group 3: Markup Normalization and Objet-Link Revert (v0.4.40)

Letters 115-117 applied 1,994 normalizations before v0.4.0 closed the writer
(142 later listed 1,075 candidates); 136 used objet-link revert and 159 was
blocked without it.

- One shared route binds the exact approval to the digest each writer's own
  dry-run already computes (`plan_digest_approval_binding`). The writer
  re-derives its plan under its own lock and refuses any drift; a supplied
  `--expected-plan-sha256` must still equal the fresh plan; a plan with nothing
  ready opens no dialog.
- `markup-normalization`, `-revert` and `-recovery` and
  `zettel-objet-link-revert` stay closed when called without the claim; every
  receipt they write carries the approval reference.
- The dormant revert code still called the pre-v0.4 objet-link lock
  signature; it now takes the same per-zet control artifact lock as the
  forward link.
- A legacy test reached a real native dialog once while group 3 was being
  verified (synthetic temporary archive, no customer data); every reopened
  command's legacy tests now replace the dialog.

Evidence: `wom-kit/tests/test_markup_and_link_revert_exact.py`.

## Group 4: Principals and Activity Groups (v0.4.40)

Letters 102, 104 and 112 asked for event groups and non-owner Principals;
both were implemented and never usable after v0.4.0.

- `principal-register` / `principal-unregister` use the group 3 plan-digest
  route; their receipts name the approval.
- `activity-group-membership-write`, `-removal-write`, `-recover` and
  `-removal-recover` bind the approval to the reviewed request digest and the
  review/recovery plan digest (`activity_group_approval_digest`); the writer
  re-verifies both under its own lock. Their receipt schemas are unchanged, so
  the approval reference lives in the claim record.
- The review affirmation and a fresh dry-run are checked before any dialog.
- Local verification now runs through a harness that replaces the real native
  dialog, so a legacy test can never open a window on the owner's desktop.

Evidence: `wom-kit/tests/test_group_principal_exact.py`.

## Group 5a: Restore Drill, .gitignore Repair, Identity Reconcile (v0.4.40)

A closed `restore-drill` left `preflight --require-restore-drill` and
`upgrade-check --require-restore-drill` unsatisfiable; `repair-gitignore` and
`identity-reconcile` had been used successfully before v0.4.0.

- These writers act from the CLI, so a shared route (`_cli_exact_route`)
  binds the approval to a digest of the fresh plan, re-derives the plan inside
  the approved writer, reauthenticates the claim, and only then writes. The
  restore-drill digest leaves out the excluded-file count, because the
  approval claim itself lands in the excluded `profiles/local/` area.
- `identity-reconcile` binds the three reviewed digests (archive, identity,
  proposed identity); a stale digest is refused before any dialog.
- Refusals before any dialog now say in text mode that the write did not
  start and name the reason code, instead of the generic "state uncertain".
- `onboard` and `runtime-skill-install` / `-uninstall` stay closed for now:
  a new archive has no claim store yet, and the skill installer writes outside
  any archive. Where their approval record lives needs a design decision.

Evidence: `wom-kit/tests/test_group5_restore_gitignore_identity_exact.py`.

## Group 6: Derived Text Capture (v0.4.40)

Customer impact first: letters 033-036 attached extracted, OCR and ASR text to
existing objets (3,746 links) before v0.4.0 fixed the writer closed; since
then only a new capture could carry a derived-text half. Nested
`derive-text capture` (single and `--from-manifest`) now writes under exact
approval. The dry-run reports `plan_sha256` over the exact text identity,
source objet, derivation metadata and planned action; approval binds that
digest (one dialog, or none under a valid session grant). The writer
re-derives the plan after the claim and refuses
`derived_text_capture_plan_changed`; `--expected-plan-sha256` binds the
reviewed preview; a run with nothing to write opens no dialog. A missing
reviewer is refused as JSON before any text is read. Evidence:
`test_derive_text_capture_exact`.

## Removal of Retired and Replaced Writers (v0.4.40)

Owner direction (2026-09-24): a useless closed command is deleted outright, not
kept closed; commands customers need are restored first.

Removed from the CLI (with their aliases): `delegate-zet`, `transfer-ownership`,
`quarantine-foreign-block`, `record-quarantine-decision`, `github-repo`,
`objet-capture-enable`, `object-storage-upload-evidence`,
`zet-abstract-backfill-write` / `-revert` / `-recover`,
`credential-keepassxc-write` (use `credential-adopt`), `external-locator-revert`
(use `external-locator-record --revert-recovery`),
`notion-ancestor-fetch-adapter-run` (use `notion-recover`),
`notion-objet-manifest-locator-label` (use `external-locator-record`),
`object-storage-wom-location-reconcile` (use `object-storage-adopt-existing`),
`scan-source` (use `source-intake-batch`), `tiro-lossless-recovery-capture`
(use `source-intake-chain`). The six MCP check tools that only previewed those
writers (`delegate_zet_check`, `ownership_transfer_check`,
`quarantine_foreign_block_check`, `record_quarantine_decision_check`,
`github_repository_setup_plan`, `source_scan_plan`) are removed too.

Kept: their read-only companions (plans, audits, recovery plans, review
indexes), shared services, receipt schemas and readers, so historical receipts
stay auditable. Guidance that named a removed command now names its
replacement.

Reclassified: `zet-title-remap-recover` and `zet-title-remap-revert-recover`
move from Retire to Reopen. A read-only investigation showed that no newer
command adopts a legacy interrupted title-remap journal or lock, so deleting
them would strand such an archive; the owner was told. Both now write under
exact approval bound to the case digest, plan digest and expected action
(the activity-group multi-digest gate): one dialog, or none under a valid
session grant. Evidence: `test_title_remap_recover_exact`, test_cli title
recovery tests (declined writes nothing, approved recovers once).

Evidence: parser, capability inventory and MCP surface pins in
`test_v03299_predecessor_surfaces.py`; `tests/removed_commands_v0440.py`.
