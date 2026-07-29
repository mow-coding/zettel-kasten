# Activity-Group Membership Removal Plan

Status: v0.3.282 read-only explicit membership-removal planning

`activity-group-membership-removal-plan` lets an archive owner review removing
one named event anchor from an explicit ordered set of canonical zets.

It writes nothing. The approval-gated removal writer is not implemented in
v0.3.282.

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

v0.3.282:

- writes no canonical zet;
- writes no receipt, journal, lock, index, or scratch file;
- removes no membership;
- repairs no malformed membership;
- exposes no MCP write method;
- grants no direct-file-edit permission.

A later approval-gated writer must use a separate removal operation, bind the
exact request and plan hashes, share serialization with addition and recovery,
publish a transaction journal before mutation, preserve exact snapshots, write
an immutable receipt last, and provide hard-interruption recovery.

Until that writer ships, keep the reviewed private request and digest as
evidence and do not edit canonical zets directly.
