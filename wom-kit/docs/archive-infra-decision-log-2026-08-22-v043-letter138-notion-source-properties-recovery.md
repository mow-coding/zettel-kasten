# Decision Log: v0.4.3 Letter 138 Notion Source Property Recovery

Date: 2026-08-22

## Context

Letter 138 reports that Notion page bodies survived migration while populated
page properties did not reach canonical zettels. Earlier work added safety and
diagnostic surfaces but did not repair the historical data. The required slice
is therefore an actual local backfill with verification and field-only
rollback, not another new planning-only command family.

The private evidence contains two raw source shapes. There are 4,034 Notion
API page objects with typed property payloads and 7,551 legacy `recordMap`
pages. Of the legacy pages, 7,441 have root property dictionaries and 110 do
not. The complete source is the recursive 11,585-file block mirror, not the
separate 3,605-page DB3 JSONL.

## Decision

- Extend the existing `archive migrate` family with the fixed target
  `notion-source-properties`; add no new top-level command and expose no
  generic writer callback.
- Join only an exact normalized `source_page_id` to canonical zettels. Missing
  targets remain `unmapped`; duplicate, malformed, conflicting, or
  semantically indeterminate cases remain `review`.
- Preserve API properties with exact names, ids, types, population states, and
  raw payloads.
- When a legacy page lacks collection schema, preserve its root property
  dictionary losslessly as property-id/raw-value pairs with
  `semantics_unavailable: true`; never invent a name or type.
- Generate the acceptance profile through a first, explicit
  `--acceptance-bootstrap` pass and persist its canonical JSON bytes create-only
  below ignored `profiles/local/notion-property-backfill/`. The second plan
  must read those exact bytes and bind their digest, the complete mirror
  snapshot, aggregate property counts, source-shape and legacy-root splits,
  and normalized source-id accounting. Manual stdout copying is not authority.
- Publish that candidate with a write-through no-replace move on Windows, or a
  single-link hard-link/unlink plus parent-directory fsync on POSIX. Never call
  a two-link cleanup residue durable or usable; uncertain publication requires
  reconciliation rather than automatic retry.
- Supersede the earlier blanket `populated-unmapped` block for this bounded
  recovery only: a human may approve the certain mapped effects when every
  unresolved source and reason belongs to deterministic manifest-bound sets.
  Unmapped evidence remains untouched and explicitly unresolved; it is never a
  silent drop, success claim, or source-lifecycle guarantee.
- Treat the historical 51/904/2,810 probe only as reproduced diagnostic
  provenance. It was a 40,000-character exact-name raw-regex probe, not a
  semantic completeness contract.
- Reuse `ExactOperationManifest v1`, its approval binding, one fixed
  archive-wide writer lock, hash-chained checkpoints, final result receipt,
  authenticated resume, and field-scoped revert. Do not create a parallel
  transaction, journal, approval, or receipt system.
- Carry the complete content-free operation accounting as common
  `operation_evidence`, bound by the manifest and approval and copied into the
  stable final receipt. Applied property and populated-property totals come
  from this operation-bound evidence, not the post-write observed category.
  Normalize only adapter-owned managed-equal fields back
  to their original mapped effects so a fresh process can reconstruct the
  byte-identical manifest after a write-before-receipt crash; never normalize a
  plain pre-existing equal field.
- Give apply and revert distinct exact-human operations and distinct manifests.
  Their native labels, approval contexts, execution digests, checkpoints, and
  final receipts cannot be substituted for one another.
- Bind every effect to stable target identity plus exact field pre/post/source
  hashes. Reread the current zettel and perform exact expected-byte
  compare-and-swap so unrelated bytes are preserved and an external edit race
  fails closed.
- Verify through an independent adapter. A same-valued but unmanaged field is
  not accepted as WOM-owned post-state.
- Bind a deterministic canonical source-id/target projection and recheck it
  under the common writer lock after the resume locator hook. A late duplicate,
  deletion, lifecycle change, or target-identity drift blocks before mutation.
- Reject a prospective replacement above the canonical file-size limit during
  planning rather than after one-use approval has started.
- Emit an immediate content-free planning status and bounded heartbeat. Scan
  canonical small files through a deterministic fixed four-worker pool, read
  each file once, read the large mirror sequentially once, index canonical
  joins in memory, and sort effects deterministically.

The complete operator contract is recorded in
[Notion Source Properties Recovery](notion-source-properties-recovery.md).

## Consequences

The working-tree implementation can perform the missing backfill, resume the
same interrupted approval-bound execution, verify it, and remove only its own
field later. It does not call Notion, rewrite the source mirror, silently merge
ambiguous pages, fabricate legacy semantics, or expose private values in
result/progress documents. The `migrate` parser-error boundary is also marked
privacy-sensitive so an unknown or misspelled option cannot echo adjacent
private path values.

Parser-derived capability inventory now marks top-level `migrate` as
`approval_available` because one target is genuinely bound. That is a
conditional parser fact, not permission for every migration target. The
handler still fixed-closes every non-`notion-source-properties` approved
migration with `compound_exact_human_approval_binding_required`.

The 2026-08-22 real read-only plan completed in 240.563 seconds. It classified
8,566 mapped, 2,882 unmapped, and 137 review pages, produced 8,566 exact field
effects, and reported zero unexplained populated-property or property-type
omissions. One malformed canonical file without a `source_page_id` token was
excluded as an opaque noncandidate rather than poisoning all joins; its BOM is
tracked as v0.4.7 hygiene debt.

This decision and source implementation are not proof of acceptance-archive mutation,
merge, tag, GitHub release, tester upgrade, or post-install live verification.
Those remain explicit later steps.

Letter 138 is not fully resolved until the real archive has a private backup,
all 8,566 certain effects are applied and independently verified, a field-only
rollback drill succeeds, and the durable result keeps the 2,882 unresolved
classification receipt.
