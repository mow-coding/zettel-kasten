# Decision log: beta letter 177 — grants across restarts, session Git receipts, remaining cleanup (2026-09-30)

## Context

Beta letter 177 came from a customer running public v0.4.52. Three of its four
observations are product gaps that earlier releases answered with diagnostics
only; the development verification did not reproduce the customer's
conditions (a restarted process, a large personal archive with many other
activities' receipts, remote credentials bound to an ended process). The
owner's direction, restated on 2026-09-30: session permissions follow the
Codex and Claude desktop apps.

## Facts

- The customer granted `allow_all` (no expiry). After the calling process
  ended, the same conversation's next process got the approval window again:
  since v0.4.34 a grant also required a presenter secret held only by the
  approving process (`work_session_presenter_missing`). The owner's 2026-09-25
  decision was "valid until released in that session", not "while that process
  lives".
- On this PC the desktop apps keep approvals as durable user-account records:
  Codex `~/.codex/config.toml` (`approval_policy`, `sandbox_mode`,
  per-project `trust_level`), Claude Code `.claude/settings.local.json` allow
  rules. Restarts and updates do not reset them; the running process holds no
  authority; the boundary is the Windows account.
- The session-scoped Git backup counted every changed exact-operation receipt,
  including other activities' and sessions', against a fixed budget of 128
  before checking which session each belonged to, so a large archive always
  failed with `work_session_git_receipt_limit`.
- The remaining 53 cleanup items (1,017 already completed) could be reconciled
  in a preview, but the original request's remote credential refs were bound to
  the ended process and no secure registration existed.

## Decisions

1. **A grant is this conversation's session record (implemented).** The
   presenter secret is no longer a condition; any new process of the same
   conversation that presents the three session refs uses the grant until it is
   released (manual, recover, pause, handoff, complete). Another conversation's
   route still does not resolve to the session. The approve returns no token;
   claims keep the presenter fingerprint and the second-presenter warning as
   evidence. The helper-AI guidance tells the AI to keep and re-export the refs.
   Letter 165's concern (another conversation reusing refs) is answered by the
   route binding and that evidence, as in the desktop apps, rather than by a
   process secret.
2. **Only this session's receipts consume the Git proof budget (implemented).**
   A cheap read of each changed receipt's original decision tells which session
   it names; receipts naming another session are excluded as
   ownership-unverified without the expensive proof and are reported as
   `other_session_hint_receipt_count`. The budget (now 512) counts only this
   session's receipts and still fails closed when exceeded.
3. **Storage keys live in the OS keychain; a reconcile may rebind them
   (implemented).** Object-storage writers resolve `env:`, `keyring:` and
   `credential-manager:` refs; an `env:` ref ends with its process. Like the
   desktop apps' keychain, the keys belong in the Windows Credential Manager.
   `activity-cleanup --reconcile` accepts `--rebind-access-key-id-ref` /
   `--rebind-secret-access-key-ref` (a pair, reconcile only) that replace only
   the two refs inside the new approval; provider, store, endpoint, bucket and
   region stay the original's, the rebind is recorded in the reconciliation
   (`credential_rebind`, digests only), and completed items are not
   reprocessed. Previews report `credential_refs_state`; an unreadable pair is
   refused before the dialog (`activity_cleanup_credential_ref_unresolved`),
   as object-storage-upload has done since v0.4.36. Object-storage reads of the
   Credential Manager accept the exact target name only; the substring
   auto-detection kept for Tiro is not used there. `object-storage-cleanup`
   already takes its refs per run, so the same keychain refs finish the remote
   temporary-object cleanup.
4. **Next in this release: a WOM-owned enrollment window for storage keys.**
   Until it lands the human adds the two generic credentials in 자격 증명
   관리자; `credential-adopt` still enrolls Notion only. Following the owner's
   rule not to defer customer friction, v0.4.53 continues with a WOM popup that
   stores object-storage keys in the Credential Manager under exact targets and
   returns the `credential-manager:` refs to use.

## Boundaries

- All checks are synthetic, reproducing the customer's conditions in tests
  (approving process gone; another session's receipt with a budget of one).
  The customer's own run is not confirmed.
- Same Windows account, same refs: any process holding this conversation's refs
  can use its grant, exactly as a process under the account can read the
  desktop apps' settings.
