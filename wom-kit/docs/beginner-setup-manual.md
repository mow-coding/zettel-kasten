# Beginner Setup Manual

Status: v0.3.64 read-only beginner setup manual with object storage setup screens
Date: 2026-06-16

This document is the beginner-facing bridge between recommendations and actual
first-use setup.

It answers the question:

```text
The system recommended a vault or an extraction tool. What do I do next?
```

## Command

```bash
archive beginner-setup-manual <archive-root> \
  --topic first_secret_and_text_tools \
  --scenario personal_local_first \
  --store-id keepassxc \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
first-use-setup-manual
setup-manual
```

Supported topics:

- `first_secret_and_text_tools`
- `credential_vault`
- `credential_bulk_migration`
- `derived_text_tools`
- `object_storage_setup_manual`

## What It Explains

The manual explains:

- what a vault is before naming products,
- why WOM records safe refs instead of real secrets,
- how to name a first KeePassXC-style vault without putting private details in
  the filename,
- how to walk through the KeePassXC 2.7.x new database wizard screen by screen,
- which first-vault KeePassXC fields WOM recommends for a local offline KDBX
  threat model,
- how to bulk-import existing secrets from a human-prepared CSV into
  KeePassXC by importing to a temporary database, merging into the main vault,
  and cleaning up temporary files,
- how to use safe non-secret group and entry labels,
- how to prepare derived-text tools such as LibreOffice and Tesseract,
- how to use a private local `--tool-hints` JSON file when a tool is installed
  but not on `PATH`,
- how to walk through Cloudflare R2 bucket and API token setup fields without
  inventing bucket names, token permissions, or public-access choices,
- which dry-run commands to run next.

## Beginner Rules

The first rule is simple:

```text
Do not paste passwords, API keys, app passwords, OAuth tokens, database paths,
account emails, or provider URLs into chat.
```

The AI can help with:

- labels,
- command shapes,
- checklist order,
- safety checks,
- explanation.

The human uses visible local app windows or terminal prompts for real secret
entry.

## KeePassXC First Vault Walkthrough

When the selected store is `keepassxc`, the JSON output includes a
`product_walkthrough` for the first database wizard.

For the WOM beginner local-vault context, the recommended field decisions are:

```text
Database format: KDBX 4.0
Encryption algorithm: AES-256
Key derivation function: Argon2d
Transform rounds / memory / threads: leave KeePassXC automatic or recommended values alone
```

Why Argon2d? This first-vault guidance is scoped to a local offline `.kdbx`
file where the main risk is a stolen database being attacked offline with
GPU/ASIC hardware. If generic internet advice says Argon2id but KeePassXC's
local database wizard recommends Argon2d, follow this WOM first-vault guidance.
If a workplace, school, or regulated environment has stricter policy, that
policy wins.

The walkthrough also tells the beginner which button to press on the general,
encryption, credentials, save, and first-entry screens. It still does not open
KeePassXC, create the database, record the database path, or read any secret.

## KeePassXC Bulk Migration Walkthrough

For existing secrets that the human has already prepared as CSV, run:

```bash
archive beginner-setup-manual <archive-root> \
  --topic credential_bulk_migration \
  --scenario personal_local_first \
  --store-id keepassxc \
  --platform windows \
  --dry-run \
  --format json
```

The output includes a `credential_bulk_migration` section and a
`product_walkthrough` for KeePassXC 2.7.x CSV import.

The beginner defaults are:

```text
CSV encoding: UTF-8
First row has field names: on
Field separator: ,
Text qualifier: "
Comment character: #
Column mapping: Group, Title, Username, Password, URL, Notes
```

The key trap is that CSV import may put the entries into a temporary/new
database first. The beginner path is:

```text
prepare CSV outside WOM
-> import CSV into a temporary KeePassXC database
-> open the main vault
-> Database > Merge from Database
-> select the temporary database and unlock it locally
-> save and verify the main vault
-> delete the temporary database and working CSV copy
```

Use the normal import path for CSV secrets. Do not choose passkey import unless
the source is actually a WebAuthn/passkey export. If the Group column contains
slashes, KeePassXC may show nested folders; that can be normal when the nesting
was intentional.

The manual still does not read the CSV, open KeePassXC, create a temporary
database, merge a vault, delete files, record local paths, or see any secret
value. It is a screen-by-screen human guide.

## Safe Label Examples

These are labels, not secret values:

```text
cred:openai-api
secret:keepassxc-openai-api
keyring:wom-mail-access
env:WOM_OPENAI_API_KEY
```

Avoid labels that contain:

- real usernames,
- email addresses,
- provider URLs,
- passwords,
- API key fragments,
- local absolute paths.

## Derived-Text Tool Hints

When LibreOffice, Tesseract, or HWP tools are installed but not on `PATH`, use a
private local hint file:

```json
{
  "schema": "wom-kit/derived-text-tool-hints/v0.1",
  "executables": {
    "soffice": "<local-soffice-path>",
    "tesseract": "<local-tesseract-path>",
    "hwp5txt": "<local-hwp5txt-path>"
  }
}
```

Then run:

```bash
archive derive-text-doctor <archive-root> \
  --tool-hints <private-local-tool-hints.json> \
  --dry-run \
  --format json
```

The doctor checks whether hinted files exist. It does not execute the tools and
does not echo the hint file path or executable paths.

## Object Storage Setup Manual

For Cloudflare R2 setup, run:

```bash
archive beginner-setup-manual <archive-root> \
  --topic object_storage_setup_manual \
  --dry-run \
  --format json
```

This topic exists because recommending a provider is not enough. A beginner also
needs the next exact bucket name, the setup screen fields, and the token/ref
bridge.

The manual tells the human to run `object-storage-recommendation` first and use
the returned bucket name. Do not invent a nicer name. The WOM default naming
rule is:

```text
zettel-kasten-<profile-slug>-objets
```

For a first private personal archive on Cloudflare R2, the v0.3.64 walkthrough
recommends:

```text
Bucket name: use the value returned by WOM
Location: None / automatic selection
Jurisdiction: do not specify by default
Default storage class: Standard
Public access: disabled / private
API token permission: Object Read & Write
API token bucket scope: specific bucket only
TTL / expiration: set a reviewed expiration when practical
Client IP filtering: use only when the human has a stable known IP/CIDR
Secret handling: store Access Key ID and Secret Access Key in a vault/keyring/env flow, never in chat
```

The Cloudflare-specific recommendations are based on official docs checked for
this release:

- [R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/)
- [R2 data location](https://developers.cloudflare.com/r2/reference/data-location/)
- [R2 storage classes](https://developers.cloudflare.com/r2/buckets/storage-classes/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Cloudflare token restrictions](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)

Interpretation notes:

- Location `None` means automatic placement. Choose a location hint only if the
  human knows the access pattern needs it.
- Jurisdiction restrictions are for data residency or compliance needs. If the
  human does not have such a requirement, do not guess one.
- Standard storage is the beginner default because Infrequent Access has
  retrieval fees and a minimum storage duration. Infrequent Access may be right
  for cold archives, but only after reviewing expected read/copy behavior and
  current pricing.
- Public development URLs and custom-domain public access are not part of the
  private WOM archive setup path.

Safe dry-run chain:

```text
object-storage-recommendation
-> beginner-setup-manual --topic object_storage_setup_manual
-> object-storage --dry-run
-> create bucket/token manually in Cloudflare only after human review
-> credential-ref-plan for the token ref
```

The manual still does not open Cloudflare, create a bucket, create an API token,
read secrets, write secrets, upload files, call provider APIs, or write files.

## Related Dry-Run Chain

Credential setup:

```text
credential-store-recommendation
-> credential-vault-onboarding-plan
-> beginner-setup-manual
-> credential-ref-plan
-> credential-access-approval-plan
-> credential-keepassxc-command-plan
-> credential-keepassxc-write
```

Derived-text setup:

```text
beginner-setup-manual
-> derive-text-doctor
-> derive-text-coverage
-> derive-text toolchain
-> derive-text capture
```

Object-storage setup:

```text
object-storage-recommendation
-> beginner-setup-manual --topic object_storage_setup_manual
-> object-storage --dry-run
-> credential-ref-plan
-> object-storage-operation-request-plan
```

## Closed Actions

`beginner-setup-manual` does not:

- ask for secrets in chat,
- read secret values,
- write secret values,
- open KeePassXC,
- open a keyring,
- open a browser password store,
- read environment variables,
- open provider dashboards,
- create buckets,
- create API tokens,
- install tools,
- execute tools,
- write a tool-hints file,
- read source bytes,
- run OCR,
- run parsers,
- run ASR,
- call providers,
- write files,
- draft zets,
- mint zets.

It is a human setup guide and command checklist, not an installer, vault
adapter, extractor, or automation runner.
