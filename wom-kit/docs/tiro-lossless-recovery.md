# Tiro Lossless Recovery

Status: v0.3.140 live Tiro REST fetch and lossless bundle capture checkpoint

`archive tiro-lossless-recovery-plan`,
`archive tiro-lossless-recovery-fetch-run`, and
`archive tiro-lossless-recovery-capture` are the recovery path after
`tiro-import-plan`.

The v0.3.137 command checked a hand-reviewed meeting manifest. v0.3.139 added
the broader recovery contract and raw-bundle capture. v0.3.140 adds the first
approval-gated live Tiro REST fetch adapter so a human can provide a local
`env:` credential reference, fetch official Tiro data directly, write a private
raw recovery bundle, and then preserve that bundle as a WOM objet before any AI
enrichment, derived text, zet drafting, or minting.

## Commands

```powershell
archive tiro-lossless-recovery-plan <archive-root> --credential-ref env:WOM_TIRO_API_KEY --dry-run --format json
```

```powershell
archive tiro-lossless-recovery-fetch-run <archive-root> --credential-ref env:WOM_TIRO_API_KEY --workspace-guid <workspace-guid> --output workbench/tiro-lossless-recovery.live.json --dry-run --format json
archive tiro-lossless-recovery-fetch-run <archive-root> --credential-ref env:WOM_TIRO_API_KEY --workspace-guid <workspace-guid> --output workbench/tiro-lossless-recovery.live.json --approve --reviewed-by human:<id> --format json
```

```powershell
archive tiro-lossless-recovery-capture <archive-root> --bundle workbench/tiro-lossless-recovery.live.json --dry-run --format json
archive tiro-lossless-recovery-capture <archive-root> --bundle workbench/tiro-lossless-recovery.live.json --approve --reviewed-by human:<id> --format json
```

Aliases:

```text
tiro-recovery-plan
tiro-recovery-fetch-run
tiro-recovery-capture
```

## Recovery Flow

1. `tiro-lossless-recovery-plan` writes nothing. It records the official-data
   surfaces and safety contract.
2. `tiro-lossless-recovery-fetch-run --dry-run` writes nothing, reads no token,
   and calls no provider. It only previews the approved fetch path.
3. `tiro-lossless-recovery-fetch-run --approve --reviewed-by ...` reads the
   approved `env:` token locally, calls Tiro REST endpoints, writes the private
   raw bundle under `workbench/`, and writes a non-secret fetch receipt under
   `receipts/tiro/lossless-fetches/`.
4. `tiro-lossless-recovery-capture --approve --reviewed-by ...` stores that raw
   bundle exactly as a content-addressed WOM objet.

## Recovery Contract

The plan and live fetch path cover these official-data surfaces where the Tiro
REST API exposes them:

- workspaces,
- workspace notes,
- note metadata,
- transcript paragraphs and diarized segments,
- note summaries,
- generated note documents,
- note document templates when available,
- folders attached to notes,
- user and workspace word memories,
- wiki info when available,
- share links when available,
- translations when available,
- original audio bytes when Tiro exposes them, or a recorded audio gap when it
  does not,
- pagination, rate-limit, and provider error observations.

The adapter follows the official Tiro REST shape:

- base API: `https://api.tiro.ooo`,
- bearer API-key authentication,
- list responses shaped as `content[]` plus `nextCursor` where present,
- 600 requests per 60 seconds,
- `Retry-After` on `429`,
- provider errors are reduced to gap categories in AI-visible output instead of
  echoing raw provider error bodies.

## Bundle Capture

`tiro-lossless-recovery-fetch-run` writes the raw recovery bundle:

```text
workbench/tiro-lossless-recovery.live.json
-> receipts/tiro/lossless-fetches/*.json
```

`tiro-lossless-recovery-capture` then preserves that reviewed raw bundle as a
content-addressed WOM objet:

```text
workbench/tiro-lossless-recovery.live.json
-> objects/sha256/<prefix>/<sha256>
-> objects/manifests/files.jsonl
-> receipts/tiro/lossless-recovery/*.json
```

The stored object preserves the raw bundle bytes exactly. Command output and
receipts report only structure, hashes, counts, paths inside the archive, and
gap categories. They do not echo credential refs, environment variable names,
meeting titles, transcript text, participant names, emails, provider URLs,
tokens, raw provider responses, or secret values.

This preserves the important boundary:

```text
raw Tiro data -> private objet
AI correction/enrichment -> separate derived layer
human-approved memory -> zet
```

The raw transcript must not be overwritten by speaker correction, relationship
inference, summary cleanup, or any other AI enrichment.

## Current Boundary

v0.3.140 implements the live credential-bounded Tiro REST fetch adapter for
local `env:` credential refs. These pieces are still separate future layers:

- keyring, vault, wallet, or OS password-manager credential reads,
- original audio byte retrieval when no official REST endpoint is confirmed,
- AI enrichment writes,
- derived-text capture,
- zet drafting,
- minting,
- provider upload or cleanup.

When audio bytes cannot be fetched by the adapter, the raw bundle records an
`audio_original_bytes` gap instead of pretending the recovery is complete.

## Safety Boundary

The plan command writes nothing and reads no credential values.

The fetch command writes only after `--approve --reviewed-by`. In dry-run mode,
it does not read the environment variable and does not call Tiro. In approve
mode, it reads only the named local environment variable, calls Tiro, writes the
raw bundle, writes a non-secret fetch receipt, and clears the token from local
runtime variables before returning.

The capture command writes only after `--approve --reviewed-by`. It reads the
selected archive-relative bundle, writes object bytes, appends one manifest
record when needed, and writes a non-secret receipt.

These commands do not draft zets, mint zets, write derived text, perform ASR,
open a keyring, open a password manager, upload data, delete the staged bundle,
or clean files.
