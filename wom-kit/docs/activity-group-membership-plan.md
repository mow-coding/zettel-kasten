# Activity-Group Membership Plan

`activity-group-membership-plan` is a read-only planning command for one
specific situation:

> A human already knows that several canonical zets belong to the same event
> and wants WOM to validate that exact selection before any future batch write.

The command does not search for members and does not infer membership from
titles, dates, nearby files, or existing edges.

## Event representation

WOM uses one canonical `record_note` as the event anchor.

The anchor must have:

```yaml
status: canonical
kind: record_note
facets:
  record_type: event
  event_start: '2022-08-26'
  # event_end: '2022-08-27'   # optional
```

The anchor's normal zettel `id` is the stable event-group identifier. Its
normal zettel `title` is the human-readable event name.

`event_start` accepts either:

- an ISO 8601 date such as `2022-08-26`; or
- an ISO 8601 date-time with an explicit offset, such as
  `2022-08-26T10:00:00+09:00`.

`event_end` is optional. When present, it must use the same date/date-time
granularity and be later than the start. The start is inclusive and the end is
non-inclusive, matching the established iCalendar event boundary.

Each member zet will eventually carry the anchor id:

```yaml
facets:
  activity_group: zet_20260729_020000_event_anchor
```

If a zet belongs to more than one event, the value can be a list. Membership
does not mean source, derivation, continuation, sequence, or containment.

## Private request

Create a JSON request under:

```text
.wom-scratch/private/activity-groups/
```

Example shape:

```json
{
  "schema": "wom-kit/activity-group-membership-request/v0.1",
  "archive_id": "archive:personal:example",
  "anchor_zettel_id": "zet_20260729_020000_event_anchor",
  "member_zettel_ids": [
    "zet_20260729_020001_member_one",
    "zet_20260729_020002_member_two"
  ]
}
```

The list is an explicit human selection. Search may help a human find
candidates, but search results are not automatically event members.

Every requested id must use the standard canonical path
`zettels/<zettel-id>.md`. The planner does not fall back to an archive-wide id
scan when that file is absent. This keeps one explicit request from reading
unrelated zet frontmatter.

The request is private working evidence. Do not commit it to a public
repository.

Duplicate JSON keys are ambiguous and block the request. Duplicate YAML mapping
keys anywhere in anchor or member frontmatter also block the plan. WOM never
chooses the first or last duplicate value as approval evidence.

## Command

```powershell
archive activity-group-membership-plan C:\path\to\archive `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --dry-run --progress --format json
```

Alias:

```text
event-group-membership-plan
```

The planning command always requires `--dry-run`. Since v0.3.281, its exact
request and `review_plan_sha256` may continue through the separate
approval-gated
[`activity-group-membership-write`](activity-group-membership-write.md)
command. The planner itself never writes.

## Result

The JSON response uses:

```text
wom-kit/activity-group-membership-plan/v0.1
```

The plan validates:

- exact request schema and archive id;
- one safe canonical anchor id;
- a non-empty, duplicate-free ordered member list;
- anchor kind, record type, title presence, and event time shape;
- exact current bytes and canonical identity of every named member;
- the standard `zettels/<zettel-id>.md` path without an archive-wide fallback;
- current `activity_group` shape;
- deterministic proposed file hashes for members that are ready to add.

Member states:

- `ready_to_add`: the exact current zet can receive this anchor;
- `already_member`: the exact current zet already carries this anchor;
- `blocked`: a content-free blocker code explains why no proposal is valid.

The result includes `review_plan_sha256`. That digest binds the request file,
anchor hash, ordered member states, current hashes, and proposed hashes.
`requested_member_count` always reports the original list length, while
`valid_member_id_count` separately reports how many entries passed id and
duplicate validation. An invalid list is never misleadingly summarized as an
empty request.

## Bounds

- request file: at most 2 MiB;
- members: at most 5,000;
- one canonical file: at most 16 MiB;
- total canonical bytes: at most 256 MiB.

The command reports content-free progress to stderr when `--progress` is used.
It validates live canonical files directly and does not depend on the generated
SQLite index.

## Privacy and write boundary

The JSON result does not return:

- the request path;
- anchor or member ids;
- zettel paths or titles;
- facet values;
- zettel body text;
- provider URLs, local absolute paths, credentials, or secret values.

It may read exact canonical bytes so it can hash and validate them, but it does
not return body text.

It writes no zettel, facet, receipt, index, diagnostic, or request file. It
calls no model, provider, network, or credential store.

## Write boundary

v0.3.281 adds the separate approval-gated writer and explicit interruption
recovery. It binds the exact request bytes and review-plan digest, revalidates
current bytes under a lock, records human review, preserves before-snapshots,
publishes a pre-mutation journal, and writes an immutable receipt last.

Member removal remains a separate reviewed operation. Neither the plan nor the
v0.3.281 writer removes any membership.
