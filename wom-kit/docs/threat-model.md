# Threat Model

This is a beginner-friendly local pre-pilot threat model.

It is not a formal penetration test. It explains what the current WOM-kit tries to prevent before a real personal or team archive touches real data.

## System Boundary

WOM-kit is the control plane.

It records:

```text
zettels
source bindings
source maps
provider bindings
object manifests
receipts
lineage
local search index
```

It does not own every original file. Originals may remain on the local PC, SSDs, Notion, Google Drive, object storage, or other systems.

## Main Threats

| Threat | Plain Meaning | Current Defense |
| --- | --- | --- |
| Spoofing | A fake actor/source/provider pretends to be trusted. | owner/operator ids, trusted counterparties, provider refs, receipt reviewers |
| Tampering | Archive files or receipts are changed incorrectly. | doctor schema checks, receipts, dry-run gates, restore drill |
| Repudiation | Nobody can prove who approved a risky action. | `--reviewed-by`, receipts, lineage events |
| Information disclosure | Secrets or private paths leak into versioned files. | secret-like file/value checks, local profiles ignored, provider refs only |
| Denial of service | A bad scan or broken archive makes the system unusable. | metadata-only scans, preflight, restore drill, rebuildable SQLite index |
| Elevation of privilege | AI/container gains more access than intended. | Docker no network, non-root user, read-only `/app`, MCP path allowlist |

## Specific Pre-Pilot Risks

### Secret Leak

Risk:

```text
User accidentally stores tokens, passwords, database URLs, private keys, or KeePassXC files in the archive.
```

Defense:

```text
archive doctor checks secret-like names and values.
provider-bindings.yml stores env/keyring references, not secret values.
Docker build context excludes common secret paths.
```

### Broad Scan

Risk:

```text
User or AI maps an entire drive, home folder, Desktop, or cloud sync root too early.
```

Defense:

```text
archive preflight blocks drive/root/home/system paths.
preflight warns on broad user folders.
source scans are metadata-only by default.
```

### Personal/Team Mixing

Risk:

```text
Private personal sources get registered into the team archive.
```

Defense:

```text
pilot-plan separates personal and team archive roots and ids.
preflight --peer-archive checks overlap and duplicate archive ids.
First real pilot starts with one narrow source.
```

### Symlink Escape

Risk:

```text
A symlink inside an archive points outside the archive and tricks tools into reading or writing outside the root.
```

Defense:

```text
doctor flags symlink escapes.
service reads/writes use archive path guards.
index/listing skips unsafe symlink targets.
```

### Malicious Export

Risk:

```text
Notion or Google Drive export contains strange paths, broken manifests, or malicious-looking metadata.
```

Defense:

```text
external import starts as dry-run.
source map paths must stay relative and safe.
live provider API sync is not enabled in the default runtime.
```

### Container Escape Assumptions

Risk:

```text
User assumes Docker is perfect isolation.
```

Defense:

```text
Docker is treated as a trusted local dependency, not a perfect sandbox.
The default runtime still reduces blast radius with non-root, read-only root filesystem, no capabilities, no network, and no Docker socket.
```

### Provider Drift

Risk:

```text
GitHub/R2/B2/Neon real permissions drift away from provider-bindings.yml.
```

Defense:

```text
provider-bindings.yml makes external assumptions visible.
provider_change_plan marks external changes manual_required.
Real provider API mutation and live drift checks are future explicit phases.
```

### Restore Failure

Risk:

```text
The archive looks fine until the user needs to restore it.
```

Defense:

```text
archive recovery-plan shows what is and is not recoverable.
archive restore-drill copies the control plane to a clean folder, runs doctor, rebuilds index, and writes a receipt.
preflight can require a successful restore drill receipt before real source pilot.
```

## Current Non-Goals

```text
formal external security audit
live Notion/Google Drive/Google Photos sync
external provider API mutation
OS keychain or KeePassXC automatic secret reads
full PC content analysis
full backup of external originals
```

