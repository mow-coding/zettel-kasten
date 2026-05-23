# WOM Profile Registry

Status: v0.2.17 dry-run baseline

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
```

MCP:

```text
wom_profile_list
wom_profile_resolve
```

Both commands are read-only. They do not scan the whole disk, write files, register profiles, register tokens, or call provider APIs.

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
    token:
      state: present
      token_ref: local-keyring:wom/profile/example-personal
```

The registry may contain `token.state` and `token_ref`.

It must not contain raw token values.

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

When it returns `token_missing`, the AI should ask the user whether to register the profile token or use a delegate flow.

When it returns `ambiguous`, the AI should ask the user to choose a profile.

When it returns `not_found`, the AI should suggest registering the profile or using a delegate flow.
