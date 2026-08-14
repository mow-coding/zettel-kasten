# Decision Log: v0.3.319 Letter 132 Native Credential Popup

Date: 2026-08-14

## Context

Repeated terminal-oriented credential-entry attempts failed in the user's real
Codex Desktop environment despite passing injected and synthetic API checks.
One later attempt returned no input and rendered Korean badly. The user
explicitly rejected further console/PowerShell UX and requested a separate
popup.

The first native-popup human exercise then exposed a second operator-safety
problem: the harness expected a fixed synthetic challenge, but the person
entered an actual secret because synthetic testing and registration were not
visually unmistakable. The child returned only a content-free mismatch; it did
not log, store, transmit to a provider, or return that value to the parent.

## Decision

1. Production `credential-adopt` uses one separate Unicode native Windows
   popup in an isolated spawned child.
2. The popup requires the exact closed enum `CredentialPopupInputIntent`.
   Missing values, plain strings, and unknown objects fail before any native
   show/focus or store/provider access.
3. `live_registration` is the only production intent. It displays the blue
   banner `실제 자격 증명 등록`.
4. `synthetic_acceptance` is the only manual-harness intent. It displays the red
   banner `합성 입력 테스트 · 실제 키 입력 금지` and the exact warning
   `경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.` /
   `고정 합성 문자열만 입력하세요. 내용과 길이는 표시되지 않습니다.`
5. The acceptance helper uses only the public fixed challenge
   `WOM-INPUT-ACCEPTANCE-0319`; it requests no PAT and performs no registration,
   credential-store write, or provider request.
6. A standard single-line password EDIT owns editing and standard paste
   dispatch. A fixed opaque sibling covers the entire field so value, mask,
   caret, count, and length are not rendered. Product code does not read the
   clipboard; copy/cut are blocked and the context menu is Paste/Clear only.
7. Confirm is disabled while empty. Cancel, X, and Escape are pre-store
   cancellation. Over-limit notification disables Confirm until a complete
   clear resets the attempt.
8. The child detaches from the inherited command host before popup/native/store/
   provider/archive work, then sends the fixed `popup_child_detached`
   acknowledgement. Failure before that acknowledgement permits no live work.
9. The parent restores its narrow `SIGINT`/`SIGBREAK` start lease before receive
   and accepts only acknowledgement → final mapping → EOF. A normal start also
   requires unbounded join. Exception text and raw secret never cross IPC.
10. Popup layout uses a verified per-thread PMv2 DPI lease, current system
    message font, measured wrapped rows, scaled geometry, and exact cleanup.
    Cleanup ambiguity wipes an otherwise-returnable result buffer.
11. Product result schemas remain v0.3 with four causal facts only. Local
    invalid input, native boundary failure, actual provider rejection, and
    rollback absence verification remain separate reason stages.
12. The old terminal-input implementation remains a legacy direct-import API
    only. It is not production/manual evidence and is not referenced by current
    operator guidance.

## Consequences

- `archive credential-adopt --help` labels the approved path as actual native
  popup registration and says the synthetic harness must never receive a PAT.
- The historically named
  `tools/check_windows_credential_console_host.py` now emits schema
  `wom-kit/windows-credential-popup-acceptance/v0.1` with popup-only routes.
- The pre-guard mismatch remains failed evidence. It is neither a synthetic
  pass nor a live registration.
- The failed human synthetic row will not be repeated as a prerequisite for
  this recovery. The helper remains optional future acceptance only.
- Actual credential registration, store persistence, provider acceptance, and
  missing-source recovery are `not_performed`.
- Automated source, fake Win32, DPI, buffer-wipe, and transport tests do not
  upgrade the failed synthetic row or pending actual registration to pass.

## Superseded decision

The earlier Letter 132 same-host input pivot is withdrawn before release. Its
automated results remain chronology only and grant no current operating
authority.

## References

- [Letter 132 guide](letter132-credential-console-keyboard-readiness-and-causal-evidence.md)
- [v0.3.319 release note](releases/v0.3.319.md)
- [Windows Edit Controls](https://learn.microsoft.com/en-us/windows/win32/controls/edit-controls)
- [Static Control Styles](https://learn.microsoft.com/en-us/windows/win32/controls/static-control-styles)
- [SetThreadDpiAwarenessContext](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddpiawarenesscontext)
