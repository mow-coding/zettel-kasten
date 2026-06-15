# Connected Accounts

Status: v0.3.38 read-only connected accounts bridge
Date: 2026-06-15

`connected-accounts` is a read-only map of external account metadata that WOM
already knows about.

It answers:

```text
Which provider/source accounts are connected in metadata?
Which credential store types are referenced?
Where should I look next without exposing the secret values?
```

## Command

```bash
archive connected-accounts <archive-root> \
  --dry-run \
  --format json
```

Aliases:

```text
accounts
account-status
```

Use `--include-disabled` to include disabled provider or source bindings in the
metadata-only overview.

## What It Reads

The bridge reads only metadata:

```text
provider-bindings.yml
source-bindings.yml
profiles/local/credential-refs.local.yml
```

The local credential inventory is still an ignored local catalog. It should
contain refs and labels only, not secret values.

## What It Returns

The output groups:

- provider bindings,
- IMAP mailbox source accounts,
- credential catalog metadata,
- credential store-type summaries such as `env`, `keyring`, `secret`, or
  `wallet`.

It may show safe non-secret account labels such as:

```text
imap:account:gmail-personal
provider:account:openai-personal
```

It does not show exact credential refs such as `keyring:...` or `secret:...`.
It reports only the store type and ref prefix.

## Current Closed Actions

`connected-accounts` does not:

- read passwords,
- read API keys,
- read OAuth tokens,
- read environment variables,
- open a password manager,
- open an OS keyring,
- open a browser password store,
- start OAuth,
- call providers,
- open IMAP connections,
- attempt IMAP login,
- read mail headers,
- read mail bodies,
- read source bytes,
- write files,
- draft zets,
- mint zets.

It is an account map, not an account connector.

## Related Commands

Use these commands after reading the map:

```text
credential-ref-inventory
provider-status
imap-mailbox-plan
credential-vault-onboarding-plan
beginner-setup-manual
```

The safe workflow is:

```text
beginner-setup-manual
-> credential-ref-inventory
-> connected-accounts
-> provider-status or imap-mailbox-plan
-> human-reviewed future adapter work
```
