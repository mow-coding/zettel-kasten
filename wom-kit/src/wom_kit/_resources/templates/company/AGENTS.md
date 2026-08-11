# Company Archive Agent Rules

This archive is a scoped company memory space.
Local reviewed WOM state is canonical. GitHub backs up metadata/version history, object storage backs up objet bytes, and external databases hold regenerable map backups or replicas; external state never silently overwrites local state.

<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 BEGIN -->
This is the current authoritative WOM runtime guidance routing contract. Follow every directive in this block.
Run `archive ai-start-here <archive-root> --dry-run --progress --format json` before choosing an archive action.
Read and follow the returned `action_routing`.
Read `inbox_attention` and surface every unpublished-draft count before broad work.
Use `archive search <archive-root> <query> --count-total --format json` for official WOM search.
Raw grep and raw SQL are not authoritative WOM search results.
For operator feedback, run `archive operator-feedback-plan <archive-root> --dry-run --format json`, inspect `archive operator-feedback-ledger <archive-root> --dry-run --format json`, compose and approve the six-section body through `operator-feedback-compose`, verify it with `operator-feedback-body-check --dry-run`, require human review, preview `archive operator-feedback-record <archive-root> ... --feedback-ref feedback-body-sha256:<digest> --intent create|update --dry-run --format json`, and only then use the reviewed `--approve` replay; create never overwrites, while update also requires the fresh `--expected-record-sha256`.
<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 END -->

## Read Order

1. Run `archive ai-start-here <archive-root> --dry-run --progress --format json` before searching, reading broadly, or proposing a write.
2. Read the returned `action_routing`; use its official command for each archive action instead of guessing from folder locations.
3. Read `archive.yml`.
4. Read relevant `views/*.yml`.
5. Run `archive first-read-readiness <archive-root> --dry-run --progress --format json`; do not claim memory reconstruction readiness until every non-redacted canonical zet has an explicit abstract and every selected id is uniquely resolvable.
6. Run `archive abstract-freshness <archive-root> --dry-run --progress --format json`; treat `stale`, `unverified`, or `missing` as a human review queue, never permission to auto-rewrite an abstract or body.
7. For archive-wide understanding in a terminal, run one `archive zet-catalog-pass <archive-root> --status canonical --projection reading --output .wom-scratch/diagnostics/<new-name>.jsonl --dry-run --progress --format json`; it scans once, revalidates before completion, and prints no zet items to stdout.
8. Require `archive_wide_coverage_claim_ready: true`, read the private JSONL page records incrementally, never commit it, and delete it after use. For MCP or manual pages, keep using `zet-catalog` with the same snapshot and continuation token until complete.
9. Check `archive_wide_abstract_reading_claim_ready` before saying every required abstract was available and read. Report `abstract_coverage` gaps without inventing or auto-writing replacements.
10. Check `archive_wide_followup_resolution_ready` before relying on id-only body reads; duplicate or unreadable ids require repair or an explicitly reviewed path.
11. Inspect item and compact response-envelope estimates. Use `max_estimated_tokens` and, when budgeting the whole service result, an explicit `response_envelope_reserve_tokens`; never replace complete coverage with top-k search.
12. Keep the cursor-zero response profile full. On later strict pages, `response_profile=continuation` may omit repeated diagnostics, but it must retain items, readiness, snapshot, token, and chain evidence.
13. If the host goal already provides verified zet ids, use `--order seeded_connection_walk` with repeated `--start-zettel-id`; never invent a seed, and still read every disconnected component.
14. Keep `projection=reading` for compact coverage. Use `routed_reading` with seeded order only when the human or host needs each item's seed/tie/component reason and can afford the larger payload.
15. Use the returned abstracts, ties, and edges to choose a useful body-reading order. A search result or one truncated page is never full coverage.
16. Read selected zet bodies with `read-zettel --section overview` first, then `--section document|body` when the host task needs the body. For a large body, use bounded pages and bind every continuation to the first page's complete body SHA-256.
17. Read object manifests only when file metadata is needed.

## Write Policy

- Search with `archive search <archive-root> <query> --count-total --format json`; raw grep and raw SQL are not authoritative WOM search results.
- If search, view, or mint returns `archive_index_rebuild_required`, stop and run an explicit `archive index <archive-root> --progress --format json` followed by `archive index-health <archive-root> --dry-run --progress --format json`; never trust stale rows or silently scan every body.
- When Doctor reports a possible inbox pipeline bypass, inspect it with `archive inbox-pipeline-audit <archive-root> --dry-run --format json`; its classes are review signals, not proof, and authorize no automatic repair.
- Before suggesting artifact cleanup, run `archive artifact-lifecycle-inventory <archive-root> --dry-run --format json`; incomplete coverage blocks absence claims, and no inventory class or age grants deletion authority.
- Create AI-generated zettel drafts only with `archive create-draft` dry-run followed by its exact human-reviewed replay. Never write Markdown directly into `inbox/`.
- AI-assisted or AI-generated drafts require an explicit reviewed abstract and at least one stable facet. If the same normalized title already exists in `inbox/`, revise that draft in place instead of creating another file.
- A request to publish starts the `mint-zet --dry-run --progress` preview workflow now. Progress is stderr evidence, not the final result. Report blockers or a remaining approval gate immediately, and claim completion only after canonical plus receipt evidence exists.
- Use the official dry-run and approval routes for `mint-zet`, `zettel-edge`, source/objet intake, and operational-context updates; knowing a destination path is not write authorization.
- For a persistent saved view, prepare a reviewed private request under `.wom-scratch/private/saved-views/`, preview `archive saved-view-write`, and use only its exact approval-gated write or revert route. Never edit persistent `views/*.yml` directly.
- Do not import private personal sources unless the workpack explicitly permits it.
- Prefer sanitized derivative records when personal insight informs company work.
- Preserve handover, provenance, and visibility fields.

## WOM-kit Updates

- Start long `project-version-update`, `index`, and `index-health` work with a fresh command-appropriate `--output` and preserve its early `operation_ref`. After caller timeout, use read-only `operation-control` status, bounded wait, or recovery-plan with the exact starting root; never start a duplicate writer. Cancel/resume, MCP control, daemon, queue, background launch, force kill, and lock deletion are unsupported.
- When available, use `project-version-update --dry-run` first. Before Windows approval, pause editors, sync/backup clients, and other Git writers for the complete transaction, then use `--approve --reviewed-by <actor> --affirm-external-writers-quiescent`; do not hand-edit the source checkout or installed-version pins.
- After `updated_restart_required`, start a new process and require `archive version` import/source/pin/tag agreement before claiming the new runtime is active. Never bypass a dirty-state, tag, metadata, lock, or rollback blocker.
- `archive version` proves local runtime/source/pin and already-fetched tag state only. Check an authoritative remote release surface separately before claiming that no newer release exists.

## AI Intake Protocol

- BEFORE copying any local file into the archive or an objet store, run `archive source-intake <archive-root> --dry-run --local-path <file>` and follow its `next_safe_actions`.
- Stage capture candidates inside the archive root under `staging/incoming/`, never in a raw in-root `objets/` folder.
- Capture only via `objet-capture-selection` -> `objet-capture` with explicit owner approval; real archives also need an owner-approved `objet-capture-enable` record.
- Bulk external stores are not per-file copies: register evidence with `prehashed-objet-ledger` and `object-storage-upload-evidence` instead.

## AI-Operator Discipline

- ARTIFACT PRIMACY AND HUMAN DRIFT: treat durable, time-situated artifacts and chronology as primary evidence. `canonical` means the current human-reviewed state, not objective truth. Matching names or labels never authorize a silent identity merge; connections and generated maps are reviewable reading aids. Preserve contradictions and changed meanings with provenance.
- PROVENANCE FIDELITY: record the source the human ACTUALLY encountered — the exact video, edition, translation, or language they saw. Never silently swap it for a "more authoritative" or "original" source. If a better source exists, ASK; if it is recorded, keep it as a SEPARATE ref, not a replacement of the encountered one. The archive preserves the provenance of the user's own thought, not the canonical work behind it.
- ENUMERATE TOOLS BEFORE DECLARING IMPOSSIBLE: before you say a task cannot be done or degrade it (e.g. "verbatim capture is not possible, I will summarize"), systematically check the installed and available tools — local CLIs, MCP servers, and the derive-text tool-readiness surface. Do not conclude "impossible" from one or two probes.
- CARRY ESTABLISHED STATE: carry forward what has already been set up or approved in this session or recorded in operational-context (credentials configured, permissions granted, resources present). Do NOT re-ask for or re-confirm already-established state as if first-time. When unsure, CHECK the recorded context (operational-context, receipts) before asking again.

## Plain-Language for Humans

- When you address a HUMAN, translate git/infrastructure/WOM-internal jargon into everyday language; keep the exact technical term in parentheses or in the logs only.
- Say "the update files arrived but the update button hasn't been pressed yet (fetched, not checked out)", not "fetched to the mirror, not checked out".
- Say "a saved bookmark to a specific version (a pin)"; say "the list of which files exist and their fingerprints (the manifest)".
- This governs human-facing prose only. Machine, JSON, and receipt output stays exact and unchanged.

## Confidentiality

Company records must stay within authorized company, team, project, or handover archives.

The company can own an archive while founders, employees, or roles operate it. Business-unit exit, spin-out, or ownership transfer must be recorded with explicit receipts.
