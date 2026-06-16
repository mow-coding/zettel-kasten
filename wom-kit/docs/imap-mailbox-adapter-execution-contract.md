# IMAP Mailbox Adapter Execution Contract

Status: v0.3.61 read-only IMAP adapter execution contract baseline
Date: 2026-06-16

v0.3.61 adds the read-only execution contract for the first future live IMAP
adapter.

This is not the live adapter.

It is the boundary document and CLI surface that says what a future local
adapter must verify, what it may do only after approval, and what it must never
return to AI-visible output.

## Command

```bash
archive imap-mailbox-adapter-execution-contract <archive-root> \
  --adapter-id local-imap \
  --source-id imap:naver \
  --provider naver \
  --account-ref imap:account:mail-personal \
  --username-ref env:MAIL_IMAP_USERNAME \
  --auth-mode app_password_ref \
  --app-password-ref keyring:mail-app-password \
  --mailbox-ref imap:mailbox:inbox \
  --credential-id cred:mail-source-access \
  --operation header_metadata_scan \
  --selection-rule newest_first \
  --selector-id mail-selection:recent-inbox \
  --approval-decision approve_once \
  --approval-receipt receipts/credentials/access-approvals/example.json \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-adapter-execution-plan
mailbox-adapter-execution-contract
```

## Relationship To Preflight

The command wraps
[IMAP Mailbox Adapter Preflight Plan](imap-mailbox-adapter-preflight-plan.md).

It returns `contract_ready_for_future_implementation` only when preflight is
already `ready_for_future_adapter_after_approval`.

If the adapter manifest is missing, the approval receipt is missing, the
selection plan is not ready, or the audit preview is blocked, the execution
contract is blocked too.

## Contract Sections

The JSON response includes:

- `preflight_summary`,
- `execution_inputs_contract`,
- `future_allowed_actions_after_implementation_and_approval`,
- `mail_material_output_contract`,
- `receipt_contract`,
- `current_capability`,
- `closed_actions`,
- `privacy_guards`.

The future adapter must repeat preflight at execution time. A previously
successful dry-run is not permanent permission.

## Future Allowed Actions

After a live adapter is implemented and after approval is verified, the first
safe operation is still narrow:

- open an IMAP TLS connection,
- use a local approved credential inside the local adapter process,
- select the reviewed mailbox ref,
- execute the reviewed selection rule,
- for `header_metadata_scan`, read only the minimum header metadata needed for
  a non-secret local receipt.

v0.3.61 describes those actions but performs none of them.

## Current Closed Actions

`imap-mailbox-adapter-execution-contract` does not:

- open an IMAP connection,
- attempt login,
- select or search a mailbox,
- list candidate messages,
- read IMAP UIDs,
- read Message-ID values,
- read headers,
- read bodies,
- read attachments,
- retrieve credential values,
- open password managers,
- open OS keyrings,
- read environment variables,
- call providers,
- write execution receipts,
- write files.

## Output Contract

Future AI-visible output must not include:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- IMAP host values,
- provider URLs,
- Message-ID values,
- subjects,
- sender or recipient values,
- headers,
- bodies,
- attachment names,
- attachment bytes,
- secret values,
- local absolute paths.

Candidate refs must be opaque or hashed. Counts and coarse result status are
allowed; mail content is not.

## Still Future Work

The live IMAP adapter is still future work.

v0.3.61 does not implement secret retrieval, IMAP login, mailbox selection,
message capture, attachment capture, derived-text capture, execution receipt
writing, or provider-specific OAuth.
