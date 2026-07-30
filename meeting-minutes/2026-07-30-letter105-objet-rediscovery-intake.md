# Letter 105 — Objet Rediscovery Intake And Release Slicing

Date: 2026-07-30

Status: accepted into the WOM engineering backlog; implementation is split
into bounded follow-up releases.

## User Intent

The user asked the WOM developers to read the new beta-tester letter carefully
while continuing the existing release train. The specified letter was read in
full and only through a read-only filesystem operation. No WOM command was run
in the beta archive and no beta file was changed.

## Incident Classification

The preserved source object was not lost. The incident combines several
different failures that must not be collapsed into one label:

1. **AI operating-procedure failure.** The first search skipped WOM's official
   `ai-start-here -> search -> read-zettel -> zettel-objet-links ->
   resolve-objet-ref` route and generalized one failed lookup into a global
   absence claim.
2. **Existing-archive guidance adoption gap.** Current routing exists for new
   templates, but an older archive or host can begin with neither the runtime
   Skill nor current `AGENTS.md` routing.
3. **Objet source-metadata/index gap.** The prehashed registration path
   preserves hashes, size, MIME when available, and storage labels, but
   intentionally does not ingest original row values such as filenames or
   source attachment provenance.
4. **Resolver scope gap.** The resolver understands archive-relative local
   candidates and safe external labels. It has no approved registration
   lifecycle for an out-of-archive local content-addressed store.
5. **Negative-claim gap.** Ordinary index search can prove its own result-set
   completeness, but it cannot prove that every applicable source record,
   external local store, unrecovered-reference ledger, or remote evidence
   layer was checked.
6. **Preservation-reporting gap.** Successful-object storage integrity and
   source-reference recovery coverage are separate axes and may truthfully
   have different completion states.

## Direct Source Finding

The reported `referenced_objets_count` contradiction is reproducible from the
current implementation design without reading beta content:

- `zettel_objet_links` scans the complete valid frontmatter and body for object
  tokens.
- `collect_referenced_objets`, which supplies overview/catalog tie counts,
  scans `assets`, `source_refs`, and `source_intake`, but not `edges`.

An objet referenced only by an `embed -> sha256:...` edge therefore appears in
`edges_preview` and `zettel-objet-links` while the tie count remains zero.

## Release Slicing

The work should remain incremental and fail closed:

1. **Tie-count correctness.** Make overview/catalog objet counts include valid
   objet edge targets and add exact regressions. No label or migration claim.
2. **Existing guidance readiness.** Add a read-only readiness surface for
   runtime Skill and current archive guidance/routing, including the official
   feedback-plan first step. Do not overwrite an existing `AGENTS.md`.
3. **Objet rediscovery evidence plan.** Add a read-only query planner/result
   taxonomy that names every checked layer and returns
   `search_incomplete` rather than global absence whenever an applicable layer
   is unavailable or unchecked.
4. **Private source-metadata contract.** Define a separately reviewed,
   provenance-bound original-name/attachment metadata record and normalization
   rules. Do not rename content-addressed bytes and do not expose private names
   on public surfaces.
5. **Metadata registration and search.** Add approval-gated ingestion only
   after the read-only contract is stable, then index the private metadata and
   provide a bounded read-only objet finder.
6. **Reviewed external-local-store lifecycle.** Add a dry-run-first,
   approval-bound store-root registration with path, symlink/reparse, digest,
   privacy, and revocation boundaries before the resolver can hash or open
   bytes outside the archive root.
7. **Source-reference coverage audit.** Keep successful object/disk/remote
   integrity separate from total source-reference recovery and residue
   counts. Never emit a global zero-loss claim when source coverage is
   incomplete.

## Read-Only Capability Gap Audit

An independent source audit mapped the letter to the current implementation
without reading or running WOM against the beta archive.

- Runtime guidance already exposes official search order through
  `runtime_context_read_action_routes()`, current first-command/runtime-order
  guidance, and `runtime_skill_status()`. The gap is archive-specific
  readiness: no read-only surface currently says whether an existing
  `AGENTS.md` and host Skill are current, missing, outdated, or deliberately
  user-owned. Operator feedback is recommended in the runtime order but is not
  yet an authoritative read/write action route.
- Prehashed registration intentionally maps only SHA-256, size, and MIME and
  records `row_values_ingested: false`. Local reviewed capture has richer
  filename metadata, so discovery behavior differs by ingestion route. Adding
  private names to the generic manifest/index would risk leaking them through
  ordinary CLI or MCP search snippets.
- `search.complete` correctly describes completeness inside the indexed result
  set. It cannot prove that source records, a future private-name index,
  approved external stores, unresolved-source ledgers, and remote evidence
  were all checked. A new checked-layer taxonomy must preserve the existing
  field's meaning and return `search_incomplete` whenever an applicable layer
  is unavailable, unchecked, blocked, or truncated.
- `resolve_objet_ref()` currently handles archive-relative candidates and safe
  external labels. Existing local-source-root support is a scan/import
  facility, not an approved external content-addressed-store trust lifecycle.
  Any future store support therefore needs a private root binding, plan digest,
  approval/revocation receipts, reparse and drift checks, an exact CAS-derived
  single-object path, and immediate SHA-256/size verification.
- Existing source-ref metadata summaries and derived-text coverage are
  intentionally narrower than archive-wide source-reference recovery. A new
  bounded census must report `storage_integrity` and
  `source_reference_coverage` as independent axes and avoid echoing raw source
  refs, paths, filenames, provider locators, or secret-like values.
- Existing safe-label helpers are fragmented by surface. There is no reviewed
  object display-label contract, privacy class, precedence rule, or ambiguity
  behavior. Human labels must remain additive aliases; matching labels must
  never merge objects or replace the SHA-256 identity.

The audit identified the following dependency-safe follow-up numbering after
the bounded v0.3.292 tie-count correction:

1. **v0.3.293 — guidance readiness and feedback routing:** read-only
   Skill/`AGENTS.md` readiness plus authoritative feedback routes; no install
   or existing-file rewrite.
2. **v0.3.294 — rediscovery evidence plan:** checked-layer taxonomy and
   fail-closed `search_incomplete`, while preserving `search.complete`.
3. **v0.3.295 — private metadata and safe-label contract:** schemas,
   normalization, privacy classes, provenance, and ambiguity rules only.
4. **v0.3.296 — approved metadata registration and bounded finder:**
   dry-run/approve/receipt ingestion and a private search projection.
5. **v0.3.297 — external-local-store registration lifecycle:** private root
   binding, fingerprinting, approval, and revocation without opening object
   bytes.
6. **v0.3.298 — external-store resolver verification:** exact one-object CAS
   resolution with safe-open, hash/size, drift, and reparse enforcement.
7. **v0.3.299 — source-reference coverage audit:** bounded recovery census,
   residue classification, and explicit separation from storage integrity.

This order prevents a metadata writer from preceding its privacy contract, an
external resolver from preceding its approved trust root, or a zero-loss claim
from preceding complete applicable-layer accounting.

## Hard Boundaries

- No automatic rewrite of an existing `AGENTS.md`.
- No unapproved scan of arbitrary folders outside the archive.
- No automatic download or provider call.
- No physical object rename from SHA-256 to a human filename.
- No public echo of private original filenames, source identifiers, local
  absolute paths, provider URLs, tokens, or secret values.
- No replacement of an unrecovered source reference with a guessed file.
- A zero-result index search is not evidence that the object does not exist in
  every source or storage layer.

## Feedback Loop

For every follow-up release:

1. record the exact bounded contract;
2. implement and add regressions;
3. run focused and complete suites;
4. obtain independent adversarial review;
5. rebase onto the exact public predecessor;
6. verify the exact merged commit, wheel, tag CI, public artifact, and fresh
   install;
7. leave semantic real-use validation to the beta tester after publication.
