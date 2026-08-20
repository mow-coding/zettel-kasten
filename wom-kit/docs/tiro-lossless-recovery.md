# Tiro Lossless Recovery

Status: v0.4.0 dry-run-only Tiro recovery; fetch/capture approval fixed closed

`archive tiro-lossless-recovery-plan`,
`archive tiro-lossless-recovery-fetch-run`, and
`archive tiro-lossless-recovery-capture` are the recovery path after
`tiro-import-plan`.

The v0.3.137-v0.3.143 checkpoints documented historical planning, fetch, and
capture behavior. In v0.4.0 only the plan and fetch/capture dry-runs are
operational. Any fetch or capture approval returns
`compound_exact_human_approval_binding_required` before credential, provider,
private bundle, object-manifest, or target reads and writes nothing.

## Commands

```powershell
archive tiro-lossless-recovery-plan <archive-root> --credential-ref env:WOM_TIRO_API_KEY --dry-run --format json
```

```powershell
archive tiro-lossless-recovery-fetch-run <archive-root> --credential-ref env:WOM_TIRO_API_KEY --workspace-guid <workspace-guid> --output workbench/tiro-lossless-recovery.live.json --dry-run --format json
```

The dry-run may validate a safe OS credential-store ref shape without opening
the store:

```powershell
archive tiro-lossless-recovery-fetch-run <archive-root> --credential-ref keyring:<safe-tiro-label> --workspace-guid <workspace-guid> --output workbench/tiro-lossless-recovery.live.json --dry-run --format json
```

```powershell
archive tiro-lossless-recovery-capture <archive-root> --bundle workbench/tiro-lossless-recovery.live.json --dry-run --format json
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
3. Stop after the preview. In v0.4.0 fetch approval reads no token, calls no
   Tiro endpoint, and writes no bundle or receipt.
4. Capture approval likewise reads no bundle and writes no object, manifest
   row, or receipt.

## Recovery Contract

The plan and historical fetch contract cover these official-data surfaces where the Tiro
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

Historical v0.3 fetch evidence used this layout; v0.4.0 does not create it:

```text
workbench/tiro-lossless-recovery.live.json
-> receipts/tiro/lossless-fetches/*.json
```

Historical v0.3 capture evidence used this layout; v0.4.0 does not append to it:

```text
workbench/tiro-lossless-recovery.live.json
-> objects/sha256/<prefix>/<sha256>
-> objects/manifests/files.jsonl
-> receipts/tiro/lossless-recovery/*.json
```

The stored object preserves the raw bundle bytes exactly. Command output and
receipts report only structure, hashes, counts, paths inside the archive, and
gap categories. They do not echo credential refs, environment variable names,
OS credential target names, meeting titles, transcript text, participant
names, emails, provider URLs, tokens, raw provider responses, or secret values.

This preserves the important boundary:

```text
raw Tiro data -> private objet
AI correction/enrichment -> separate derived layer
human-approved memory -> zet
```

The raw transcript must not be overwritten by speaker correction, relationship
inference, summary cleanup, or any other AI enrichment.

## Current Boundary

v0.4.0 retains content-free planning only. Fetch/capture approval is fixed
closed before any credential-store lookup, provider request, private bundle
read, object-manifest read, or target write. Historical v0.3 receipts remain
auditable but grant no replay authority.

These pieces are still separate future layers:

- macOS Keychain, Linux Secret Service, KeePassXC, wallet, or browser
  password-manager credential reads,
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

The fetch and capture dry-runs do not read an environment variable, open
Windows Credential Manager, call Tiro, read a selected bundle, or write any
file. Every approval attempt returns the fixed content-free blocker before
those reads and effects.

These commands do not draft zets, mint zets, write derived text, perform ASR,
open unapproved credential stores, upload data, delete the staged bundle, or
clean files.
