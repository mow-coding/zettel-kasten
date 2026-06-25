# Derived Artifact Staleness

Status: v0.3.147 read-only freshness checkpoint

`archive derived-artifact-staleness` checks whether external or derived
artifacts declared in zettel frontmatter may be stale relative to their source
zets.

It is designed for the real-use problem where a report site, client handoff
page, or other derived artifact is edited separately from the WOM source zets.

## Command

```powershell
archive derived-artifact-staleness <archive-root> `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive report-staleness <archive-root> --dry-run
archive artifact-staleness <archive-root> --dry-run
```

## Required Frontmatter Shape

The check reads `derived_artifacts` entries such as:

```yaml
derived_artifacts:
  - artifact_ref: report:client-brief
    source_zettels:
      - zet_20260625_source_outline
    last_synced_at: "2026-06-25T09:00:00Z"
    sync_status: synced
```

`source_zettels` may contain zettel ids or archive-relative zettel paths.

## What It Reports

- Artifacts whose source zets are newer than `last_synced_at`.
- Artifacts with missing `source_zettels`.
- Artifacts with source zettel refs that do not resolve.
- Artifacts with no sync timestamp.
- Limited path/id examples and next-action guidance.

## Safety Boundary

The command:

- writes nothing,
- calls no providers,
- opens no external report body,
- edits no zets,
- syncs no reports,
- reads only zettel metadata needed for freshness checks,
- echoes no artifact refs, zet titles, zettel body text, provider URLs, local
  absolute paths, tokens, or secret values.

## Still Future

- Automatic report refresh.
- A reviewed one-click "mark synced" receipt.
- A visual dependency dashboard.
- Audience-aware report rendering checks.
- Artifact body comparison or visual diffing.
