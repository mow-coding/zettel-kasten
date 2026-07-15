# Optional MOW Harness Compatibility

Status: documented optional integration with implemented local namespace isolation
Date: 2026-07-16

WOM works without MOW Harness. MOW Harness is an optional, separate operating
layer for structured multi-agent sessions; it is not WOM's archive, semantic
engine, or source of truth.

## Ownership Boundary

The two systems own different things:

```text
WOM owns archive records, zets, objets, receipts, indexes, and backup contracts.
MOW Harness owns its local coordination room and installer metadata.
```

MOW Harness may use only these host-local namespaces:

```text
<archive-root>/collab/
<archive-root>/.mow-harness/
```

WOM-generated archives ignore both roots by default. WOM artifact hygiene also
classifies them as local collaboration and harness state, so normal archive
indexing, minting, backup, and public-repository checks do not mistake them for
durable WOM records.

MOW Harness must not modify WOM product files, archive records, zets, objets,
source maps, provider profiles, credentials, or indexes. WOM does not install,
update, activate, or remove MOW Harness.

## Durable Outcomes

Files under `collab/` can contain useful plans, reviews, and decisions, but they
remain operating-room evidence. When a session produces knowledge that should
survive independently of the harness, summarize or capture it deliberately
through normal WOM records. Do not bulk-mint a mailbox or session transcript.

## Install And Update Boundary

Follow the separate MOW Harness project's current instructions:

```text
https://github.com/mow-coding/mow-harness
```

At this checkpoint, the stable file-based Harness release is `v0.1.23`. Its new
dependency-free CLI is still a source alpha and is not published to npm. WOM
therefore does not advertise an npm install command or pin an unreleased CLI.

The intended external command order is:

```powershell
mow status C:\path\to\archive
mow doctor C:\path\to\archive
mow update C:\path\to\archive --adopt --dry-run
mow update C:\path\to\archive --adopt --yes
mow doctor C:\path\to\archive
```

`status`, `doctor`, and `--dry-run` are read-only. `--yes` is a separate MOW
Harness write approval; WOM does not grant it implicitly. A legacy manual room
may require explicit adoption, and an active claim, unknown metadata, or changed
plan must stop the update.

## Activation Is Separate

Installing or updating files does not turn MOW Harness on. `OFF`, `ON`, agent
readiness, and numbered-step gates remain MOW Harness state. They do not change
WOM archive validity. A room that is `OFF` stays `OFF` until the human separately
requests activation and the harness records the required evidence.

## Honest Current Limit

WOM currently provides namespace isolation and this interoperability contract.
It does not call the MOW CLI, render a Cockpit UI, parse MOW receipts as WOM
knowledge, or claim that the source-alpha legacy adoption path has been applied
to a real archive. Those actions remain external and separately approved.
