# Archive Infra Decision Log - v0.3.263 Reviewed Title Remap Plan

Date: 2026-07-26

Status: accepted for v0.3.263 implementation and release

## Context

v0.3.262 shipped a census of canonical zets whose title is an imported page id
rather than a name. It counted and deliberately fixed nothing.

The pilot archive that reported the condition then asked a direct question:
should the remap be done by this project, or by a local script on their side?
They froze canonical `zettels/` pending the answer, which was the right call.

The material for a repair already exists. The source records carried a
human-readable name in a separate property; the importer had no fallback when
the title property was itself an identifier. The names did not vanish, they were
never carried over.

## Decision

1. The remap belongs on this side, not in a local script. A script rewrites
   canonical titles with no preview, no binding to exact bytes, no receipt, and
   no revert. The archive would lose its ability to answer "why does this title
   read the way it does", which is the property the whole system exists to keep.
2. v0.3.263 ships the plan rung only, modeled structurally on
   `zet_abstract_backfill_plan`: validate a private reviewed proposal against
   exact current canonical bytes, write nothing. The approved write, receipts,
   and revert are separate later releases, staged the way the abstract backfill
   family was.
3. **The command proposes no text of its own.** Every replacement comes from the
   operator's proposal file, and each row declares a `basis` of
   `source_export_property` or `human_written`. This project does not invent a
   name for a record it never saw; if no name exists anywhere a human can point
   at, the correct output is nothing rather than something generated.
4. **A row is accepted only when the current title is identifier-shaped.**
   Without this the same machinery that repairs an import failure would rewrite
   any title in the archive from a file.

   The first implementation stated this as "one the census would flag" and
   enforced exactly that — any non-empty signal list. A pre-release review
   reproduced the hole: `title_matches_external_id` fires whenever the title
   equals a registered page-ref facet value, with no shape test, so a zet titled
   `Weekly Planning Database` whose `external_id` repeats that string opened the
   gate and was additionally reported `provenance_bound: true`, which suppressed
   the very warning meant to tell a reviewer to look harder. The gate now
   requires `title_is_identifier_shaped` itself. **"The census would flag it" and
   "it is an identifier" are not the same predicate, and the narrower one is the
   one this tool needs.**
5. A replacement the census would flag is refused, checked with the full census
   predicate against the target's own facets rather than for shape alone. Shape
   alone missed a replacement equal to the record's own page-ref value — which is
   not hypothetical, since the operator's source export is exactly where a
   record's identifier and its human name can coincide. Either way the archive
   would be re-flagged the moment an approved write landed.
6. **A non-canonical target, including a redacted zet, is blocked without being
   judged.** The first implementation appended the status blocker and then went on
   to compute and publish `current_title_signals` and `provenance_bound` for it —
   i.e. it stated that a deliberately suppressed record's title equals that
   record's own imported page id. v0.3.262 excludes redacted zets for exactly this
   reason and this release now matches.
6. A replacement that fails `title_is_specific_enough_for_checklist` is refused,
   so a remap cannot introduce a title that minting itself would not accept.
7. Provenance is reported separately from shape. `provenance_bound_ready_count`
   counts ready rows whose old title was provably that record's own imported
   identifier; when it is lower than `ready_for_review_count`, the report warns.
   That gap is precisely how much the reviewer must take on the operator's
   source rather than on the zet, and collapsing the two would hide it.
8. **Neither the old title nor the replacement is echoed, and neither is a digest
   or a length of one.** The first implementation published a per-row
   `title_sha256` beside the exact `title_char_count`, reasoning that this
   followed the abstract backfill family's handling of reviewed text. The mirror
   was wrong: an abstract is paragraph-scale free text, while this command accepts
   a title as short as four display units. A pre-release review recovered a
   two-syllable Korean replacement title from the published digest and length
   alone in seconds. Salting was considered and rejected — every candidate salt in
   the envelope (`proposal.sha256`, `archive_id`) is printed in the same report.
   Both fields are removed, and `plan_digest` no longer carries a per-title digest
   either, since with the other row fields published a single-row proposal would
   be brute-forceable through the aggregate too. The proposal file's own `sha256`
   already binds every replacement collectively and a future approved write
   revalidates it. The proposal path is not echoed either.

   This is the same failure v0.3.262 fixed one rung down, where emitted paths and
   ids could reproduce a withheld title. **The rule generalizes: a value derived
   from a short human-scale string, published beside enough context to bound the
   search, is that string.**
9. The privacy echo guard is derived from the assembled payload rather than
   asserted as a literal, matching v0.3.262 rather than the older sibling. The
   first implementation reverted all nine guards to literals, which is precisely
   the anti-pattern v0.3.262 removed 350 lines above in the same module.
9. The proposal is untrusted private input: archive-relative under
   `.wom-scratch/title-remap/`, `.jsonl` only, no symlink on any path segment,
   64 MiB file ceiling, 1 MiB per row, and no content reflected back.
10. A blocked row makes the command exit non-zero. This differs from the
    readiness commands on purpose: a census reporting attention is a finding,
    but a plan that does not fully validate is not a plan.

## What This Release Deliberately Excludes

- **No write.** `approval_contract.approved_write_implemented` is `false`.
- **No source-export reading.** The command never opens the operator's export,
  calls no provider, and infers nothing. The mapping is the operator's evidence
  to produce and a human's to review.
- **No importer change.** The root cause is a missing fallback when a source
  record's title property is itself an identifier. Adding that fallback prevents
  recurrence and is a separate change with its own compatibility question; it
  does not belong in a repair-planning release.

## Open Conflict The Write Rung Must Settle First

The revert path is not simply a later release. It is an unsolved conflict between
two properties this project currently holds simultaneously, and it was identified
during the v0.3.262 design pass before this release existed:

- Abstract backfill reverts without storing any text because its change is an
  **insertion**: delete the inserted line and the original hash returns.
- A title change is a **replacement**, so a revert needs the previous title value
  to exist somewhere.
- This family's established privacy property is that **receipts never contain
  text**.

Those cannot all hold. The resolution is a decision, not an implementation
detail — candidates include storing the prior title outside the receipt in a
private local area, accepting a one-way remap with no revert, or narrowing the
no-text-in-receipts property with an explicit, argued exception. Recording it as
"a separate release" would present a design conflict as a scheduling matter,
which is the failure mode this project's release surfaces exist to prevent.

**No approved write rung ships until this is settled and written down.**

## Verification Contract

- A proposal whose row names an identifier-titled zet, with a matching
  `expected_file_sha256`, reports `ready_for_human_review` with
  `provenance_bound_ready_count` reflecting whether the old title equalled a
  registered page-ref facet.
- A row naming a zet whose title a human chose blocks with
  `current_title_not_identifier_shaped` and the command exits 1.
- A row whose zet changed after the proposal was built blocks with
  `canonical_file_sha256_mismatch`.
- A row whose replacement is itself identifier-shaped blocks with
  `title_is_identifier_shaped`.
- Neither the old identifier nor the replacement title appears anywhere in the
  output, in any form, and no file in the archive changes.

## Consequences

The pilot can now produce a mapping from the names their source already holds,
run it against their archive, and get a per-row verdict bound to exact bytes —
without anything being written and without either value leaving the archive.
What a human then approves is a plan whose every row was checked, rather than a
script whose effect is discovered afterwards.

The remaining risk is not in this command. It is that a `source_export_property`
basis is only as good as the export, and this release cannot check that. It says
so in `claim_boundary.not_checked` rather than implying otherwise.
