# v0.4.5 local recovery inventory and first product slice

Date: 2026-08-22 (Asia/Seoul)

## User direction

The user approved the v0.4.3-v0.4.7 recovery sequence and resumed work after a
short pause. This branch owns the v0.4.5 local-only slice. It must use the
v0.4.3 common exact-operation foundation, must not add another console entry
point, and must not write the private Basoon archive until a released build and
a native human approval exist.

## Exact starting point and safety boundary

- Worktree: dedicated `zettel-kasten-v045-local-recovery` worktree.
- Branch: `codex/v045-local-recovery`.
- Starting commit: `f9d2ed70f86bfc46ab4b3f2664cb7edf3584c11f`.
- The private archive was inspected read-only. Its Git worktree was clean on
  `main`, tracking `origin/main`, at commit
  `8973ab96150e2c6ced87eaa8b05ae5de3cf8ee0d`.
- No provider call, approval UI, archive write, receipt write, or release action
  is authorized in this slice.
- The private absolute archive path and source filenames are deliberately not
  recorded here.

## Read-only inventory

The following counts were recomputed from the private archive rather than
copied from Letter 144:

- object manifest: 23,580 rows;
- source map: 3 rows;
- canonical zettels directory: 8,606 Markdown files;
- the target Objet capture receipt contains 508 successful item records;
- every capture item retains an object id, source staged path, original
  filename, and source-intake plan digest;
- every one of the 508 original filenames retains one unique source page UUID;
- none of those 508 UUIDs occurs in a canonical zettel;
- exact normalized original-filename-title matching also produces zero
  canonical targets;
- therefore the current evidence proves 0 exact one-to-one links, 0 ambiguous
  title matches, and 508 `no_target` outcomes. This is not permission to
  re-import the 508 already-captured objects.

Letter 144's other v0.4.5 facts were also checked against the current command
surface:

- `zettel-objet-link` has an exact-human-approved single-item writer, but no
  receipt-driven batch planner;
- the locator loss audit only returns zettels whose body still contains an
  omission marker, so it cannot classify the 1,061 frontmatter occurrences
  whose markers disappeared;
- external locator record and all relevant revert writers remain in the fixed
  compound-approval closure;
- title remap receipt audit is receipt-global, which allows one divergent
  generation to hide the item-local state needed to remove a global blocker.

## First complete product slice

Extend the existing `archive zettel-objet-link` family with a mutually
exclusive receipt-recovery dry-run mode. It will:

1. validate one official completed Objet capture receipt by a stable,
   archive-contained read;
2. validate the complete object manifest once and require one exact manifest
   record for every linkable object;
3. index canonical zettels once by preserved source identifiers and normalized
   title without returning private source values;
4. classify every capture item as `exact_link_ready`, `already_linked`,
   `review_required`, or `no_target`;
5. treat title-only evidence as review evidence, never automatic authority;
6. build an `ExactOperationManifest v1` only for unique source-id matches whose
   `assets` field can be changed safely;
7. expose only ordinal/count/digest/state evidence. Page titles, original
   filenames, source paths, source IDs, and provider locators remain absent
   from output.

This slice intentionally implements planning, complete classification, and
exact-manifest construction only. `--approve` with a capture receipt remains
fixed closed until the common manifest runner is connected to the existing
zettel-Objet writer and independently reviewed. A read-only planner that says
508 `no_target` is a real result; it does not pretend that the links were
written.

## Test design

- synthetic exact source-id match produces one exact-manifest item;
- title-only unique match is review-required, not auto-linkable;
- absent and ambiguous targets are fully classified;
- already-linked targets are not added to the manifest;
- malformed, aborted, foreign-archive, symlinked, oversized, or duplicate-key
  receipts fail closed;
- missing or duplicate object-manifest records cannot become exact links;
- output contains none of the private filename/path/title/source-id fixtures;
- CLI mode validation forbids mixing receipt recovery with the existing
  single-link mode and forbids receipt `--approve`;
- final read-only acceptance runs against the real 508-item receipt and must
  satisfy `exact + already + review + no_target == 508` with no writes.

## Implemented checkpoint result

The first slice was implemented under the existing `zettel-objet-link` parser
path as `--capture-receipt ... --dry-run`. Receipt approval remains explicitly
closed. The planner emits content-free progress stages and a ten-second
heartbeat when `--progress` is selected.

Focused verification at this checkpoint:

- 5 new receipt-recovery unit/CLI tests passed;
- 25 pre-existing Letter 140 link service/CLI tests passed unchanged;
- the real private 508-item receipt completed read-only in 55.109 seconds;
- real classification: exact-link-ready 0, already-linked 0,
  review-required 0, no-target 508;
- classification sum: 508 of 508;
- canonical zettels indexed: 8,606, unreadable: 0;
- object manifest rows validated once: 23,580;
- no exact manifest was emitted because there is no evidence-bound target;
- the receipt size and modification time remained unchanged;
- every privacy guard reported no echo, provider call, object-byte read, or
  write.

This is a planning/classification checkpoint, not a v0.4.5 completion claim.
The 508 links remain unwritten because the archive presently contains no
evidence-bound canonical targets for those captured pages.
