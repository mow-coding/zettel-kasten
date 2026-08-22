# Archive infrastructure decision log - v0.4.5 local recovery

## Receipt evidence is candidate authority, not target invention

Context: 508 Notion-page Objets are durably captured, but the old source map has
only three rows and none links those objects to canonical zettels. The capture
receipt still retains the original source identifiers and paths.

Decision: build one content-free, receipt-driven candidate index. A unique
match on a target's own preserved source identifier may enter an exact-operation
manifest. A title-only match is review evidence. No match is `no_target`; it is
not a reason to re-capture or create a zettel automatically.

Consequence: the current Basoon snapshot truthfully classifies all 508 items as
`no_target`. Future archives with preserved source IDs can batch-plan exact
links without 508 approval dialogs, while ambiguous or provenance-free cases
remain under human review.

Longer record:
`meeting-minutes/2026-08-22-v045-local-recovery-inventory.md`.

## Population totals are verified evidence, not release targets

Context: Letter 144 reports 2,144 target zettels and 7,172 locator pairs. The
current local mirror reproduces the 2,144 target zettels but its complete unique
set contains 7,171 pairs after subtracting the 525 pairs already represented by
the 110 validated sidecar zettels from the 7,696-pair source population.

Decision: preserve the verified 7,171 set digest, and make an expected count of
7,172 a blocking mismatch. Never synthesize, duplicate, or weaken validation to
make a historical report total balance.

Consequence: integration must reconcile the one-row discrepancy before making
a 7,172 completion claim. The independent 2,144-zettel population remains
verified and the 7,171 present pairs remain fully classified.

## Local recovery is field-bound and receipt-bound

Context: whole-file drift after a legitimate title change caused all 2,769
title receipt items to appear globally blocked. Similarly, missing locator
markers must be attributed to the exact markup transactions that removed them,
not to any zettel that happens to lack a marker today.

Decision: title audit and rollback bind only `frontmatter.title`; missing-marker
recovery binds the declared locator projection to each receipt's before/after
body snapshots. Identifier-title replacement requires a candidate from the
same zettel's own body and same source-mirror record.

Consequence: current evidence classifies all 2,769 title items as still applied,
all 1,061 newly orphaned rows as restore-ready, and all four identifier titles
as exact-recovery-ready without allowing unrelated body changes or neighboring
source records to authorize a write.

## Plans do not imply writes

Decision: extend existing command families with read-only plan modes and
durable population evidence, but do not connect approval/apply in this branch.

Consequence: this branch can be reviewed and merged as deterministic recovery
planning. A released build, native human approval, writer integration, resume
evidence, rollback exercise, and independent post-write verification are still
required before any Basoon data is called repaired.
