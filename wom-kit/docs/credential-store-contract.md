# Credential Store Contract

Status: v0.3.20 read-only credential reference baseline
Date: 2026-06-14

This document defines how WOM-kit talks about secrets without storing secrets in
the archive.

Secrets include:

- mail usernames,
- mail app passwords,
- mail OAuth tokens,
- OpenAI API keys,
- OCR provider API keys,
- object storage tokens,
- backup repository passwords,
- generic provider credentials.

## Rule

WOM archive files store references only.

They must not store the real secret value.

```text
archive metadata -> keyring:openai-api-key
actual secret    -> OS keyring, environment variable, or external secret manager
```

This is the difference between a label on a key hook and the key itself.

## Current Behavior

v0.3.20 adds:

```powershell
python cli\archive.py credential-ref-plan .\my-archive `
  --credential-id cred:openai-api `
  --credential-kind openai_api_key `
  --provider openai `
  --credential-ref keyring:openai-api-key `
  --dry-run `
  --format json
```

and MCP:

```text
credential_ref_plan
```

The command/tool validates that a credential reference is shaped like one of:

```text
env:NAME
keyring:name
secret:name
wallet:name
```

It writes nothing, reads nothing, opens no OS keyring, reads no environment
variable, starts no OAuth flow, calls no provider API, calls no paid OCR API,
calls no OpenAI API, and never asks the user to paste a secret into chat.

## Supported Credential Kinds

The first contract recognizes:

```text
mail_username
mail_app_password
mail_oauth_token
openai_api_key
ocr_api_key
provider_api_key
object_storage_token
backup_password
generic_secret
```

These kinds cover Gmail, Naver, university mail, company mail, OpenAI-backed AI
work, paid OCR providers, object storage, backups, and future provider adapters.

## Store Types

`env:` means the secret is supplied by the host process environment.

`keyring:` means the secret should live in the operating-system credential
store, such as Windows Credential Manager, macOS Keychain, or a Linux Secret
Service compatible keyring.

`secret:` means an external/local secret manager is expected. Examples include
password managers or deployment secret stores.

`wallet:` means a future WOM wallet or local custody layer is expected.

v0.3.20 does not implement any read/write adapter for those stores. It only
checks the reference shape and records the intended boundary.

v0.3.20 does not store passwords, OAuth tokens, OpenAI API keys, OCR API keys,
or provider credentials.

v0.3.21 adds a read-only inventory companion:

```powershell
python cli\archive.py credential-ref-inventory .\my-archive `
  --dry-run `
  --format json
```

See [Credential Ref Inventory And Onboarding](credential-ref-inventory-and-onboarding.md).

The inventory helps a human remember which refs exist without turning WOM into
a password vault. It scans provider bindings, source bindings, and the ignored
local catalog `profiles/local/credential-refs.local.yml`, but it does not echo the exact ref value or read the secret behind it.

v0.3.22 adds [Credential Store Recommendations](credential-store-recommendations.md)
so WOM can explain which external store class fits a human scenario without
opening a vault or reading any secret value.

v0.3.23 adds [Credential Access Broker Plan](credential-access-broker-plan.md)
so WOM can describe future approved secret use without implementing secret retrieval.

v0.3.24 adds [Credential Access Approval Plan](credential-access-approval-plan.md)
so WOM can preview the human-reviewed approval receipt without writing it or
granting live access.

## Mail Sources

Mail source access should use refs such as:

```text
env:WOM_MAIL_USERNAME
keyring:naver-app-password
keyring:gmail-oauth-token
```

Institutional mail, university mail, and company mail should start as
`generic_imap` when IMAP is available. If a provider requires Microsoft Graph,
Exchange, SAML, browser login, or a custom webmail flow, that needs a separate
future adapter.

The archive should still record only refs, never the email address, password,
OAuth refresh token, mailbox URL, or private folder name.

## Model And OCR Providers

OpenAI and paid OCR providers should also use refs:

```text
keyring:openai-api-key
keyring:ocr-provider-api-key
env:WOM_OCR_API_KEY
```

A future OCR or model adapter may resolve a ref only after policy checks and
human approval. The adapter should record result metadata such as source object
id, derivation method, tool/provider name, cost class, and review status. It
must not record the secret value.

## Closed Actions

v0.3.20 does not:

- store passwords,
- store OAuth tokens,
- store OpenAI API keys,
- store OCR API keys,
- write to Windows Credential Manager, macOS Keychain, Linux keyring, or
  KeePassXC,
- read from any keyring,
- read environment variables,
- start OAuth,
- call OpenAI,
- call OCR providers,
- call mail providers,
- call object storage providers,
- upload files,
- download files,
- draft zets,
- mint zets.

It creates a safe contract for future local adapters.

## Future Workflow

The intended future sequence is:

1. Human stores or rotates the real secret outside the archive.
2. WOM records only a credential ref.
3. AI requests a capability that needs the ref.
4. WOM checks policy, purpose, provider, archive context, and human approval.
5. A trusted local adapter resolves the ref without echoing it.
6. The provider result is stored as source/derived evidence with provenance.
7. The secret value never appears in Git, zets, receipts, logs, source maps,
   screenshots, prompts, or public docs.
