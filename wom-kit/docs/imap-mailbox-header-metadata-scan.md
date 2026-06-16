# IMAP Mailbox Header Metadata Scan

Status: v0.3.62 approval-gated local IMAP header metadata scan baseline
Date: 2026-06-16

v0.3.62 opens the first narrow live IMAP adapter path.

It is intentionally small:

- app-password auth only,
- `env:` username and app-password refs only,
- `header_metadata_scan` only,
- inbox mailbox ref only,
- approval receipt required,
- execution contract required,
- non-secret execution receipt only.

This is not message capture, body reading, attachment capture, OAuth, keyring
retrieval, or derived-text capture.

## Command

```bash
archive imap-mailbox-header-metadata-scan <archive-root> \
  --adapter-id local-imap \
  --source-id imap:naver \
  --provider naver \
  --account-ref imap:account:mail-personal \
  --username-ref env:MAIL_IMAP_USERNAME \
  --auth-mode app_password_ref \
  --app-password-ref env:MAIL_IMAP_APP_PASSWORD \
  --mailbox-ref imap:mailbox:inbox \
  --credential-id cred:mail-source-access \
  --credential-kind mail_app_password \
  --credential-provider naver \
  --store-kind environment \
  --adapter-kind environment_injection \
  --operation header_metadata_scan \
  --selection-rule newest_first \
  --selector-id mail-selection:recent-inbox \
  --max-messages 25 \
  --approval-decision approve_once \
  --approval-receipt receipts/credentials/access-approvals/example.json \
  --dry-run \
  --format json
```

Aliases:

```text
imap-header-metadata-scan
mailbox-header-metadata-scan
```

Use `--approve` instead of `--dry-run` only after reviewing the manifest,
approval receipt, selection rule, and execution contract.

## Required Setup

The command requires:

- an IMAP adapter manifest,
- a credential access approval receipt,
- a ready IMAP adapter execution contract,
- `env:` refs for username and app password,
- environment variables set outside WOM and outside public Git.

v0.3.62 does not read `keyring:`, `secret:`, or `wallet:` refs. Those remain
future adapters.

## What It Does In Approved Mode

Approved mode may:

- read the two environment variables named by the safe `env:` refs,
- open an IMAP TLS connection,
- attempt login,
- select `INBOX` read-only,
- search candidate messages using the reviewed selection rule,
- fetch limited header metadata for up to `--max-messages`,
- write a non-secret receipt under `receipts/imap/adapter-executions/`.

## What It Never Returns

The command output and receipt must not include:

- username values,
- password values,
- environment variable names,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- IMAP host values,
- provider URLs,
- raw UID values,
- Message-ID values,
- subject values,
- sender or recipient values,
- raw headers,
- bodies,
- attachment names,
- attachment bytes,
- local absolute paths.

Candidate refs are opaque hashes such as `imap-candidate:<sha256>`.

## Still Future Work

The first live adapter does not implement:

- OAuth,
- OS keyring retrieval,
- password-manager retrieval,
- generic secret-manager retrieval,
- mailbox names other than inbox refs,
- body capture,
- RFC822 `.eml` capture,
- attachment capture,
- derived-text capture,
- mailbox flag changes,
- deletion or send behavior.
