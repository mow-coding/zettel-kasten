# Runbook — `object-storage-adopt-existing --key-map`

Status: active
Date: 2026-07-05
Applies to: `wom-kit` v0.3.171+ (tiny-first gate decoupled from the upload 5 GiB proof since v0.3.174; large plan resolution indexed since v0.3.180)

Use `--key-map` when objects already sit in your bucket under your own key layout and
the content-addressed template cannot rebuild the exact key — most importantly when
each object carries its ORIGINAL filename extension that WOM's manifest does not
record (the prehashed-ledger case: the manifest `logical_key` has no extension, so
`--key-append-extension` recovers nothing and every template HEAD 404s). `--key-map`
hands WOM the exact existing key per object so those objects are adopted instead of
re-uploaded.

## 1. The format WOM consumes (authoritative)

A JSONL file, UTF-8, one object per line, exactly:

```json
{"sha256":"<64 lowercase hex>","remote_key":"<exact bucket-relative key>"}
```

Rules WOM enforces:

- `sha256` — 64 hex. An `sha256:` prefix or uppercase is normalized, then validated.
- `remote_key` — the FULL bucket-relative key the object already lives under. Not a
  URL, not the bucket name, no leading slash, no `..`, no whitespace. The object's
  sha256 must appear in the key as a full `/`-delimited path segment OR as the
  filename stem (the tail after the last `/`, up to its first `.`).
- One object per line. Blank lines are skipped. A leading UTF-8 BOM on the first line
  is stripped.
- No other field is consumed. A `size`/`length` field, even if present, is IGNORED —
  size always comes from the manifest.
- Whole-run fatal (WOM adopts NOTHING): an unreadable/non-JSONL file, a row missing
  `sha256` or `remote_key`, a non-hex sha, an unsafe `remote_key`, a duplicate sha
  with conflicting keys, or more than 200,000 entries. A duplicate sha with the
  identical key is deduped.

## 2. Generic recipe (provider-agnostic)

From ANY per-object record that pairs an object's sha256 with the exact key it was
PUT under, emit one JSONL line per object. Conceptually:

```text
for each (sha256, exact_put_key) in your upload record:
    emit  {"sha256": sha256, "remote_key": exact_put_key}
```

The record can be a CSV, a database table, an S3 inventory report, `aws s3 ls`
output, or your own uploader's log — whatever pairs the object's content sha256 with
the exact key. WOM only cares about the JSONL it consumes; how you produce it is up
to you. Emit only the objects you want adopted; extra rows are ignored, and objects
you omit are reported as unmapped and left to re-upload.

## 3. Illustration only — a reported client scheme

The following is ONE reported example of how a client's keys look; it is NOT a
format WOM parses and NOT a file WOM reads. WOM never reads your uploader's log — it
reads only the JSONL in section 1.

Reported scheme: objects stored at `archives/<archive_id>/objets/<sha>.<ext>`, e.g.
`archives/archive:personal:basoon/objets/<sha256>.png`. If a client's own upload
record listed each object's sha and that exact key, the JSONL WOM consumes would be:

```json
{"sha256":"<sha256-of-object-1>","remote_key":"archives/archive:personal:basoon/objets/<sha256-of-object-1>.png"}
{"sha256":"<sha256-of-object-2>","remote_key":"archives/archive:personal:basoon/objets/<sha256-of-object-2>.pdf"}
```

Treat this only as a shape illustration. Your actual keys, extensions, and prefix
come from your own bucket; the client's uploader-log line format is unknown to WOM.

## 4. Run it

Dry-run first (no network, no secret read) to see coverage and the discoverability
hint:

```bash
archive object-storage-adopt-existing <archive-root> \
  --provider-kind cloudflare-r2 \
  --store-ref <store-ref> \
  --key-map ./key-map.jsonl \
  --reviewed-by person:me \
  --dry-run --format json
```

Then a verified adopt. This is a two-step run — **tiny-first before a batch is
mandatory**, and it is the only thing that unblocks a large `--key-map` handover.

**Step A — one verified tiny-first adopt (unlocks the batch).** Pick any single object
and adopt it with `--only <one-sha>`:

```bash
archive object-storage-adopt-existing <archive-root> \
  --provider-kind cloudflare-r2 \
  --store-ref <store-ref> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  --endpoint-host <account>.r2.cloudflarestorage.com \
  --bucket <bucket> \
  --key-map ./key-map.jsonl \
  --only sha256:<one-sha> \
  --reviewed-by person:me \
  --approve --format json
```

**Step B — the full batch.** Once Step A has adopted one object, re-run WITHOUT
`--only` (the full `--key-map` batch of all 19,054 objects now proceeds). For large
batches, add `--progress` so WOM streams safe stage/count heartbeats to stderr while
it resolves rows and performs presence-only HEAD checks:

```bash
archive object-storage-adopt-existing <archive-root> \
  --provider-kind cloudflare-r2 \
  --store-ref <store-ref> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  --endpoint-host <account>.r2.cloudflarestorage.com \
  --bucket <bucket> \
  --key-map ./key-map.jsonl \
  --reviewed-by person:me \
  --approve --progress --format json
```

**Resume an interrupted batch (v0.3.182+).** If a prior verified batch was stopped
after writing some `wom_uploaded` manifest locations, re-run with
`--skip-existing-wom-uploaded` to avoid remote-HEADing those already adopted rows:

```bash
archive object-storage-adopt-existing <archive-root> \
  --provider-kind cloudflare-r2 \
  --store-ref <store-ref> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  --endpoint-host <account>.r2.cloudflarestorage.com \
  --bucket <bucket> \
  --key-map ./key-map.jsonl \
  --reviewed-by person:me \
  --approve --skip-existing-wom-uploaded --progress --format json
```

The default remains conservative: without `--skip-existing-wom-uploaded`, verified
adopt re-HEADs every resolved key. The resume option is refused with
`--content-hash-verify`, because a fresh content-hash verification request must not
turn into a manifest-only skip.

Since v0.3.183, `--progress` also prints a plan-time resume summary before the
remote HEAD loop:

```text
[object-storage-adopt] adopt-plan: resume summary matching_locations=<n> wom_uploaded=<n> declared_uploaded=<n> other=<n> skip_existing_wom_uploaded=on
```

Only matching `wom_uploaded` rows can be skipped. Matching `declared_uploaded`
rows are visible in the summary and warning output, but they are not WOM-verified;
verified adopt must still HEAD them before promoting them to `wom_uploaded`.

Since v0.3.185, `--progress` can also print a same-provider nonmatching summary:

```text
[object-storage-adopt] adopt-plan: resume nonmatching-provider summary same_provider_nonmatching_locations=<n> wom_uploaded=<n> declared_uploaded=<n> other=<n> store_ref_mismatch=<n> remote_key_mismatch=<n>
```

This means WOM found digest-bound object-storage locations for the same provider,
but they do not match the current run's `store_ref` or resolved `remote_key`.
Those rows are useful history, but they are not `--skip-existing-wom-uploaded`
proof for the current store/key run. If the old store ref is the intended store,
run adopt against that store identity; otherwise continue verified adopt for the
current store ref so new `wom_uploaded` rows are written under the intended
identity. v0.3.185 intentionally does not add an automatic store-ref migration.

Since v0.3.186, use `--stop-after-plan` when you want only the plan-time
diagnostics and no partial writes:

```bash
archive object-storage-adopt-existing <archive-root> \
  --provider-kind cloudflare-r2 \
  --store-ref <store-ref> \
  --access-key-id-ref env:WOM_R2_ACCESS_KEY_ID \
  --secret-access-key-ref env:WOM_R2_SECRET_ACCESS_KEY \
  --endpoint-host <account>.r2.cloudflarestorage.com \
  --bucket <bucket> \
  --key-map ./key-map.jsonl \
  --reviewed-by person:me \
  --approve --skip-existing-wom-uploaded --stop-after-plan --progress --format json
```

This resolves the same key-map/resume plan and then stops after `adopt-plan`.
It reads no credential values, issues no provider HEADs, and writes no manifest
locations or execution receipts. The final JSON/text result is written to stdout;
`--progress` heartbeats are written to stderr. The JSON `adopt_summary` also
distinguishes a raw same-`store_ref` `wom_uploaded` location count from the
stricter resume skip candidates that match this run's key hint, resolved
`remote_key`, and digest binding.

**Why two steps, and the in-band signal.** A batch verified adopt on a store with no
prior verified adopt fails closed with the blocker `adopt_tiny_first_unmet`; the
message names Step A as the exact remedy. Since v0.3.174 the adopt gate is DECOUPLED
from the object-storage-upload 5 GiB / multipart tier proof — adopt is HEAD-only and
moves zero bytes, so it does NOT need a large-object PUT proof. Exactly ONE prior
verified tiny-first adopt unlocks a batch of any size N; an object-storage-upload
receipt does NOT unblock adopt. If you see `adopt_tiny_first_unmet`, run Step A once
and re-run Step B — that is the only in-band unblock signal and remedy.

Read the report: `adopt_summary` shows `mapped_count`, `unmapped_count`,
`map_rejected_count`, and `mapped_but_no_manifest_size_count`, and each
`adopt_results` row shows `key_source` ∈ {`template`,`map`,`map_rejected`,`unmapped`}.
An adopted row records `remote_key_verification` = `presence_size` (or `content_hash`
under `--content-hash-verify`).

Since v0.3.180, the plan phase builds one per-run manifest index before resolving
object ids, so a large key-map batch should not re-scan `objects/manifests/files.jsonl`
once per object. If `--progress` still shows a slow `adopt-plan` stage, capture the
last progress lines and the object count; that is now evidence for a different
planner bottleneck rather than the pre-v0.3.180 manifest lookup pattern.

## 5. Content identity — read this before trusting a hand-edited map

Presence + size proves the object at the key has the SAME LENGTH, not the same bytes.
A map whose key binds the digest but points at a same-size, different object would
false-adopt. `--content-hash-verify` is the ONLY cryptographic proof: it downloads
and re-hashes each object, and a hash mismatch does not adopt (that object
re-uploads). Use it for any map that is not mechanically generated from a trusted
per-object upload record.

## 6. Mime-derived extension — a lossy fallback, not a key builder

WOM stores a `mime` per object, and `extension_from_mime_hint` maps common mimes to
an extension (`application/pdf` -> `.pdf`, `application/x-hwp` /
`application/haansofthwp` -> `.hwp`, `image/*` -> `.png`). This is LOSSY: it cannot
tell `.jpg` from `.jpeg`, and `application/octet-stream` yields nothing, so a
mime-built key can still HEAD-404. WOM does NOT use it to build adopt keys
automatically — the exact-key `--key-map` is the reliable path. It is mentioned only
as a fallback in the discoverability hint.
