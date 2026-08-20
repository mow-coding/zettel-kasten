# Zettel Edge Batch

Status: v0.4.0 dry-run-only batch and rollback planning boundary
Scale checkpoint: Status: v0.3.108 approval-gated policy batch zettel edge write scale and rollback checkpoint
Previous checkpoint: Status: v0.3.102 approval-gated policy batch zettel edge write ergonomics checkpoint

`archive zettel-edge-batch` is the read-only policy planning companion to
the exact single-operation `archive zettel-edge` writer.

The beginner version is:

```text
One edge writer = review and approve one exact edge.
Batch planner = classify a complete reviewed policy plan without writing it.
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

Approve is intentionally unavailable in v0.4.0. This shape fails closed with
`compound_exact_human_approval_binding_required` and writes nothing. There is
no approved batch command to copy or run.

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

Rollback approve is also unavailable in v0.4.0. This shape fails with the same
code and writes nothing. There is no approved revert-batch command to copy or
run.

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
remaining policy-writable rows still pass through the same single-edge
preflight, but no batch mutation follows in v0.4.0.

If every policy-writable row already exists and `--skip-existing` is used, the
command returns `write_status: nothing_to_write`. No v0.4.0 batch invocation
creates a batch receipt.

## Writes

There is no batch writer in the v0.4.0 authority model. Dry-run applies the
same endpoint, duplicate, policy, and registry preflights to every candidate
and returns the complete content-free classification. `--approve` exits before
any zettel or receipt mutation with
`compound_exact_human_approval_binding_required`.

The old v0.3 batch receipt and rollback formats remain readable historical
evidence. Their existence does not reactivate the old executor or let one
single-target claim authorize a compound target set.

Since v0.3.290, the reused single-edge preflight also enforces the selected
active `types.yml` record's `from` and `to` entity-type lists. A row whose
resolved `Zettel`/`OriginalObject` endpoints are incompatible, or whose
selected registry contract is malformed, cannot become an eligible plan row and
is reported deterministically. The contract field and fixed blockers copy
no target content, registry payload, path, or exception text; existing safe
source archive-relative paths, target refs, manifest path, and receipt paths
remain part of the established result.

## Reverts

`archive revert-batch --dry-run` reads a
`receipts/edges/batches/*.zettel-edge-batch.json` receipt and plans one
`revert-edge` operation for each listed edge receipt.

It writes nothing. `--approve` stops with
`compound_exact_human_approval_binding_required`; original edge and batch
receipts remain untouched, no zettel changes, and no revert receipt is created.

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

`archive zettel-edge-batch` is a review plan only. A human can take one selected
candidate through the exact `archive zettel-edge --dry-run|--approve` route.
Multi-edge approval requires a future binding that covers the complete target
set and is not implemented in v0.4.0.
