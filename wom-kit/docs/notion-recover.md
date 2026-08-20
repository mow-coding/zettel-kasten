# Notion Recover

Status: v0.4.0 content-free recovery preview; live execution is fixed closed
Date: 2026-06-22

Current v0.4.0 boundary: only `archive notion-recover --dry-run` remains an
executable preview. The implicit non-dry-run route and every approval attempt
return `compound_exact_human_approval_binding_required` before credential,
private target, or provider reads; they call no provider and write no fixture
or receipt. Live behavior below is historical v0.3 evidence.

`archive notion-recover --dry-run` is the beginner-facing content-free preview
for the historical Notion ancestor recovery workflow.

It exists because a non-developer should not have to choose a page id, invent an
environment variable name, copy an approval receipt path, and run a chain of
low-level commands in the right order.

## Command

Run the no-write preview from an archive root:

```bash
archive notion-recover --dry-run
```

Do not supply a credential ref for execution in v0.4.0. Approval is blocked
before credential resolution, so no token file, environment value, or hidden
prompt is read.

For the connection-experience product contract:

```bash
archive notion-connection-plan --dry-run --format json
```

## What The v0.4.0 Preview Does

The command:

- auto-selects the reviewed Notion tree fixture that still has missing
  location links,
- shows how many location checks and affected items it found,
- explains that it reads location links only,
- reports that execution requires an unavailable operation-specific exact-human
  binding,
- reads no credential and makes no provider call,
- writes no approval receipt or sanitized ancestor fixture, and
- keeps historical failure categories and merge guidance available for audit.

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

## Historical v0.3 Safety Boundary

The bullets in this section describe the v0.3 execution evidence only. They do
not grant v0.4.0 authority. The current route stops before credential, private
target, or provider access and creates no fixture or receipt.

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

Power users may still use read-only `notion-ancestor-crawl-plan`, adapter
dry-run, and `notion-ancestor-merge-plan` surfaces for planning or historical
audit. No live provider automation is available through this route in v0.4.0.
The beginner path starts and stops with `archive notion-recover --dry-run`.
