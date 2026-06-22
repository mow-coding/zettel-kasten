# Tiro Lossless Recovery

Status: v0.3.139 Tiro lossless recovery bundle contract and capture checkpoint

`archive tiro-lossless-recovery-plan` and
`archive tiro-lossless-recovery-capture` are the next step after
`tiro-import-plan`.

The v0.3.137 command checked a hand-reviewed meeting manifest. This checkpoint
adds the broader recovery contract for Tiro data and an approval-gated way to
preserve a raw Tiro recovery bundle as a WOM objet before any AI enrichment,
derived text, zet drafting, or minting.

## Commands

```powershell
archive tiro-lossless-recovery-plan <archive-root> --credential-ref env:WOM_TIRO_API_KEY --dry-run --format json
```

```powershell
archive tiro-lossless-recovery-capture <archive-root> --bundle workbench/tiro-lossless-raw.json --dry-run --format json
archive tiro-lossless-recovery-capture <archive-root> --bundle workbench/tiro-lossless-raw.json --approve --reviewed-by human:<id> --format json
```

Aliases:

```text
tiro-recovery-plan
tiro-recovery-capture
```

## Recovery Contract

The plan names the official-data surfaces that a future credential-bounded Tiro
adapter must cover:

- workspaces,
- workspace notes,
- note metadata,
- transcript paragraphs and diarized segments,
- note summaries,
- generated note documents,
- note document templates,
- folders attached to notes,
- user and workspace word memories,
- wiki info, pages, mentions, and graph data,
- share links when available,
- translations when available,
- original audio bytes when Tiro exposes them, or a recorded audio gap when it
  does not,
- pagination, rate-limit, and provider error observations.

The command also records the pagination and error rules the adapter must obey:
`content[]` plus `nextCursor` where present, 600 requests per 60 seconds,
`Retry-After` on `429`, and provider error envelopes without raw error echo in
AI-visible output.

## Bundle Capture

`tiro-lossless-recovery-capture` preserves a reviewed raw Tiro recovery JSON
bundle as a content-addressed WOM objet:

```text
workbench/tiro-lossless-raw.json
  -> objects/sha256/<prefix>/<sha256>
  -> objects/manifests/files.jsonl
  -> receipts/tiro/lossless-recovery/*.json
```

The stored object preserves the raw bundle bytes exactly. Command output and
receipts report only structure, hashes, counts, paths inside the archive, and
gap categories. They do not echo meeting titles, transcript text, participant
names, emails, provider URLs, tokens, or secret values.

This preserves the important boundary:

```text
raw Tiro data -> private objet
AI correction/enrichment -> separate derived layer
human-approved memory -> zet
```

The raw transcript must not be overwritten by speaker correction, relationship
inference, summary cleanup, or any other AI enrichment.

## Current Limit

This checkpoint does not yet implement the live credential-bounded Tiro REST or
CLI fetch adapter that generates the bundle. It implements:

In short, the live credential-bounded Tiro REST or CLI fetch adapter is still
future work in this checkpoint.

- the official endpoint inventory,
- the lossless private bundle contract,
- the approval-gated bundle-to-objet preservation path,
- non-secret receipts and manifest records.

The next implementation step is the live adapter that reads an approved
credential reference locally, calls Tiro directly, writes the raw bundle, and
then hands that bundle to `tiro-lossless-recovery-capture`.

## Safety Boundary

The plan command writes nothing and reads no credential values.

The capture command writes only after `--approve --reviewed-by`. It reads the
selected archive-relative bundle, writes object bytes, appends one manifest
record when needed, and writes a non-secret receipt.

Neither command drafts zets, mints zets, writes derived text, performs ASR,
calls Tiro, opens a keyring, opens a password manager, uploads data, deletes
the staged bundle, or cleans files.
