# Decision amendment: session permission modes are one approval system

Date: 2026-09-18
Status: accepted; v0.4.24 implementation, development verified

## Context

Beta letter 160 counted 42 approval popups for three drafts and letter 161
(request 6) asked for a session-scope pre-approval. On 2026-09-17 the user
chose the shape: per-work-session permission modes like the Codex and Claude
desktop apps — `manual`, `limited`, `allow_all` — as the first v0.4.24 unit,
with the combined client reply waiting until v0.4.24 is public.

Decision 1 of the
[2026-09-05 session-resume log](archive-infra-decision-log-2026-09-05-v0420-session-resume.md)
forbids "a competing lease or a new approval system". This amendment records
why a permission mode is neither, and what it may never become.

## Decisions

1. The grant is an exact human decision on the claimed work session
   (`work-session --action set-permission-mode --approve`), taken in the same
   native dialog, bound to the exact registry post-image and recorded on the
   actor as a `human_session_decision`. Returning to `manual` is the same
   action, so who changed the mode is always on record.
2. A permitted write skips only the dialog. It still acquires the archive lock,
   observes fresh state, publishes its own authenticated one-use `started`
   claim bound to its exact plan and target digests, and reports through the
   same receipts. Nothing is leased ahead of time; the grant authorizes no
   specific write until that write's own claim exists.
3. The claim records how its decision was obtained:
   `interactive_intent.mechanism = "work_session_permission_mode"`, a fixed
   literal beside the two Windows task-dialog mechanisms, which remain the
   only live-dialog values. `public_summary()` carries it as
   `approval_mechanism` with `live_dialog_shown`. `public_reference()` — the
   five-key block embedded in receipts, MAC-bound and compared by equality in
   thirteen sites — is unchanged; the receipt names the claim, the claim states
   the mechanism.
4. Storage is one optional session-row key (`permission`), allowed only while
   the session is `claimed`, absent for `manual`, cleared by every transition
   that drops or rotates the claim (pause, complete, handoff, the successor's
   accept, recover) and excluded from the `WorkSessionBinding` digest. Older
   generations without the key stay valid.
5. Eligibility is a fixed allowlist. Never grantable in any mode:
   `project_version_update`, `git_backup`, `notion_property_backfill` and its
   revert, the three `object_storage_*` kinds, `work_session`,
   `integrity_repair`, `duplicate_object_reconcile`, `local_recovery` and its
   revert, `warning_override`, `human_artifact_lifecycle`. Credential writers
   use the Windows credential native path and are unaffected by construction.
   The user's question whether project updates and credential writes could
   also skip under `allow_all` was left unanswered; this log records the
   default until the user decides otherwise: they always ask.
6. Enforcement lives at the broker's single choke point. The grant is
   resolved read-only from the registry and the caller's actor record (the
   route must retain that session, claimed under the same claim ref, with a
   permission), re-resolved immediately before claim publication, and any
   doubt or revocation resolves to the dialog or fails closed
   (`exact_human_approval_permission_revoked`). Resume, abandon and original
   review never consult a grant.
7. The caller's session is process context, not a flag on every writer:
   `WOM_CLIENT_APP_REF`, `WOM_TASK_ROUTE_REF`, `WOM_WORK_SESSION_REF`, with a
   command's explicit session refs taking precedence. This reaches every native
   approval path now without waiting for the per-writer session integration
   (LR-06), whose classification and denominator are unchanged.

## Evidence

`tests/test_v0424_session_permission_modes.py` (8 tests) on the synthetic
session fixture: one dialog per grant and per return to manual; a permitted
write opens no dialog and its claim records the mechanism; the environment
context grants a sessionless write while a stale route and `manual` still
ask; pause clears the grant; a grant revoked between decision and claim fails
closed with no dialog and no claim; always-dialog kinds ignore `allow_all`;
command modes, MCP enum, registry transitions and the legacy row shape. The
release record is `docs/releases/v0.4.24.md`; the register row is SP-01.
