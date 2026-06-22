# Notion Recover

Status: v0.3.141 beginner-friendly one-command local Notion location recovery with actionable failure classification
Date: 2026-06-22

`archive notion-recover` is the beginner-facing wrapper for the existing
Notion ancestor structure fetch adapter.

It exists because a non-developer should not have to choose a page id, invent an
environment variable name, copy an approval receipt path, and run a chain of
low-level commands in the right order.

## Command

Run this from an archive root:

```bash
archive notion-recover
```

For a no-write preview:

```bash
archive notion-recover --dry-run
```

If the human already has the Notion integration token in a local text file, the
CLI-only fallback is:

```bash
archive notion-recover --credential-ref file:<local-token-file>
```

The file path is a local handoff only. WOM does not echo the path, file name, or
token value in command output or receipts.

For the connection-experience product contract:

```bash
archive notion-connection-plan --dry-run --format json
```

## What It Does

The command:

- auto-selects the reviewed Notion tree fixture that still has missing
  location links,
- shows how many location checks and affected items it found,
- explains that it reads location links only,
- asks for local human confirmation,
- accepts the Notion token through an existing local process value, a local
  `file:<path>` token-file fallback, or a hidden local terminal prompt when
  needed,
- writes the one-time approval receipt internally,
- runs the approved location fetch,
- classifies provider failures into safe human-action categories without raw
  provider error echo,
- writes a sanitized ancestor result fixture,
- previews the merge handoff so the human can ask AI to tidy and merge the
  recovered locations.

## What It Does Not Do

It does not:

- ask the user to paste a token into chat,
- require the user to choose a page id,
- require the user to create or name an environment variable when a local file
  ref or local process value is available,
- require the user to copy an approval receipt path,
- echo the local token-file path,
- echo the local token-file name,
- read page titles,
- read page bodies,
- read comments,
- download media bytes,
- refresh signed file URLs,
- return raw provider responses,
- return raw provider error bodies,
- mint zets,
- write zettel edges.

## Failure Categories

If the provider fetch fails, `notion-recover` now reports safe categories rather
than only saying that checks failed:

```text
token_invalid_or_expired
notion_connection_not_shared_or_permission_denied
notion_object_missing_or_not_shared
provider_rate_limited
network_or_timeout
provider_temporarily_unavailable
provider_request_failed
```

The category most relevant to internal Notion integrations is usually
`notion_connection_not_shared_or_permission_denied`: the token may be valid, but
the target page or database has not been shared with the connection. WOM still
does not echo the raw provider error body, page title, page body, provider URL,
account id, email, or token.

## Safety Boundary

The security boundary is unchanged from the lower-level adapter:

- the human approves locally,
- the token stays in the local terminal/process; when `file:<path>` is used,
  the file is read only by the local CLI wrapper and then passed through the
  same approval-gated adapter chain,
- the AI receives no secret value,
- provider access happens only after the local approval gate,
- the result fixture contains sanitized structure metadata for location
  recovery only.

Vault/keyring refs such as `keyring:<label>` and `secret:<label>` are still the
right long-term direction for one-click credential handoff, but live vault or OS
keyring reads are not implemented in this wrapper yet. If such a ref is passed
today, the wrapper fails closed instead of pretending the vault was opened.

The product direction after the beta-tester recovery breakdown is stronger than
vault/keyring alone: the default future path should be a managed "Connect
Notion" browser flow. See `notion-connection-plan` for the one-click connection
contract. The current token paths remain power-user fallbacks.

Power-user commands such as `notion-ancestor-crawl-plan`,
`credential-access-approval`, `notion-ancestor-fetch-adapter-run`, and
`notion-ancestor-merge-plan` remain available for automation and debugging.
The beginner path should start with `archive notion-recover`.
