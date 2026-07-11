# Local Sovereignty And Backup Authority

Status: implemented contract in v0.3.213

## One Authority Model

Local WOM is the canonical working and recovery state. External services are
backup, replica, or projection layers. They do not silently outrank reviewed
local state.

| Data | Local authority | External role | Conflict default | Recovery direction |
| --- | --- | --- | --- | --- |
| zet documents, frontmatter, ties, manifests, receipts, configuration | reviewed files in the local WOM archive | GitHub backs up metadata, version history, and reviewable changes | local wins pending explicit reconcile | GitHub backup to local WOM |
| objet original bytes | sha256-identified bytes in a registered local objet store or reviewed local source | object storage, including Cloudflare R2, backs up bytes | verified local identity wins pending explicit reconcile | verified remote bytes to a local objet store |
| relationship and map data | local zet edges, ties, source maps, and manifest links | external DB stores a map backup or replica | local relation-bearing records win | regenerate the external map from local records |
| generated indexes and caches | not canonical | no authoritative backup role | regenerate | rebuild from current local records |
| credentials and secrets | human-controlled OS or vault storage | outside this GitHub/R2/DB contract | human review | provider-specific recovery outside public metadata |

An object that exists only remotely is not proof that the local-sovereignty
goal is complete. It is a recovery dependency and should be reported as such.
Similarly, an external DB row that cannot be regenerated from local records is
an architecture gap, not a new source of truth.

## Offline Boundary

Without a network, WOM can still read local zets and frontmatter, inspect ties
and edges, draft and review local records, run local validation, rebuild
disposable indexes, and read locally present objet bytes.

Without a network, WOM cannot push a GitHub backup, verify or restore remote
object-storage bytes, or sync/query an external DB replica. Offline capability
therefore depends on the required local records and bytes actually being
present, not merely referenced.

## Backup Evidence

Backup claims require boundary-specific evidence:

- GitHub: a local commit alone does not prove that a remote ref contains it.
  WOM-kit does not yet issue a generic GitHub backup-completion receipt.
- Object storage: a provider-verified `wom_uploaded` manifest location linked
  to an execution receipt can prove the implemented live upload boundary.
  `declared_uploaded` alone does not prove remote bytes.
- External DB: a provider-specific export or replication receipt bound to a
  local snapshot is required. WOM-kit does not yet issue one generic DB backup
  receipt.
- Generated local index: a successful rebuild is health evidence, not backup
  proof.

The authority contract does not perform a live backup audit. It calls no
provider, network, database, or secret store.

## Machine-Readable Surfaces

```powershell
archive local-sovereignty <archive-root> --dry-run --format json
archive storage-authority <archive-root> --dry-run --format json
```

The same `storage_authority` model appears in `runtime-context`,
`ai-start-here`, `recovery-plan`, and the recovery section of `upgrade-check`.
This keeps AI instructions and human documentation on one contract.

## Recovery Order

```text
1. Restore GitHub metadata and version history into local WOM.
2. Restore sha256-verified objet bytes into a local objet store.
3. Validate local manifests, receipts, zets, and ties.
4. Regenerate local indexes and external DB map replicas from local records.
```

No archive migration or existing zet rewrite is required.
