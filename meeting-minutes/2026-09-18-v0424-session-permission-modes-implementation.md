# v0.4.24 session permission modes implementation record

Date: 2026-09-18 (Korea Standard Time)
Status: development in progress; not integrated, released, or client-verified

## User intent and scope

Beta letters 160 (42 approval popups for three drafts) and 161 (request 6:
session-scope pre-approval) asked for fewer dialogs. On 2026-09-17 the user
decided the shape: per-work-session permission modes like the Codex and
Claude desktop apps — **manual** (every write opens the native dialog; the
behaviour since v0.4.0), **limited** (operation kinds chosen at grant time run
without a dialog, the rest ask) and **allow-all** (no dialog for the session)
— built as the first unit of v0.4.24 immediately after v0.4.23, with the
client reply waiting until v0.4.24 is public ("v0.4.24까지 하고 회신을
하자"). The user did not answer whether project updates and credential writes
should also skip in allow-all; my recommendation stands until he says
otherwise: those always open the dialog.

Executing model: Claude Fable 5.1. One bounded read-only workflow (4 reader
agents: broker, registry, callers, receipts/docs) mapped the code paths; every
code change, test and release step is solo. Worktree
`zettel-kasten-v0424-work`, branch `claude/v0424-session-permission-modes`
from main `ad0738f3` (v0.4.23). Boundaries unchanged: synthetic archives only,
the client workspace read only, explicit staging, every decision recorded.

## Design decisions

1. **One approval system, not a competing one.** The grant is itself an exact
   human decision on the work session (a new human action
   `set-permission-mode` beside create/handoff/accept/recover), approved in
   the same native dialog, bound to the exact registry post-image and
   recorded as a `human_session_decision` on the actor. A skipped dialog does
   not skip the one-use claim: every write still publishes its own
   authenticated started claim bound to its exact plan and target digests,
   and every receipt still names that claim.
2. **The claim tells the truth about how it was obtained.** A claim minted
   under a permission mode records
   `interactive_intent.mechanism = "work_session_permission_mode"` (a new
   fixed literal accepted by the claim validator; the two Windows task-dialog
   mechanisms stay the only live-dialog values) and its `public_summary()` —
   the `exact_human_approval` block of every write result — gains
   `approval_mechanism`. `public_reference()` (the five-key block embedded in
   receipts, MAC-bound and compared by equality in thirteen places) is
   unchanged; the receipt names the claim, the claim states the mechanism.
   Putting the mode literally inside receipt JSON would require editing eleven
   closed schemas and the integrity audit's envelope set; deferred to a later
   unit if the user wants it.
3. **Storage: one optional session-row key.** `sessions[ref]["permission"]`
   is absent/`None` (manual) or `{"mode": "limited" | "allow_all",
   "operations": [sorted unique operation values]}`, allowed only while the
   session is `claimed`, and cleared by every transition that drops or
   rotates the claim (pause, complete, handoff, accept of the successor,
   recover). Historical generations without the key stay valid; the key is
   never mandatory. The permission is not part of the `WorkSessionBinding`
   digest.
4. **Eligible operations are a fixed allowlist.** Always-dialog operations
   (never grantable, even in allow-all): `project_version_update`,
   `git_backup`, `notion_property_backfill`, `notion_property_backfill_revert`,
   `object_storage_setup_registration`, `object_storage_bytes_preservation`,
   `object_storage_formal_adoption`, `work_session`, `integrity_repair`,
   `duplicate_object_reconcile`, `local_recovery`, `local_recovery_revert`,
   `warning_override`, `human_artifact_lifecycle`. Credential writers use
   their own Windows credential native path, not the broker, so they are
   unaffected by construction. Everything else (drafts, mint, edges, links,
   captures, intake, discard, revision, batches) is grantable.
5. **Enforcement at the single choke point.** The broker
   (`_execute_exact_human_approved_write_with_review_kind_core`) receives an
   optional session permission grant; when the grant permits
   `context.operation` it produces the decision without calling the dialog,
   reproduces the dialog path's target-binding check when a target observer
   is supplied, re-resolves the grant immediately before the claim is
   published (a mode revoked by pause/handoff/complete in the meantime fails
   closed as `exact_human_approval_permission_revoked`), and mints the claim
   with the permission mechanism. Otherwise the dialog opens exactly as
   before. Resume, abandon and original-review paths never consult the grant.
6. **The caller's session is process context, not a new flag on every
   writer.** The AI client already retains its app, task route and claimed
   session refs; `archive_cli.main()` reads `WOM_CLIENT_APP_REF`,
   `WOM_TASK_ROUTE_REF` and `WOM_WORK_SESSION_REF` from the environment (the
   session-aware commands' explicit refs take precedence) and the broker
   resolves the grant read-only from the registry and the caller's actor
   record: the route must retain that session, the session must be claimed
   with the same claim ref, and the row must carry a permission. Any doubt
   resolves to the dialog. This covers all fifteen native approval paths
   without waiting for LR-06 per-writer integration.
7. **What the human sees when granting.** The dialog copy for
   `work_session_set_permission_mode` states that the listed operations will
   run without a dialog until the session is paused, handed off or completed
   and that project updates and credential writes still ask; the target
   preview lists the mode and each granted operation by its Korean label.
   Returning to manual is the same action with mode `manual` (it clears the
   key) and also opens the dialog, so the record of who changed the mode is
   complete.

## Implementation units

- A. Registry and session action: optional `permission` key, structural
  rules, clearing, `set-permission-mode` transition (claimed + claim ref
  proof, revision bump), 7-key request for this action only (bundle/intent
  decoders accept the legacy 6-key set and the 7-key set), operation table
  and dialog copy, target preview items, command modes (approve / approve
  --review-original / resume), dispatcher request shape
  `{reviewer_claim, permission_mode, operations}`, service function, held
  facade modelled on handoff (fresh, original resume, original review), CLI
  `--action` choices and help, MCP enum.
- B. Broker grant: `work_session_permission.py` (eligibility, grant
  resolution, revoke check), broker kwarg and skip branch, claim mechanism
  literal + validator + summary projection, CLI environment context,
  `exact_human_approval_permission_revoked` code.
- C. Tests: registry validation/transitions/clearing, modes matrix (+3 rows),
  bundle round trip (+1 action), broker skip/deny/exclusion/revoke with a
  fake native that must not be called, claim mechanism validation, end to end
  through the public work-session and create-draft commands with the session
  fixture, MCP enum pin.
- D. Docs: exact-human-approval contract (human-presence boundary and the
  four recorded facts), agent-operator capabilities, capability matrix intro,
  work-session CLI help, release note, register row and log entries.

## Progress

- Units A and B implemented (registry key and transition, action table and
  dialog copy with mode/operation preview items, command modes, dispatcher,
  service, held facade `work_session_permission_mode.py`, CLI/MCP action
  lists, bundle request keys, query projection; `work_session_permission.py`
  eligibility/grant/lookup, broker skip branch with target check and
  pre-publication revalidation, claim mechanism literal + validator +
  summary projection, explicit grant on the session-bound create-draft).
  Two corrections found by the first test run: the service module alias
  `permission_mode` was shadowed by the request parameter of the same name
  (renamed to `permission_facade`), and the permission error classes had to
  be added to the service's error mapping or every refusal read as
  `work_session_service_unavailable`.
- Unit C: `tests/test_v0424_session_permission_modes.py` (8 tests) passes:
  one dialog per grant and per return to manual; `limited` create-draft
  approve opens no dialog and its claim records
  `work_session_permission_mode`; the environment context grants a
  sessionless create-draft under `allow_all` while a stale route and manual
  still open the dialog; pause clears the grant and resume starts manual; a
  grant revoked between decision and claim fails closed with no dialog and
  no claim; always-dialog kinds ignore an `allow_all` grant; command modes,
  MCP enum, registry transition and the legacy row shape. The wider session
  and approval cohort is recorded once complete.
- Unit D: approval contract (human-presence boundary paragraph on what a
  permission-mode claim is and is not; the recorded facts become five, the
  fifth being the mechanism), capability matrix and agent-operator intros
  (the stale "5 integrated … of 47" coverage sentence corrected to the
  checker's 6 / 1 / 29 / 20 of 56), decision-log amendment
  `docs/archive-infra-decision-log-2026-09-18-v0424-session-permission-modes.md`
  (why this is not the "competing approval system" the 2026-09-05 log
  forbids), register row SP-01 and its log entry, release note
  `docs/releases/v0.4.24.md`. Correction: the doc `Status:` lines are pinned
  verbatim by every historical release-docs test, so they move only in the
  version bump (with the pins), not in the feature unit; the first doc test
  run caught the prefix I had added and it was reverted (244 doc tests green).
