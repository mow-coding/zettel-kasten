# Object Storage Recommendations

Status: v0.3.64 read-only manifest-aware object storage recommendation matching with setup bridge
Date: 2026-06-16

`object-storage-recommendation` maps a human storage scenario to the existing
WOM-kit `object-storage --dry-run` planner.

It is not live pricing, provider signup, bucket creation, upload approval, or
remote availability proof.

## Command

```bash
archive object-storage-recommendation <archive-root> \
  --scenario personal_low_ops \
  --dry-run \
  --format json
```

For a manifest-based suggestion:

```bash
archive object-storage-recommendation <archive-root> \
  --scenario auto_from_manifest \
  --dry-run \
  --format json
```

Aliases:

```text
object-storage-match
objet-storage-recommendation
```

Optional bridge fields:

```text
--profile-id <safe-profile-id>
--profile-slug <safe-ascii-slug>
--storage-account-ref storage:account:<label>
```

When those are supplied, the output includes:

- `recommended_setup_values.bucket_name`,
- the bucket naming rule,
- a ready next-command shape for `archive object-storage --dry-run`,
- the `beginner-setup-manual --topic object_storage_setup_manual` command,
- Cloudflare R2 screen-field guidance when R2 is the primary recommendation.

This is intentionally redundant. The bucket name must be visible as a value,
not hidden only inside a command string, so a human or AI helper does not invent
one.

## Scenarios

Supported scenarios:

- `personal_low_ops`
- `auto_from_manifest`
- `s3_compatible`
- `backup_cost_sensitive`
- `aws_native`
- `google_cloud_native`
- `generic_provider`

The matcher prefers existing WOM-kit setup providers:

- `cloudflare-r2`
- `backblaze-b2`
- `aws-s3`
- `google-cloud-storage`
- `generic-s3`

## Manifest-Aware Mode

`--scenario auto_from_manifest` reads aggregate metadata from:

```text
objects/manifests/files.jsonl
```

It reports:

- total manifest size,
- sized record count,
- dominant content class,
- content-class byte percentages,
- inferred scenario and confidence,
- rough storage/egress estimates for the candidate providers.

It does not echo object filenames, local paths, provider URLs, exact credential
refs, or object bytes. It uses `logical_key` only internally to infer a file
kind when MIME is missing.

Rough estimates are not live pricing. They are a comparison aid based on a
static 2026-06-15 public-pricing snapshot. Before spending money, the human must
check the official calculator/docs:

- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Backblaze B2 pricing](https://www.backblaze.com/cloud-storage/pricing)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Google Cloud Storage pricing examples](https://cloud.google.com/storage/pricing-examples)

## Provider Notes

The matcher uses stable capability labels, not live market data.

- Cloudflare R2 has an S3-compatible API path:
  [Cloudflare R2 S3 API](https://developers.cloudflare.com/r2/api/s3/api/).
- Backblaze B2 documents an S3-compatible API:
  [Backblaze B2 S3-Compatible API](https://www.backblaze.com/docs/cloud-storage-s3-compatible-api).
- Amazon S3 is the native AWS object storage path:
  [Amazon S3 documentation](https://docs.aws.amazon.com/s3/).
- Google Cloud Storage is the native Google Cloud object storage path:
  [Cloud Storage documentation](https://docs.cloud.google.com/storage/docs).

Before spending money or uploading source objets, the human must separately
verify current pricing, retention, region, data residency, lifecycle policy,
provider account ownership, and recovery/restore needs.

## Cloudflare R2 Setup Bridge

For the default `personal_low_ops` recommendation, WOM-kit usually ranks
`cloudflare-r2` first.

The recommendation output now surfaces:

```text
recommended_setup_values.bucket_name
recommended_setup_values.bucket_naming_rule
next_exact_commands.object_storage_setup_manual
next_exact_commands.object_storage_dry_run
setup_bridge.provider_setup_guidance
```

For R2, the screen guidance covers:

- bucket name,
- Location,
- Jurisdiction,
- Default storage class,
- Public access,
- API token type,
- API token permission,
- bucket scope,
- TTL / expiration,
- client IP filtering,
- secret handling after creation.

The Cloudflare-specific guidance is based on official docs checked for this
release:

- [R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/)
- [R2 data location](https://developers.cloudflare.com/r2/reference/data-location/)
- [R2 storage classes](https://developers.cloudflare.com/r2/buckets/storage-classes/)
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Cloudflare token restrictions](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)

The guidance still does not check live pricing, bucket availability, account
policy, or the current dashboard UI. It is a safe setup bridge, not provider
automation.

## Current Closed Actions

`object-storage-recommendation` does not:

- call provider APIs,
- look up live prices,
- call pricing APIs,
- check bucket availability,
- create buckets,
- create API tokens,
- upload files,
- download files,
- read object bytes,
- echo object filenames,
- create presigned URLs,
- start OAuth,
- read secret values,
- write files,
- draft zets,
- mint zets.

It is a recommendation matcher, not a storage connector.

## Safe Workflow

```text
object-storage-recommendation
-> object-storage --dry-run
-> provider-status
-> human provider signup / bucket review outside WOM
-> approved local metadata write only when reviewed
```
