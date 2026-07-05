# Runbook — `object-storage-adopt-existing --key-map`

Status: active
Date: 2026-07-04
Applies to: `wom-kit` v0.3.171+

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

Then a verified adopt. Start tiny-first (`--only <one-sha>`) to prove the store, then
run the batch:

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
  --approve --format json
```

Read the report: `adopt_summary` shows `mapped_count`, `unmapped_count`,
`map_rejected_count`, and `mapped_but_no_manifest_size_count`, and each
`adopt_results` row shows `key_source` ∈ {`template`,`map`,`map_rejected`,`unmapped`}.
An adopted row records `remote_key_verification` = `presence_size` (or `content_hash`
under `--content-hash-verify`).

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
