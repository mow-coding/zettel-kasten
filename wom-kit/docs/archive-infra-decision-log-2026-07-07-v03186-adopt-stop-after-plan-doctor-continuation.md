# Archive Infra Decision Log - v0.3.186 Adopt Stop-After-Plan And Doctor Continuation Progress

Date: 2026-07-07
Status: accepted
Release: v0.3.186

## Context

Basoon's v0.3.185 revalidation confirmed that:

- `archive version` import-origin diagnostics work;
- `object-storage-adopt-existing --progress` reports same-provider nonmatching
  declared rows correctly;
- doctor now reaches `target mint receipt link ok` for the first mint receipt.

The same revalidation showed two remaining operator issues:

- running a short approved adopt just to inspect the summary still performs
  remote HEADs and can write partial object manifest / execution receipt state;
- after the first `target mint receipt link ok`, doctor may stay quiet long
  enough that the next bottleneck is unclear.

## Decision

Add `object-storage-adopt-existing --stop-after-plan`.

The flag is intentionally read-only even when combined with `--approve`: WOM
resolves the adopt plan and emits the same summary diagnostics, then stops before
credential value reads, provider HEADs, manifest updates, or execution receipt
writes. The result records `execution_status: plan_only`.

Also add same-store `wom_uploaded` raw-vs-gating counts. This explains why a
simple store-ref manifest count can exceed the stricter resume skip candidates.

For doctor, emit detailed sub-steps for the first three mint receipts and add a
`completed receipt checks` marker for detailed receipt scans.

## Consequences

- Operators can inspect large adopt resume summaries without creating partial
  private-archive state.
- JSON consumers can watch stdout for the final result while progress remains on
  stderr.
- WOM still does not migrate legacy store refs automatically.
- Doctor progress remains content-free and does not expose zettel text, object
  ids, remote keys, paths outside the archive, or secrets.

## Verification

- Focused tests cover stop-after-plan, same-store gating diagnostics, and doctor
  receipt completion progress.
- Full release gates are run before publishing.
