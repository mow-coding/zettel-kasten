# Presigned URL Plan

Status: v0.3.40 read-only planning baseline
Date: 2026-06-15

`presigned-url-plan` is the safe planning step before any future object-storage
presigned URL adapter exists.

It answers a narrow question:

```text
For this object_id, is there a reviewed external store label that a future
adapter could use after credential policy and human approval?
```

It does not create a URL.

## Command

```bash
archive presigned-url-plan <archive-root> \
  --object-id sha256:<hex> \
  --store-ref object-store-20260615 \
  --ttl-seconds 900 \
  --dry-run \
  --format json
```

Aliases:

```text
object-presigned-url-plan
objet-presigned-url-plan
```

MCP:

```text
presigned_url_plan
```

## Inputs

- `--object-id` must be `sha256:<64 lowercase hex>` or a bare 64-character
  lowercase sha256 digest.
- `--store-ref` is optional when the object has exactly one external manifest
  candidate. It is required when multiple external candidates exist.
- `--store-ref` must be a safe label/ref. It must not be a provider URL, local
  path, token, email address, secret, or clickable storage locator.
- `--operation` is `download` or `head`.
- `--ttl-seconds` must be between `60` and `86400`.

## What It Reads

The planner reuses `resolve-objet-ref`.

It reads local archive metadata only:

```text
objects/manifests/files.jsonl
provider-bindings.yml
archive.yml
```

It uses `provider-bindings.yml` only to return a boolean saying whether an
object-storage provider binding is present. It does not echo bucket names,
prefixes, provider URLs, credential refs, or provider account values.

## Output Shape

The JSON output includes:

- `presigned_url_request`
- `resolution_summary`
- `current_capability`
- `future_adapter_requirements`
- `privacy_guards`
- `closed_actions`
- `next_safe_actions`
- `blockers`
- `warnings`

`current_capability.presigned_url_creation_implemented` is always `false` in
v0.3.40.

## Closed Actions

`presigned-url-plan` does not:

- create presigned URLs,
- call provider APIs,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- read object file bytes,
- hash object file bytes,
- upload objects,
- download objects,
- prove remote availability,
- echo provider URLs,
- echo local absolute paths,
- echo exact credential refs,
- write files or receipts,
- draft zets,
- mint zets.

## Safe Workflow

```text
resolve-objet-ref
-> presigned-url-plan
-> provider-status
-> credential-policy-check
-> human approval receipt
-> future provider adapter, not implemented in v0.3.40
```

The future adapter must keep generated URLs private and receipt-scoped. Public
archive records should store non-secret audit facts, not live URLs.

## Common Blockers

- `object_id_not_found_in_manifest`
- `no_external_store_candidate_for_object_id`
- `store_ref_required_when_multiple_external_candidates`
- `store_ref_not_found_for_object_id`
- unsafe `store_ref`
- invalid TTL

These blockers are intentional. A presigned URL is a temporary access grant, so
WOM-kit treats it as a credential-adjacent operation rather than a normal public
link.
