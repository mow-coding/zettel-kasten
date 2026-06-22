# Notion OAuth Connection Preflight

Status: v0.3.142 secret-blind Notion OAuth connection preflight checkpoint
Date: 2026-06-22

`archive notion-oauth-connection-preflight` is a read-only safety gate for the
future one-click Notion connection flow.

It does not open a browser or complete OAuth. It checks whether the local
runtime has the right non-secret shape before a later live command is allowed
to do that work.

## Command

```powershell
archive notion-oauth-connection-preflight <archive-root> `
  --client-id-ref env:WOM_NOTION_OAUTH_CLIENT_ID `
  --client-secret-ref keyring:WOM_NOTION_OAUTH_CLIENT_SECRET `
  --redirect-uri <local-loopback-callback-uri> `
  --state-ref keyring:WOM_NOTION_OAUTH_STATE `
  --token-store-ref keyring:WOM_NOTION_OAUTH_TOKEN_STORE `
  --dry-run `
  --format json
```

Aliases:

```text
notion-oauth-preflight
notion-connect-oauth-preflight
```

## What It Checks

The command validates the local contract for the intended product flow:

```text
Connect Notion -> human approves once in browser -> trusted local runtime stores tokens -> AI receives only sanitized results
```

It checks:

- client id and client secret are named by safe local refs, not pasted values,
- the callback URI is local loopback HTTP only,
- the callback URI uses an explicit non-privileged port,
- the callback path is short, ASCII, absolute, and traversal-free,
- OAuth state is required for the future live flow,
- the future access/refresh token store is keyring, secret, or wallet backed,
  not an env var or repo file.

## Actor Boundary

The AI runtime may plan, review, and explain. It must not see:

- client secret values,
- authorization codes,
- access tokens,
- refresh tokens,
- exact credential refs,
- the exact redirect URI,
- provider URLs,
- raw provider responses,
- account ids or emails.

The future trusted local runtime is the only actor allowed to open the browser,
receive the callback, validate state, exchange the temporary code, store tokens,
and run the live adapter.

## What v0.3.142 Implements

v0.3.142 implements:

- read-only `archive notion-oauth-connection-preflight`,
- aliases `archive notion-oauth-preflight` and
  `archive notion-connect-oauth-preflight`,
- safe credential-ref shape validation,
- local loopback redirect validation,
- explicit token-store rejection for plain env storage,
- a machine-readable security contract for the future live runtime.

## What Is Still Not Implemented

Still future:

- opening the Notion authorization page,
- running a callback server,
- generating the authorization URL,
- receiving an authorization code,
- exchanging the code for access/refresh tokens,
- storing tokens in an actual OS keyring or vault,
- running `notion-recover` from stored OAuth tokens,
- UI button surface.

## Failure Categories For The Future Live Flow

The preflight names the categories the eventual live flow should classify:

```text
oauth_access_denied_by_human
oauth_state_mismatch
oauth_callback_timeout
oauth_redirect_uri_mismatch
oauth_token_exchange_failed
oauth_token_storage_unavailable
notion_page_selection_missing
```

## Safety Boundary

`notion-oauth-connection-preflight` writes nothing, calls no provider, opens no
browser, starts no callback server, reads no credential value, exchanges no
token, stores no token, and echoes no credential refs, redirect URI, provider
URLs, local paths, raw provider responses, page titles, page bodies, account
ids, or emails.

## Official Notion Flow Reference

The contract follows Notion's public OAuth model: public integrations use
OAuth 2.0, the human authorizes access in the browser, Notion redirects back
with a temporary code, and the trusted app exchanges that code for tokens.

References:

- https://developers.notion.com/guides/get-started/authorization
- https://developers.notion.com/reference/create-a-token
