# 2026-06-17 v0.3.99 Policy Batch Zettel Edge Write

## Context

The client feedback after the Phase 3 live-use sweep confirmed that the
single-edge `zettel-edge` approval path was safe, but too slow for real
connection import work.

The key operational problem was approval scale:

- AI or a parser can produce many candidate ties.
- A human should not approve every obvious edge one by one.
- High-confidence candidates need a policy-level path.
- Ambiguous and low-confidence candidates still need a human queue.

The same feedback also noted that Notion connection types beyond relation
properties and real export parsers remain future work.

## Decision

Implement the next safe step as a CLI-only approval-gated batch writer:

```text
archive zettel-edge-batch <archive-root> --plan <json> --dry-run|--approve
```

Aliases:

```text
bulk-zettel-edge
batch-zettel-edge
```

The command reads a reviewed JSON plan with:

- `policy.auto_write_edge_types`
- `policy.minimum_confidence`
- candidate `edges`

It writes only rows that match the policy. Other rows are returned in
`human_review_queue`.

## Implementation Notes

The batch writer deliberately reuses the existing single-edge writer for each
policy-writable row. This keeps the older validation path in force:

- source zettel resolution,
- target resolution,
- edge type validation,
- duplicate edge detection,
- single-edge receipt creation,
- privacy-safe JSON output.

Approved batches also write:

```text
receipts/edges/batches/*.zettel-edge-batch.json
```

If an approved batch fails partway through, the command restores touched zettel
and receipt files from in-process snapshots.

## Safety Boundary

The new command does not:

- parse real Notion exports,
- call providers,
- start OAuth,
- open Notion,
- call an LLM,
- write candidate records,
- update object manifests,
- expose an MCP write tool.

It also avoids zettel body text, zettel titles, provider URLs, local absolute
paths, account ids, emails, tokens, and secret values in output.

## Files Changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `wom-kit/docs/zettel-edge-batch.md`
- `wom-kit/docs/zettel-edge-write.md`
- `wom-kit/docs/connection-edge-intelligence-plan.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/docs/releases/v0.3.99.md`
- `README.md`
- `wom-kit/README.md`
- `CHANGELOG.md`

## Next Work

The next non-feedback-blocked path is likely one of:

- turning body/locator rewrite review plans into approved edge/ref writes,
- adding manifest-side Notion locator labels so object matching is not zero,
- adding real export parsers behind the same candidate-plan boundary.
