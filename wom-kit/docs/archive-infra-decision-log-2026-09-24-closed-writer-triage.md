# Archive Infra Decision Log: Closed-Writer Triage (2026-09-24)

Status: owner decision recorded; groups 1-5a, the title-remap reclassification, group 6 and the removals implemented for v0.4.40; five removals reversed on 2026-09-25 (see Correction).

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

Letter 147 listed `saved-view-write` among the commands it needed. The
dormant writer and its revert already re-derived their plan under
`_SavedViewLock` and refused drift; `saved-view-write` / `saved-view-revert
--approve` now bind that plan digest through the group 3 route (the route
accepts a `sha256:`-prefixed digest). The write keeps its
`--affirm-view-reviewed` requirement before any dialog. Evidence:
`test_saved_view_exact`.

Letter 105 asked to find an objet by its original filename;
`objet-source-metadata-write --approve` records one reviewed filename
observation through the private metadata engine, which already bound the
intake digest and its own plan digest. The approval binds that plan digest.
Deviation to note: the approval broker binds reviewers as `person:<id>` while
the engine's receipt schema pins `operator:<id>`; the CLI accepts either form
and uses the same `<id>` in both, checked before the dialog so a malformed id
never consumes an approval. Evidence: `test_objet_source_metadata_exact`.

Letter 116 retired duplicate external locators with
`external-locator-deactivate` (R-B4b-12). The dormant writer re-derived its
plan under the per-zet locator lock; `--approve` now binds that plan digest
(`--expected-plan-sha256` stays required). Evidence:
`test_external_locator_deactivate_exact`.

Letter 129 hit update collisions. `project-bytecode-repair` deletes only the
untracked `.pyc`/`.pyo` files and empty `__pycache__` folders an update left
behind, and `project-version-update-collision --action preserve-relocate`
moves one reviewed collision aside (never deletes it). Both run on the
project folder, so the approval is recorded in the project's archive (the
project-version-update approval root). Bytecode repair binds its repair plan
digest; collision relocation binds the failed update's materialization plan
digest, the entry ref and the action. Evidence:
`test_project_bytecode_repair_exact`, `test_project_update_collision_exact`.

`zet-revision-restore-proposal-from-snapshot` copies one retained
before-snapshot into a private restore proposal file that the open
`zet-revision-restore-write` consumes; canonical zets never change. The
approval binds the revision receipt digest and the preview's plan digest; the
command gained `--reviewed-by`. Evidence: test_cli restore-proposal tests.

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

## Correction: Five Commands Restored (2026-09-25)

After the removal, a read-only inventory of the owner's design documents
(ideas, roadmap and backlog notes from 2026-05 to 2026-09) found that five
removed commands carry the owner's ZET sharing and ownership design, the
declared v0.5 roadmap line: `delegate-zet` is the only "share" step of
publish -> share -> accept -> reflect (including the one-use claimable license
the owner specified on 2026-05-23), `transfer-ownership` is composite-archive
inheritance/split/transfer, `quarantine-foreign-block` and
`record-quarantine-decision` are the receiving checkpoint, and `github-repo`
is the planning tool the 2026-06-05 onboarding spec shows first. Claude had
classified them as useless because they were never usable after v0.4.0; that
judged availability, not the owner's intent.

They are restored exactly as before the removal (dry-run previews available,
approval still fixed closed) together with their MCP previews
(`delegate_zet_check`, `ownership_transfer_check`,
`quarantine_foreign_block_check`, `record_quarantine_decision_check`,
`github_repository_setup_plan`). Their approval opens with the ZET sharing
design, not by itself. v0.4.40 therefore removes 12 commands, not 17;
`source_scan_plan` stays removed with `scan-source`.

Lesson recorded: before removing a command, check the owner's design
documents and roadmap, not only customer letters and current availability.

## Independent Review Before Release (2026-09-25)

A separate review context read the v0.4.40 diff for paths where a reopened
writer could write without a reauthenticated claim. It found none, and no
added dialog under a valid session grant. Fixed before release:

- `derive-text capture` now re-plans each item from the exact bytes it
  writes and refuses `derived_text_capture_item_changed_after_approval` when
  they differ from the approved item.
- `identity-reconcile` passes the values bound into the approval to the
  writer instead of re-reading them.
- A reconcile batch that contains `content_change` items needs
  `--content-changed-ack`, like one zet (a flag, not an extra dialog).
- A blank `--zettel-id` is refused; duplicated calls and dead code left by
  patch scripts are removed.

Known limitation kept: several reopened writers do not name their approval in
a receipt, so `exact-approval-claim-finalize` can only warn
(`exact_approval_claim_write_evidence_receipts_only`) for a started claim of
theirs, as for earlier receipt-less operations. In-process flags such as
`_exact_verified` are reachable only from Python callers, not from the CLI or
MCP.

## Group 7: Legacy Coordination Retire (v0.4.41)

Owner delegation (2026-09-25): designs for the remaining closed writers follow
Claude's recommendation; each is recorded as a delegated operating choice.

Letters 142, 148 and 156 were blocked three times by
`legacy-coordination-cleanup` (`collab_present_in_target`,
`nested_git_repository_present`, `git_tracking_check_failed`). Delegated
choice (Claude recommendation): retire by moving, never deleting.
`--destination` moves the whole folder in one same-volume rename, keeps
collaboration records and nested repositories intact as preserved classes,
keeps the user's global Git configuration for the tracking check and names
its cause, binds the plan digest under one exact approval recorded in the
workspace archive, verifies the moved folder, and writes a content-free
receipt. The delete-only approve stays fixed closed. Evidence:
`test_legacy_coordination_retire`.

## Group 7b: Notion Page Recovery (v0.4.41)

Letters 116-118 (620 pages) and 142/148/156 (zero requests could be produced)
were blocked because execution was fixed closed and the CLI accepted only the
letter-118 577+43 batch. Delegated choice (Claude recommendation): accept any
self-consistent reviewed request (unique groups, per-group counts equal to
items, total equal to `expected_item_count`, each group bound to a credential
and workspace fingerprint), and run the existing resumable engine after one
exact approval bound to the plan digest (which covers the exact page list).
The credential capability is issued in-process and adds no dialog. A request
builder from existing ledgers and proven credential reuse are the next step;
moving verified-recovered pages to the Notion trash comes after that.
Evidence: `test_notion_page_recovery_exact`.

## Planned: Notion Trash Cleanup After Verified Recovery

Owner idea (2026-09-24), delegated design (2026-09-25, Claude
recommendation). Not implemented; this records the design and the verified
provider facts it rests on.

Provider facts, checked against the official Notion API reference on
2026-09-25: a page moves to the trash with `PATCH /v1/pages/{page_id}` and
body `{"in_trash": true}` (API version 2026-03-11 replaced `archived` with
`in_trash`); `{"in_trash": false}` restores it; the integration needs the
"Update content" capability. There is no permanent delete through the API.

Design:
- Only pages with a verified `recovered` result qualify: a terminal journal
  row, every stored fragment re-hashing to its recorded digest and size, and
  manifest and projection rows present. A read-only plan lists the
  qualifying pages; its digest covers the exact page list and the recovery
  receipt digests.
- Immediately before each PATCH, a fresh GET must show the page unchanged
  since recovery (`last_edited_time`) and not already in the trash; a changed
  page is skipped and reported.
- The credential must carry a verified update capability; the current
  read-only capability set is not enough, so adoption gains an explicit
  update-capability check.
- One exact approval (a native dialog, or none under a valid session grant)
  covers the list. A journal row precedes each PATCH and a terminal row
  follows a GET confirming `in_trash: true`; an interrupted run resumes.
- A restore plan sets `in_trash` back to `false` for the same list.

## Planned: New-User Entry (onboard, init, runtime skill)

Finding (2026-09-25, read-only research): in v0.4.40 a new user cannot create
an archive at all. `onboard --approve`, non-dry-run `init` (CLI and MCP) and
`runtime-skill-install/-uninstall --approve` are fixed closed, and
`setup-windows.ps1 -ApproveOnboarding` calls the closed `onboard` and exits
1. Docker onboarding cannot show the Windows approval dialog at all.

Delegated design (Claude recommendation, not yet implemented):
- `onboard` dry-run gains a `plan_sha256` over type, archive id, principal,
  profile, template and layer digests, WOM-kit version, target path hash and
  target state (absent or empty) with its parent identity.
- One dialog (a session grant cannot apply: no work session exists yet).
  After the decision, create only what the key and claim need (target folder,
  final `.gitignore` with `profiles/local/`, final `archive.yml`, claims
  folder), then write the claim in the new archive; if that fails, remove
  exactly those files. The writer then re-derives the plan, copies the rest,
  runs strict doctor and writes `receipts/onboarding/<approval_id>.json`.
  This deliberately moves the claim-store setup ahead of the claim, as the
  broker already does for the key and claims folder.
- `init` becomes an alias of this route; MCP `archive_init` stays dry-run and
  returns the CLI command; `setup-windows.ps1` runs the native
  `archive.exe onboard --approve` instead of Docker.
- `runtime-skill-install/-uninstall --approve` require `--archive-root`; the
  claim and a hash-only receipt go in that archive, and the digest binds the
  existing operation plan (exact file set) plus the archive id and the
  target folder identity. `onboard --install-skill <host>` covers archive and
  skill under one approval for beginners.

## Implemented: New-User Entry (v0.4.41, 2026-09-25)

Implemented by Claude (Opus 5.5) under the owner's delegation. What shipped:
- `onboard --dry-run` prints `plan_sha256`; `onboard --approve --reviewed-by`
  opens one dialog bound to it (`onboard_archive` operation). After the
  decision the plan is derived again (target still absent or empty, not a
  link); then the folder, `archive.yml` and the safe `.gitignore` are written,
  the key and claim are created in the new archive, and the writer creates
  the rest, runs strict Doctor and writes `receipts/onboarding/<plan16>.json`.
  If the key or claim step fails, the target is returned to absent or empty.
- `init --approve` forwards to the same route. MCP `archive_init` is unchanged
  (dry-run only).
- `setup-windows.ps1 -ApproveOnboarding` runs the Windows-native `archive
  onboard --approve` after the Docker dry-run; `setup-unix.sh
  --approve-onboarding` explains that Linux and macOS have no approval dialog
  yet and stops.
- `runtime-skill-install/-uninstall --approve --archive-root <archive>` run
  after one exact approval recorded in that archive (dialog, or none under a
  valid session grant); the service reauthenticates the claim before any host
  write. Without `--archive-root` they are refused before any dialog.

Deviations from the plan above (for the owner to confirm or correct):
- The onboarding digest binds type, archive id, principal id/kind/name,
  archive name, provider profile, the resolved target path and the WOM-kit
  version. Template and layer digests and the parent identity are not bound;
  target absence/emptiness is re-checked after the decision instead.
- The onboarding receipt is named by the plan digest, not the approval id
  (the approval summary is in the command result).
- On a key or claim failure the whole (previously empty) target is cleared,
  including the lock and claim folders the key step created. The Windows
  archive key for that archive id may remain; a retry reuses it.
- `onboard` is recorded as a documented bootstrap exception in the
  writer-session coverage manifest: it never uses a session grant, because
  no session can exist for an archive that does not exist yet. This is not a
  new always-dialog operation: every grantable operation stays grantable.
- Runtime skill: the digest is the existing operation plan (it already binds
  the target-path hash, source package and prior manifest); no separate
  receipt is written in the archive, the claim is the record.
  `onboard --install-skill <host>` is not implemented yet (carried).

## Implemented: Relation Candidate Accept (v0.4.41, letter 108)

`relation-candidate-decide --decision accept` opens (operation
`relation_candidate_accept`). One approval binds a digest over the reviewed
relation plan, the candidate, edge type, visibility, the review reason's
hash, confidence, and the edge writer's own item approval digests for that
exact edge. The service re-derives the edge preview under its lock, verifies
the claim through the existing batch-authority mechanism narrowed to that one
edge, writes the edge, then the judgment record and receipt. The
`--decision` conditional scope is removed (ten conditional scopes remain).
An accepted pair leaves the candidate plan, so a repeat is refused before any
dialog.

## Implemented: External Import (v0.4.41, letter 141)

`import-external --approve` opens (operation `import_external`). The customer
had used it for 437 notes before v0.4.0 closed it. The dry-run now returns a
`plan_sha256` over the target archive, source, export path, locator policy,
receipt path and, per item, the draft id, source digest, external id and
source path; the writer re-discovers the export once, rebuilds the same
projection and refuses unless it equals the approved digest, then writes the
drafts and receipt with the pre-v0.4.0 rollback of partial files. The
pre-v0.4.0 apply tests were restored and pass on the new route. Limit stays
at most 1000 items per run.

## Implemented: Credential Lifecycle (v0.4.41, letter 119)

While wiring Notion trash, Claude found that an adopted credential becomes
usable for page recovery only after a lifecycle decision records it as the
workspace default (its scope binding is then `persisted`). With
`credential-lifecycle --approve` fixed closed, no customer credential could
ever pass the request builder's readiness check, so Notion recovery (and the
trash cleanup after it) was unreachable in practice. `--approve` now records
the reviewed plan after one exact approval (operation
`credential_lifecycle`) bound to its `plan_sha256`; the existing registry
core re-derives the plan and refuses drift. Labels only: nothing is deleted
or revoked, no secret is read.

## Implemented: Prehashed Objet Ledger (v0.4.41, letters 038-039, 164, 168)

Delegated decision (Claude recommendation): hash-only registration stays. It
is how large external stores (for example a Notion source export) were
registered, the upload planner already classifies such rows as
byte-external (`external_prehashed`), and every record says WOM-kit did not
verify the bytes. `--approve` runs after one exact approval (operation
`prehashed_objet_ledger`) bound to a dry-run `plan_sha256` over the archive,
store kind and label, field names, row cap, ledger file digests and the exact
candidate rows; the writer re-derives it and refuses drift. One store-label
scheme (letter 168): the dry-run lists the registered store labels and warns
`store_ref_not_a_registered_store_label` when the label is not one of them;
it is a warning, not a blocker, because an external prehashed store need not
be an object-storage registration.

## Implemented: Notion Link Convert (v0.4.41, feature request 34)

The conversion had nothing to convert: no manifest record said which objet
a Notion locator meant. The mapping path now comes from Notion recovery: a
locator's page id (the last id in the URL path, or the `?p=` peek id; a
`#block` fragment is ignored) is looked up in the recovery projection rows
(`receipts/import/notion-page-recovery-*.jsonl`, outcome `recovered`), and the
recovered objet becomes a candidate (`match_kind: recovered_notion_page`).
`--approve` (operation `notion_objet_link_convert`) binds a digest over the
zettel, locator fingerprint, object, occurrence count, visibility, conversion
receipt and the edge writer's own item digests; the batch authority is
narrowed to that one embed edge, as for relation accept. The zettel body is
not rewritten.

## Implemented: Tiro Fetch (v0.4.41, feature request 13)

`tiro-lossless-recovery-fetch-run --approve` opens (operation
`tiro_lossless_recovery_fetch`). The approval binds a digest over the output
path, the row caps and hashes of the workspace id, note id and credential
reference; the credential is read only after the reauthenticated approval.
The pre-v0.4.0 apply tests were restored and pass on the new route.
Deviation (for the owner): Tiro keeps its operator credential reference
(`env:` / `keyring:` / `credential-manager:`), because there is no Tiro
equivalent of `credential-adopt`; a Tiro adoption path would be separate
work. The fetch is read-only against Tiro and writes a private bundle under
`workbench/` plus a receipt.

## Implemented: Add Source (v0.4.41)

`add-source --approve` opens (operation `add_source`). The dry-run prints a
`plan_sha256` over the exact source binding, whether an ignored local root
profile is written (its path only as a hash), `--replace`, and the current
`source-bindings.yml` bytes; the writer re-derives it and refuses drift.
The pre-v0.4.0 apply tests were restored (their `scan-source` step was
dropped: that command was removed in v0.4.40). An IMAP mailbox source can
now be registered; reading mail stays closed (next section).

## IMAP (v0.4.41): manifest reopened, header scan stays closed

`imap-mailbox-adapter-manifest-write --approve` opens (operation
`imap_mailbox_adapter_manifest`): it writes the local non-secret adapter
policy after one exact approval bound to a digest of the reviewed arguments
(reference values only as hashes). The pre-v0.4.0 apply test passes again.

`imap-mailbox-header-metadata-scan` stays closed. Its preflight requires a
legacy `credential-access-approval` receipt, and that command became a
plan-only preview in v0.4.0, so no such receipt can be produced; and headers
alone do not meet the request to keep full messages and attachments.
Delegated design (Claude recommendation, next work): a full-message IMAP
fetch under one exact approval that stores each selected raw RFC 822 message
(`.eml`, which keeps its attachments losslessly) as an objet through the
existing intake chain, with the credential reference read only after the
approval; the header scan is then either folded into it or removed.

## Still closed: notion-recover (recommendation recorded)

`notion-recover` was the client-requested one-command wrapper (2026-06-22,
v0.3.136) over `notion-ancestor-crawl-plan`, `credential-access-approval`,
`notion-ancestor-fetch-adapter-run` and `notion-ancestor-merge-plan`. Two of
its parts no longer run (the fetch adapter was removed in v0.4.40; the access
approval is a plan-only preview since v0.4.0), so it cannot simply reopen.
Recommendation (not implemented): keep the client's intent, one command for a
beginner, by turning it into a read-only guide over the current chain
(`credential-adopt` -> `credential-lifecycle` -> `notion-page-recovery-request-build`
-> `notion-page-recovery` -> `notion-page-trash`) that reports which step is
done and prints the exact next command. Changing an existing command's
meaning is left for the owner to confirm.

Correction (2026-09-25, v0.4.42): `notion-recover` restores missing Notion
parent locations (the ancestor crawl, fetch and merge), not page bodies. A
guide over the page-recovery chain would change what the command means, so
the recommendation above is withdrawn. The command stays closed; the owner
decides between redesigning the parent-location fetch on the current
credential and adapter, or removing the command.

## Implemented: Notion Trash Cleanup (v0.4.41)

Implemented by Claude (Opus 5.5) under the owner's delegation, following the
plan above:
- `notion-page-trash <archive> --request <recovery request> --dry-run |
  --approve [--restore]` (operation `notion_page_trash`). The plan digest
  covers the mode, the request digest, the slice, and per page the recovery
  plan digest, completion time and fragment digests.
- The Notion adapter gains one write, `move_page_to_trash`: `PATCH
  /v1/pages/{id}` with exactly `{"in_trash": bool}`, one transport attempt,
  never retried; every other call stays a GET.
- A second credential-capability profile `notion_page_trash_write` (GET
  `retrieve_page`, PATCH `move_page_to_trash`); the recovery profile is
  unchanged. The live token exists only in a spawned child, as for recovery.
- Journal `profiles/local/notion-page-trash/<plan>.journal.jsonl` (ignored,
  holds page ids); content-free receipt `receipts/notion-page-trash/`.

Deviations from the plan (for the owner to confirm or correct):
- Recovery did not store `last_edited_time`, so "unchanged since recovery"
  compares the fresh `last_edited_time` with the recovery completion time:
  an edit in the same minute as the completion or later counts as changed
  (Notion reports minutes), so some unchanged pages may be skipped, never the
  reverse.
- Adoption did not gain an update-capability check: the adopted credential's
  receipt records only read capabilities and Notion offers no endpoint that
  reports an integration's capabilities. The first PATCH proves it; a 403
  stops the run with `notion_update_capability_missing` after one refused
  request.
- Restore moves back only pages whose latest trash-journal outcome is
  `trashed`; pages that were already in the trash stay there.

## Implemented: IMAP Full-Message Fetch (v0.4.42)

Implemented by Claude (Opus 5.5) under the owner's delegation, following the
IMAP recommendation above:
- `imap-mailbox-message-fetch <archive> --source-id <imap source> --batch-id
  <id> --imap-host <host> --username-ref env:NAME --app-password-ref env:NAME
  [--mailbox] [--selection-rule] [--since-days] [--max-messages] --dry-run |
  --approve` (operation `imap_mailbox_message_fetch`).
- The dry-run reads no credential and opens no connection. Its plan digest
  binds the archive, source, batch, host/port/credential references and
  mailbox (the host, references and mailbox only as hashes), the selection
  rule and window, the message cap, the timeout and the output folder.
- `--approve` runs after one exact approval bound to that digest (a native
  dialog, or none under a valid session grant); the writer re-plans, refuses
  any drift, and only then reads the two environment references.
- The mailbox is opened read-only (EXAMINE) and every body is fetched with
  `BODY.PEEK[]`, so no server flag such as Seen changes. Each message is
  written byte for byte as `workbench/imap-fetch/<batch>/mail-NNNN.eml`
  (attachments stay inside it losslessly) with create-new semantics under an
  output folder that must not exist.
- It writes `source-intake-batch-request.json` next to the files (one
  `message/rfc822` primary-source item per message) so the existing intake
  chain captures them as objets under its own approval, and a content-free
  receipt `receipts/imap-message-fetch/<batch>.json` (file digests, sizes,
  status, stop reason). Headers, subjects, addresses, bodies, the host and the
  credential values are never printed or stored in the receipt.

Deviation: the fetch writes the intake request but does not capture the
objets itself; capture stays the intake chain's own approved step, so one
approval is not stretched over two different effects.

`imap-mailbox-header-metadata-scan` stays closed and is superseded by the
fetch. It was part of the v0.3.49-v0.3.62 IMAP design chain, so it is not
removed without the owner's confirmation; the recommendation is to remove it
together with its plan-only audit companions.
