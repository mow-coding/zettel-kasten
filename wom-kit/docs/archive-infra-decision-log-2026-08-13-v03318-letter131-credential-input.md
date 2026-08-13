# v0.3.318 Letter 131 credential-input decision

Status: v0.3.318 implementation and release scope. This document does not claim
merge, CI, tag, Release, wheel publication, real provider enrollment, physical
paste acceptance, beta-client execution, or human acceptance.

## Context

Letter 131 reported that the separate black console appeared, but hidden input
made it impossible to tell whether a paste arrived. The transaction later
returned `provider_identity_unverified` after exact-entry rollback and verified
absence, which is evidence that a non-empty value reached provider verification,
not evidence that no paste occurred. One generic provider code also prevented
the operator from distinguishing bad authentication, identity-service failure,
and inaccessible reviewed content.

## Decision

1. Keep secret intake in the spawned Unicode Windows console. Keep input
   `echo` disabled and forbid programmatic `clipboard` reads. Do not add chat,
   argv, ordinary stdin, environment, plaintext file, log, parent IPC, or UI
   reflection as a secret surface.
2. Guide `Ctrl+V` and `Shift+Insert` first, identify `Ctrl+Shift+V` as a Windows
   Terminal default, and describe right-click as host-dependent. Do not promise
   that WOM controls customized terminal bindings.
3. Keep cooked processed/line/edit input modes, ignore `Ctrl+C` only during the
   prompt, and document empty Enter as cancellation. Detach before default
   handler behavior can resume.
4. After one complete non-empty line, show only
   `입력값을 받았습니다. 검증 중입니다.` for a bounded dwell. Show neither
   value nor length. This is input receipt, not authentication or persistence.
5. Publish v0.2 result envelopes and five ordinary public reason codes:
   `credential_input_cancelled_or_empty`, `credential_input_not_received`,
   `provider_auth_rejected`, `provider_identity_endpoint_unavailable`, and
   `reviewed_anchor_inaccessible`.
6. Bind cancellation and console-read failures to the pre-store state with
   `rollback_status: not_required`. Bind all three provider-stage failures to a
   completed temporary store write and exact-entry rollback with `deleted` or
   `delete_failed`. Accept `deleted` only with verified store absence.
7. Keep unrecognized provider/verifier failures on
   `provider_identity_unverified`; a new specific code must come only from the
   allowlisted official adapter boundary.
8. Wipe every mutable secret buffer, including temporary UTF-16 duplicates,
   and keep public results, logs, screen output, exceptions, and receipts
   secret-free.
9. Treat automated Win32 API canaries and actual host gesture acceptance as two
   different evidence classes. The opt-in
   `wom-kit/tools/check_windows_credential_console_host.py` may record one
   fixed-synthetic human attempt without a real PAT, store, provider, private
   path, or clipboard API. Until performed, publish actual host acceptance as
   `not_performed`.

## Consequences

- The operator can see that a complete hidden line reached WOM before provider
  verification begins.
- A result tells the operator whether to retry input, review the credential,
  wait for the provider identity service, or review page sharing.
- Forged or internally inconsistent reason/rollback combinations fail closed.
- No new persistent credential, clipboard, provider, or AI-chat authority is
  introduced.
- API canary success cannot be generalized into physical gesture success for
  Windows Terminal, Console Host, ConPTY, remote, or customized hosts.
