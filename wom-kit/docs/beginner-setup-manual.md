# Beginner Setup Manual

Status: v0.3.135 read-only beginner setup manual with Notion recovery guidance
Date: 2026-06-22

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
- `notion_nested_recovery`

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
- how to run the Notion nested recovery human steps in plain language before
  the approval-gated live structure fetch,
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

The v0.3.74 walkthrough adds Korean-label and location-based guidance for the
same Cloudflare screens. This matters because translated dashboards may not
match English docs exactly.

Bucket creation location hints:

```text
Storage and databases / 스토리지 및 데이터베이스
-> R2 object storage / R2 객체 스토리지
-> Overview / 개요
-> Create bucket / 버킷 만들기
```

R2 API token location hints:

```text
Storage and databases / 스토리지 및 데이터베이스
-> R2 object storage / R2 객체 스토리지
-> Overview / 개요
-> Account details / 계정 세부 정보
-> Manage API tokens / API 토큰 관리
-> Create Account API token / Account API 토큰 생성
```

Important beginner trap:

- The R2 token screen is reached from the R2 account/overview area, not from one
  bucket's settings page.
- The permission label may appear as `Permissions` or `권한`; choose
  `Object Read & Write` / `개체 읽기 및 쓰기` for a reviewed first private objet
  bucket that needs upload/read access.
- The bucket-scope label may appear as `Bucket scope` or `버킷 지정`; choose the
  specific-bucket option, not all buckets.
- The TTL field may show a default like `계속`; if you leave it long-lived, mark
  it as something to review later.
- After creation, Cloudflare may show `Token value`, `Access Key ID`, and
  `Secret Access Key`. For S3-compatible objet access, configure the Access Key
  ID and Secret Access Key pair. Do not paste the separate Token value into chat
  or store it in WOM unless a future non-S3 API-token flow explicitly asks for
  it.

The Cloudflare-specific recommendations are based on official docs checked for
this release:

- [R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/)
- [R2 data location](https://developers.cloudflare.com/r2/reference/data-location/)
- [R2 storage classes](https://developers.cloudflare.com/r2/buckets/storage-classes/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [R2 authentication](https://developers.cloudflare.com/r2/api/tokens/)
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

## Notion Nested Recovery

For a beginner-facing Notion recovery guide, run:

```bash
archive beginner-setup-manual <archive-root> \
  --topic notion_nested_recovery \
  --dry-run \
  --format json
```

This topic exists because the live Notion structure fetch adapter is useful only
when the human can understand and approve the human-operated step.

The guide uses plain user language before internal terms:

```text
ancestor / parent / child -> folder, shelf, upper page, and item location
fetch / crawl              -> ask Notion again for the missing location links
fixture / node             -> review list and item
merge                      -> put the recovered locations back into the reviewed list
untraceable                -> items whose old location is still unknown
```

The beginner explanation is:

```text
We are checking where the last missing Notion items belonged.
Your local computer asks Notion for structure only: upper page and location links.
The AI does not receive your Notion token.
The AI does not read page bodies or media in this flow.
You approve one local run, then the AI can review the sanitized result list.
```

The guided flow is:

```text
review the missing-location scope
-> put the Notion token into a private local environment variable outside chat
-> preview a one-time credential approval receipt
-> write that one-time approval receipt after human review
-> preview the live structure fetch with that receipt
-> run the approved local structure fetch
-> hand the sanitized result fixture to notion-ancestor-merge-plan
```

The guide still keeps the v0.3.134 actor boundary:

- the human approves one local run,
- the local CLI reads the approved env ref during the approved run,
- the AI receives only sanitized result metadata,
- Notion page titles, page bodies, comments, media bytes, signed file URLs, raw
  provider responses, token values, exact env var names, account emails, and
  provider URLs are not returned.

Stop if the preview asks for a broader scope than the human reviewed, if the
approval is not `approve_once`, if any command would read titles/bodies/comments
or media, if a token is requested in chat or in a tracked repository file, or if
the output path is outside `workbench/`.

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

Notion nested recovery:

```text
notion-ancestor-crawl-plan
-> beginner-setup-manual --topic notion_nested_recovery
-> credential-access-approval --dry-run
-> credential-access-approval --approve
-> notion-ancestor-fetch-adapter-run --dry-run
-> notion-ancestor-fetch-adapter-run --approve
-> notion-ancestor-merge-plan --dry-run
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
- write approval receipts,
- run Notion location fetches,
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
