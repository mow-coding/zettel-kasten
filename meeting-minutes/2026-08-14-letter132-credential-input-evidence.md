# Meeting minutes: Letter 132 credential input and stage evidence

Date: 2026-08-14

## Chronology

1. The human supplied protected feedback Letter 132 and asked WOM development
   to continue. The source was read without modification. Its SHA-256 is
   `d92b12b375110c178c3712c464fcc6d0f577850d6630137e6acafd5e21b72ede`.
2. The human strongly corrected the previous diagnosis: the observed problem
   was not merely a paste shortcut. The separate black credential window did
   not give the human confidence that direct keyboard input was being received
   at all.
3. The released v0.3.318 evidence was re-examined instead of being treated as
   proof of physical keyboard acceptance. Its fake console tests inject text
   directly at the `ReadConsoleW` boundary, and its automated Windows canary
   injects console records. Neither proves that the newly visible window owns
   physical keyboard focus in the Codex Desktop launch path.
4. A live, secret-free focus probe reproduced the missing boundary: the WOM
   console window was visible, but it was never the foreground window during
   191 observations over two seconds. Synthetic records written directly to
   `CONIN$` could still be received, proving that buffer conversion alone was
   not the physical-input contract the human needed.
5. A second defect explained the apparently contradictory final result. Local
   UTF-8 or provider-shape rejection could produce `provider_auth_rejected`
   without issuing any provider request. A non-empty accidental, partial,
   whitespace, or input-method line could therefore be temporarily written,
   locally rejected, deleted, and incorrectly reported as a provider rejection.
6. The work was split into three reviewed boundaries: a human-visible keyboard
   readiness handshake, content-free transaction-stage evidence, and a provider
   adapter that can assert a request only at the real transport boundary.

## Decisions

- Basoon and other protected archives remain read-only. No real credential,
  account identifier, reviewed anchor, private path, or private body is copied
  into this repository.
- The credential window must first receive a separate, empty Enter readiness
  gesture before secret entry begins. This proves that the WOM input buffer,
  rather than the parent terminal, currently receives keyboard events.
- Quick Edit must be disabled during the prompt so clicking the window cannot
  suspend input in selection mode.
- The UI must distinguish keyboard readiness, secret-entry waiting, complete
  line receipt, and provider-verification preparation without showing the
  secret, its length, or per-character mask symbols.
- Public results will carry only fixed booleans for credential input receipt,
  complete-line receipt, temporary store-write attempt, and provider-request
  attempt. Unknown worker state uses JSON null rather than false certainty.
- `provider_auth_rejected` is valid only after the real provider transport was
  attempted. Local decoding or provider-shape failures require a separate
  pre-provider reason.
- `store_absence_verified` is valid only after exact deletion followed by an
  exact absence probe.
- Windows CredUI remains an evaluated alternative, not an automatic fallback.
  Its standard password masking can reveal length, so adopting it without a
  rendered acceptance decision would violate the current no-length-display
  contract.

Microsoft's console documentation supports the focus diagnosis: keyboard
events enter a console input buffer when that console window has keyboard
focus. Microsoft's `SetForegroundWindow` documentation also states that
Windows may deny foreground activation, so the implementation does not treat
programmatic focus stealing as a reliable proof. The readiness Enter is an
end-to-end receipt from the exact WOM input buffer instead.

Official references:

- <https://learn.microsoft.com/en-us/windows/console/console-input-buffer>
- <https://learn.microsoft.com/en-us/windows/console/high-level-console-input-and-output-functions>
- <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow>
- <https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw>

## Verification boundary

- Unit tests and synthetic Win32 input are implementation evidence, not proof
  of a human's physical typing gesture.
- The manual acceptance matrix must add direct keyboard typing and a distinct
  Codex Desktop launch route, while continuing to use only a fixed synthetic
  value and performing no provider or credential-store operation.
- A real PAT registration attempt must wait until the synthetic path clearly
  proves keyboard readiness and complete input receipt.

## Current implementation state

Implementation is integrated on branch
`codex/v0.3.319-letter132-console-input` and is still under release review.
The console now disables Quick Edit, requires a readiness-only empty Enter,
shows separate input-waiting and complete-line/provider-preparation receipts,
and keeps those content-free receipts visible for three seconds. The secure
intake and parent workflow use v0.3 result envelopes with the four causal
booleans. Notion local-shape rejection is pre-store and pre-transport, and the
provider observer fires only immediately before an actual transport call.
Rollback now verifies exact absence after deletion.

At this point the independently rerun core, Windows console, Notion adapter,
and host-tool group is 95/95 passing. This is automated implementation
evidence only. Workflow integration, full regression, and human physical
typing acceptance are not yet complete, so this record does not claim a
release or a successful real credential registration.

## Stage-evidence correction during release review

A later P1 audit found one more projection error. After the credential phase
had already observed valid, empty, or partial input, content-free status/dwell,
mode or code-page restoration, handle-close, or `FreeConsole` failure could
collapse the public evidence to the `false, false, false, false` no-input state
or be confused with invalid credential content.

The correction introduces fixed reason `credential_input_boundary_failed` and
operator action `repair_secure_input_boundary_and_create_a_new_plan`. It
preserves `true, false, false, false` (`1000`) for partial input or `true, true,
false, false` (`1100`) for a complete valid/empty line. Both are
`rollback_status: not_required`; any secret is wiped and neither store nor
provider is attempted. `credential_input_invalid_for_provider` is separately
reserved at `1100` for a complete malformed/control/provider-shape or UTF-8
byte-oversize line. No value, length, gesture, native error, or timing is
published.

The no-prompt reuse path was also aligned with new intake: it validates the
exact saved secret locally before provider verification. A local reuse
rejection therefore performs no provider request and reports four false stage
facts because that attempt opened no prompt and attempted no new store write.

The v0.3.319 release documentation, beginner upgrade guides, capability and
runtime maps, runtime skill/operator contract, and package resource mirror now
record both corrections. Physical direct-keyboard human acceptance remains
`not_performed`; no release or live credential-registration claim was added.
Package resource write/check reported 145 synchronized files for v0.3.319.
Release-document/resource tests passed 23/23, current-version integration tests
completed 217 passed with two expected skips, public privacy/link/language/runtime
documentation tests passed 63/63, and release-readiness/root-shim tests passed
6/6.

## Final input-boundary reason verification

The completed classification keeps input content and secure-console operation
separate. `credential_input_boundary_failed` plus
`repair_secure_input_boundary_and_create_a_new_plan` is now the only documented
status/dwell/restore/CloseHandle/FreeConsole failure route after observed
credential input. It permits `1000` or `1100`, always with rollback not
required, store false, and provider false. Complete malformed/control/provider
shape or UTF-8 byte-oversize content remains
`credential_input_invalid_for_provider` at `1100`.

After the final documentation and package-mirror update, resource check again
reported 145 synchronized v0.3.319 files. The focused current/historical
release-doc, package-resource, runtime-skill, capability, privacy, public-link,
and Korean-language group passed 212/212. The core visible-console,
Windows-intake, secure-intake, and adoption-workflow group passed 102/102.
These are still automated results; physical direct-keyboard human acceptance
remains `not_performed`, and this record does not claim release or live
credential enrollment.

## Strict-evidence hardening found during independent review

The final security pass found three additional truthiness hazards. None was
allowed to remain as an inferred success:

1. An exact-store probe result such as `None`, integer `0`, integer `1`, text,
   or a custom truthy/falsey object is not proof of presence or absence. The
   Windows exact-store adapter now accepts only an exact Boolean. The worker
   requires exact `true` before provider work, and rollback reports `deleted`
   only after an exact `false` post-delete probe. Every malformed probe result
   is fail-closed as unverified presence or `delete_failed`; it cannot publish
   `store_absence_verified: true`.
2. Provider identity and reviewed-anchor flags must each be exact `true`.
   Integer, string, or custom truthy values cannot authorize a receipt. A
   malformed subject flag becomes `provider_identity_unverified`; a malformed
   anchor-access flag becomes `reviewed_anchor_inaccessible`. Both remain
   post-request failures and use the verified rollback path without committing
   a receipt.
3. A parent may claim an exact pre-launch failure only when worker-start
   evidence is exact `false` and no child result exists. `None`, integer `1`,
   text, a covert object, or a result paired with `false` now becomes
   `credential_adoption_worker_state_unknown` with all four causal facts null.
   This prevents an uncertain post-start state from being rewritten as zero
   work.

These corrections were added after the earlier focused counts above. The
latest workflow planning and end-to-end module passed 38/38 after the exact
worker-start rule, and the combined credential/continuity group passed 194
tests with two expected host-permission skips before the last exact-Boolean
identity/probe rerun. A final frozen regression and physical-keyboard row are
still required before release.

## Release-review correction: bounded operator homework

The final integration audit found a documentation gap rather than a code
failure. The v0.3.319 guide explained synthetic Codex Desktop input acceptance
but did not yet carry Letter 132 through the requested real-task homework:
authenticated list verification, a fresh adoption plan and one digest-bound
approval, authenticated list verification after success, and a bounded
missing-source recovery dry-run.

The correction records separate synthetic direct-keyboard rows for Codex
Desktop, Windows Terminal, classic Console Host, and a ConPTY parent. It then
adds a fail-closed four-step homework checklist. Every example uses explicit
placeholders; no real PAT, anchor UUID, request digest, recovery request path,
or private source identifier was inserted. The PAT remains exclusive to the
isolated echo-disabled credential console. Unexpected existing state, any
failed or unknown causal result, or an unauthenticated post-list stops the
sequence without automatic retry, replacement, or recovery approval.

The last step is only a five-item `notion-page-recovery-plan --dry-run`. It
resolves no provider credential, calls no provider, writes no recovery
evidence, and does not authorize the recovery executor. Human physical-input
acceptance, live credential enrollment, verified post-enrollment listing, and
missing-source recovery all remain unperformed until separately evidenced.

## Final parent-projection object-boundary correction

An adversarial projection review found one more distinction that ordinary
JSON-value tests had not exercised. A child could send a pickled subclass of
`str` whose visible text matched an allowed reason, rollback status,
credential identifier, operation enum, or workspace-identity basis while the
object retained a custom attribute or representation. The earlier validators
compared the text but could preserve that child-owned object in the rebuilt
result, allowing noncanonical object state to cross the worker boundary.

The core and adoption projections now require `type(value) is str` for every
retained string field. Allowlisted reason, rollback, reuse reason, operation,
and workspace-identity-basis values are rebuilt from parent-owned canonical
literals. Pickle-roundtrip regressions inject string subclasses with fixed
sentinel attributes and custom representations into failure, success, and
reuse shapes. Every case is rejected as unknown, all four causal fields become
null, and neither the final object representation nor JSON contains the
sentinel. Normal plain-string results continue to project through newly
constructed dictionaries.

The final defensive-data-validation audit ran 401 focused executions with two
expected release-only skips and zero failures. It also passed the 145-file
v0.3.319 resource check, compilation of 24 changed Python files, and
`git diff --check`. These are automated boundary results only. The visible
Codex Desktop direct-keyboard human row remains separately unperformed at this
point in the chronology.

## Human correction, two failed rows, and the pre-Enter receipt

The next human interaction corrected the UX diagnosis again, more precisely.
The person reported that `y` and `n` were accepted normally in the parent
terminal, but the spawned secret-entry window appeared to accept neither
typing nor paste. The distinction matters: the acceptance tool's parent
questions use ordinary echo-enabled `sys.stdin`, while the secure child owns a
separate echo-disabled `CONIN$`. A visible parent `y` or `n` therefore does not
prove child focus, child receipt, or usable secret-entry feedback.

Two content-free Codex Desktop/direct-keyboard attempts had already run with
the fixed synthetic line and the v0.2 manual-helper schema. Both durable result
rows were identical at the machine boundary:

- `credential_input_received: true`;
- `complete_line_received: true`;
- `nonempty_line_received: true`;
- `exact_synthetic_line_received: false`.

For both attempts, the person reported seeing `입력 대기 중`, normal Korean,
and no echoed input. The person did not attest that the designated fixed-line
gesture had actually been completed and did not report seeing the complete-line
or provider-verification preparation receipts. Both rows therefore remain
`actual_host_acceptance_status: failed`. They are not retroactively converted
to pass. The machine facts prove that some non-empty Enter-terminated line
reached the child's `ReadConsoleW` boundary, but they do not prove that the
fixed line matched, that the designated physical gesture was completed, or
that the old human feedback was usable. Neither attempt used a real PAT,
programmatic clipboard read, Credential Manager write, or provider request.

The UX failure was the silence before final Enter. Echo was intentionally off,
but the window also provided no content-free acknowledgement of the first
hidden input signal. The correction preserves cooked Unicode `ReadConsoleW`
line input, `ENABLE_LINE_INPUT`, and Windows line editing. A bounded
`PeekConsoleInputW` observer now non-destructively inspects queued records for
the first relevant key-down `KEY_EVENT`; it never consumes or edits the line,
and `ReadConsoleW` remains the sole consumer/editor. On the first
input-producing character WOM writes exactly one fixed receipt before final
Enter:

```text
입력 신호를 받았습니다.
입력 내용과 길이는 표시하지 않습니다.
입력을 마치면 Enter를 누르세요.
```

The receipt contains no input value, length, asterisk, count, or per-character
marker. Empty Enter can still cancel without producing a false input receipt.
After final Enter, the existing complete-line and provider-preparation states
remain separate.

The manual host envelope advances to
`wom-kit/windows-credential-console-host-acceptance/v0.3`. It adds exact
Boolean `input_signal_receipt_observed` and a strict content-free machine
classification over only five causal rows: `0000 no_input`, `1000
partial_line`, `1100 empty_line`, `1110 nonempty_line_mismatch`, and `1111
exact_line_received`. Every inconsistent Boolean vector fails closed. Human
questions are chronological and separate the actual whole fixed-line plus
final-Enter attempt from perceived success, first-input receipt, forbidden
character/asterisk/length display, later receipts, and Korean rendering. The
fixed synthetic line is also shown inside the WOM child prompt so the person
does not need to memorize it or switch windows for direct typing.

Automated source tests after this correction are implementation evidence only.
The two earlier rows remain attempted/failed, while a fresh post-fix Codex
Desktop human row remains `not_performed`/pending. No release, published wheel,
live credential enrollment, provider acceptance, durable store write, or
missing-source recovery is claimed from this work.

After the current source documentation stabilized, package-resource write and
check each reported 145 synchronized v0.3.319 files. The focused current and
historical release, package-resource, runtime-skill/guidance, capability,
public-privacy, public-link, Korean-language, predecessor-resource, and private
resource group ran 257 tests with two expected skips and zero failures. The
additional exact current-release, wheel, and root-shim group ran 66 tests with
zero failures. Compilation of the changed release-doc test and
`git diff --check` also passed. Exact SHA-256 assertions keep the v0.3.318
Letter 131 release, guide, decision, and all three related meeting-minute files
unchanged. These
automated documentation results do not change the pending post-fix human row.
After the two additional v0.3.318 release-minute hashes were added, the final
v0.3.319 release-document test ran 13/13 passing; resource check, compilation,
and diff check remained clean.

## Final human correction and same-terminal pivot

The next physical exercise occurred after the one-time first-input receipt had
been added to the separate-console design. Its fixed-synthetic machine row was
again:

- `credential_input_received: true`;
- `complete_line_received: true`;
- `nonempty_line_received: true`;
- `exact_synthetic_line_received: false`.

The human row recorded `human_physical_gesture_attested: false`,
`input_signal_receipt_observed: false`,
`complete_line_receipt_observed: false`, and
`provider_verification_preparation_status_observed: false`. The row is
`actual_host_acceptance_status: failed`, not pass. It used no real PAT,
credential-store write, programmatic clipboard read, or provider request.

The human then expressed understandable frustration and corrected the design
boundary decisively: the ordinary `y` and `n` answers worked in the exact Codex
Desktop terminal already in use, but the separately opened secret window
repeatedly appeared unable to accept either typing or paste. This showed why
the earlier explanation was incomplete. The parent questions read echo-enabled
`sys.stdin` from the working parent terminal, whereas `AllocConsole` created a
different console input buffer for the spawned child. A first-input receipt in
that other window did not repair the underlying UX path. The separate-console
design was withdrawn.

A read-only architecture audit then established the bounded replacement. The
isolated spawned child can inherit the exact working parent terminal while the
parent blocks on the child result and performs no concurrent stdin read. The
child directly opens `CONIN$` and `CONOUT$`, disables echo, Quick Edit, and
virtual-terminal input, keeps cooked processed `ReadConsoleW` line input and
Windows editing on, and preserves the readiness-only empty Enter followed by
`입력 대기 중` and the one-time `입력 신호를 받았습니다` receipt. It does not
call `AllocConsole` or `FreeConsole` and creates no new window.

Parent and child both hold `Ctrl+C`-ignore leases while the child owns the
terminal; empty Enter remains the official cancellation gesture. The child
restores the exact input mode and closes its console handles before the parent
resumes, and lease or restoration failures fail closed without disclosing
input content. Raw secret material remains child-local and never enters parent
`sys.stdin`, IPC, argv, environment, plaintext files, logs, or a clipboard API.

The final source audit found one same-terminal handoff risk: cooked
`ReadConsoleW` can leave later records queued after its first Enter-terminated
line or a buffer-full return. The first implementation tried to flush at most
three times and then return a content-free boundary failure. Although its
focused tests and successful-flush canary passed, the security review rejected
that design: an unproved residual queue could then become input to a later
parent prompt or shell. No release claim was based on the rejected semantics.

The first fail-safe correction deliberately performed no flush between
readiness and phase two, preserving fast prequeued typing or paste, and made the
first cooked credential line the only candidate. It initially gated exit on
`FlushConsoleInputBuffer(CONIN$)` success. A final P1 review found that this was
still unsafe: if the following input-mode restoration failed once, the parent
could resume without the original mode restored, and input could arrive between
flush and a later restore attempt. The design was corrected again so cleanup
and restoration are one indivisible gate. Every attempt now requires a fresh
successful flush immediately followed by exact `SetConsoleMode(original_mode)`
success. Restore false/throw restarts at flush, clearing input that arrived
during retry. After three immediate combined failures the child attempts exactly
one notice write: a leading blank line followed by these three content-free
CRLF-terminated lines. It then retries the combined gate every 0.1 seconds:

```text
공유 터미널을 안전하게 정리하고 원래 상태로 복원하고 있습니다.
정리와 복원이 끝날 때까지 이 작업과 부모 터미널은 계속 기다립니다.
운영 체제가 정리나 복원을 완료하지 못하면 터미널을 닫을 수 있습니다.
```

Combined success is the only normal exit from that loop. Until then, child and
parent remain blocked with both `Ctrl+C` leases, masked input mode, and console
handles held. No handle closes, returns, or raises, and an exception from the
retry delay cannot escape the boundary. Only a fresh flush success immediately
followed by exact mode-restore success permits handle close and parent resume.
Closing the terminal ends the OS process, so no result, reason, or evidence is
returned. The fail-safe visible-console suite passed 27/27, and the four-module
combined current-tree same-terminal group passed 122/122.

A visible PowerShell synthetic API canary completed in under one second with
empty stderr. It recorded a real fresh `FlushConsoleInputBuffer` success
immediately followed by exact input-mode restore success, then handle close.
Child and parent both observed the queue empty. The canary observed no concurrent
parent read, secret value, IPC value, or residual record. Its
interpretation is explicitly `synthetic_api_canary_only: true` and
`physical_keyboard_evidence: false`; it does not alter the pending human row.

The manual helper advances to
`wom-kit/windows-credential-console-host-acceptance/v0.4` and route
`codex_desktop_attached_parent_console`. It keeps exact Boolean
`input_signal_receipt_observed` and the five strict content-free classifications
`no_input`, `partial_line`, `empty_line`, `nonempty_line_mismatch`, and
`exact_line_received`; inconsistent Boolean vectors still fail closed and no
input value or length enters JSON.

No fresh physical same-terminal human exercise has run. Its acceptance state is
`not_performed`/pending. The failed separate-console rows do not prove this new
route, and neither automated checks nor this design decision proves release,
wheel publication, live credential enrollment, provider acceptance, durable
store persistence, or missing-source recovery.

## Same-terminal human failure and popup pivot

The pending same-terminal exercise was then run with the fixed synthetic value
only. The first visible PowerShell instance was closed at the human's request
and relaunched once after the process and all children were confirmed absent.
The second instance used one parent PowerShell window and did not open another
credential console. Nevertheless, the isolated prompt child returned the exact
machine classification `no_input`:

- `credential_input_received: false`;
- `complete_line_received: false`;
- `nonempty_line_received: false`;
- `exact_synthetic_line_received: false`.

The human also reported that the Korean instructions were corrupted and that
the revised interaction was less usable than the prior design. The observation
questions were all answered negatively, so the row is
`actual_host_acceptance_status: failed`. This run used no real PAT, credential
store, provider request, or programmatic clipboard read. A private local
transcript was retained temporarily only to diagnose the failed human row; it
is not a release artifact and must not be committed.

The human expressed strong and justified frustration: ordinary terminal input
still worked, but both the earlier separate console and the new same-terminal
credential flow had failed in practice, and the Korean UI had regressed. The
human explicitly asked WOM to stop relying on terminal or PowerShell input and
to return to a separate popup-style interaction. This is a new design decision,
not a request for another console retry. The same-terminal route and its v0.4
manual helper are therefore withdrawn before release despite their automated
and synthetic API results.

The historical `CredUIPromptForCredentialsW` implementation was recovered from
project history as useful evidence, but restoring it unchanged would violate
the current visual privacy contract because its password field displays one
mask glyph per character and therefore reveals approximate length. The selected
replacement is a Unicode Windows popup in the isolated child. A standard
single-line Windows edit control owns keyboard editing and paste behavior, while
an opaque fixed-text sibling overlay covers the control so no value, mask glyph,
caret movement, or length is rendered. The edit control remains password-styled
as a fail-safe; copy and cut are blocked, and a fixed Paste/Clear-only context
menu delegates paste to the standard edit control without any product clipboard
API read. Cancel, close, and Escape remain pre-store cancellation.

The Windows computer-control safety rules prohibit automating an authentication
dialog. Accordingly, no UI automation will type into or submit this popup.
Automated work may validate code, buffer wiping, fixed Unicode strings, message
routing, and synthetic non-human boundaries. A final real typing and paste row
must still be performed by the human with a fixed synthetic value only, after
the popup implementation and an independent review are complete.

## Popup start containment and first visible layout rejection

Before the popup was offered to the human, an independent review found a
parent/child start race. `multiprocessing.Process.start()` could have created a
Windows child before returning while an asynchronous `KeyboardInterrupt`
prevented the parent from recording that the child existed. The old parent
branch could then have resumed without waiting for the popup child. A proposed
helper-thread workaround was rejected because `Thread.start()` has its own
asynchronous-exception ambiguity.

The release candidate now holds a narrowly scoped Python `SIGINT` and Windows
`SIGBREAK` ignore lease across `Process.start()` and the local start-proof
write, then gates until both original handlers are restored exactly. The child
calls `FreeConsole()` before all popup, native facade, archive, credential
store, or provider work and sends one fixed detached-child acknowledgement. If
that acknowledgement cannot be sent, live work does not begin. The parent
closes its duplicate send handle and accepts only the strict sequence
acknowledgement, final mapping, and terminal pipe EOF. An exceptional
`Process.start()` therefore cannot be mistaken for exact pre-start evidence:
EOF before the acknowledgement proves no live work began, while an observed
acknowledgement forces the parent to wait through the final mapping and EOF.
Normal start return additionally requires an unbounded join. No exception text
or secret is transported in this protocol. The final popup/security/workflow
focused run passed 118 tests and 218 subtests; an independent workflow run
passed 48 tests, and the reviewer found no remaining P0/P1 in that production
path.

The first visible popup exercise then launched a fixed-synthetic harness only.
It used no real PAT, credential-store write, provider request, or product
clipboard API. The separate native window existed, responded to Windows, and
reported the exact Unicode title `WOM · 안전한 자격 증명 입력`.
However, before the human entered anything, a window-only capture showed that
the upper instruction region was too cramped and appeared visually overlapped.
The Confirm button was still disabled, proving no non-empty input had been
submitted. The exact synthetic harness process was terminated and no result
receipt was created. This is a rejected UI attempt, not a human input pass.

The next correction is limited to the native popup layout: standard Windows
font metrics, non-overlapping instruction rows, clear spacing around the opaque
input overlay and status, and a rendered-window review before the popup is
shown to the human again. Security, causal evidence, and the withdrawn console
decision remain unchanged.

## DPI-correct render review and first popup input receipt

The apparent clipping in the first post-font capture was subsequently proven
to be a capture-tool error rather than a popup-rendering error. The monitor was
running at 168 DPI (175%), while the first PowerShell capture thread remained
DPI-unaware and allocated a virtualized 660 by 470 bitmap for a physical 1155
by 823 PMv2 popup. A PMv2-aware recapture included the entire window. Pixel
comparison proved that the smaller image was exactly the upper-left crop of the
full image. The full capture showed every Korean and ASCII instruction, the
opaque input overlay, status row, and both buttons without overlap or clipping.
The invalid undersized capture is not release evidence.

After that visual review, the popup was brought to the foreground for a human
exercise using the public fixed synthetic challenge only. The human reported
that input had been completed. The resulting content-free receipt was:

- `child_console_detached: true`;
- `credential_input_received: true`;
- `complete_line_received: true`;
- `cancelled: false`;
- `exact_synthetic_input: false`;
- `credential_store_write_attempted: false`;
- `provider_request_attempted: false`;
- `clipboard_read_api_called_by_product: false`;
- `secret_value_present: false`.

This closes the original mechanical failure narrowly: the separate popup did
receive a non-empty complete human input and returned normally. It does not yet
prove an exact fixed-value typing or paste row because the received text did
not exactly match the fixed synthetic challenge. The actual entered value was
not logged, returned, stored, or sent to a provider; the mutable child buffer
was wiped. No real credential adoption or recovery action was attempted.

Immediately after that result, the human corrected the record: they had entered
an actual secret rather than the displayed fixed synthetic challenge. This was
an operator-safety failure in the exercise design. A synthetic-only harness
must not merely describe the challenge in surrounding prose; it must make the
boundary unmistakable and must not invite a real credential-shaped action
until the synthetic exercise is complete.

The correction does not change the observed technical boundary. The child had
already exited, its mutable result buffer was wiped, and the content-free
receipt again confirmed `credential_store_write_attempted: false`,
`provider_request_attempted: false`, `secret_value_present: false`, and no
product clipboard read. The entered secret was never printed or written to the
receipt. If paste was used, the operating-system clipboard may still contain
what the human copied; that is outside this product harness and must be cleared
by replacing or deleting the clipboard entry. No token rotation or live
provider action is inferred solely from this local transient input, but the
actual secret must not be entered into another test harness.

After the content-free receipt was recorded, the exact synthetic harness,
receipt JSON, and both temporary render captures were deleted. No harness
process remained. None of those temporary artifacts contained the entered
secret; deletion also prevents the test-only popup from being launched again
by mistake.

## Explicit popup intent guard and release-surface pivot

The human's correction was treated as decisive product feedback, not as a
successful registration. The synthetic popup had accepted a non-empty complete
line, but the person had entered an actual secret because the exercise did not
make the test-versus-registration boundary unmistakable. That row remains a
failed, pre-intent-guard human attempt. It involved no credential-store write,
provider request, archive mutation, product clipboard read, or retained value.

The popup now requires a typed input intent before any native window can be
shown. Production constructs
`CredentialPopupInputIntent.live_registration` and displays the exact blue
banner `실제 자격 증명 등록`. The acceptance helper constructs
`CredentialPopupInputIntent.synthetic_acceptance` and displays the exact red
banner `합성 입력 테스트 · 실제 키 입력 금지`, followed by the fixed warning
`경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.` and the instruction
to enter only the fixed synthetic string. Missing intents and plain strings
fail before native calls or `ShowWindow`.

The manual helper was rebuilt around schema
`wom-kit/windows-credential-popup-acceptance/v0.1`, route
`codex_desktop_native_popup`, and fixed challenge
`WOM-INPUT-ACCEPTANCE-0319`. It asks for a separate pre-launch acknowledgement
that this is a synthetic-only test. It has no route to credential store,
provider, archive mutation, or actual PAT collection. Its result contains only
strict Boolean observations and one content-free machine classification; it
never contains the submitted string or its length.

An independent review then found that the first popup helper implementation
had recreated an asynchronous `Process.start()` interruption race. A
`KeyboardInterrupt` after native child creation but before the local
`started=True` assignment could have allowed an orphan synthetic popup to keep
running after the parent reported failure. The helper now uses the same narrow
start-signal lease and containment protocol as production: exact handler
capture and install, start proof while ignored, exact restoration before
receive, then strict detached-child acknowledgement, final mapping, terminal
EOF, and a no-timeout join after normal start. Ambiguous starts drain the pipe
to EOF and never guess that no child existed. Fixed tests cover interruptions
before, during, and after launch without opening a real window.

All current v0.3.319 operator-facing release surfaces were consequently
pivoted from the withdrawn terminal experiments to the native popup. Historical
v0.3.318 artifacts and the chronological failure evidence in this minute remain
unchanged. The legacy console module is retained only as a direct-import
compatibility artifact and is not imported by production or the manual helper.

No new human popup, real key entry, credential-store write, provider request,
archive mutation, release, or live recovery occurred during this documentation
and test pass. A fresh human run of the explicit synthetic popup remains
`not_performed`/pending. Actual credential registration is a separate later
action and also remains `not_performed`/pending; only that later action may ask
for a real PAT under the blue `실제 자격 증명 등록` banner.

Current files changed for this pivot include:

- `wom-kit/src/wom_kit/archive_cli.py`;
- `wom-kit/tools/check_windows_credential_console_host.py` (legacy filename,
  native-popup behavior);
- `wom-kit/tests/test_windows_credential_console_host_acceptance.py` and the
  related CLI/release-document tests;
- the v0.3.319 release note, Letter 132 guide, decision record, changelog,
  README/UPGRADE surfaces, capability/runtime documents, and runtime
  SKILL/operator-contract sources plus packaged mirrors.

## Human correction: do not make another synthetic row a recovery gate

The human then corrected the operating plan again. Because the earlier harness
confusion had already caused an actual secret to be entered into a synthetic
test, asking for another exact synthetic row before recovery would repeat the
very risk the intent guard was meant to remove. The team therefore withdrew
that proposed prerequisite.

The current evidence remains exact: automated/fake native boundaries passed,
DPI-correct rendering was reviewed, and the popup returned a truthful non-empty
complete human-input receipt. The human synthetic row itself remains failed
because it did not match the fixed challenge and is not repeated for this
recovery. The synthetic helper remains available only as optional future
acceptance evidence and never authorizes or blocks actual registration.

Actual credential registration remains `not_performed`. It may begin after the
published v0.3.319 runtime is verified in a new process and the human explicitly
confirms that the popup shows the blue `실제 자격 증명 등록` banner. No new popup,
PAT input, store write, provider request, archive mutation, release, or recovery
was performed while recording this correction.

## Full-regression correction after the popup freeze

The frozen popup, workflow, provider, manual-helper, release-document, privacy,
and package-resource checks passed. The first complete CLI regression then
found one test-code error rather than a product error:
`test_runtime_context_returns_deterministic_redacted_json` contained a
credential-result assertion block that referenced the undefined local name
`first`. The block had been inserted into the unrelated runtime-context test
while the v0.3 causal-evidence assertions were being added elsewhere.

The authoritative first CLI run completed all 1,376 tests and reported that
single `NameError`, with no assertion failure and no second error. The misplaced
block alone was removed. The exact failing test passed immediately afterward,
and a fresh complete CLI rerun was started against the corrected tree. The
non-CLI run was already independent of `tests/test_cli.py` and completed 1,652
unittest cases plus 210 pytest-native cases with no failure or error.

This correction opened no popup, requested no secret, touched no credential
store or provider, and changed no product behavior. Commit, publication,
installation, actual credential registration, and recovery remained pending at
this point.
