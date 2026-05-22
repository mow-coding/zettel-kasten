# Provider Bindings Spec v0.1

`provider-bindings.yml` describes outside services attached to an archive.

The archive may know that GitHub stores zettels/specs/code, Cloudflare R2 or Backblaze B2 stores large original objects, Neon stores optional shared coordination metadata, and KeePassXC stores secrets. The archive must not pretend it owns those provider accounts directly.

## Rule

Archive ownership and provider account ownership are related but separate.

```text
archive owner/operator = archive-internal control model
provider owner/operator = external service IAM, billing, account, bucket, repo, or database role
```

Ownership transfer updates `archive-identity.yml` locally and writes a receipt. Provider changes are listed as a manual `provider_change_plan` until a future explicit integration exists.

## File

```yaml
version: provider-bindings/v0.1
archive_id: archive:personal:example
bindings:
  - binding_id: github:archive-repo
    provider: github
    enabled: true
    purpose: zettels_specs_code_and_view_definitions
    resource:
      org: example-org
      repo: personal-archive
    auth:
      token_env: GITHUB_TOKEN
    owner_mapping:
      admin_team: archive-admins
      operator_team: archive-operators
```

## Secret Boundary

Provider bindings may store:

```text
env var names
role names
bucket names
repo names
database names
KeePassXC entry references
manual custody notes
```

Provider bindings must not store:

```text
API tokens
secret access keys
database connection strings
passwords
password-manager exports
```

`archive doctor` validates the schema and fails on obvious secret-like fields or values.

## Current Providers

```text
github
cloudflare_r2
backblaze_b2
neon
external_ssd
rclone
restic
keepassxc
```

SQLite remains the local generated index/cache for each archive. Neon/Postgres is optional shared coordination infrastructure, not the source of truth for personal archive contents.
