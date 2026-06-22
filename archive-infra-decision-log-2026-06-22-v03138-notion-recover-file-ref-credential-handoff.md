# Decision Log: v0.3.138 Notion Recover File-Ref Credential Handoff

Date: 2026-06-22

## Decision

Add a CLI-only `file:<path>` credential fallback to `archive notion-recover`
while keeping vault/keyring live reads closed until a dedicated local adapter
exists.

## Context

The existing one-command Notion recovery wrapper solved the page-id,
approval-receipt, fetch, and merge-preview command chain. The remaining
real-use blocker was non-developer credential entry. Users could possess a
valid local token file but still be forced into hidden terminal paste or
environment-variable setup.

## Consequences

- `archive notion-recover --credential-ref file:<local-token-file>` can now
  read a local token file in the CLI process and continue through the existing
  approval-gated fetch chain.
- The AI-visible result still does not include token values, local credential
  file paths, filenames, env var names, receipt paths, provider URLs, account
  ids, or emails.
- `keyring:` and `secret:` refs remain valid future contract language but do
  not perform live reads in this wrapper today.
- The recommended long-term human storage surface remains a vault or OS
  keyring; the file-ref fallback is a bridge for users who already have a token
  file.
