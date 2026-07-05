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

Layout ruling (D2, 2026-07-03): the sibling local objet store is for bulk
external originals under never-touch protection (represented through
`prehashed-objet-ledger` plus `object-storage-upload-evidence` evidence).
Capture intake stages INSIDE the archive root under `staging/incoming/` and
lands originals in the content-addressed `objects/sha256/` store. A raw
in-root `objets/` folder is discouraged; the migration guide lives in
[artifact-hygiene.md](artifact-hygiene.md) section 5.

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

## Adopting Objects Already In Your Bucket (`object-storage-adopt-existing`)

When objects already sit in your bucket under your own key layout, adopt them so a
later upload does not re-PUT them. The verified adopt HEADs each computed key and
records a matcher-honored `wom_uploaded` location ONLY on presence + size-match; a
404 or size-mismatch re-uploads, never a silent skip.

For objects that carry the ORIGINAL per-object filename extension (for example
`archives/<archive_id>/objets/<sha>.png`), the content-addressed template cannot
always rebuild the exact key: prehashed-ledger objects have a manifest `logical_key`
with no filename extension, so `--key-append-extension` recovers nothing and the
template key 404s. In that case, hand WOM the exact keys with `--key-map`.

### `--key-map` — exact existing keys per object

`--key-map <file>` takes a JSONL file, UTF-8, one object per line, exactly:

```json
{"sha256":"<64 lowercase hex>","remote_key":"<exact bucket-relative key>"}
```

- `remote_key` is the FULL bucket-relative key the object already lives under — not a
  URL, not the bucket name, no leading slash. The object's sha256 must appear in the
  key as a full `/`-delimited path segment or as the filename stem (mechanically
  generated ledgers satisfy this by construction).
- For a mapped object the map value becomes the resolved key verbatim;
  `--key-strategy`, `--key-prefix`, and `--key-append-extension` are IGNORED for that
  object. Objects with no map entry are reported and NOT adopted.
- Size is always taken from the manifest, never from the map. A mapped key that 404s
  or size-mismatches re-uploads. A malformed or ambiguous map (unreadable, a missing
  field, a non-hex sha, an unsafe key, or a duplicate sha with conflicting keys) is
  whole-run fatal — WOM adopts nothing.

Presence + size proves same LENGTH, not same BYTES. For any map you did not
mechanically generate from a trusted per-object upload record, add
`--content-hash-verify` (it downloads and re-hashes each object; a mismatch does not
adopt). The mime-derived extension path (`extension_from_mime_hint` over the stored
manifest `mime`) is a LOSSY fallback only — it cannot tell `.jpg` from `.jpeg` and
yields nothing for `application/octet-stream` — and WOM never uses it to build adopt
keys automatically.

The full generation flow and format details live in
[object-storage-adopt-existing-key-map-runbook.md](object-storage-adopt-existing-key-map-runbook.md).
