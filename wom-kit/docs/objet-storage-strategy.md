# Objet Storage Strategy

Status: active baseline
Date: 2026-05-25

This document explains where WOM source/original objets should live when they are too large, private, or binary-heavy for Git.

## Product Language

WOM uses `objet` for source/original files stored outside Git.

Cloud providers and APIs often call the technical layer `object storage`. WOM-kit keeps that technical term in command names and provider bindings where it describes S3-compatible storage, buckets, regions, endpoint references, and credentials.

For first personal onboarding, say `local objet store (raw source/original
files)` on first mention. The recommended local default is:

```text
C:\Users\<user>\zettel-kasten-<profile_slug>-objets
```

Remote object storage remains a deferred manual external step unless the user
explicitly chooses to plan R2, B2, S3, or another provider.

## Default Layout

For a resolved WOM profile, the v0.2.21 planner proposes:

```text
bucket/container: zettel-kasten-<normalized-profile-slug>-objets
prefix:           archives/<archive_id>/objets/
visibility:       private
```

The bucket/container name uses conservative provider-safe rules:

- lowercase ASCII letters, numbers, and hyphens,
- start and end with an alphanumeric character,
- no dots, underscores, slashes, spaces, URL fragments, or secret-like values,
- maximum 63 characters.

WOM-kit does not check global bucket availability because that would require provider API access.

## CLI Planner

Dry-run first:

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:username \
  --profile-slug username \
  --storage-account-ref storage:account:username \
  --format json
```

Dry-run returns provider binding metadata, local profile preview, provider setup receipt preview, objet storage policy preview, manual steps, blockers, warnings, and would-change paths. It writes nothing.

Approved local metadata write:

```bash
archive object-storage <archive-root> --approve \
  --reviewed-by person:me \
  --provider cloudflare-r2 \
  --profile-id profile:personal:username \
  --profile-slug username \
  --storage-account-ref storage:account:username \
  --format json
```

Approved mode writes only:

- `provider-bindings.yml`,
- `receipts/providers/*.object-storage-setup.json`,
- optional ignored `profiles/local/object-storage-accounts.local.yml` when `--write-local-profile` is supplied.

Approved writes are rollback-safe: WOM-kit should not leave `provider-bindings.yml` modified without its matching setup receipt.

## Non-Goals

This planner does not:

- create buckets or containers,
- run OAuth,
- call provider APIs,
- upload files,
- sync files,
- copy source files,
- calculate object hashes,
- import source content,
- configure external tools.

Those operations need separate explicit designs because they touch private source material.

## Secret Boundary

Versioned provider bindings may store safe references:

```text
bucket/container names
provider kind
region labels
endpoint refs
env var names
account refs
manual custody notes
```

They must not store:

```text
raw access keys
raw secret keys
OAuth refresh tokens
cookies
passwords
private provider URLs with credentials
local absolute paths
private source filenames
```

Real credentials belong in environment variables, OS/keyring tools, or ignored local profile files.
