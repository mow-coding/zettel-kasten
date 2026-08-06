# Decision: Close Letter 112 With Evidence-Bound Completion Batches

Date: 2026-08-07

## Context

The v0.3.300 beta report confirms that the integrated Letters 098-111 release
is installable and useful at real archive scale, while exposing several gaps
that cannot be solved by prose guidance alone:

- zettels can discover exact Objet references but cannot safely write a
  structured Zet-Objet link;
- imported table markup blocks normalization;
- external locators cannot distinguish service, account, or repeated
  occurrences;
- AI-authored zettels can contain execution traces or ignore archive-specific
  authoring conventions;
- an unminted draft has no approval-gated, reversible discard path;
- source-intake record paths and duplicate records do not converge cleanly;
- relation scoring recognizes coordinates, but not the coordinate names used
  by the beta archive; and
- argparse can emit only stderr even when the caller requested JSON.

A content-free census of 8,594 beta zettels showed that the current relation
projection misses the archive's actual coordinate vocabulary. In particular,
`notion_event_time_start` appears on 3,191 zettels, `source_category` on 7,289,
and `db1_category` / `db1_subcategory` on 119 / 169. No titles, body text, or
facet values were retained in this census.

The table design follows the GitHub Flavored Markdown table extension. Markup
will be parsed with Python's standard `html.parser` support rather than a
table-shaped regular expression. New and tightened schemas remain JSON Schema
Draft 2020-12 documents.

## Decision

Use one integration branch and one public release candidate, but implement and
verify the work as bounded internal batches:

1. **Deterministic boundary fixes**
   - return a content-free JSON error envelope for CLI parse failures when
     JSON output was requested;
   - resolve source-intake plan paths from the archive root;
   - make matching source-intake records idempotent and distinguish genuine
     path collisions;
   - add a non-reversible, content-free local-source identity fingerprint so
     metadata-identical local files do not collapse to one plan.
2. **Human record integrity**
   - extend the AI response and zet authoring contracts so operational traces
     stay in receipts/logs, file claims use openable references, and unminted
     drafts are edited in place;
   - warn at mint review when likely tool-execution traces remain;
   - block truncated SHA-256 Objet tokens at the object-identity checklist.
3. **Missing write workflows**
   - add digest-bound Zet-Objet link plan/write/revert behavior and a closed
     frontmatter asset schema;
   - add reversible, approval-gated unminted draft discard with exact-byte
     snapshot and immutable receipt;
   - extend external locator records with safe service/account/occurrence
     coordinates while retaining backward reading compatibility.
4. **Migration completion and retrieval quality**
   - convert conservative HTML/Notion table structures to GFM tables, blocking
     spans or nested structures that would lose meaning;
   - recognize the beta archive's time/category coordinates in relation
     scoring without echoing private coordinate values.
5. **Batch the remaining metadata-only intake gate**
   - add one strict 1-1,000-item source-intake request schema;
   - resolve relative request and item paths from the archive root;
   - bind approval to one deterministic aggregate digest;
   - write the existing redacted per-item source-intake plan records plus one
     aggregate receipt, with idempotent bounded-per-item replay and no atomic
     batch claim.

Every mutating workflow must use a fresh dry-run plan, expected digest,
explicit approval, reviewer identity, exact-byte or semantic rollback
evidence, stale-input revalidation, and content-free failure output. Existing
private corpora are evidence inputs only and are never modified by this public
release work.

## Verification and release gates

- Add focused unit and CLI regressions for every new success, stale-plan,
  duplicate, traversal, privacy, and recovery boundary.
- Run resource synchronization checks and the complete local release gate only
  after focused batches pass.
- Use one PR and the existing sharded cross-platform CI gate.
- A release is complete only after the annotated tag targets merged `main`,
  tag CI passes, the public wheel digest and size are recorded, and a fresh
  token-free isolated install passes the packaged-wheel checker.
- Do not contact beta testers automatically. Prepare one consolidated retest
  protocol after the public artifact is independently verified.

## Consequences

- The release ceremony is paid once, while implementation failures remain
  localized to small, reviewable batches.
- Table conversion prefers an explicit blocker over silent semantic loss.
- Locator repetition is represented as reviewed occurrence identity rather
  than defeated by a single-value uniqueness rule.
- Relation suggestions can use the beta archive's real coordinates, but
  category/time values remain private and are not added to generic error
  output.
- A draft can be intentionally discarded without pretending it was minted,
  and can be restored byte-for-byte from durable evidence.

## Implementation checkpoint

The bounded product batches are implemented on
`codex/letter112-completion`. Focused regressions and the 28-test completion
workflow module pass. The complete four-shard local unittest run collected
2,278 tests: 2,254 passed, 24 were conditionally skipped, and none failed. The
explicit Windows pytest-native authority run added 113 passes. Release
readiness, packaged-resource synchronization, and diff hygiene also pass for
the staged candidate.

The exact 508-item synthetic source-intake batch completed with 508 distinct
item plan hashes and 509 written files (508 ordinary item records plus one
batch receipt). Planning took 4.126 seconds, approval took 6.289 seconds, and
an exact replay converged to `already_recorded` in 10.278 seconds. This is a
metadata-only scale result, not a claim about private source bodies or
transaction-wide batch atomicity.

The public completion contract and human-run retest protocol are recorded in
`docs/letter112-completion.md` and
`docs/letter112-beta-retest-protocol.md`. Packaged resources contain 139
validated files for v0.3.301.

Early remote workflow attempts exposed a hosted-runner scheduling
boundary rather than a product failure: every matrix job that received a
runner passed, while one or more excess queued jobs were cancelled after 15
minutes without executing. The test matrix now uses the standard
`strategy.max-parallel: 1` bound and makes the test matrix depend on the fast
release gate. This admits only one hosted matrix job at a time instead of
leaving excess jobs in the external runner queue. No shard, operating system,
interpreter, test, or required aggregation gate was removed. The workflow
concurrency group also includes both
`github.workflow` and `github.ref`, preventing an orphaned retry state or a
different workflow on the same ref from occupying the old overly broad group.
Its `ci-v2` namespace deliberately separates the corrected scheduler from
already completed runs that the GitHub rerun/cancel API left as jobless
`queued` records.

This checkpoint is not a release claim. Build, candidate wheel inspection,
pull-request CI, merged-main tag verification, public asset digest/size, and a
fresh token-free install remain required release gates.
