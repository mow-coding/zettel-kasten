# Beginner Setup Manual

Status: v0.3.37 read-only beginner setup manual
Date: 2026-06-15

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
- `derived_text_tools`

## What It Explains

The manual explains:

- what a vault is before naming products,
- why WOM records safe refs instead of real secrets,
- how to name a first KeePassXC-style vault without putting private details in
  the filename,
- how to use safe non-secret group and entry labels,
- how to prepare derived-text tools such as LibreOffice and Tesseract,
- how to use a private local `--tool-hints` JSON file when a tool is installed
  but not on `PATH`,
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

## Closed Actions

`beginner-setup-manual` does not:

- ask for secrets in chat,
- read secret values,
- write secret values,
- open KeePassXC,
- open a keyring,
- open a browser password store,
- read environment variables,
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
