# WOM Profile Registry

Status: v0.2.25 wallet-ready identity baseline

## Purpose

The WOM profile registry is a local, read-only-before-write address book for AI runtimes.

It answers a simple safety question:

```text
When the user names a target profile, which archive is the AI supposed to operate on?
```

This matters because a user may be working under a default personal archive but ask for a draft to go to a team archive. The AI must resolve the requested profile first instead of assuming the current/default archive.

## Commands

CLI:

```bash
archive profile-list --registry <path> --format json
archive profile-resolve --registry <path> --target <query> --format json
archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json
```

MCP:

```text
wom_profile_list
wom_profile_resolve
wom_profile_wallet_check
```

The profile list and resolve commands are read-only. They do not scan the whole disk, write files, register profiles, register tokens, or call provider APIs.

`profile-wallet` and `wom_profile_wallet_check` are also read-only. They preview wallet-ready identity metadata only; they do not generate private keys, sign data, register wallets, store seed phrases, store wallet secrets, call blockchain APIs, or call provider APIs.

## Registry Shape

```yaml
version: wom-profile-registry/v0.1
default_profile: profile:personal:me
profiles:
  - profile_id: profile:personal:me
    label: Personal archive
    aliases:
      - me
      - personal
    node_id: person:me
    archive_id: archive:personal:me
    archive_type: personal
    archive_root: <local-private-path>/personal-archive
    operator_id: person:me
    authority_mode: owner_operator
    node:
      node_id: node:person:example
      node_kind: person
      display_label: Example Person
    wallet:
      wallet_id: wallet:local:example
      fingerprint: wom-fp-example
      custody: local_device
      signing_status: placeholder
      signer_ref: signer:local-placeholder
    token:
      state: present
      token_ref: local-keyring:wom/profile/example-personal
```

The registry may contain `token.state` and `token_ref`.

It must not contain raw token values.

The optional `node` and `wallet` sections are public-safe metadata only.

Allowed `node.node_kind` values are:

```text
person
organization
team
family
project
agent
```

Allowed `wallet.custody` values are:

```text
local_device
os_keychain_future
hardware_wallet_future
multisig_future
external_wallet_future
```

Allowed `wallet.signing_status` values are:

```text
not_configured
placeholder
future
```

These fields must not contain private keys, seed phrases, raw wallet addresses, payment credentials, raw provider URLs, local absolute paths, tokens, passwords, cookies, or OAuth refresh tokens.

`v0.2.17` treats unsupported token fields, including names such as `value`, `token`, `secret`, `password`, `api_key`, `access_token`, `refresh_token`, and `private_key`, as blockers.

The registry `version` must be exactly `wom-profile-registry/v0.1` for this release.

## Resolution Rules

- Exact `profile_id` match wins.
- Exact `label` match wins.
- Exact alias match wins.
- Matching normalizes Unicode text to NFC and removes zero-width boundary markers.
- Matching is case-insensitive after normalization.
- Multiple same-strength matches return `resolution_state: ambiguous`.
- No match returns `resolution_state: not_found`.
- Missing token returns `resolution_state: token_missing` and `direct_write_available: false`.
- Missing `archive_root` also disables direct write availability.

## Output Privacy

Local absolute paths are redacted by default:

```json
{
  "archive_root": "<local-path-redacted>"
}
```

CLI users may explicitly pass `--no-redact-local-paths` for trusted local debugging.

MCP clients cannot force local path disclosure unless the MCP server was started with:

```text
AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1
```

## Next Step

When `profile-resolve` returns `resolution_state: resolved`, the AI should run:

```text
archive runtime-context <archive-root> --expected-archive-id <id> --expected-type <type> --format json
```

If runtime context passes and the user asked to put new material into that archive, the AI should then run create-draft dry-run before writing:

```text
archive create-draft <archive-root> --dry-run --expected-archive-id <id> --expected-type <type> --profile-id <profile-id> --format json
```

Draft approval creates only an `inbox/` draft. Minting remains a separate approval step.

When it returns `token_missing`, the AI should ask the user whether to register the profile token or use a delegate flow.

When it returns `ambiguous`, the AI should ask the user to choose a profile.

When it returns `not_found`, the AI should suggest registering the profile or using a delegate flow.

When `profile-wallet` returns `ok: true`, the AI may explain the profile's wallet readiness to the human operator, but it must not treat that preview as signing authority. Real key custody and signing are future work.
