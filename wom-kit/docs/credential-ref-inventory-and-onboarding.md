# Credential Ref Inventory And Onboarding

Status: v0.3.21 read-only inventory baseline
Date: 2026-06-14

This document explains how a human can remember which credentials exist without
putting passwords into WOM.

## Short Answer

WOM should not become a plaintext password vault.

Use a password manager, OS credential store, or secret manager for the actual
secret values. Use WOM for the catalog:

```text
What credential exists?
What is it for?
Which provider does it belong to?
Which store type holds it?
Which source/tool is allowed to reference it?
```

v0.3.21 adds a read-only inventory command for that catalog:

```powershell
python cli\archive.py credential-ref-inventory .\my-archive `
  --dry-run `
  --format json
```

Aliases:

```text
credentials
credential-status
```

MCP:

```text
credential_ref_inventory
```

The inventory does not echo the exact ref value. It reports only safe metadata
such as credential id, kind, provider, purpose, and ref prefix/store type.

## Why Not Plaintext In WOM?

Plaintext secrets in archive files would spread into:

- Git history,
- backups,
- search indexes,
- AI context,
- screenshots,
- logs,
- release artifacts,
- accidental public repositories.

That is exactly what the credential-ref contract is designed to avoid.

## What The Inventory Reads

The inventory scans:

```text
provider-bindings.yml
source-bindings.yml
profiles/local/credential-refs.local.yml
```

`profiles/local/credential-refs.local.yml` is local-only and should stay ignored
by Git.

Example local inventory:

```yaml
version: wom-local-credential-ref-inventory/v0.1
credentials:
  - credential_id: cred:openai-api
    credential_kind: openai_api_key
    provider: openai
    purpose: model_api_access
    credential_ref: keyring:openai-api-key
  - credential_id: cred:naver-mail-access
    credential_kind: mail_app_password
    provider: naver
    purpose: mail_source_access
    credential_ref: keyring:naver-app-password
```

The command output does not print `keyring:openai-api-key` or
`keyring:naver-app-password`. It prints that these refs use the `keyring:`
store type.

## Beginner Workflow

1. Choose a real secret store.
2. Put the real username, password, app password, token, or API key there.
3. Give that secret a boring local label.
4. Run `credential-ref-plan --dry-run` to check the ref shape.
5. Put only the ref into a provider/source binding or the local inventory.
6. Run `credential-ref-inventory --dry-run` to check your catalog.

## Windows Options

On Windows, the common choices are:

- Windows Credential Manager / OS keyring,
- KeePassXC or another password manager,
- environment variables for automation-only cases.

The safer default for a non-expert personal archive is usually a password
manager or OS keyring for long-lived secrets, and environment variables only
for short-lived automation shells.

WOM-kit v0.3.21 does not write to any of those stores. It only documents and
validates refs.

For scenario-based store choice, see
[Credential Store Recommendations](credential-store-recommendations.md).

## Mail Account Labels

`account_ref` is not a secret.

Use this:

```text
imap:account:naver-personal
```

Do not use this for `account_ref`:

```text
keyring:naver-account
```

`keyring:` belongs in fields that point to actual credential values:

```text
username_ref
app_password_ref
oauth_token_ref
credential_ref
```

This keeps the non-secret account label separate from the secret store label.

## Closed Actions

`credential-ref-inventory` does not:

- read passwords,
- read API keys,
- read OAuth tokens,
- read environment variables,
- open an OS keyring,
- open KeePassXC,
- call providers,
- start OAuth,
- write files,
- draft zets,
- mint zets.

It is a catalog of refs, not a secret reader.

## Future Work

Future local adapters may add approved keyring reads. That should still stay
behind policy checks, human approval, and non-echo guarantees.

Future work may also add provider-specific onboarding assistants, such as:

- Gmail OAuth setup,
- Naver app-password setup,
- university/company IMAP setup,
- OpenAI API key setup,
- paid OCR provider setup.
