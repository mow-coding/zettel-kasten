# Notion Connection Plan

Status: v0.3.142 one-click Notion connection contract plus OAuth preflight checkpoint
Date: 2026-06-22

`archive notion-connection-plan` is a read-only product-contract command for
the Notion connection experience.

It exists because the live recovery capability can be technically correct while
the human experience still fails. A beginner should not have to create an
internal integration token, remember where the token file is, assemble terminal
commands, manually share pages with the connection, and then debug a wall of
failed provider checks.

## Command

```powershell
archive notion-connection-plan <archive-root> --dry-run --format json
```

Aliases:

```text
notion-connect-plan
notion-one-click-connection-plan
```

## Product Diagnosis

The current env/file token path remains useful for power users and local
testing, but it is not the right default experience for the target user.

The target product experience is:

```text
Connect Notion -> human approves once in browser -> WOM runs recovery locally -> AI tidies without seeing secrets
```

The AI remains secret-blind. The change is that the human approval should be a
familiar browser click, not a token hunt plus terminal recovery ritual.

## Official Notion Connection Models

Notion has several connection models:

- Internal connections use a static installation token. They are developer or
  admin friendly, but pages and databases must be shared with the connection
  before the API can read them.
- Personal access tokens are user-scoped static tokens for scripts, CLI
  workflows, Workers, and trusted tools. They use the creating user's workspace
  membership and page permissions.
- Public connections use OAuth 2.0. The user visits an authorization URL,
  reviews the connection capabilities, selects pages during the authorization
  flow, approves, and Notion redirects back with a temporary authorization code.

For WOM, the intended product direction is a managed public connection/OAuth
path. Personal access tokens may be a trusted local stopgap. Internal
connection tokens should remain a power-user fallback, not the beginner
default.

## What v0.3.141 Implemented

v0.3.141 implements:

- read-only `archive notion-connection-plan`,
- safe provider-failure classification for `notion-recover`,
- plain next-action categories without raw provider error echo.

The safe failure categories are:

```text
token_invalid_or_expired
notion_connection_not_shared_or_permission_denied
notion_object_missing_or_not_shared
provider_rate_limited
network_or_timeout
provider_temporarily_unavailable
provider_request_failed
```

For the beta-tester case, the important category is usually:

```text
notion_connection_not_shared_or_permission_denied
```

That means the human likely needs to share the top-level recovery page or
database with the connection, or WOM needs to move to the planned OAuth/PAT
connection path.

## What v0.3.142 Adds

v0.3.142 adds `archive notion-oauth-connection-preflight`, a read-only bridge
between this product plan and the future live OAuth runtime.

The new preflight checks the safe shape of:

- client id and client secret refs,
- a local loopback callback URI,
- optional one-time state storage,
- a keyring/secret/wallet token store.

It still does not open a browser, start a callback server, generate an
authorization URL, exchange a code, store tokens, or call Notion. It exists so
the eventual "Connect Notion" command has a locked actor boundary before any
secret or authorization code can move.

## What Is Still Not Implemented

This command does not implement the one-click connection yet. It deliberately
does not claim otherwise.

Still future:

- browser OAuth authorization,
- managed local callback server,
- token exchange,
- keyring/vault storage of the resulting credential,
- Notion page picker handoff,
- automatic connection repair,
- UI button surface.

The current next command for local readiness is:

```powershell
archive notion-oauth-connection-preflight <archive-root> --dry-run --format json
```

## Safety Boundary

`notion-connection-plan` writes nothing, calls no provider, opens no browser,
starts no OAuth, reads no credential value, and echoes no credential refs,
tokens, provider URLs, local paths, raw provider responses, page titles, page
bodies, account ids, or emails.

`notion-recover` still keeps raw Notion errors redacted. It now preserves the
safe classification layer so a human can tell whether the next action is token
repair, page-share/permission repair, waiting for rate limits, checking the
network, or retrying after provider downtime.
