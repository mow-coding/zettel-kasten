# Letter 132 Native Credential Popup And Causal Evidence

Status: native-popup source and automated boundaries implemented. The human
synthetic row remains failed and will not be repeated as a recovery
prerequisite. Live credential registration is `not_performed`.

## Why the design changed

Letter 132 began as a keyboard-input investigation. Multiple terminal-oriented
attempts failed for the person even when injected and synthetic API checks
passed. One attempt returned no input, and its Korean instructions rendered
badly. The user explicitly rejected more terminal/PowerShell retries and asked
for a separate popup.

That correction is authoritative. The old attempts remain failed historical
evidence; they do not qualify the final route. Production now uses a native
Unicode Windows popup in an isolated spawned child.

## What the production popup shows

The exact title is:

```text
WOM · 안전한 자격 증명 입력
```

Production registration has the colored top banner:

```text
실제 자격 증명 등록
```

The fixed privacy cover over the whole input control says:

```text
입력 내용과 길이는 화면에 표시되지 않습니다.
```

The popup also shows reviewed public-safe task, connection reason, account
label, and workspace label. Those strings are bound into the approved request;
they cannot contain a token, secret-shaped value, private locator, path, or URL.

The underlying control is a standard single-line Windows EDIT. It retains
normal keyboard editing, `Ctrl+V`, `Shift+Insert`, and the popup's fixed
Paste/Clear-only context menu. WOM sends the standard paste message to the
EDIT and never calls a clipboard-read API. Copy and cut are blocked. The EDIT
is password-styled as a fallback, while the opaque sibling cover prevents any
value, mask glyph, caret movement, count, or length from appearing.

Confirm stays disabled while the field is empty. Cancel, X, and Escape close
without a completed secret. Over-limit input shows only a fixed content-free
status, disables Confirm, and requires a complete clear before another attempt.
IME is detached and proved absent before the window can be shown.

## Synthetic acceptance and actual registration are different operations

The popup requires one exact enum value:

| Intent | Exact banner | Permitted input | Store/provider |
| --- | --- | --- | --- |
| `CredentialPopupInputIntent.synthetic_acceptance` | `합성 입력 테스트 · 실제 키 입력 금지` | only `WOM-INPUT-ACCEPTANCE-0319` | never |
| `CredentialPopupInputIntent.live_registration` | `실제 자격 증명 등록` | the reviewed actual credential | only after explicit `credential-adopt` approval |

Synthetic mode also says:

```text
경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.
고정 합성 문자열만 입력하세요. 내용과 길이는 표시되지 않습니다.
```

Missing intent, a plain string such as `"live_registration"`, or an unknown
object fails before any native show or focus. The production facade always
supplies the live enum. The manual acceptance helper always supplies the
synthetic enum.

The first human popup exercise predated this guard. It returned a complete
non-empty mismatch. The person then clarified that an actual secret had been
entered because the harness did not distinguish the two operations clearly
enough. No value entered receipt JSON, IPC, a store, or a provider request, and
the child-owned buffer was wiped. That row is failed and cannot prove either
synthetic acceptance or registration.

## Process and secret boundary

`archive credential-adopt --approve` starts one isolated spawned child. Its
first OS boundary detaches only that child from the inherited command host. It
then sends the fixed acknowledgement `popup_child_detached`. If detachment or
acknowledgement fails, the popup, native facade, credential store, provider,
and archive remain untouched.

The parent accepts only acknowledgement → final mapping → terminal pipe EOF.
It holds a narrow `SIGINT`/`SIGBREAK` ignore lease around `Process.start()` and
the exact local start proof, restores both original handlers before receiving,
and joins every normally started child without a timeout or terminate path.
This closes the asynchronous start ambiguity without transporting exception
text or secret material.

Raw input remains in mutable child buffers. It never enters the parent process,
AI chat, command arguments, environment variables, ordinary stdin, logs,
plaintext files, result JSON, or IPC. All owned buffers are wiped. Native EDIT
text and undo state are cleared before window destruction.

## Native UI cleanup and DPI boundary

The popup enters a verified per-thread per-monitor-v2 DPI context before owner
lookup or window creation. It uses `SystemParametersInfoForDpi` message-font
metrics, one owned font for every control, measured wrapped instruction rows,
scaled geometry, and owner centering. After every window is destroyed, it
deletes the owned font, unregisters the window class, and restores the exact
prior DPI context. Cleanup ambiguity wipes an otherwise-returnable secret and
raises only a fixed content-free error.

The initially reported post-font clipping was a capture error. The monitor was
168 DPI, but the first capture allocated a virtualized 660×470 bitmap for a
physical 1155×823 popup. A DPI-correct recapture showed the complete window and
proved the smaller PNG was its exact upper-left crop. Every instruction, the
privacy cover, status, and both buttons fit without overlap or clipping.

## Causal result contract

The product publishes four causal booleans only:

```text
credential_input_received
complete_line_received
temporary_store_write_attempted
provider_request_attempted
```

Unknown worker state projects four nulls. Local invalid or over-limit input is
`credential_input_invalid_for_provider`, with no store/provider attempt.
Post-input native cleanup failure is `credential_input_boundary_failed`, with
operator action `repair_secure_input_boundary_and_create_a_new_plan`, truthful
`1000` or `1100` input evidence, and store/provider false.
`provider_auth_rejected` is reserved for a real provider request.
`provider_request_not_attempted` covers a temporary store write whose verifier
never crossed the provider boundary. Rollback says `deleted` only after an
exact post-delete absence probe.

## Human-only popup acceptance

The helper's historical filename is retained so existing operator references
do not break, but its schema and routes are popup-only:

```text
wom-kit/windows-credential-popup-acceptance/v0.1
```

Use a real Windows desktop session and the public fixed challenge only. Never
enter a PAT:

```powershell
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family codex_desktop --launch-route codex_desktop_native_popup --gesture direct_keyboard_typing --format json
```

Additional host labels exercise the same separate native popup:

```powershell
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family windows_terminal --launch-route windows_terminal_native_popup --gesture direct_keyboard_typing --format json
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family console_host --launch-route console_host_native_popup --gesture direct_keyboard_typing --format json
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family conpty_parent --launch-route conpty_parent_native_popup --gesture direct_keyboard_typing --format json
```

Supported gestures are `direct_keyboard_typing`, `ctrl_v`, `shift_insert`, and
`right_click_menu_paste`. The helper asks, in order, whether the person:

1. acknowledged synthetic-only input before launch;
2. saw a separate WOM native popup;
3. saw the synthetic banner and real-credential warning;
4. actually completed the designated whole fixed-line gesture and Confirm;
5. saw any forbidden value, mask, caret, count, or length indicator;
6. saw Confirm disabled while empty and enabled only after input;
7. saw the popup close normally after confirmation; and
8. saw legible Korean without overlap, clipping, or replacement question marks.

The result contains no input value or length. It fixes
`actual_credential_registration_performed`, `actual_pat_requested`,
`credential_store_write_performed`, and `provider_request_performed` to false.
Injected unit tests prove only projector behavior, never physical input.

## Bounded post-acceptance homework

These four steps are future operator homework, not evidence that they ran or
succeeded. The failed synthetic row is not repeated as a prerequisite. Start
only after the published v0.3.319 runtime is verified in a new process and the
human confirms the blue `실제 자격 증명 등록` banner.

### Step 1 — Pre-enrollment authenticated list

```powershell
archive credential-secure-list <archive-root> --verify --format json
```

Stop on any unexpected existing, duplicate, unreadable, or unauthenticated
registration.

### Step 2 — New adoption dry-run and one digest-bound approval

```powershell
archive credential-adopt <archive-root> --account-label <public-safe-account-label> --workspace-label <public-safe-workspace-label> --purpose notion-page-recovery --task-summary "<public-safe-task-summary>" --connection-reason "<public-safe-connection-reason>" --reviewed-anchor-page-id <reviewed-anchor-uuid> --interactive --dry-run --format json
```

Review the exact fresh digest, then repeat the same public-safe fields once:

```powershell
archive credential-adopt <archive-root> --account-label <public-safe-account-label> --workspace-label <public-safe-workspace-label> --purpose notion-page-recovery --task-summary "<public-safe-task-summary>" --connection-reason "<public-safe-connection-reason>" --reviewed-anchor-page-id <reviewed-anchor-uuid> --interactive --expected-request-sha256 <fresh-request-sha256> --approve --format json
```

Only the popup banner `실제 자격 증명 등록` authorizes actual credential input.
Do not use the fixed synthetic challenge here and do not retry automatically.

### Step 3 — Post-enrollment authenticated list

```powershell
archive credential-secure-list <archive-root> --verify --format json
```

Continue only when the authenticated content-free row is the expected current
registration.

### Step 4 — Missing-source recovery dry-run

```powershell
archive notion-page-recovery-plan <archive-root> --request <archive-relative-reviewed-recovery-request.json> --max-items 5 --offset 0 --dry-run --format json
```

Stop after reviewing the plan. It makes no provider request, writes no recovery
evidence, authorizes no recovery approval, and is not evidence of recovery.

## Current truth

- Final production route: separate native popup with live-registration intent.
- Human synthetic row: failed and not repeated as a recovery prerequisite;
  optional future acceptance only.
- Actual credential registration: `not_performed`.
- Credential-store write/provider request from the synthetic harness: false.
- Release/tag/wheel/live-recovery claims from this source work: none.
