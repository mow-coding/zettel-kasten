# WOM v0.3.312 Letters 120, 121, and 123 triage and implementation record

Date: 2026-08-10 KST

## User intent and working style correction

While the v0.3.311 Letter 118/119 release was still being completed, the user
forwarded Letters 120, 121, and 123 from the read-only source archive. The user
repeated that correctness may take time, but the work must remain efficient and
must not be stretched into unnecessary batches. The user then left for a meal
and explicitly asked Codex to continue working rather than pause.

The implementation response is therefore deliberately sequential at the
release boundary and parallel only inside bounded, non-overlapping components:

1. finish the already validated v0.3.311 release without changing its scope;
2. audit all three new letters read-only while v0.3.311 CI runs;
3. group only the defects that share one technical authority; and
4. keep the independent source-fidelity contract out of the index patch.

## Workspace and source boundary

- Development root: the local `zettel-kasten` development checkout.
- v0.3.312 worktree: the isolated `letter120-123-zettel-kasten` worktree.
- Branch: `codex/v0.3.312-letter120-123` from exact merged v0.3.311 main commit
  `e2eec2fb60aa8ccce43152724106fd282a7d0801`.
- The source archive and all beta-tester letters are read-only evidence.
- No source-archive zettel, index, receipt, feedback body, provider, credential,
  or external service may be modified or invoked during development tests.

## v0.3.311 closeout checkpoint

Before starting v0.3.312, PR 54 passed every Linux and Windows CI shard and the
required aggregate gate. It was squash-merged into main. The main push and the
annotated `v0.3.311` tag each passed the release gate. The public GitHub Release
was published with one wheel. A fresh public download had size 1,705,591 bytes
and SHA-256
`ac18630c6c6c3a5c0c889bf24c8e589673f5b185369f70e60dcb2a197d169d0b`;
an isolated installation reported version 0.3.311. The task worktree and branch
were removed, and local `main` matched `origin/main` before this branch began.

## Letter 120 finding

The beta tester asked for the two most recently WOM-minted, Break Silence
canonical zets. The official index-backed readers returned a plausible but
wrong answer: one draft and its canonical twin, while omitting the newer second
canonical. `index-health` independently proved one missing canonical row, one
extra retired-draft row, and a blocked index. `view-zets` and `search` nevertheless
treated the stale index as successful authority.

The same letter also reports an independent gap: the operator-feedback tools
manage lifecycle metadata and receipts but do not compose or validate a body,
required sections, privacy, reproduction evidence, or a body hash binding.

## Letter 123 reproduction

The reported `mint-zet --dry-run --format json` timeout is reproducible without
using the real archive. The CLI emits no stdout or stderr until the service
returns. The duplicate check reads every canonical body from SQLite, stats the
complete live zettel tree, and, when one stat is stale, repeats the strict stat
preflight and reads every canonical Markdown body from disk.

A temporary synthetic fixture with 8,599 canonical files and one inbox draft
produced the following content-free evidence:

- current index: 0.807 seconds, one stat pass over 8,600 paths, zero canonical
  body parses;
- one canonical mtime changed: 17.964 seconds, two stat passes, exactly 8,599
  canonical body parses; and
- actual CLI: 17.909 seconds total, first stdout byte at 17.872 seconds, and
  zero stderr bytes.

The temporary fixture was automatically removed. The real source archive,
network, provider, and credentials were not used.

## Letter 121 triage

Letter 121 caused no actual data loss because the tester refused to create or
mint the AI-shortened draft. The code nevertheless has a reproducible
guardrail gap: `create-draft` accepts the supplied body without comparing it to
a source transcript, and mint verifies draft stability rather than source
fidelity. Some AI-assisted draft paths can write without a universal explicit
approval replay. A shortened draft could therefore become canonical even
though the user requested verbatim personal preservation.

This is a P1 prevention contract, but it does not share the index authority of
Letters 120 and 123. It remains the next independent implementation after this
release: explicit `verbatim`, `faithful_summary`, and `sanitized_derivative`
modes; source/body digest binding; and human approval replay for every
AI-generated draft.

## v0.3.312 decision

The release closes two bounded contracts:

1. one fail-closed generated-index freshness authority shared by index-backed
   query and mint duplicate planning, plus exact mint/retirement index lifecycle
   updates, structured recent/native canonical filters, bounded duplicate
   candidate reads, and content-free mint progress; and
2. a companion operator-feedback body request, compose, check, digest, privacy,
   approval, and lifecycle-record binding contract.

Stale, legacy, incomplete, unsafe, or dirty index state must never trigger a
silent whole-corpus body fallback or an `ok: true` query. It must return the
fixed rebuild-required boundary. Full rebuild remains an explicit operator
action; WOM does not silently scan or mutate the real archive.

## Implementation feedback loop

1. Freeze public service and CLI signatures before parallel edits.
2. Implement index schema/freshness, bounded duplicate candidates, lifecycle
   deltas, and structured query projection in `archive_services.py`.
3. Implement JSONL progress and CLI argument/result contracts in
   `archive_cli.py`.
4. Implement the feedback body companion contract in an isolated module.
5. Run focused tests for each component, then cross-component and predecessor
   regressions; inspect failures before expanding scope.
6. Update schemas/resources, runtime guidance, public docs, release notes, and
   version surfaces only after implementation contracts stabilize.
7. Perform independent security and operational-honesty review, full release
   gates, wheel/fresh-install checks, PR CI, tag/release evidence, and owned
   cleanup before declaring v0.3.312 complete.

## Final source checkpoint before full release gates

The three implementation lanes converged without writing the source archive:

- the generated index now has an explicit v0.3 `current|dirty` generation
  authority, bounded duplicate candidates, structured view fields, and
  dirty-before-file-mutation closeout;
- mint progress has an immediate content-free event and bounded heartbeats on
  stderr while stdout remains one final result; and
- feedback-body planning, approval, checking, privacy filtering, receipt
  binding, tracked-private-request rejection, and runtime routing are wired.

The security feedback loop found and closed stale-row success, silent
whole-body fallback, post-write false-current closeout, concurrent replacement
overwrite/delete, body/receipt final-verification drift, malformed YAML and
Unicode escape paths, secret-shaped public projections, inaccurate Git-ignore
parsing, and force-added private request acceptance. A narrow final independent
review reported zero remaining P1 blocker. Its remaining P2 boundary is the
portable pathname race in which a hostile same-user process swaps a validated
output parent before create/link; public docs therefore require external-writer
quiescence instead of claiming handle-bound atomicity.

A final post-review pass then found one undefined-variable check inside the
no-delta index reseal helper used after an exact failed-write cleanup. The two
unrelated references were removed. A direct regression now commits a dirty
intent, reseals the unchanged live tree under the same generation, and proves
the index returns to current. The dedicated v0.3.312 lifecycle module passed
13/13 after the correction, and the independent reviewer found no further
release-blocking P1 issue in the resulting diff.

Focused evidence at this checkpoint includes 85/85 lifecycle, CLI, feedback,
runtime, and rediscovery tests; 199/199 capability, predecessor, checkout-shim,
and wheel-resource tests; 21/21 dedicated feedback-body tests; and the 8,599-row
candidate test with one SQL candidate and zero canonical-body reads. Full
unittest shards, CI, release readiness, wheel/fresh-install, exact-tag, and
public-download verification remain required before release completion.

No production archive, Basoon source, Notion provider, credential store, or
external service was changed or invoked.
