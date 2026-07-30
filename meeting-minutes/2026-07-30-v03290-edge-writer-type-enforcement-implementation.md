# v0.3.290 edge writer entity-type enforcement implementation record

- Date: 2026-07-30
- Branch: `codex/v0.3.290-edge-writer-type-enforcement`
- Starting point: `7d48aaaa5bf4ccaaeb792dd3c3341ef654d0c298`
- Status: implementation and verification in progress

## User intent

The user asked the WOM development team to continue the remaining beta and
review backlog carefully through multiple ordered releases while they were
away. Work must be complete and evidence-backed rather than rushed.

## Defect selected for this release

The generic `zettel-edge` writer accepted an active edge-type ID and resolved
both records, but did not enforce the active registry record's `from` and `to`
entity types. Because `zettel-edge-batch` delegates writable rows to this
gate, one missing safety check covered both single and batch writes.

## Plan

1. Add a strict active-link-type definition loader without weakening the
   archive-local registry authority rule.
2. Map resolved source/target records to WOM entity types.
3. Fail closed on malformed or incompatible endpoint contracts before any
   write.
4. Make the machine result bounded and content-free.
5. Add single, batch, fallback, malformed-registry, and no-write regressions.
6. Update version, public docs, decision record, and packaged resources.
7. Run focused, documentation, resource, full-suite, clean-wheel, fresh
   install, onboarding, Doctor, and public-release checks in release order.

## Parallel ownership

- Production: `wom-kit/src/wom_kit/archive_services.py`
- Regression tests: `wom-kit/tests/test_cli.py`
- Supervisor: integration, version and documentation surfaces, resource sync,
  combined review, commits, rebases, and public release

No worker was authorized to touch the beta archive, push, tag, or release.

## Implementation evidence

- Added a strict safe entity-type-list validator.
- Added one registry contract evaluator that:
  - chooses archive-local `types.yml` whenever it exists;
  - uses the packaged registry only when the local file is absent;
  - maps source to `Zettel`;
  - maps a verified target to `Zettel` or `OriginalObject`;
  - returns stable `allowed`, `blocked`, `malformed`, `unavailable`, or
    `target_unresolved` status plus fixed blocker codes; and
  - copies no registry values or parser exception text into the new fields.
- Routed all three single-edge return paths through the same
  `entity_type_contract`.
- Propagated that contract into batch item results without changing batch
  policy classification.
- Preserved batch transaction behavior: one blocked policy-writable preflight
  blocks the complete batch before any edge or receipt write.
- Added 471 lines of regression coverage for incompatible endpoints, malformed
  contracts, local authority, packaged fallback, parser failure privacy,
  valid `format_variant` targets, and mixed batch no-write behavior.

## Verification evidence

- New contract-focused unittest selection: 4 tests passed.
- Full focused edge/format-variant pytest selection: 19 tests passed and 26
  subtests passed; 1,265 tests deselected.
- Documentation contract suite: 144 tests passed.
- Packaged resource synchronization: 102 files for v0.3.290.
- Release readiness: public links, Korean product language, public privacy,
  and runtime skill all passed (4/4).
- `py_compile`, staged/unstaged `git diff --check`: passed.
- Independent standard quality review found no production defect but found
  two Medium documentation mismatches:
  1. new privacy prose could be read as claiming that the whole established
     edge result contains no refs or paths, although only the new contract and
     blockers are content-free;
  2. the capability matrix said an incompatible policy-writable row enters
     `human_review_queue`, while the transactional implementation correctly
     keeps it in `policy_writable_edges` with `write_status: blocked` and
     blocks the complete batch.
- Both documentation findings were corrected to match runtime and regression
  evidence.
- Post-fix focused edge tests (19 plus 26 subtests), documentation tests
  (144), packaged-resource check (102), readiness (4/4), compile, and diff
  checks all passed again.
- A separate post-fix review confirmed both corrected claims and returned
  PASS with no remaining High or Medium defect.

The complete source suite and exact clean-wheel lifecycle are intentionally
reserved for the final predecessor rebase. This local checkpoint is not a
public-release claim.

## Release-order boundary

This branch starts from the local v0.3.289 checkpoint. It cannot be released
until v0.3.287, v0.3.288, and v0.3.289 are each public and this candidate is
rebased onto their exact final chain.
