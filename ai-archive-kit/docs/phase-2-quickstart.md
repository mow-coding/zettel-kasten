# Phase 2 Quickstart

This quickstart is for a first safe local run of AI Archive Kit v0.2.

The goal is not to build a web app. The goal is to check an archive, create an inbox draft, preview minting, build search, and understand the safety rails.

## What Exists Now

Implemented:

```text
archive doctor
archive validate
archive init
archive list-zettels
archive read-zettel
archive create-draft
archive mint-zettel --dry-run
archive mint-zettel --approve --reviewed-by
archive promote --dry-run
archive promote --approve --reviewed-by
archive index
archive search
archive pack
archive import --dry-run
archive share --dry-run
minimal stdio MCP server
```

Still planned:

```text
real workpack import
OS keyring integration
web UI
real Notion/cloud migration
CI matrix
```

## 1. Check The Fake Archive

From the project root on Windows PowerShell:

```powershell
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --strict
```

Expected result:

```text
0 error(s), 0 warning(s)
```

Run the tests:

```powershell
cd ai-archive-kit
python -m unittest discover -s tests
cd ..
```

Expected result:

```text
all tests pass
```

## 2. Create A Temporary Archive

Use a temporary folder first. Do not start with real private data.

```powershell
python ai-archive-kit\cli\archive.py init .\tmp-my-archive `
  --type personal `
  --archive-id archive:personal:me `
  --principal-id person:me `
  --principal-name "Me" `
  --name "My Personal Archive"
```

Check it:

```powershell
python ai-archive-kit\cli\archive.py doctor .\tmp-my-archive --strict
```

## 3. Create An AI Draft

AI-created notes go to `inbox/` first.

```powershell
python ai-archive-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "First safe draft" `
  --body "# First safe draft`n`nThis is a temporary inbox draft created during the quickstart."
```

List drafts:

```powershell
python ai-archive-kit\cli\archive.py list-zettels .\tmp-my-archive --status draft
```

## 4. Preview Minting

Start with dry-run. It is the safe review step before canonical memory is written.

Use the path printed by `create-draft`, then run:

```powershell
python ai-archive-kit\cli\archive.py mint-zettel .\tmp-my-archive `
  --path inbox\PUT-THE-DRAFT-FILENAME-HERE.md `
  --dry-run
```

The dry-run reports:

```text
blockers
warnings
checklist status
near duplicate hints
proposed canonical path
proposed mint receipt path
proposed draft snapshot path
```

If the draft is rough, dry-run should block it. That is expected.

If dry-run passes and you have intentionally reviewed the draft, real minting is available through the CLI:

```powershell
python ai-archive-kit\cli\archive.py mint-zettel .\tmp-my-archive `
  --path inbox\PUT-THE-DRAFT-FILENAME-HERE.md `
  --approve `
  --reviewed-by person:me
```

Real minting keeps the inbox draft, writes the canonical zettel under `zettels/`, writes a mint receipt under `receipts/mint/`, and writes the exact draft snapshot under `receipts/mint/drafts/`.

If dry-run reports warnings, real minting requires:

```powershell
--allow-warnings
```

Only use that flag after reading the warnings.

`archive promote` still exists as a v0.2 legacy compatibility command, but new users should start with `archive mint-zettel`.

## 5. Build And Search The Index

The search index is a generated map. It is not canonical memory.

```powershell
python ai-archive-kit\cli\archive.py index ai-archive-kit\examples\fake-life-archive
python ai-archive-kit\cli\archive.py search ai-archive-kit\examples\fake-life-archive "lunch"
```

The generated file is:

```text
db/archive-index.sqlite
```

It can be rebuilt.

## 6. Try Workpacks Safely

`pack` writes a workpack, so use a temporary copy of the fake archive.

```powershell
Copy-Item -Recurse ai-archive-kit\examples\fake-life-archive .\tmp-fake-life-archive
```

Create a small workpack from a saved view:

```powershell
python ai-archive-kit\cli\archive.py pack .\tmp-fake-life-archive `
  --view view.fake.education.gilwon `
  --purpose "Quickstart education context." `
  --mode reference
```

Preview importing the workpack into your temporary archive:

```powershell
python ai-archive-kit\cli\archive.py import .\tmp-my-archive `
  .\tmp-fake-life-archive\workpacks\PUT-THE-WORKPACK-FOLDER-HERE `
  --dry-run
```

Real import is intentionally unavailable.

## 7. Run MCP Locally

From inside `ai-archive-kit/`:

```powershell
$env:PYTHONPATH = "src"
python -m ai_archive_kit.mcp_server
```

The server speaks JSON-RPC over stdio. It is meant to be launched by an AI client, not used like a normal terminal command.

## Safety Rules To Remember

- Use fake or temporary archives while learning.
- AI writes drafts to `inbox/`.
- Canonical `zettels/` require human minting.
- `mint-zettel --dry-run` writes nothing.
- Real `mint-zettel` requires `--approve` and `--reviewed-by`.
- `promote` remains available for legacy v0.2 compatibility.
- `import --dry-run` writes nothing.
- `share --dry-run` writes nothing and checks scope plus counterparty trust.
- Archive ownership and archive operation are separate; real ownership transfer is future work.
- Original object files are referenced by `object_id`.
- Provider URLs and local absolute paths should not live in zettels.
- Secrets do not belong in the archive.
