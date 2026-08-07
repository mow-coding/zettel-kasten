# AI Start-Here Quick And Full Inspection

Status: quick/default and explicit full-Doctor contract implemented in v0.3.222;
safe full-Doctor receipt phase and callback coalescing added in v0.3.223;
no-repeat runtime-context handoff added in v0.3.224; identity consistency and
review routing added in v0.3.226; aggregate edge-receipt progress added in
v0.3.227; official AI command-path routing added in v0.3.278; explicit
runtime-guidance readiness and feedback routing added in v0.3.293;
checked-layer objet rediscovery routing added in v0.3.294; privacy-safe
unpublished-draft attention added in v0.3.305

## Purpose

An AI entering a WOM archive needs a fast orientation map before broad reading.
That first map must not silently become a multi-minute complete archive scan.

## Quick Default

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
```

Quick mode reads bounded archive identity, policy, local-sovereignty authority,
canonical entrypoint presence, WOM-kit version context, and the current
operational-context record. It returns:

```text
inspection.mode: quick
inspection.full_doctor_run: false
inspection.doctor_summary.checked: false
```

It does not construct Doctor, enumerate every zet or receipt, read zet bodies,
read objet bytes, access a credential store/provider, or write archive state.
Its result is an entry map, not an archive health claim.

Quick mode does run the existing bounded frontmatter-only inbox audit. The
result's `inbox_attention` gives the unpublished draft count, oldest safely
parseable age, possible current-pipeline-shape bypass count, and explicit
abstract/facet readiness-gap count. It returns no title, id, path, body, actor,
or source value. Markdown renders the same summary under `Unpublished Draft
Attention`. This signal must be surfaced before broad work, but grants no
repair, discard, semantic-merge, or mint authority.

The map already includes runtime-context. Since v0.3.224, the compatibility
`first_commands` list marks that command `already_included` with
`run_required: false`. AI operators should continue through `next_commands` and
`remaining_ai_runtime_order`, not execute the full recommendation list again.
Markdown output separates `Already Included` from `Next Commands`.

The source operational-context record remains unchanged. If its default next
list says `Run runtime-context first.`, start-here does not copy that already
satisfied sentence into `next_safe_steps`.

## Host Guidance Is An Explicit Check

Quick and full start-here modes both leave host guidance at `not_checked`.
They do not inspect the Codex Skill install or repository `AGENTS.md`
implicitly. Run the following only when that host-specific question matters:

```powershell
archive runtime-guidance-readiness <archive-root> --host codex --scope repo --repo-root <repo-root> --format json
```

The result may prove that files and required routing anchors are present. It
cannot prove the host actually consumed them, so
`host_guidance_consumption` remains `not_proven`.

## Official Read And Write Paths

Introduced in v0.3.278 and extended through v0.3.294, JSON output includes
the current `wom-kit/ai-command-path-routing/v0.12`, and Markdown output renders
`Official Read Command Paths` and `Official Write Command Paths`.

The routes require `archive search --count-total --format json` for
authoritative WOM index search and then
`archive objet-rediscovery-plan --dry-run --count-total --format json` before
any global claim that an objet or source does not exist. The plan reports ten
fixed evidence layers without echoing the private query or rows; index
`complete` alone is not global absence. Routes also require
`archive create-draft` preview plus reviewed
replay for AI-assisted inbox drafts. Raw grep/SQL do not prove a WOM search
result, and direct Markdown writes to `inbox/` are forbidden. The same object
states that local version inspection does not check remote release freshness
and that saved-view recommendation has no persistent writer yet. It also
routes historical inbox-shape review through the read-only
`inbox-pipeline-audit`, whose classifications are not proof and trigger no
repair. Explicit event-membership review routes through the read-only
`activity-group-membership-plan`; approved additions then route through the
digest-bound `activity-group-membership-write`, and interrupted transactions
route through a separate plan/approval recovery pair. Explicit removals route
through `activity-group-membership-removal-plan`, the separate digest-bound
`activity-group-membership-removal-write`, and their own
recovery-plan/approval pair. v0.3.284 advances the routing object to v0.6.
Addition and removal share one global writer lock and block retained journals
across both private roots, but their request, journal, receipt, and recovery
contracts remain separate. No route infers membership, authorizes a direct
canonical edit, exposes an MCP writer, or supplies a removal revert.
See [AI Command-Path Routing](ai-command-path-routing.md).

## Identity Consistency

Quick mode compares the principal declaration in `archive.yml` with the
identity and ownership core in `archive-identity.yml`. The JSON result exposes
`identity_consistency`; Markdown shows its status in the Archive section. A
mismatch is not silently resolved and adds this read-only next step:

```text
archive identity-reconcile <archive-root> --dry-run --format json
```

The preview reads no zet or objet content and does not expose duplicated
identity values. Principal or archive-id conflicts block automatic repair.
Only a same-principal display mismatch and a missing or template-like identity
id can proceed through the separate reviewed approval command. See
[Archive Identity Reconcile](archive-identity-reconcile.md).

## Explicit Full Doctor

```powershell
archive ai-start-here <archive-root> `
  --dry-run `
  --full-doctor `
  --progress `
  --format json
```

Full mode runs the complete Doctor before composing the same start map. The
result changes to `inspection.mode: full_doctor`, embeds the Doctor severity
counts, and records observed reads under `inspection.read_observations`. Its
safety block can report:

- zet bodies read;
- local objet bytes read by validation;
- archive text scanned for secret-like patterns;
- no credential store accessed;
- no provider called;
- no archive state written.

Booleans describe this execution rather than marking every allowed read true.
This mode can take minutes on a large archive. That is expected complete
validation work, not the default cost of entering the archive.

## Progress Meaning

Counted progress identifies a stable unit. In particular:

```text
zettels -> zet_files
mint-receipts -> mint_receipts
```

Each counted line includes total elapsed time, stage elapsed time, rate, and
ETA. Heartbeats keep the latest count, so an operator can distinguish a long
single item from a process with no visible stage state.

Compact output prints the same stage/count at most once per 30 seconds unless
the event is a heartbeat. A receipt's many internal checks therefore cannot
produce dozens of identical `1/N progress` lines. Full detailed events remain
available through Doctor verbose/progress-log modes.

In v0.3.223, a long full-Doctor mint receipt heartbeat also names one fixed safe
phase such as `file_hash`, `target_edge_evolution`, or `edge_receipt_index`.
Private substep text never enters the phase. The shared reporter coalesces later
same-count callbacks before formatter/lock work while continuing to update the
phase used by heartbeat.

In v0.3.227, a fast edge-receipt filename index prints only lifecycle lines in
compact mode. Targeted source loads keep content-free cumulative `sources`,
`candidates`, and `cache_hits` in the 10-second heartbeat and one final summary
instead of printing each short candidate batch. Direct Doctor verbose output
and private progress-log JSONL retain those per-source events.

## Output And Privacy

`--output` remains an explicit private-scratch exception under
`.wom-scratch/diagnostics/`. It never turns the result into a receipt or public
artifact, refuses overwrite/traversal, and prints only a compact stdout summary.

Both modes redact local absolute paths by default. Progress never emits zet
ids, paths, titles, abstracts, bodies, receipt paths, provider values,
credential refs, tokens, or secret values.

## Compatibility

No archive migration is required. Scripts that relied on `ai-start-here` to run
a complete Doctor must add `--full-doctor`. Scripts that only needed the entry
map become faster without changing archive data. CLI and MCP runtime-context
also become quick by default in v0.3.224; see
[Runtime Context Quick And Full Inspection](runtime-context-quick-and-full-inspection.md).
