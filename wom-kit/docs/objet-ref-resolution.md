# Objet Ref Resolution

Status: v0.3.17 read-only baseline
Date: 2026-06-14

This document describes the first reading-side command for source/original
objets:

```text
archive resolve-objet-ref <archive-root> --object-id sha256:<hex> --dry-run
```

## Purpose

WOM zets and manifests can cite source/original objets by content identity:

```text
sha256:<64 lowercase hex characters>
```

That identity is good for provenance, but a human reader also needs to know:

```text
Where can I inspect this original objet?
```

`resolve-objet-ref` answers that question from local WOM metadata only.

## What It Reads

The command reads:

```text
objects/manifests/files.jsonl
```

It looks for manifest records whose `object_id` matches the requested sha256
object id.

## What It Returns

The resolver separates candidates into two groups.

### Local candidates

Local candidates are archive-relative paths such as:

```text
objects/sha256/ab/abcdef...
```

The command reports whether the file exists at that archive-relative path.

It does not print local absolute paths by default, and it does not hash the file
again during resolution.

### External candidates

External candidates are manifest locations such as:

```json
{
  "provider": "external_prehashed",
  "store_kind": "notion_source_export",
  "store_ref": "notion-export-20260614",
  "availability": "declared_external"
}
```

The resolver reports safe labels only. `store_ref` remains a reviewed external
store label, not a raw path, URL, token, secret, or proof that bytes are
currently downloadable.

## Boundaries

`resolve-objet-ref` is read-only.

It does not:

- write files,
- open local files,
- read object bytes,
- re-hash object bytes,
- call provider APIs,
- create presigned URLs,
- download objects,
- upload objects,
- prove remote availability,
- decide whether local originals can be deleted.

Those are future workflows with separate approval and provider-credential
policies.

## Example

```bash
archive resolve-objet-ref <archive-root> \
  --object-id sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --dry-run \
  --format json
```

Possible local result shape:

```json
{
  "resolution_state": "local_available",
  "local_openable": true,
  "local_candidates": [
    {
      "archive_relative_path": "objects/sha256/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "exists": true,
      "sha256_verified_now": false
    }
  ]
}
```

Possible external-only result shape:

```json
{
  "resolution_state": "external_declared",
  "local_openable": false,
  "external_candidates": [
    {
      "provider": "external_prehashed",
      "store_kind": "notion_source_export",
      "store_ref": "notion-export-20260614",
      "presigned_url_created": false
    }
  ]
}
```

## Future Work

Future versions may add:

- provider-specific open/download adapters,
- presigned URL creation with explicit credential policy,
- remote byte availability checks,
- UI/MCP hyperlink rendering,
- deletion-safety workflows that require remote availability evidence.

None of those are implemented in v0.3.17.
