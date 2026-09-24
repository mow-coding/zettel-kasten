# Archive Infra Decision Log: Closed-Writer Triage (2026-09-24)

Status: owner decision recorded; groups 1-2 implemented for v0.4.40.

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
