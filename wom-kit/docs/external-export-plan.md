# External Export Plan

Status: v0.3.66 read-only text-first external export planning checkpoint

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

## Provider Notes

The Notion guidance is based on official Notion export documentation: pages and
databases can be exported as Markdown & CSV, while broad workspace export can
include uploaded files and can take a long time depending on workspace size.

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

v0.3.66 does not implement provider export automation, Notion API sync, Google
Drive API sync, Takeout automation, attachment download, object upload, media
deduplication, or automatic import. It only gives a safe pre-export planning
signal.
