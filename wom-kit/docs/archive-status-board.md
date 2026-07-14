# Archive Status Board

Status: v0.3.231 read-only archive state and first-read checkpoint

`archive status-board` gives a beginner-facing status summary for one WOM
archive without making the operator inspect `inbox/`, `zettels/`, mint
receipts, and draft snapshots by hand.

It is a CLI/read-only surface that an AI operator can summarize directly in
conversation. A web UI is not required.

## Command

```powershell
archive status-board <archive-root> `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive archive-status-board <archive-root> --dry-run
archive zet-status-board <archive-root> --dry-run
```

To include body-inspecting quality counts:

```powershell
archive status-board <archive-root> `
  --dry-run `
  --include-quality `
  --format json
```

## What It Reports

- Canonical zet count.
- Draft zet count.
- Active draft count.
- Minted inbox drafts that are ready for `retire-draft` review.
- Canonical zets missing lifecycle metadata.
- Mint receipt gaps.
- Missing `document_type`.
- Missing `audience`.
- Source acquisition, verification, or rights metadata gaps.
- Derived artifact source-link or sync-status gaps.
- Explicit, compatibility-only, missing, unreadable, and redacted first-read
  counts for canonical zets.
- A bounded first-read attention list that routes to
  `archive first-read-readiness`.
- Optional quality blocker/warning candidate counts.

The command also returns limited path/id examples and next-action guidance.

## Safety Boundary

The status board:

- writes nothing,
- calls no providers,
- retires no drafts,
- edits no zets,
- creates no revision candidates,
- syncs no reports,
- cleans no scratch files,
- echoes no zet titles, abstract text, body text, source-ref values, provider URLs, local
  absolute paths, tokens, or secret values.

## Why It Exists

After real mint workflows, beginners can struggle to distinguish:

- final canonical zets,
- still-active drafts,
- minted drafts that are safe to close after review,
- receipts,
- source metadata gaps,
- external artifact sync gaps,
- canonical zets whose frontmatter abstract is not yet an explicit AI first read,
- revision/quality attention candidates.

`status-board` makes those categories visible without changing archive state.

## Still Future

- Optional visual rendering by a future custom UI layer.
- One-click reviewed draft retirement.
- Automatic revision-candidate creation.
- Audience-aware publishing checks.
- Viewer integration that hides YAML frontmatter in a metadata panel.
