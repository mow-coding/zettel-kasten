# Credentials, Provider Secrets, And Session Grants

Load this reference before any provider credential task, and before using or
explaining a work-session permission grant.

## Session Grants

- A `limited` or `allow_all` grant set with `work-session --action
  set-permission-mode --approve` lets this conversation's writes run without
  an approval window. Since v0.4.44 it lasts until `set-permission-mode
  manual`, `recover`, or the session is paused, handed off, or completed;
  a request may still name `grant_hours` for a time-boxed grant.
- The approve result returns `presenter_token` once. Keep it only in this
  conversation's process (`WOM_WORK_SESSION_PRESENTER`); never write it or the
  session refs into memory files, notes, letters, or another conversation.
- Another conversation that finds session refs must not reuse them. It asks the
  human, or continues through `work-session` handoff/accept.
- Do not tell the human a window will appear or not appear; the result states
  what happened (`session_permission_refused` names why a window opened).
- "Carry established state" never covers grants, tokens, or session refs.

## Provider Credentials

- Never ask for a provider secret in chat. Use `credential-adopt` only for first
  enrollment or reviewed replacement. Check authenticated state; supply only
  public-safe task/reason sentences; WOM owns every security notice. Production
  uses a separate native Unicode Windows popup with exact input intent
  `CredentialPopupInputIntent.live_registration` and banner
  `실제 자격 증명 등록`. Its isolated spawned child detaches from the inherited
  console before live work; the parent blocks and does not read ordinary stdin.
  The popup uses a standard password edit covered by an opaque fixed-text layer,
  so it reveals no value, mask, caret, character count, or length. Copy and cut
  are blocked; standard edit paste stays available without WOM reading clipboard
  data. Do not put a secret in chat, argv, environment, ordinary stdin, or a file.
  Interpret v0.3 facts exactly: `credential_input_received`,
  `complete_line_received`, `temporary_store_write_attempted`, and
  `provider_request_attempted`. `provider_auth_rejected` requires a real request.
  Complete malformed/control/provider-shape or UTF-8 byte-oversize input is
  `credential_input_invalid_for_provider` at `1100`;
  `credential_input_boundary_failed` preserves truthful `1000`/`1100` facts and
  never attempts store/provider. No transport
  after store is `provider_request_not_attempted`; `deleted` requires a fresh
  post-delete absence probe; unknown state has four nulls.
  The manual helper is synthetic-only: schema
  `wom-kit/windows-credential-popup-acceptance/v0.1`, route
  `codex_desktop_native_popup`, and intent
  `CredentialPopupInputIntent.synthetic_acceptance`. It displays
  `합성 입력 테스트 · 실제 키 입력 금지`, requires only the fixed synthetic
  line, never requests a real PAT, and cannot call store/provider. Synthetic
  acceptance and actual registration are separate actions. The human synthetic
  row remains failed and is not repeated as a recovery prerequisite; the helper
  is optional future acceptance only. Actual registration remains
  `not_performed` and requires a verified published runtime plus confirmation of
  the blue live-registration banner. Automated evidence is not human
  acceptance. Later approved work reuses the exact saved credential; another
  page may reuse the same PAT, but labels are not authority. Legacy scope
  evolution and complex lifecycle state require human review. Approved live
  Notion recovery requires a fresh plan-bound one-use capability, durably
  claimed before secret read. Replayed, expired, or changed authority blocks;
  verified local replay creates no claim.
