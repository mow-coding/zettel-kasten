# Object Storage Upload Evidence

Status: v0.3.85 approval-gated upload evidence registration checkpoint
Date: 2026-06-17

`object-storage-upload-evidence` records a reviewed external upload ledger after
a human or separate script has already handled object-storage upload outside
WOM-kit.

It is not the live upload adapter. It does not upload bytes to R2 or S3, check a
remote object, create a provider URL, or retrieve secrets. It only connects two
local facts:

```text
an existing object manifest record
+ a reviewed external upload evidence ledger
= a local receipt and safe object_storage location label
```

## Command

```bash
archive object-storage-upload-evidence <archive-root> \
  --ledger upload-evidence.jsonl \
  --provider-kind cloudflare-r2 \
  --store-ref object-store-20260616 \
  --dry-run \
  --format json
```

Approved mode:

```bash
archive object-storage-upload-evidence <archive-root> \
  --ledger upload-evidence.jsonl \
  --provider-kind cloudflare-r2 \
  --store-ref object-store-20260616 \
  --approve \
  --reviewed-by person:reviewer \
  --format json
```

Aliases:

```text
object-storage-external-upload-evidence
objet-storage-upload-evidence
```

MCP:

```text
No MCP write tool is exposed for this surface.
```

## Ledger Shape

The ledger must be UTF-8 JSONL. By default, each successful row uses:

```json
{"sha256":"<64 hex>","bytes":12345,"status":"uploaded"}
```

Accepted success statuses are:

```text
uploaded
verified
succeeded
already_present
ok
```

`sha256:<64 hex>` values are also accepted. `bytes` may be omitted, but when a
ledger byte size and manifest byte size are both present, they must match.

Field names can be changed with:

```text
--sha256-field
--size-field
--status-field
```

Field names are validated as safe short field names.

## Dry-Run Behavior

Dry-run mode:

- reads one or more JSONL evidence ledgers,
- hashes the ledger files themselves for receipt evidence,
- counts rows, successful rows, skipped rows, invalid rows, duplicates, and
  declared bytes,
- matches successful sha256 values against `objects/manifests/files.jsonl`,
- previews how many `object_storage` locations would be added,
- writes nothing.

It does not echo:

- ledger file paths,
- row values,
- object ids,
- source filenames,
- local absolute paths,
- provider URLs,
- bucket names,
- account ids,
- emails,
- tokens,
- secret values.

## Approved Behavior

Approved mode requires:

- `--approve`,
- `--reviewed-by <safe actor id>`,
- `--store-ref <safe label>`.

When approved, WOM-kit writes:

```text
receipts/providers/object-storage-upload-evidence/*.json
objects/manifests/files.jsonl
```

The manifest location uses safe fields such as:

```json
{
  "provider": "object_storage",
  "provider_kind": "cloudflare-r2",
  "store_ref": "object-store-20260616",
  "availability": "declared_uploaded",
  "content_addressed": true,
  "key_strategy": "sha256_content_addressed",
  "byte_verification_by_wom_kit": false,
  "provider_confirmation_by_wom_kit": false
}
```

The important words are `declared_uploaded`, `byte_verification_by_wom_kit:
false`, and `provider_confirmation_by_wom_kit: false`.

For beginners: this means WOM-kit is saying, "A reviewed external upload ledger
claims this object was uploaded." It is not saying, "WOM-kit itself uploaded it"
or "the remote object was checked live just now."

## Closed Actions

This command does not:

- read source object bytes,
- compute local source-object hashes,
- call provider APIs,
- create buckets,
- create provider URLs,
- check remote availability,
- upload objects,
- download objects,
- sync objects,
- open a password manager, keyring, browser password store, or secret manager,
- read environment variables,
- retrieve secret values,
- draft zets,
- mint zets.

## Why This Exists

Client feedback #11 showed a gap: an external upload script may produce an upload
ledger, but the archive still needs a safe local receipt and manifest location
evidence.

This checkpoint fills that gap without taking the live-adapter step yet. The
future live adapter still needs credential retrieval, local byte verification,
provider HEAD/idempotency checks, upload execution, remote confirmation, and
provider-confirmed manifest updates.
