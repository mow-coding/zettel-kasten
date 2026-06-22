# Meeting Minutes: v0.3.138 Notion Recover File-Ref Credential Handoff

Date: 2026-06-22

## Context

Client feedback confirmed that `archive notion-recover` reached the desired
one-command recovery shape, but real users still got stuck at the credential
entry step. The blocked path was not the Notion recovery algorithm; it was the
human step of supplying a token through terminal paste or environment-variable
setup.

## User Intent

The user wanted WOM to reduce that friction while preserving the actor
boundary:

- AI must not receive live provider credentials,
- the human must still approve the local action,
- token entry should not require command-line regex or env-var setup,
- users who already have a local token file should be able to point to it,
- vault/keyring one-click handoff should remain the target direction,
- the public repository must not expose secret values, local paths, provider
  account data, or sensitive operational context.

## Implementation

- Added CLI-only support for
  `archive notion-recover --credential-ref file:<local-token-file>`.
- The wrapper reads a small UTF-8 local token file, extracts a Notion token
  candidate, injects it only into the existing transient local process path, and
  restores any previous transient process value afterward.
- Existing approval-gated Notion ancestor fetch execution remains the live
  provider-call path.
- `keyring:` and `secret:` refs now fail closed in the wrapper instead of
  implying live vault/keyring reads exist.
- Updated `notion-recover` dry-run output, docs, beginner setup manual,
  capability matrix, README summaries, changelog, and release notes.
- Added tests proving file-ref success against the fake Notion adapter without
  echoing token file path, file name, token value, transient env ref, provider
  URL, or receipt paths.

## Safety Notes

This release does not implement a real vault, OS keyring, or password-manager
read adapter. That is still a future credential-broker boundary.

The file-ref fallback is a local bridge for users who already have a token text
file. It should not be treated as the long-term secret storage recommendation.

## Verification Plan

- Targeted CLI tests for `notion-recover`.
- Targeted documentation tests for `notion-recover`, beginner setup manual,
  version truth-source coverage, and Tiro docs.
- Full WOM-kit tests before release.
- Public privacy and release-readiness scans before tagging.
