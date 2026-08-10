# Letters 120 and 123: index authority, mint progress, and feedback bodies

Status: v0.3.312 source implementation complete in the isolated release
worktree; full-suite, CI, exact-tag, wheel, and public-install evidence remain
release gates rather than source claims.

Date: 2026-08-10

## What the beta reports proved

Letter 120 showed two separate product gaps:

1. generated-index readers could return a plausible successful result from
   stale rows; and
2. operator-feedback metadata could exist without a checked feedback body that
   preserves the environment, task, observed failure, suspected cause,
   requested resolution, and reproduction steps.

Letter 123 showed the opposite index policy in mint planning. When the generated
index was stale, mint duplicate detection silently fell back to a complete live
scan and body parse. The CLI emitted no progress until that work finished, so a
correctly running dry-run looked frozen and could exceed an agent timeout.

The controlled reproduction used a temporary synthetic archive, not a user's
archive. With 8,599 canonical zets and one inbox draft, a current index completed
the mint preview in 0.807 seconds with one 8,600-path stat pass and no canonical
body parse. Touching one canonical mtime made the index stale; the same preview
took 17.964 seconds, performed two stat passes, and parsed all 8,599 canonical
bodies. In the actual CLI harness, stderr remained empty and the first stdout
byte arrived at 17.872 seconds of a 17.909-second run.

These measurements explain the beta tester's longer real-archive observation
without reading or modifying that archive.

## One fail-closed index authority

The v0.3.312 contract gives index-backed zettel readers and mint planning one
shared freshness decision. A usable index must have current schema metadata,
an explicit `current` state, one generation identifier, a complete build, and a
live path/stat snapshot that still matches the archive.

That fast gate is intentionally body-free. It detects ordinary path, size, and
nanosecond-mtime changes, but not an unmanaged same-size content rewrite whose
mtime is deliberately preserved. Rebuild after external tools that preserve
both values rather than treating the generated index as primary evidence.

Missing, legacy, incomplete, dirty, unsafe, or mismatched evidence returns the
fixed blocker:

```text
archive_index_rebuild_required
```

The command does not silently trust stale rows and does not silently repair the
problem by scanning every body. The operator runs one explicit index rebuild,
then checks `index-health` before retrying the original command.

This is deliberately fail-closed. A generated index is disposable, but a
successful query or mint decision is an authority claim and therefore needs
current evidence.

## Mutation and crash boundary

Supported mint and retirement mutations mark the index dirty before the file
lifecycle can make its previous snapshot stale. They return the index to
`current` only after the exact SQLite delta and generation closeout succeed.

SQLite transactions protect the changes inside the database. They cannot make
the separate Markdown file, receipt file, and SQLite database one atomic unit.
If a process or machine stops between those systems, WOM keeps an honest dirty
or incomplete state and requires reconciliation instead of reporting a clean
success.

## Bounded duplicate planning

A current index stores normalized title and bounded body-prefix digest fields,
plus canonical publication fields needed by the structured reader. Mint
duplicate planning asks SQLite for indexed candidates and reads only the target
and bounded candidates. It does not select every canonical body and it has no
whole-archive live-body fallback.

`view-zets` can select status, origin, and mint-time bounds, choose a supported
sort order, and deduplicate by zettel id. Canonical WOM-native records can
therefore be requested directly instead of inferred from path order or file
mtime. Search and view commands return no results when the shared current-index
evidence is unavailable.

## Progress and output channels

`mint-zet --progress` is optional. It emits an immediate content-free start
event and bounded heartbeats to stderr while reserving stdout for exactly one
final command result.

For `--format json --progress`, every stderr line is one UTF-8 JSON object. The
public fields are limited to stage/event labels, safe counts, elapsed time, and
the last completed stage. Paths, ids, titles, body text, queries, raw exception
text, and private values are not progress fields. A progress-rendering failure
does not change the mint decision or the final result.

## Feedback-body companion contract

The feedback body is a companion to the existing lifecycle metadata record. It
does not turn a metadata listing command into a body reader.

An ignored-local request declares exactly one feedback id, one title, and six
required sections:

```text
environment
task
observed_failure
suspected_cause
requested_resolution
reproduction
```

Planning is write-free and content-free. It binds the exact request to a
SHA-256 plan and returns section-presence and byte-count evidence without
echoing the title, body, request path, or rejected value. Approval reparses the
same request, requires the expected plan digest and a reviewer, and creates the
Markdown body and receipt without overwriting an existing authority.

The checker validates the body structure, content digest, privacy boundary,
and the lifecycle record's exact `feedback-body-sha256:<digest>` reference.
Having a body without that lifecycle binding is incomplete evidence, not a
ready or delivered feedback item.

The request must be under the exact ignored-local request directory. In a Git
worktree, a file that was already force-added or otherwise tracked is rejected
even when `.gitignore` contains the local-profile rule; ignore syntax is not a
privacy boundary for a tracked file.

## Source verification checkpoint

The finalized focused batches cover the v0.3 index lifecycle, 8,599-row bounded
candidate proof, mutation crash windows, CLI progress/output contract,
feedback-body privacy and replay, runtime routing, rediscovery fail-closed
behavior, public capability documentation, predecessor surfaces, and wheel
resource integrity. Independent review found no remaining P1 release blocker.

This checkpoint is deliberately narrower than a release claim. Full unittest
shards, CI, release readiness, wheel build, fresh installation, exact-tag, and
public-download evidence are recorded only after they actually complete.

## What v0.3.312 does not claim

- It does not automatically scan or migrate a user's real archive.
- It does not prove that any particular beta archive has been rebuilt.
- It does not submit feedback to an external service or prove human receipt.
- Its privacy gate rejects fixed known secret, provider, contact, and local-path
  shapes; it is not a complete data-loss-prevention classifier, so human review
  remains required.
- It rejects existing symlink/reparse output parents but does not claim to
  defeat a hostile same-user process racing to replace a directory during the
  write.
- Approved mint/promotion path owners must remain quiescent. Failure cleanup
  rechecks file identity and digest before unlinking, but portable unlink is not
  an expected-inode compare-and-swap; a mismatch is preserved and leaves the
  index dirty.
- It does not make files and SQLite one cross-filesystem transaction.
- It does not implement Letter 121's separate source-to-draft fidelity modes.
- Source tests do not replace CI, exact-tag, wheel, fresh-install, real-archive,
  or human-acceptance evidence.

Letter 121 is queued next because its risk is different: the product must bind
an explicit `verbatim`, `faithful_summary`, or `sanitized_derivative` intent to
the source and draft before any AI-assisted write. The beta report confirmed no
actual draft or mint write, but the missing guardrail remains important.
