# Beta and Fable backlog reconciliation after v0.3.290 checkpoint

Date: 2026-07-30

## User direction

The user asked the WOM development team to continue the large remaining beta
tester and review backlog carefully while they were away, producing ordered
releases rather than one rushed bundle.

The beta archive remains read-only. Engineering changes belong in the public
WOM repository; private real-use execution remains a later beta validation
step.

## Reconciliation method

A read-only audit compared:

- the post-v0.3.264 implementation handover;
- the latest Fable code review;
- beta feedback letters 101, 102, and 103;
- current source and public documentation; and
- the v0.3.287 through v0.3.290 release candidates.

No WOM command was run against the beta archive and no provider was accessed.

## Engineering already public through v0.3.286

- Interrupted multi-zet title writes gained private journals, audit, recovery,
  exact-byte preservation, and receipt-backed revert.
- Title proposal diagnostics, length handling, privacy categories, and
  human-written-title support were implemented.
- Event/activity-group membership gained read-only planning plus
  approval-gated add/remove and recovery.
- AI operator guidance gained explicit command routing and an inbox bypass
  audit.
- New exact Notion manifest items can use a safe top-level lowercase `index`
  title fallback when the normal title is identifier-shaped.
- `format_variant` became an active manual-only
  `Zettel -> Zettel | OriginalObject` type without inference or corpus
  reclassification.

These items still need representative private real-use validation, but they
are not open public-code gaps unless that evidence finds a defect.

## Candidate-only release chain

The following work is implemented but not yet all public:

1. v0.3.287: read-only Notion locator occurrence evidence validation;
2. v0.3.288: content-free MCP failure envelope;
3. v0.3.289: exact wheel packaged-resource integrity; and
4. v0.3.290: active edge registry endpoint entity-type enforcement.

They must be released in that order, with each later candidate rebased onto
the exact public predecessor and reverified from a clean tree.

## Genuinely open engineering

The audit found these remaining categories:

- `sequence` meaning and activation policy;
- third-party `Principal` registration and storage;
- recurring institution/program versus individual event instances;
- canonical representation for 77 course-coordinate records;
- canonical locator restoration after the read-only evidence step;
- a safe adoption/readiness path for existing archive `AGENTS.md`;
- a saved-view writer;
- abstract-batch cross-basis participant arbitration;
- a product decision on whether identifier-shaped titles must block mint;
- low-priority Fable audit/test-precision debt.

## Decision boundary

The following must not be guessed during unattended implementation:

- whether weekly installments should use `sequence`;
- whether third-party real-world entities belong in `Principal`;
- whether recurring programs need their own series/institution anchor;
- whether identifier-shaped legacy titles should block mint; and
- whether course coordinates belong in title, facet, or a separate entity.

Safe read-only assessment releases can gather evidence, but semantic
activation and canonical writers require a human decision first.

## Next feedback loop

1. Finish the public v0.3.287–v0.3.290 chain.
2. Separate beta-validation-only items from code gaps.
3. Prefer a read-only evidence/assessment release for the next unresolved
   representation problem.
4. Ask the user only for semantic product decisions that materially change
   canonical data.
5. Keep canonical restoration writers behind exact evidence, dry-run,
   approval, receipt, recovery, and revert boundaries.
