# Work Log: v0.2.36 Foreign Block Quarantine Decision Review Index

Date: 2026-05-25

## Intent

Add a read-only index after v0.2.35 quarantine decision records.

The user wanted AI runtimes and operators to inspect recorded foreign block quarantine decisions and their receipts without accepting, trusting, importing, attesting, minting, anchoring, delegating, signing, applying, sharing, or calling providers.

## Implementation

- Added `archive quarantine-decision-review`.
- Added decision filters for case id and decision value.
- Added optional receipt summaries through `--include-receipts`.
- Added validation of decision records, decision receipts, the current quarantine case, and the original quarantine receipt.
- Added blockers for unsafe values, mismatched case ids, mismatched receipt fields, missing original cases, malformed timestamps, and stale recorded source hashes.
- Added warnings for no matching decisions, missing decision receipts, safe unknown optional fields, and missing optional current-state hash references.
- Added read-only MCP `foreign_block_quarantine_decision_review_index`.
- Added tests for empty indexes, valid records, filters, receipt inclusion, missing receipts, missing original cases, contradiction blockers, unsafe value redaction, safe unknown optional warnings, no-write behavior, MCP dry-run enforcement, and MCP tool-surface boundaries.

## Boundaries

The command writes nothing and returns `would_change: []`.

It does not:

- accept quarantine decisions,
- grant trust,
- import foreign blocks,
- create attestations,
- mint,
- anchor,
- delegate,
- sign,
- execute foreign text,
- apply decisions,
- call provider APIs,
- expose MCP write tools.

## Documentation

Updated public docs, CLI/MCP docs, runtime skill guidance, changelog, upgrade/versioning files, release notes, public documentation maps, and this work log.

## Verification Plan

- `python -m unittest discover -s wom-kit\tests`
- `python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict`
- `python -m wom_kit.archive_cli doctor wom-kit\examples\fake-life-archive --strict`
- `git diff --check`
- naming and privacy scans requested for the batch.

## Pre-Merge Fixes

Claude's pre-merge review found no critical security issues, but identified three correctness/clarity fixes.

Applied fixes:

- `--decision` now filters only the displayed decision summaries. Every discovered decision record, decision receipt, current quarantine case, and original quarantine receipt is still validated before top-level `ok` is set.
- Added `displayed_decision_count`, `total_decision_count`, `filter_applied`, and `filters` to make filter behavior explicit while keeping `decision_count` as the displayed count.
- Replaced duplicate `decisions`/`cases` payloads with a real case-level `cases` projection.
- Receipt summary booleans now use direct semantics such as `trust_granted: false` and `provider_api_called: false`.
- Case consistency is computed from case-scoped validation, so a decision receipt-only contradiction does not make the case itself appear blocked.
- Added regression tests for hidden filtered blockers, invalid decisions, review-note content leak guards, receipt summary shape, distinct cases output, and receipt-only blocker behavior.
