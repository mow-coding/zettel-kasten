# Project Intake Cookbook

Status: fake-archive rehearsal
Date: 2026-06-14

This cookbook shows the current manual project-intake spine with public-safe
fake data. It is for rehearsal before using a real personal archive.

The goal is not automatic import. The goal is:

```text
AI asks one question.
The human reviews one answer.
WOM-kit records one receipt.
The next command uses that receipt only as context.
```

## Bulk Raw First, Selective Promotion Later

For thousands or tens of thousands of already-hashed files, do not run this
cookbook once per raw file. Split the migration into two layers:

```text
already-hashed raw store
        |
        v
archive prehashed-objet-ledger --ledger ... --approve
        |
        v
raw bytes are represented in the object manifest
        |
        v
human selects a small meaningful subset
        |
        v
this cookbook: ask, record, capture selection, draft, mint
```

`prehashed-objet-ledger` is the bulk raw-preservation bridge. It can register
one or more external content-addressed ledgers without reading blob bytes,
copying objects, drafting, minting, uploading, or cleaning. This cookbook is the
human-guided promotion spine for the selected subset that should become visible
drafts or zets.

Earlier revisions used a sibling `archive-objets/` as a recommended local staging
root for new intake rehearsals. Since the intake layout ruling (D2, 2026-07-03),
capture rehearsals stage INSIDE the archive at `staging/incoming/` — exactly what
the commands below do — because `objet-capture-selection` requires
archive-relative staged paths. A dated layer such as
`staging/incoming/<YYYY-MM-DD>/` is recommended for real intake sessions, not
required; this rehearsal keeps the bare folder. The sibling store remains the
home for bulk external originals, and that does not mean an existing external
content-addressed store must be moved there. Keep raw stores outside the
Git-tracked archive unless your archive policy says otherwise, and use a safe
`--store-ref` label when registering an externally verified prehashed ledger.

## 1. Copy The Fake Archive

Use a temporary folder outside the repository:

```powershell
$tmp = Join-Path $env:TEMP "wom-project-intake-rehearsal"
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tmp | Out-Null
Copy-Item -Recurse ".\wom-kit\examples\fake-life-archive" "$tmp\archive"
Set-Content -Path "$tmp\archive\.wom-sandbox" -Value "sandbox" -Encoding utf8
New-Item -ItemType Directory -Path "$tmp\archive\staging\incoming" -Force | Out-Null
Set-Content -Path "$tmp\archive\staging\incoming\project-note.txt" -Value "Fake source note for project intake rehearsal." -Encoding utf8
```

The `.wom-sandbox` marker keeps destructive real-data assumptions out of this
rehearsal. Do not point these commands at a real private archive until the dry
runs and receipts make sense.

## 2. Ask For The Session Shape

```powershell
archive project-intake-session-guide "$tmp\archive" --staged-folder "$tmp\archive\staging\incoming" --dry-run --format json
archive project-intake-plan "$tmp\archive" --staged-folder "$tmp\archive\staging\incoming" --dry-run --format json
archive project-intake-next-question "$tmp\archive" --staged-folder "$tmp\archive\staging\incoming" --dry-run --format json
archive project-intake-decision-template "$tmp\archive" --staged-folder "$tmp\archive\staging\incoming" --session-id rehearsal-project-20260614 --dry-run --format json
```

These commands write nothing. They do not read file bodies, classify the whole
folder, capture objets, draft zets, mint zets, upload files, or clean the staged
folder.

## 3. Record One Human-Reviewed Answer

Create one answer file:

```powershell
@'
{
  "schema": "wom-kit/project-intake-answer/v0.1",
  "checklist_id": "scope.single_project",
  "answer": "yes",
  "notes": "This fake staged folder is one rehearsal project."
}
'@ | Set-Content -Path "$tmp\scope-answer.json" -Encoding utf8
```

Preview, then approve:

```powershell
archive project-intake-record-answer "$tmp\archive" --answer "$tmp\scope-answer.json" --session-id rehearsal-project-20260614 --dry-run --format json
archive project-intake-record-answer "$tmp\archive" --answer "$tmp\scope-answer.json" --session-id rehearsal-project-20260614 --approve --reviewed-by person:test --format json
```

The approved command writes a project-intake decisions receipt under
`receipts/project-intake/`. Console output does not echo the answer text.

Save the returned `receipt_path` as `$projectReceipt` for the next commands:

```powershell
$projectReceipt = "<receipt_path from the approved command>"
```

## 4. Check What Is Still Missing

```powershell
archive project-intake-status "$tmp\archive" --receipt $projectReceipt --dry-run --format json
archive project-intake-next-question "$tmp\archive" --receipt $projectReceipt --dry-run --format json
```

The receipt can show checklist coverage and the next missing question. It is not
permission to run the rest of the workflow automatically.

## 5. Plan One Selected File

Ask for the next unpacking choice before naming one file for source-intake:

```powershell
archive project-intake-unpack-queue "$tmp\archive" --staged-folder "$tmp\archive\staging\incoming" --receipt $projectReceipt --dry-run --format json
```

The queue returns opaque `item-0001` style refs and coarse hints only. It does
not expose staged entry names, read bodies, hash content, classify
automatically, capture, draft, mint, upload, or clean. The human still chooses
the actual local item before `project-intake-item-plan`.

Record that one reviewed choice before planning the local file:

```powershell
@'
{
  "schema": "wom-kit/project-intake-unpack-choice/v0.1",
  "item_ref": "item-0001",
  "intended_action": "preserve_as_objet",
  "human_confirmed": true,
  "notes": "The human chose the first opaque rehearsal item."
}
'@ | Set-Content -Path "$tmp\unpack-choice.json" -Encoding utf8

archive project-intake-unpack-choice "$tmp\archive" --choice "$tmp\unpack-choice.json" --receipt $projectReceipt --staged-folder "$tmp\archive\staging\incoming" --dry-run --format json
archive project-intake-unpack-choice "$tmp\archive" --choice "$tmp\unpack-choice.json" --receipt $projectReceipt --staged-folder "$tmp\archive\staging\incoming" --approve --reviewed-by person:test --format json
$unpackChoiceReceipt = "<receipt_path from the approved unpack-choice command>"
```

The unpack-choice receipt records the human's opaque `item_ref` and intended
action. Command output still does not echo choice notes, staged entry names, or
local paths, and it does not run source-intake or capture.

```powershell
archive project-intake-item-plan "$tmp\archive" --receipt $projectReceipt --local-path "$tmp\archive\staging\incoming\project-note.txt" --dry-run --format json
archive source-intake "$tmp\archive" --dry-run --local-path "$tmp\archive\staging\incoming\project-note.txt" --project-intake-receipt $projectReceipt --redact-local-paths --format json
```

Save and review the source-intake JSON outside the command, then record it:

```powershell
$sourcePlan = "$tmp\source-intake-plan.json"
# Write the reviewed source-intake dry-run JSON to $sourcePlan.
archive source-intake-record "$tmp\archive" --source-intake-plan $sourcePlan --dry-run --format json
archive source-intake-record "$tmp\archive" --source-intake-plan $sourcePlan --approve --reviewed-by person:test --format json
```

Save the approved command's returned `receipt_path` as `$sourceIntakeReceipt`
for the capture-selection commands:

```powershell
$sourceIntakeReceipt = "<receipt_path from the approved source-intake-record command>"
```

## 6. Capture Only After A Separate Selection

Use `objet-capture-selection` to prepare a reviewed selection manifest for one
staged file, then pass that selection to `objet-capture`.

```powershell
archive objet-capture-selection "$tmp\archive" --staged-path staging/incoming/project-note.txt --source-intake-receipt $sourceIntakeReceipt --dry-run --format json
archive objet-capture-selection "$tmp\archive" --staged-path staging/incoming/project-note.txt --source-intake-receipt $sourceIntakeReceipt --approve --reviewed-by person:test --format json
$selectionJson = "<selection path from the approved objet-capture-selection command>"
archive objet-capture "$tmp\archive" --selection $selectionJson --project-intake-receipt $projectReceipt --dry-run --format json
archive objet-capture "$tmp\archive" --selection $selectionJson --project-intake-receipt $projectReceipt --approve --reviewed-by person:test --format json
```

Capture still does not draft, mint, upload, or clean.

## 7. Draft, Mint, Then Check Cleanup

After capture and any derived text review, draft and mint remain separate
approval gates:

```powershell
archive create-draft "$tmp\archive" --title "Rehearsal zet" --body "Rehearsal body from a reviewed captured source." --source-intake-plan $sourcePlan --format json
archive mint-zet "$tmp\archive" --path <draft-path> --approve --reviewed-by person:test --allow-warnings --format json
archive staged-cleanup-check "$tmp\archive" --staged staging/incoming --dry-run --format json
```

Only the cleanup report can say whether the staged folder is safe to remove.
WOM-kit still never deletes it for you.

## Safety Summary

- Use one staged project folder at a time.
- Record one answer at a time.
- Preserve one selected item at a time.
- Treat receipts as context, not automatic permission.
- Keep provider sync, uploads, draft creation, minting, and cleanup as separate
  approval gates.
