# Letter 131 credential console paste and failure stages

Status: implemented in v0.3.318 source and locally verified at the Win32 API
boundary. Exact release publication and physical host-gesture acceptance remain
separate evidence.

## What Letter 131 showed

The black credential console opened with the intended task and security copy,
but hidden input gave the human no visible sign that an attempted paste had
arrived. The final public code, `provider_identity_unverified`, was too broad to
explain the next safe action.

The transaction's rollback was successful: the temporary exact credential
entry was deleted and absence was verified. Because rollback occurs only after
a non-empty value has been written and provider verification has started, the
record indicates that some input arrived. It does not identify whether
`Ctrl+Shift+V`, right-click, or another action supplied it.

## What the human sees in v0.3.318

The input remains masked. Immediately above it, WOM explains:

```text
- Ctrl+V 또는 Shift+Insert를 사용하세요.
- Windows Terminal 기본 설정에서는 Ctrl+Shift+V도 사용할 수 있습니다.
- 오른쪽 클릭 동작은 터미널 설정에 따라 다릅니다. 메뉴가 뜨면 붙여넣기를 선택하세요.
- 붙여넣은 글자는 화면에 표시되지 않습니다. 붙여넣은 뒤 Enter를 누르세요.
- 취소하려면 아무것도 입력하지 않고 Enter를 누르세요.
```

During that short prompt WOM ignores `Ctrl+C`, because processed console input
is required for classic edit shortcuts and the default console Ctrl+C handler
could otherwise terminate the worker. Empty Enter is the single documented
cancellation gesture.

After WOM receives one complete non-empty line, it displays:

```text
입력값을 받았습니다. 검증 중입니다.
이 창은 자동으로 닫힙니다.
```

The value and its length are never displayed. This message confirms only input
receipt. Provider authentication, reviewed-page access, exact-store persistence,
and authenticated receipt publication still have their own later gates.

## Supported host guidance, not host control

Windows Terminal provides default paste bindings, but users can customize them.
Right-click behavior can also be configured. Classic Console Host uses its own
processed-input and edit-mode behavior. ConPTY transports console input between
a terminal host and a console application; it does not give WOM authority over
the parent host's key bindings.

Therefore WOM:

- enables processed, line, insert, Quick Edit, and extended input modes;
- disables echo and virtual-terminal input;
- reads the completed Unicode line through the console API;
- never calls a clipboard API;
- never claims that `credential_input_not_received` proves a particular
  physical paste action failed.

## Fixed public results

The child uses `wom-credential-secure-intake-result/v0.2`; the adoption workflow
uses `wom-credential-workflow-result/v0.2`.

### `credential_input_cancelled_or_empty`

No complete non-empty value was accepted. The store write did not begin, so
`rollback_status` must be `not_required`. The operator may create a fresh plan
when ready.

### `credential_input_not_received`

The safe console boundary failed to return one valid complete value. The store
write did not begin, so `rollback_status` must be `not_required`. This result is
not paste-gesture telemetry. Retry a supported console method only through a
fresh plan.

### `provider_auth_rejected`

The provider rejected the credential. This occurs after the temporary exact
store write, so rollback must be `deleted` with verified absence or
`delete_failed`. Review the credential before making a new plan.

### `provider_identity_endpoint_unavailable`

The provider identity endpoint or its required response could not be verified.
The same post-write rollback rule applies. Wait for service recovery before a
new plan; do not guess that the credential is wrong.

### `reviewed_anchor_inaccessible`

The reviewed page could not be verified through this connection. The same
post-write rollback rule applies. Review page sharing and access before a new
plan; do not automatically rotate a saved credential.

Unknown official evidence or a custom verifier exception keeps the generic
`provider_identity_unverified` fallback. This prevents a new unreviewed error
shape from being misreported as a specific stage.

## Persistence and reuse stay unchanged

`credential-adopt` remains a first-enrollment or explicitly reviewed
replacement command. A successful registration is stored as an exact Windows
Generic Credential and described by an authenticated non-secret receipt. Later
approved work reuses the matching entry after receipt, exact-secret fingerprint,
and current reviewed-anchor checks. The human does not enter the PAT on every
task.

Provider-stage failure during a new registration deletes the temporary exact
entry and verifies absence. A deletion failure stops with `delete_failed`; it
does not retry, hide the residue, or publish a successful registration.

## Verification layers

The automated unit and synthetic Win32 API layers verify code behavior without
a real PAT, provider account, page, private data source, Credential Manager
write, or clipboard access. The latest canary verified exact Korean output,
echo and VT-input disablement, status dwell, Ctrl+C survival, cleanup-window
survival, and mode/code-page restoration.

Those checks inject synthetic input at the console API boundary. They are not
actual physical paste gesture evidence.

For one explicit human-observed host attempt, run the opt-in source-tree tool
only with the fixed synthetic value:

```powershell
python -B wom-kit/tools/check_windows_credential_console_host.py --host-family windows_terminal --launch-route direct_terminal --gesture ctrl_v
```

The tool permits only exact matched `host_family` and `launch_route` pairs plus
bounded `gesture` labels. It reports `automated_win32_boundary_status` separately from
`actual_host_acceptance_status`, never asks for a real PAT, calls no provider or
Credential Manager, performs no clipboard API read, emits no local path, and
wipes its mutable synthetic buffer. The prompt runs in a spawned worker so the
original terminal remains attached; only `(nonempty_bool, exact_bool)` returns
to the parent. Run it from the host being evaluated and
follow its fixed synthetic instructions. A result from one host does not cover
another host or customized key binding.

At release preparation time, physical gesture acceptance for Windows Terminal,
classic Console Host, and ConPTY is `not_performed`. This is an explicit
remaining human acceptance item, not a hidden source-test claim.

## Safe next attempt

After installing and verifying the exact v0.3.318 release artifact:

1. start a new process and confirm `archive --version`;
2. verify existing authenticated credential state before deciding enrollment is
   needed;
3. create a new `credential-adopt --dry-run` with public-safe task and reason
   copy;
4. approve only the unchanged request digest;
5. use `Ctrl+V` or `Shift+Insert` in the separate black console, or a supported
   host-specific action described there;
6. confirm the receipt status appears, then interpret the fixed public outcome;
7. on success, verify the authenticated registry and continue the separately
   approved Notion recovery workflow without another PAT prompt.

Never place a real PAT, page title, body excerpt, URL, identifier, email,
local filesystem path, native credential target, or provider response in
chat, argv, ordinary stdin, environment variables, documentation, logs, or a
manual acceptance record.
