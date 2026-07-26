# Archive Infra Decision Log - v0.3.262 Identifier-Title Census

Date: 2026-07-26

Status: accepted for v0.3.262 implementation and release

## Context

A pilot archive reported that one import batch had left thousands of canonical
zets whose `title` is a bare hexadecimal page id. The bytes are faithful: the
source records genuinely carried that value in their title property, and the
human-readable name lived in a separate source property the importer did not
carry over. This is a missing fallback rule, not corruption, and no data was
lost.

The condition is invisible to every existing check. `zettel-frontmatter.schema.json`
declares `title` as an unconstrained string. The promotion checklist's
`understandable_title` item resolves through `title_is_specific_enough_for_checklist`,
which rejects empty titles, a fixed generic word set, and titles under five
display units — a 32-character hex string passes all three. So an archive can
hold thousands of unbrowsable titles and report itself healthy.

## Decision

1. v0.3.262 ships a census and nothing else: a read-only, archive-wide,
   frontmatter-only sweep, modeled structurally on `first_read_readiness`.
2. Detection reports two signals separately rather than collapsing them:
   - `title_matches_external_id`: the compared title equals this record's own
     imported identifier. Provenance-bound and provable from the zet alone.
   - `title_is_identifier_shaped`: the compared title is a bare hexadecimal run
     of at least 16 characters. A shape heuristic.
   Only the first identifies a source record that still holds the intended name,
   so merging them would destroy the distinction that decides what can be
   repaired.
3. Comparison uses the existing house form — casefold, then remove whitespace,
   dots, underscores, and hyphens — so a dashed uuid and its compact form
   compare equal. The 16-character floor keeps ordinary short words such as
   `deadbeef` from being accused.
4. The report never echoes a title value or an identifier value. This is the
   consistent rule across every read-only surface here, and a census of bad
   titles is exactly where it would be most tempting to break it. Keeping it
   requires more than not printing the `title` field: `make_zettel_id` derives a
   zet's id, and therefore its filename, from its title, so an attention row's
   own `path` and `zettel_id` can carry the withheld value. Both are gated by a
   single predicate and emitted as `null` with a `discloses_title` reason when
   they would reproduce the title, whole or as a prefix of identifier length.
   The count of withheld references is reported so suppression is visible rather
   than silent.
5. The disclosure predicate is title-relative, not shape-based. A shape rule
   ("withhold any reference carrying a 16+ character hex run") would also
   suppress importer-minted names — `external_import_zettel_id` produces
   `zet_import_<system>_<digest16>`, whose hex run digests the source record and
   cannot disclose a title. That is precisely the population this census exists
   for, so a shape rule would blind the report to its own subject.
6. The privacy echo guards are derived from what each emitted row actually
   carries, never asserted as literals. A hardcoded `False` cannot detect its own
   gate failing; a derived flag can.
7. Redacted zets are excluded, not judged. They expose no title to assess.
8. Zets whose frontmatter could not be read, and zets whose title is absent or
   was suppressed by the catalog as private or unsafe, are counted in their own
   buckets and block a `ready` verdict. They were not judged, and scoring them as
   human-readable would claim a check that never ran. Redaction remains a
   separate, deliberate, separately reported exclusion.
9. `counts` partitions the entries seen; `signal_counts` reports how often each
   rule fired. They are separate blocks because one zet can trip both rules, so
   the signal numbers overlap and do not sum to a count of zets. Sharing one dict
   invited a consumer to compute a rate that can exceed 100%.
10. The provenance-bound comparison consults the existing
    `NOTION_SOURCE_MAP_PAGE_REF_KEYS` vocabulary through
    `notion_source_map_ref_family_for_key`, not a hand-written key pair, and the
    report names the keys it compared. The original pair included
    `source_page_id`, a key nothing in this project writes.
11. Fields are read from the existing canonical catalog projection, so the sweep
    costs one frontmatter pass and reads no bodies.
12. The service returns the house result envelope — `blockers`, `warnings`,
    `exit_policy` — and its real `dry_run` value. It previously computed
    `blockers` to derive `ok` and `state` and then dropped it, so a library
    caller received `ok: false` with no machine-readable reason.

## What This Release Deliberately Excludes

- **No retitle.** A reviewed bulk rewrite needs preview, exact-hash binding,
  approval, receipts, and a revert path, and will be staged across its own
  releases as the abstract backfill family was.
- **No promotion-checklist change.** `understandable_title` is machine-inferred
  and not human-affirmable, so making an identifier-shaped title fail it would
  block minting such zets outright. That is a behavior change with its own
  compatibility question and deserves its own release rather than riding along
  with a read-only census.

## Verification Contract

- A zet whose title equals its own `facets.external_id` in a different format
  reports both signals with `provenance_bound: true`.
- A zet with the same shape but no identifier in frontmatter reports only the
  shape signal.
- A short hex-looking title such as `deadbeef` is not reported at all.
- A planted identifier value appears nowhere in the output in either its dashed
  or compact form, and the privacy guards report both echo flags false. The
  fixtures are named the way `make_zettel_id` would name them, covering the exact
  32-character slug, the truncated-slug case from a dashed uuid, and the
  bare-identifier-as-draft-id case that carries no `zet_` prefix to gate on. Each
  of these fails against an implementation that emits `path` and `zettel_id`
  ungated; a hand-named fixture does not, which is why the original regression
  proved nothing.
- A zet whose reference cannot disclose its title — an importer-minted
  `zet_import_<system>_<digest16>` name — still reports its path and id, and the
  withheld counts stay zero. Over-withholding is a failure too.
- A canonical zet with unreadable frontmatter produces no attention rows and
  still prevents `readiness_met`, `all_titles_human_readable`, and a `ready`
  state, and the exclusion is named in `claim_boundary.not_checked`.
- A redacted zet with an identifier-shaped title is counted as redacted and does
  not make the archive report attention.
- The partition counts plus the attention total equal `canonical_zet_count`; the
  signal counters live outside that partition and are not summable into it.
- The command exits 1 without `--dry-run`, changes no file, and a
  `needs_attention` finding still exits 0.

## Pre-Release Review

An adversarial review across privacy, detection, and scope lenses ran against the
finished implementation before release. All three returned GO-WITH-FIXES. It
found the ungated `path`/`zettel_id` echo, the readiness verdict asserted over
unjudged entries, the overlapping counters sharing one dict, the dead
`source_page_id` key, and the dropped result envelope. All are fixed above rather
than recorded as known limitations.

One review claim was not adopted as stated. The privacy lens held that the echo
leaks for 100% of listed rows because the pilot population's paths are minted
from their titles. That is true of the `create_draft_zettel` route, but
`external_import_zettel_id` names imported zets `zet_import_<system>_<digest16>`,
which carries no title-derived slug — so the leak is reachable rather than
universal, and the imported population is the safer case, not the worse one. The
distinction is load-bearing: it is the reason the gate is title-relative
(decision 5) rather than the shape-based rule the same review proposed, which
would have suppressed nearly every imported row and left the census unable to
name its own subject.

## Consequences

An archive owner can now answer "how many of my titles are actually page ids,
and which of those can be traced back to a source record" without reading a
single zet body and without any value leaving the archive. That answer is the
precondition for deciding whether a reviewed retitle is worth staging, and it
is the input a later plan command will consume.

The census does not assert that a title which is *not* identifier-shaped is
meaningful. It answers one narrow question honestly rather than a broad one
vaguely.
