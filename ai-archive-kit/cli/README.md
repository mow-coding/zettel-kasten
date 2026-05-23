# AI Archive Kit CLI

This is the first minimal CLI for zettel-kasten archives.

For a beginner-friendly full walkthrough, see:

```text
docs/phase-2-quickstart.md
docs/new-user-flow.md
```

It is intentionally small:

```text
doctor
  Inspect an archive for missing files, invalid YAML/frontmatter, schema problems, manifest problems, unsafe zettel references, and minting-rule warnings.

init
  Initialize a personal, company, or family archive from a safe template.

validate
  Run strict archive validation.

list-zettels
  List canonical and/or draft zettels.

read-zettel
  Read one zettel by id or archive-relative path.

create-draft
  Create a draft zettel in inbox/.

mint-zettel --dry-run
  Check minting readiness and preview canonical path, mint receipt, and draft snapshot without writing.

mint-zettel --approve --reviewed-by
  Mint an inbox draft zet into canonical private archive memory and write receipt/snapshot evidence.

promote --dry-run
  Legacy-compatible promotion readiness check.

promote --approve --reviewed-by
  Legacy-compatible command that writes the older promotion receipt after all dry-run gates pass.

index
  Build a generated local SQLite search index.

search
  Search zettels, object manifest entries, views, and source map entries through the generated index.

pack
  Create a portable workpack from a saved view.

import --dry-run
  Preview a workpack import without mutating the target archive.

share --dry-run
  Preview a governed archive share from a saved view with scope and trust gates.

pilot-plan
  Plan a safe first real personal/team archive pilot without writing files.

preflight
  Check an archive before connecting real personal or team data.

recovery-plan, restore-drill
  Plan and rehearse local control-plane recovery before the first real source scan.

sources, add-source, source-mounts, scan-source
  Register and map source worlds with metadata-only dry-runs before approved writes.
```

## Requirements

```text
Python 3.10+
PyYAML
```

Install dependency:

```powershell
python -m pip install PyYAML
```

## Usage

Windows PowerShell from the repository root:

```powershell
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive
```

macOS/Linux shell from the repository root:

```bash
python ai-archive-kit/cli/archive.py doctor ai-archive-kit/examples/fake-life-archive
```

From inside `ai-archive-kit/`, you can also use the package module without installing by temporarily setting `PYTHONPATH`.

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m ai_archive_kit.archive_cli doctor examples\fake-life-archive
```

macOS/Linux shell:

```bash
PYTHONPATH=src python -m ai_archive_kit.archive_cli doctor examples/fake-life-archive
```

Strict mode treats warnings as failure:

```powershell
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --strict
```

JSON output:

```powershell
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --json
```

`doctor --json` returns stable structured diagnostics. Paths inside diagnostics are archive-relative `/` paths where possible.

Initialize a new archive:

```powershell
python ai-archive-kit\cli\archive.py init .\tmp-my-archive `
  --type personal `
  --archive-id archive:personal:me `
  --principal-id person:me `
  --principal-name "Me" `
  --name "My Personal Archive"
```

The target path must be absent or empty.

List all zettels:

```powershell
python ai-archive-kit\cli\archive.py list-zettels ai-archive-kit\examples\fake-life-archive --status all
```

Read a zettel:

```powershell
python ai-archive-kit\cli\archive.py read-zettel ai-archive-kit\examples\fake-life-archive --zettel-id zet_20240504_fake_lunch_thought
```

Create an inbox draft:

```powershell
python ai-archive-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft title" `
  --body "Draft body"
```

Preview minting without writing canonical memory:

```powershell
python ai-archive-kit\cli\archive.py mint-zettel ai-archive-kit\examples\fake-life-archive `
  --path inbox\zet_20260519_draft_ai_lunch_note.md `
  --dry-run
```

Minting dry-run checks:

```text
draft lives in inbox/
status is draft
kind is allowed to become canonical
required frontmatter is present
provenance and visibility are explicit
provider URLs and local absolute paths are absent
required checklist items in zettel-kasten/zettel-rules.yml are passed
possible duplicate canonical zettels are reported
```

The JSON output includes:

```text
proposed_canonical_path
proposed_mint_receipt_path
proposed_draft_snapshot_path
checklist
near_duplicates
receipt_preview
blockers
warnings
```

Dry-run writes nothing. Real minting is available only through the CLI and requires both an approval flag and a reviewer id:

```powershell
python ai-archive-kit\cli\archive.py mint-zettel .\tmp-my-archive `
  --path inbox\PUT-THE-DRAFT-FILENAME-HERE.md `
  --approve `
  --reviewed-by person:me
```

Real minting writes:

```text
zettels/<same filename>.md
receipts/mint/<zettel_id>.mint.json
receipts/mint/drafts/<zettel_id>.draft.md
```

It keeps the original inbox draft. Blockers always stop the command. If warnings are present, add `--allow-warnings` only after intentionally reviewing them. `promote` remains available as a compatibility command for older examples and tests.

Build the generated search index:

```powershell
python ai-archive-kit\cli\archive.py index ai-archive-kit\examples\fake-life-archive
```

Search the generated index:

```powershell
python ai-archive-kit\cli\archive.py search ai-archive-kit\examples\fake-life-archive "lunch"
```

The index file lives at:

```text
db/archive-index.sqlite
```

It is a rebuildable search map. It is not the source of truth for archive memory.

Create a workpack from a saved view:

```powershell
python ai-archive-kit\cli\archive.py pack ai-archive-kit\examples\fake-life-archive `
  --view view.fake.education.gilwon `
  --purpose "Portable education context." `
  --mode reference
```

`pack` writes a new folder under:

```text
workpacks/
```

The first implementation includes selected zettel files, a view snapshot, and object manifest metadata. Original object files are not copied by default.

Preview importing a workpack:

```powershell
python ai-archive-kit\cli\archive.py import .\tmp-my-archive `
  .\some-workpack `
  --dry-run
```

Import dry-run reports proposed inbox writes, object manifest merges, duplicate zettel IDs, warnings, blockers, and a receipt preview. Real import is intentionally unavailable.

Preview sharing a saved view with another archive:

```powershell
python ai-archive-kit\cli\archive.py share ai-archive-kit\examples\fake-life-archive `
  --view view.fake.company.derived `
  --target-archive archive:company:fake-blue `
  --counterparty-id archive:company:fake-blue `
  --counterparty-fingerprint SHA256:fake-company-blue `
  --dry-run
```

Share dry-run checks:

```text
which zettels are included
which zettels are excluded
whether sensitive categories are blocked
whether the counterparty fingerprint matches archive-identity.yml
where the future share receipt would live
```

Preview ownership transfer without changing the archive:

```powershell
python ai-archive-kit\cli\archive.py transfer-ownership .\some-archive `
  --new-owner person:child `
  --operator-after person:child `
  --approved-by person:parent-a `
  --counterparty-id person:child `
  --counterparty-fingerprint SHA256:child-primary `
  --dry-run
```

Apply an archive-internal ownership transfer after the same gates pass:

```powershell
python ai-archive-kit\cli\archive.py transfer-ownership .\some-archive `
  --new-owner person:child `
  --operator-after person:child `
  --approved-by person:parent-a `
  --counterparty-id person:child `
  --counterparty-fingerprint SHA256:child-primary `
  --approve `
  --reviewed-by person:parent-a
```

`archive-identity.yml` also records the archive owner and operators. A family or company can own an archive while people or roles operate it. `transfer-ownership --dry-run` returns scope, trust, ownership, provider-change, and receipt previews. `transfer-ownership --approve --reviewed-by` updates only local archive identity and writes a `dry_run:false` receipt. It does not call GitHub, Cloudflare R2, Backblaze B2, Neon, rclone, restic, or KeePassXC APIs.

Inspect external provider bindings:

```powershell
python ai-archive-kit\cli\archive.py providers .\some-archive --format json
```

`provider-bindings.yml` describes GitHub, R2/B2, Neon, local backup, sync, backup, and keyring references without storing actual secrets. External permission changes remain manual and are listed in `provider_change_plan`. Real share, merge, fork, and external provider mutation are intentionally unavailable.

## Tests

From `ai-archive-kit/` on any OS:

```powershell
python -m unittest discover -s tests
```

The CLI accepts OS-native archive root paths, but archive-internal paths in JSON output are stable `/` relative paths.

Commands that return structured data support:

```powershell
--format json
```

## Editable Install

From `ai-archive-kit/`:

```powershell
python -m pip install -e .
archive doctor examples\fake-life-archive
```

## Safe Defaults

`init` writes:

```text
archive.yml
AGENTS.md
inbox/
zettels/
views/
objects/manifests/files.jsonl
db/schema.sql
zettel-kasten/
workbench/
receipts/
.gitignore
```

The generated archive keeps these defaults:

```text
AI writes to inbox only.
Canonical zettels require human minting.
Original files are referenced by sha256 object_id.
Provider URLs are forbidden inside zettels.
Secrets are ignored by .gitignore.
Local keyring/profile files are ignored by .gitignore.
```

Ignored local-only profile paths include:

```text
profiles/local/
profiles/*.local.yml
keyrings/local/
keyrings/*.local.yml
.archive-local/
```

`doctor` also checks for common accidental secret files and values, such as `.env`, private keys, credential exports, `api_key: ...`, `token: ...`, and `password: ...`.

## Schema Validation

`doctor` validates the main archive files against JSON Schema documents in `schemas/`.

It also validates ownership-transfer receipt examples at:

```text
receipts/lineage/*.ownership-transfer.json
```

Currently checked:

```text
archive.yml
archive-identity.yml
zettel frontmatter
objects/manifests/files.jsonl
views/*.yml
workpacks/*/package.yml
zettel-kasten/types.yml
zettel-kasten/actions.yml
zettel-kasten/policies.yml
zettel-kasten/zettel-rules.yml
```

The runtime validator intentionally supports a small useful JSON Schema subset: `type`, `required`, `properties`, `items`, and `enum`.
