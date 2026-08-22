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
