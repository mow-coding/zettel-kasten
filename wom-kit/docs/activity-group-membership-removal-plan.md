# Activity-Group Membership Removal Plan

Current v0.4.0 boundary: this plan remains read-only. It grants no removal-
writer or recovery authority; affected approvals fail before private target
read or mutation with `compound_exact_human_approval_binding_required`.

Status: v0.4.0 read-only planning; v0.3.284 removal writer evidence is historical

`activity-group-membership-removal-plan` lets an archive owner review removing
one named event anchor from an explicit ordered set of canonical zets.

This command writes nothing. Historical v0.3.284 writer and interruption
recovery evidence is documented in
[Activity-Group Membership Removal Write And Recovery](activity-group-membership-removal-write.md).

## Why This Is Separate

v0.3.280 planned activity-group additions and v0.3.281 added the approved
writer and interruption recovery. Those releases intentionally did not remove
memberships.

Removal has different authority and evidence:

- an existing membership must be present before it can be removed;
- another event membership on the same zet must remain untouched;
- an absent membership is an idempotent no-op, not permission to edit;
- malformed or ambiguous current data must be blocked rather than normalized;
- a later writer must bind a separately reviewed removal request and plan.

For these reasons removal is not an option on the addition command.

## Event And Membership Contract

The event anchor contract is unchanged:

- the anchor is a canonical `record_note`;
- its `title` is present;
- `facets.record_type` is `event`;
- `facets.event_start` is an ISO 8601 date or datetime with an explicit offset;
- optional `event_end` uses the same granularity and is later than the start.

A member stores the event anchor id in `facets.activity_group`.

The removal plan changes no meaning. It does not imply sequence, continuation,
source, derivation, containment, or causation.

## Exact Candidate Semantics

The planner computes proposed bytes but never publishes or writes them.

| Current `facets.activity_group` | Planned result |
|---|---|
| exact scalar anchor | remove the `activity_group` key |
| list containing only the anchor | remove the `activity_group` key |
| list containing the anchor and other ids | remove only the named anchor; preserve the other ids, order, and list shape |
| missing key, another scalar, or list without the anchor | `already_absent`; no byte change |
| empty, duplicate, mixed, non-string, unsafe, mapping, or null shape | `blocked` |

The candidate preserves every other facet, all other frontmatter semantics,
the body, `updated_at`, UTF-8 BOM state, and newline convention. It does not
compact a one-item remaining list to a scalar because that would be an
unrelated normalization.

## Private Request

Store one reviewed JSON object under:

```text
.wom-scratch/private/activity-group-removals/
```

Example shape:

```json
{
  "schema": "wom-kit/activity-group-membership-removal-request/v0.1",
  "archive_id": "archive:personal:example",
  "anchor_zettel_id": "zet_20260729_120000_event",
  "member_zettel_ids": [
    "zet_20260729_120001_member",
    "zet_20260729_120002_member"
  ]
}
```

The request is a private AI working file. Do not commit it to the public
repository.

The JSON parser rejects duplicate object keys. The member list is ordered,
must contain unique safe canonical ids, and must not contain the anchor itself.

## Command

```powershell
archive activity-group-membership-removal-plan <archive-root> `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --dry-run --progress --format json
```

Alias:

```text
event-group-membership-removal-plan
```

`--dry-run` is mandatory. The command has no `--approve`, reviewer, or
affirmation option.

## Result

Result schema:

```text
wom-kit/activity-group-membership-removal-plan/v0.1
```

Each request row is one of:

- `ready_to_remove`: the exact anchor is present and exact proposed bytes were
  computed;
- `already_absent`: the exact anchor is not present and the proposed hash
  equals the current hash;
- `blocked`: the file, identity, canonical status, frontmatter, membership
  shape, byte bound, or event contract is unsafe or ambiguous.

`review_plan_sha256` binds:

- the removal plan schema;
- archive id;
- exact raw request SHA-256;
- exact current event-anchor file SHA-256;
- ordered row indexes, states, blocker codes, current hashes, and proposed
  hashes.

Changing request bytes, request order, the anchor, or a named member changes
the digest. `zet` records absent from the request are not scanned and are not
removal authority.

## Privacy And Bounds

The command accepts at most:

- 2 MiB of request JSON;
- 5,000 explicit member ids;
- 16 MiB per canonical file;
- 256 MiB of total canonical bytes.

It returns no request path, zettel id, zettel path, title, facet value, body,
reviewer, provider locator, secret, or absolute local path. Progress output is
content-free.

It uses exact standard `zettels/<id>.md` files. It does not use the generated
index, raw search results, title inference, time proximity, edges, a provider,
a model, the network, a database, or a credential store.

## Write Boundary

This planning command:

- writes no canonical zet;
- writes no receipt, journal, lock, index, or scratch file;
- removes no membership;
- repairs no malformed membership;
- exposes no MCP write method; and
- grants no direct-file-edit permission.

v0.3.284 makes its `future_write` continuation official through the separate
`activity-group-membership-removal-write` command. That writer requires this
plan's exact request and review-plan hashes, an attributed human reviewer, and
an explicit removal-review affirmation. It replans under the shared writer
lock, preserves exact snapshots, publishes a separate removal journal before
mutation, and writes a separate immutable removal receipt last.

`already_absent` remains part of the reviewed plan but is not a mutation
candidate. The writer excludes those rows from snapshots, journal participant
items, canonical write attempts, and receipt participant items.

The separate removal journal suffix is
`.activity-group-membership-removal.transaction.json`. Retained add or removal
journals block both operation writers before and under one global
activity-group writer lock. Use the dedicated read-only removal recovery plan
and separately approved removal recovery command after a hard exit.

Keep the reviewed private request and digests as evidence. Do not edit
canonical zets or transaction evidence directly. See
[Activity-Group Membership Removal Write And Recovery](activity-group-membership-removal-write.md).
