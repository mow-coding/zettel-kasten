# Keyring Profile Spec v0.1

A keyring profile selects which archives an AI runtime can access.

Secrets should live in an external password manager or secure credential store. Profile files may describe required environment variables, but should not contain long-lived secrets.

## Profile Example

```yaml
profile_id: keyring:life
name: Life archive keyring
principal_id: person:example
mounted_archives:
  - archive_id: archive:personal:example
    path: ./archives/personal
    access: read_write
  - archive_id: archive:family:example
    path: ./archives/family
    access: read_only
env:
  required:
    - ARCHIVE_ROOT
    - RCLONE_CONFIG
secrets_policy:
  store: keepassxc
  write_env_files: temporary_only
  delete_env_files_after_session: true
```

## Common Profiles

```text
life
company
family
project
client
handover
```

## Core Rule

The AI may only know what the active keyring mounts.

## Local Profile Resolution Baseline

This first implementation does not connect to an OS keyring yet.

Use these paths for local-only profile material inside an archive:

```text
profiles/local/*.yml
profiles/*.local.yml
keyrings/local/*.yml
keyrings/*.local.yml
.archive-local/
```

These paths are ignored by default. They may describe local mounts and required environment variable names, but they must not contain long-lived secrets.

Portable examples may use:

```text
profiles/*.example.yml
```

Resolution order for a future runtime should be:

1. Explicit CLI or MCP profile path.
2. `AI_ARCHIVE_PROFILE` environment variable.
3. Archive-local ignored profile under `profiles/local/`.
4. No profile, meaning only the explicitly provided archive root is mounted.

Profile files may contain:

```yaml
env:
  required:
    - ARCHIVE_ROOT
  optional:
    - RCLONE_CONFIG
```

Profile files must not contain:

```yaml
api_key: "..."
token: "..."
password: "..."
secret: "..."
```

The archive doctor should warn about missing ignore rules and fail on obvious secret-like files or values.
