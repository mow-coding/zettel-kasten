# External Export Plan

Status: v0.3.76 read-only large-media export trap checkpoint

`archive external-export-plan` is a pre-export safety label. It is meant to run
before a human or AI helper starts a broad Notion, Google Drive, or generic
workspace export.

The problem it prevents is simple: a user may only want text for review, but a
workspace export can also pull uploaded files, attachments, images, audio, or video into a large local download. WOM should ask the scope question before the
export button is pressed.

## Command

```powershell
archive external-export-plan <archive-root> `
  --source notion `
  --export-goal full_workspace_review `
  --media-policy full_media_requested `
  --estimated-media-gb 164 `
  --dry-run `
  --format json
```

Supported sources:

```text
notion
google_drive
generic_workspace
```

Supported export goals:

```text
text_only
targeted_pages
full_workspace_review
```

Supported media policies:

```text
avoid_bulk_media
selected_media_only
full_media_requested
```

## Output

The planner returns:

- `risk_level`,
- `risk_reasons`,
- `recommended_export_mode`,
- provider-specific text-first guidance,
- stop rules,
- exact next command shapes for later `scan-source`, `import-external`, and
  object-storage recommendation work.

For example, a high estimated media size with `full_media_requested` returns
`stop_and_split_media_before_export`. That means the first pass should not be a
bulk media export. The human should first decide what text is needed and handle
selected media as separate objets or object-storage work.

## Large Media Export Trap

v0.3.76 makes the trap explicit in CLI JSON as `large_media_export_trap`.

The common failure shape is:

```text
The human wants text/database review.
The helper starts a broad workspace or database export.
The export also pulls uploaded files, attachments, images, audio, or video.
The download becomes huge or stalls before WOM has a reviewed source plan.
```

When the trap is detected, the planner returns:

```text
detected: true
trap_kind: workspace_or_database_export_can_pull_bulk_media
stop_before_first_export: true
requires_text_only_or_targeted_first: true
```

The safe first passes are:

```text
text_only_review
  -> export only page/database text needed for review

targeted_page_or_database_review
  -> export one top-level page, database, folder, or bounded slice

selected_media_after_review
  -> handle only human-selected media as source objets after text scope is known
```

Do not treat a provider export zip as already registered WOM objets. After the
text pass, run `scan-source`, use source-intake or project-intake receipts to
decide what matters, and route selected media to object-storage recommendation
or objet-capture planning.

## Provider Notes

The Notion guidance is based on official Notion export documentation: pages and
databases can be exported as Markdown & CSV, while broad workspace export can
include uploaded files and can take a long time depending on workspace size.
Notion's backup guidance also recommends smaller batches from important
top-level pages when full workspace export is too large or fails.

The Google guidance is based on official Google Takeout documentation: users can
choose which data to include, archives may be split by size, and smaller product
or folder selections can reduce failures for large downloads.

## Closed Actions

This command does not:

- open a provider dashboard,
- start a provider export,
- call provider APIs,
- start OAuth,
- read files,
- read media bytes,
- download attachments,
- write source maps,
- write inbox drafts,
- write archive receipts,
- echo provider URLs, local paths, filenames, account ids, emails, tokens, or
  secret values.

In short, it reads no files and writes no archive receipts.

## Not Implemented

v0.3.76 does not implement provider export automation, Notion API sync, Google
Drive API sync, Takeout automation, attachment download, object upload, media
deduplication, or automatic import. It only gives a safe pre-export planning
signal.
