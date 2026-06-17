# Zettel Edge Batch

Status: v0.3.108 approval-gated policy batch zettel edge write scale and rollback checkpoint
Previous checkpoint: Status: v0.3.102 approval-gated policy batch zettel edge write ergonomics checkpoint

`archive zettel-edge-batch` is the policy approval companion to
`archive zettel-edge`.

The beginner version is:

```text
One edge writer = approve one edge.
Batch edge writer = approve one policy, then write only the candidates that
match that policy.
```

Low-confidence, ambiguous, blocked, or policy-mismatched candidates are not
written. They are returned in `human_review_queue` for a later human review.

When batch rows target manifested objets, v0.3.108 preloads
`objects/manifests/files.jsonl` once and reuses a local object-id index instead
of resolving every objet target through repeated full manifest scans.

## Command

Preview:

```powershell
archive zettel-edge-batch <archive-root> `
  --plan workbench/zettel-edge-batch.plan.json `
  --dry-run `
  --format json
```

Approve:

```powershell
archive zettel-edge-batch <archive-root> `
  --plan workbench/zettel-edge-batch.plan.json `
  --approve `
  --reviewed-by person:reviewer `
  --skip-existing `
  --format json
```

Aliases:

```text
bulk-zettel-edge
batch-zettel-edge
```

Rollback preview:

```powershell
archive revert-batch <archive-root> `
  --receipt receipts/edges/batches/<batch>.zettel-edge-batch.json `
  --dry-run `
  --format json
```

Rollback approve:

```powershell
archive revert-batch <archive-root> `
  --receipt receipts/edges/batches/<batch>.zettel-edge-batch.json `
  --approve `
  --reviewed-by person:reviewer `
  --format json
```

Rollback alias:

```text
rollback-batch
```

## Plan Path Resolution

`--plan` is resolved archive-relative first. This matches the connection
commands, so a plan under the archive workbench can be passed as:

```text
workbench/zettel-edge-batch.plan.json
```

If that archive-relative path is not found, the command falls back to the
current working directory for compatibility with older absolute/temp-file
workflows. Missing-path blockers give a short hint and do not echo local
absolute paths.

## Plan Shape

The plan is JSON:

```json
{
  "schema": "wom-kit/zettel-edge-batch/v0.1",
  "policy": {
    "policy_id": "policy:high-confidence-material",
    "policy_label": "High confidence material edges",
    "auto_write_edge_types": ["material", "derived"],
    "minimum_confidence": "high",
    "ambiguous_edges_to_review_queue": true
  },
  "edges": [
    {
      "candidate_id": "candidate:relation-1",
      "from_zettel": "zet_20240504_fake_lunch_thought",
      "target": "zet_20240505_fake_company_onboarding_insight",
      "edge_type": "material",
      "visibility": "private",
      "confidence": "high",
      "review_status": "policy_candidate",
      "evidence_ref": "fixture:relation-row-1"
    }
  ]
}
```

Each candidate must identify exactly one source with either:

```text
from_zettel
from_path
```

Policy-writable candidates must:

- use an `edge_type` listed in `policy.auto_write_edge_types`,
- meet or exceed `policy.minimum_confidence`,
- avoid `requires_human_review: true`,
- avoid review statuses such as `needs_review`, `ambiguous`, `blocked`, or
  `human_review_required`.

## Existing Edge Handling

By default, duplicate safety remains strict: an already-written edge, existing
edge receipt, or existing batch receipt blocks the batch.

When a human explicitly passes `--skip-existing`, already-written edge rows are
returned in `skipped_existing_edges` instead of blocking the whole batch. The
remaining policy-writable rows still pass through the same single-edge preflight
and approval-gated write path.

If every policy-writable row already exists and `--skip-existing` is used, the
command writes nothing, returns `write_status: nothing_to_write`, and does not
create a new batch receipt.

## Writes

With `--approve --reviewed-by <safe-id>`, the command first dry-runs every
policy-writable item through the single-edge writer.

Only after all policy-writable items pass preflight does it write:

```text
zettels/*.md or inbox/*.md frontmatter edges +N
receipts/edges/*.zettel-edge.json
receipts/edges/batches/*.zettel-edge-batch.json
```

The batch receipt records the policy id, reviewer id, written edge receipts,
skipped-existing count, and review queue count. If an approved batch write fails
partway through, WOM-kit restores the touched zettel and receipt files from
in-process snapshots.

## Reverts

`archive revert-batch` reads a
`receipts/edges/batches/*.zettel-edge-batch.json` receipt and plans one
`revert-edge` operation for each listed edge receipt.

With `--approve --reviewed-by <safe-id>`, it writes:

```text
zettels/*.md or inbox/*.md frontmatter edges -N
receipts/edges/reverts/*.zettel-edge-revert.json
receipts/edges/batches/reverts/*.zettel-edge-batch-revert.json
```

The original edge receipts and original batch receipt are preserved. If a batch
revert fails partway through, WOM-kit restores the touched zettel and new revert
receipt files from in-process snapshots.

## What It Does Not Do

This command does not classify candidates by itself. It expects a reviewed JSON
plan from a fixture parser, future real export parser, or AI runtime.

It does not:

- call providers,
- start OAuth,
- open Notion,
- read real source exports,
- read zettel body text,
- read comments,
- download media,
- call an LLM,
- write candidate records,
- update object manifests,
- upload objects,
- create provider URLs,
- expose a matching MCP write tool.
- delete original edge or batch receipts.

The output also avoids zettel body text, zettel titles, provider URLs, local
absolute paths, page titles, comment bodies, account ids, emails, tokens, and
secret values.

## Relationship To Connection Intelligence

`archive connection-edge-intelligence-plan` still remains read-only. It can
help prepare candidate rows and review queues, but it does not write durable
edges.

`archive zettel-edge-batch` is the next approval step for the subset of
candidates that a human is willing to accept under one explicit policy.
