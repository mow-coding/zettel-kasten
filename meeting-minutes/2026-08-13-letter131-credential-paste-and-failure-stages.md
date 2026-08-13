# Meeting minutes: Letter 131 credential paste and failure stages

Date: 2026-08-13

Status: v0.3.318 source implementation and local Win32 API verification
complete. Release publication and physical host paste acceptance remain
separate gates.

## Chronology

1. The operator supplied protected-archive feedback Letter 131 and asked
   implementation to start immediately. The source letter was read from the protected archive
   archive without modifying it. Its SHA-256 is
   `651ccd5326d203af0680cb69a963c6fad181263b3dbba8dfa1c0bad43536a39d`.
2. Letter 131 reports that the separate black credential console opened and
   showed the intended task/security copy, but Ctrl+Shift+V and right-click did
   not visibly paste a real Notion PAT. The final public result was only
   `provider_identity_unverified`, so the operator could not distinguish no
   input, partial or invalid input, rejected authentication, provider outage,
   or inaccessible reviewed page.
3. The failed transaction did preserve the important rollback boundary:
   `accepted=false`, `persisted=false`, the temporary exact store entry was
   deleted, and absence was verified. The operator did not use a manual secret
   path or automatic retry.
4. The operator requested exact Korean paste guidance immediately above the
   input, a secret-free confirmation after Enter, fixed stage-specific reason
   codes, and acceptance coverage for Windows Terminal, classic Console Host,
   and ConPTY while keeping echo disabled, programmatic clipboard reads
   forbidden, logs secret-free, and rollback fail-closed.

## Standards findings

- Microsoft documents Ctrl+V, Ctrl+Shift+V, and Shift+Insert as the default
  Windows Terminal paste bindings. These bindings are user-configurable.
- Windows Terminal right-click behavior is also configurable: it may paste,
  copy a selection, or open a context menu. A console application cannot
  truthfully promise one right-click behavior for every user configuration.
- Classic console Quick Edit must be enabled with
  `ENABLE_QUICK_EDIT_MODE | ENABLE_EXTENDED_FLAGS`. WOM can set the console
  input mode, but it must still avoid any direct clipboard API.
- `ReadConsoleW` receives characters after the terminal host has handled its
  paste action. Product code can verify that a complete non-empty line arrived;
  it cannot inspect or override a user's terminal keybinding without creating
  a new clipboard or UI-automation authority.
- Notion documents HTTP 401 as an invalid bearer token, 403 as restricted
  access, and 404 as either missing content or content not shared with the
  caller. Transport/server failures and reviewed-page access failures therefore
  require different public stages.

## Current implementation plan

1. Make Ctrl+V the first recommended paste action. State Windows Terminal's
   default Ctrl+V, Ctrl+Shift+V, and Shift+Insert bindings, and state honestly
   that right-click depends on host settings. Enable safe classic-console edit
   modes explicitly while keeping echo disabled. Processed input is required
   for classic Console Host's paste shortcuts, so the prompt temporarily
   ignores Ctrl+C at the native control-handler boundary and uses empty Enter
   as the single documented cancellation gesture. Cleanup restores modes and
   code pages while Ctrl+C remains ignored, then detaches the console; it never
   re-enables the default process-terminating handler while still attached.
2. After a complete non-empty line is received, show only
   `입력값을 받았습니다. 검증 중입니다.` The value and its length remain
   absent from the screen, logs, parent process, argv, environment, files, and
   IPC.
3. Replace the ordinary cancel/empty and console-read failure outputs with
   `credential_input_cancelled_or_empty` and
   `credential_input_not_received`.
4. Let only the official provider adapter raise an allowlisted, value-free
   verification stage. Map Notion authentication rejection, identity endpoint
   unavailability, and reviewed-anchor inaccessibility to
   `provider_auth_rejected`, `provider_identity_endpoint_unavailable`, and
   `reviewed_anchor_inaccessible`. Unknown custom-verifier failures remain the
   conservative `provider_identity_unverified` fallback.
5. Preserve exact rollback, absence verification, buffer wiping, parent result
   reconstruction, and authenticated registry behavior. Keep API-boundary
   tests separate from the opt-in human host acceptance tool
   `wom-kit/tools/check_windows_credential_console_host.py`, which uses fixed
   synthetic input only. Do not use a real PAT, provider account, or protected archive
   data.

## Evidence produced

- Focused source/workflow/CLI tests passed 104/104. The visible-console set
  later passed 7/7 after adding an immediate UTF-16 duplicate wipe assertion.
  The opt-in manual host-check tool tests passed 6/6 after exact host-route
  pairing and exact-boolean result validation were added.
- The latest actual Windows API canary verified mode `503 -> 499 -> 503`, code
  pages `949 -> 65001 -> 949`, `[TRUE]` control-handler calls with no attached
  re-enable, successful detach, exact Korean without `???`, echo/VT-input off,
  status dwell, no value reflection, Ctrl+C survival plus empty-Enter cancel,
  and forced cleanup-window survival.
- Strict reason/rollback matrices cover all five new codes and retain a generic
  unknown-verifier fallback.
- The manual host tool separates `automated_win32_boundary_status` from
  `actual_host_acceptance_status` and uses no real PAT, store, provider, protected archive
  data, private locator, or clipboard API.

## Evidence still required

- Package-resource synchronization now passes for 145 v0.3.318 files, and the
  focused release-document selection passes. The first full CLI regression
  passed; the first non-CLI regression found only two stale current-review
  version labels in the philosophy evidence documents. Those labels were
  corrected without changing the historical checkpoint, and a final full
  regression on the recorded candidate is still required.
- Wheel build/inspection and final repository diff checks remain required after
  the final regression.
- Actual physical paste gestures in Windows Terminal, Console Host, and a
  ConPTY-parent route remain `not_performed`. Synthetic API injection proves
  the WOM boundary, not a human keybinding or right-click configuration.
- Merge, external CI, exact tag, GitHub Release, wheel publication, fresh
  installation, beta-client execution, and live credential enrollment remain
  unproven.

## Protected boundary

The feedback source and protected archive are read-only. No actual credential,
Notion account, workspace, page body, private locator, or Windows Credential
Manager entry is used by this implementation work.
