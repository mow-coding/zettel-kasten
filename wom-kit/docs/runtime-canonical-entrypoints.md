# Runtime Canonical Entry Points

Status: v0.3.251 installed-wheel resource, quick start, session handoff, and local backup evidence checkpoint

When an AI runtime enters a WOM archive, it needs a small, explicit "start
here" map. The archive may contain zets, source bindings, provider metadata,
object manifests, receipts, local instructions, and generated indexes. Without a
canonical entrypoint summary, an agent can mistake a partial export, mirror, or
secondary folder for the archive source of truth.

For the complete beginner-facing entry map, start with:

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
```

The underlying raw context packet remains available through:

```powershell
archive runtime-context <archive-root> --format json
```

Both paths are quick by default and do not construct Doctor. Add
`--full-doctor` only when a complete archive health check is required. The
result includes `canonical_entrypoints`. From v0.3.117, it also includes
`operational_context`, a read-only view of `ops/operational-context.yml` for
AI-facing mission, scope, state, gotchas, and reviewed decisions. The
`canonical_entrypoints` object includes machine-readable `ai_runtime_order`,
`recommended_first_commands`, and `material_link_routes` so a terminal-capable
AI can discover both the operational handoff and the guide handoff without
waiting for the human to mention them.

## AI Runtime Order

When an AI enters an archive, use this order before interpreting or writing
anything:

1. Run `archive ai-start-here <archive-root> --dry-run --progress --format
   json`, or use quick `runtime-context` when the host specifically needs the
   raw packet. Do not run both back-to-back.
2. Follow `next_commands`; runtime-context is already listed under
   `completed_commands` with `run_required: false`.
3. Read `operational_context.session_start_injection` when present.
4. Read `canonical_entrypoints`, especially `archive.yml`, `AGENTS.md`, and
   `ops/operational-context.yml`.
5. Run `archive first-read-readiness <archive-root> --dry-run --progress
   --format json`. Repair explicit-abstract or unique-id gaps through reviewed
   flows before claiming memory-reconstruction readiness. Process exit zero
   means the diagnostic completed; only `readiness_met` proves this gate is
   ready. For a large legacy gap, use only the official three-zet pilot first.
6. Run `archive abstract-freshness <archive-root> --dry-run --progress --format
   json`. Treat stale, unverified, or missing rows as a human review queue;
   never auto-rewrite an abstract or body. Its progress is two stages;
   `stage=1/2` ending is not whole-command completion.
7. Run the complete private `zet-catalog-pass`, validate and read it from page
   zero, and distinguish generated node coverage from actual host consumption.
8. Run `archive ai-response-concept-guide <archive-root> --topic all --dry-run`
   when the human is asking what to do next.
9. For Notion material links, choose the route from that guide:
   `notion-objet-import-clue-audit` to check omitted-locator imports,
   `notion-objet-source-map-link-plan` when source maps or ledgers can recover
   a candidate, or `notion-objet-link-index` / `notion-objet-link-plan` when
   body locators still exist.
10. Run `archive operator-feedback-plan <archive-root> --dry-run` (read-only)
   when the human reports tool friction, a workflow gap, or asks where
   feedback records live; recording still needs a separate
   `archive operator-feedback-record --approve` review gate. From v0.3.160 the
   record/receipt shapes ship as
   `wom-kit/schemas/operator-feedback.schema.json` and
   `wom-kit/schemas/operator-feedback-receipt.schema.json`.

After any approved `zet-revision-write`, run the separate CLI-only
`archive zet-revision-receipt-audit <archive-root> --dry-run --progress
--format json` before session handoff. This is a bounded history and
transaction-lock check, not another archive startup scan and not permission to
delete a leftover lock.

For a v0.2 ordinary revision receipt, first use CLI-only `archive
zet-revision-restore-proposal-from-snapshot <archive-root> --receipt
<canonical-revision-receipt> --expected-receipt-sha256 <sha256> --dry-run
--format json`, then approve only its unchanged plan digest. This creates an
independent private review copy and does not approve a restore. For a legacy
v0.1 receipt, a human must still recover complete old zet bytes from a trusted
private backup. Then use CLI-only `archive zet-revision-restore-plan <archive-root>
--receipt <canonical-revision-receipt> --expected-receipt-sha256 <sha256>
--restore-proposal .wom-scratch/revisions/restores/<private>.md --dry-run
--format json`. A green plan only prepares private human review and grants no
manual-copy authority. The selected receipt must be the actual newest event,
even when current bytes repeat an older state. Since v0.3.239, pass the exact
plan hashes through CLI-only `zet-revision-restore-write --dry-run`, then use
its unchanged write digest and event time only after explicit human approval.
The approved writer installs exact reviewed bytes and appends one restore
receipt; rerun the exact approved command after interruption. MCP has no
restore writer.

This order keeps archive identity, operational mission/state, local
instructions, beginner-facing wording, and material-link safety gates aligned
before any later approval-gated write.

Runtime context treats `archive.yml principal` as the archive principal
declaration and `archive-identity.yml` as the identity and ownership core. Its
`identity_consistency` block reports whether duplicated metadata agrees. A
non-aligned result routes first to `archive identity-reconcile <archive-root>
--dry-run --format json`; it never grants automatic write authority.

To inspect only the operational handoff, run:

```powershell
archive operational-context <archive-root> --dry-run --format json
```

Before ending or resetting the AI session, verify that current work has a
durable handoff rather than trusting chat memory:

```powershell
archive session-handoff-checkpoint <archive-root> --dry-run --format json
```

The checkpoint requires receipt-backed operational-context bytes and a complete
reviewed AI artifact inventory. Its separate confirmation and approval flow is
described in [Session Handoff Checkpoint](session-handoff-checkpoint.md). It
does not read the host chat and does not prove remote backup.

Before an AI describes backup condition, use the local-only evidence surface:

```powershell
archive backup-evidence <archive-root> --dry-run
```

It reports receipt-time object coverage separately from the still-unverified
GitHub and external-database lanes. It performs no remote check and never turns
configuration or a declared label into backup completion. See
[Backup Evidence Status](backup-evidence-status.md).

The same order is returned in JSON:

```text
canonical_entrypoints.ai_runtime_order
canonical_entrypoints.recommended_first_commands
canonical_entrypoints.completed_commands
canonical_entrypoints.next_commands
canonical_entrypoints.remaining_ai_runtime_order
canonical_entrypoints.material_link_routes
operational_context.session_start_injection
```

The route list includes `notion-objet-import-clue-audit`,
`notion-objet-source-map-link-plan`, `notion-objet-link-index`, and
`notion-objet-link-plan`, with each route marked as read-only and provider-free.

## Start Here

The first authoritative file is:

```text
archive.yml
```

It identifies the archive, type, principal, root policy, and write policy. The
runtime entrypoint summary then lists other archive-relative files/directories
and their roles:

- `AGENTS.md`: local agent instructions,
- `archive-identity.yml`: owner and principal identity context,
- `source-bindings.yml`: source catalog,
- `provider-bindings.yml`: provider setup metadata,
- `ops/operational-context.yml`: AI-facing mission, scope, state, gotchas, and
  reviewed decisions,
- `zettels/`: canonical zets,
- `inbox/`: draft inbox,
- `objects/manifests/files.jsonl`: objet manifest,
- `objects/manifests/derived-text.jsonl`: derived-text manifest,
- `views/`: saved views,
- `db/schema.sql`: SQLite schema context.

Each item reports only a role, expected kind, required flag, status, and
archive-relative path. Missing optional files remain optional. Missing required
files should make the human or AI stop and repair the archive before treating
the workspace as authoritative.

## Privacy Boundary

The entrypoint check is mostly a map, not an import. The operational context
field intentionally reads only `ops/operational-context.yml` so the AI can
rehydrate the current mission/state. Apart from that bounded record:

- it reads no other file bodies,
- it writes no files,
- it calls no providers,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it echoes no local absolute paths by default.

Use `runtime-context --no-redact-local-paths` only for trusted local debugging.
Use `runtime-context --full-doctor --progress` only when complete validation is
needed. Quick mode reports `doctor_summary.checked: false` and is not an archive
health claim.

## Not Implemented

The quick/default path does not enforce migration, auto-upgrade project folders, scan broad
file contents, choose between competing exports, synchronize providers, write
material links, or run IMAP adapters. It gives AI runtimes a deterministic
archive-relative map, a bounded operational-context rehydration record, and the
read-only guide command or material-link route to run next.
