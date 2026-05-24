# WOM-kit CLI

This is the current minimal CLI for WOM archive nodes.

The filesystem folder is `wom-kit/`, the Python import package is `wom_kit`, and the preferred product language remains WOM, `zet`, `node`, and `mint -> delegate -> attest -> anchor`.

See `wom-kit/docs/concepts/naming-and-terminology.md` for the naming baseline.

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
  Create a draft zettel in inbox/. It can consume a validated source-intake dry-run plan with --source-intake-plan and a validated prompt-boundary dry-run report with --prompt-boundary-report.

profile-wallet --dry-run
  Preview wallet-ready WOM profile/node identity metadata. This never generates private keys, signs data, stores secrets, creates wallets, or calls blockchain/provider APIs.

prompt-boundary --dry-run
  Inspect inline or archive-relative untrusted text for obvious prompt-injection and unsafe-agent strings. This never calls LLMs, executes inspected text, approves, mints, or writes files.

block-header --dry-run
  Preview the derived header for one draft or canonical zet. This returns `block = zet + header` metadata and hashes without writing, minting, reading objet bodies, or calling providers.

source-intake --dry-run
  Classify one source/objet locator and return safe `source_refs_for_draft` before draft creation. This never reads file bodies, hashes, copies, uploads, imports, OCRs, transcribes, extracts, or calls provider APIs.

github-repo --dry-run
  Plan a private GitHub repository for a resolved WOM profile without writing files or calling GitHub.

github-repo --approve --reviewed-by
  Write only local provider metadata and a provider setup receipt. This does not create a repository, configure remotes, push, or sync.

object-storage --dry-run
  Plan private object storage for WOM objets without writing files, creating buckets, calling provider APIs, uploading, syncing, copying, hashing, or importing source content.

object-storage --approve --reviewed-by
  Write only local provider metadata and a provider setup receipt. This does not create buckets, authenticate, upload, sync, copy, hash, or import source files.

mint-zet --dry-run
  Check minting readiness and preview canonical path, mint receipt, and draft snapshot without writing.

mint-zet --approve --reviewed-by
  Mint an inbox draft zet into canonical private archive memory and write receipt/snapshot evidence.

mint-zettel
  Transitional compatibility alias for mint-zet.

promote --dry-run
  Legacy-compatible promotion readiness check.

promote --approve --reviewed-by
  Legacy-compatible command that writes the older promotion receipt after all dry-run gates pass.

index
  Build a generated local SQLite search index.

search
  Search zettels, object manifest entries, views, and source map entries through the generated index.

parcel
  Create a portable parcel from a saved view. The v0.2 compatibility path still writes under workpacks/.

pack
  Transitional compatibility alias for parcel.

admit --dry-run
  Preview admitting a parcel/workpack without mutating the target archive.

import --dry-run
  Transitional compatibility alias for admit.

share --dry-run
  Legacy-compatible dry-run for the older share language. Product language should prefer delegate.

delegate-zet --dry-run
  Preview scoped zet delegation and return a delegate capability receipt preview without writing files.

delegate-zet --approve --reviewed-by
  Write a local delegate receipt after the same dry-run gates pass.

attest-zet --dry-run
  Preview attestation of a delegated foreign zet receipt without writing files.

anchor-zet --dry-run
  Preview anchoring an attested foreign zet into local meaning without writing metadata.

check-safe-html --path <zet> --dry-run
  Read-only validator that previews whether a v0.2 Markdown-compatible zet is compatible with future WOM Safe HTML Profile migration. It blocks obvious unsafe raw HTML patterns and never writes files.

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
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive
```

macOS/Linux shell from the repository root:

```bash
python wom-kit/cli/archive.py doctor wom-kit/examples/fake-life-archive
```

From inside `wom-kit/`, you can also use the package module without installing by temporarily setting `PYTHONPATH`.

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli doctor examples\fake-life-archive
```

macOS/Linux shell:

```bash
PYTHONPATH=src python -m wom_kit.archive_cli doctor examples/fake-life-archive
```

Strict mode treats warnings as failure:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
```

JSON output:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --json
```

`doctor --json` returns stable structured diagnostics. Paths inside diagnostics are archive-relative `/` paths where possible.

Initialize a new archive:

```powershell
python wom-kit\cli\archive.py init .\tmp-my-archive `
  --type personal `
  --archive-id archive:personal:me `
  --principal-id person:me `
  --principal-name "Me" `
  --name "My Personal Archive"
```

The target path must be absent or empty.

List all zettels:

```powershell
python wom-kit\cli\archive.py list-zettels wom-kit\examples\fake-life-archive --status all
```

Read a zettel:

```powershell
python wom-kit\cli\archive.py read-zettel wom-kit\examples\fake-life-archive --zettel-id zet_20240504_fake_lunch_thought
```

Create an inbox draft:

```powershell
python wom-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft title" `
  --body "Draft body"
```

Compose a draft preview from a prompt-boundary report:

```powershell
python wom-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft title" `
  --body "Draft body" `
  --dry-run `
  --prompt-boundary-report .\prompt-boundary-report.json `
  --format json
```

The report path is not stored in draft frontmatter. `low` risk is not proof of safety, `medium` risk is allowed with warnings, and `high` risk blocks draft creation.

Preview minting without writing canonical memory:

```powershell
python wom-kit\cli\archive.py mint-zet wom-kit\examples\fake-life-archive `
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
python wom-kit\cli\archive.py mint-zet .\tmp-my-archive `
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
python wom-kit\cli\archive.py index wom-kit\examples\fake-life-archive
```

Search the generated index:

```powershell
python wom-kit\cli\archive.py search wom-kit\examples\fake-life-archive "lunch"
```

The index file lives at:

```text
db/archive-index.sqlite
```

It is a rebuildable search map. It is not the source of truth for archive memory.

Create a parcel from a saved view:

```powershell
python wom-kit\cli\archive.py parcel wom-kit\examples\fake-life-archive `
  --view view.fake.education.gilwon `
  --purpose "Portable education context." `
  --mode reference
```

`parcel` writes a new folder under the v0.2 compatibility path:

```text
workpacks/
```

The first implementation includes selected zettel files, a view snapshot, and object manifest metadata. Original object files are not copied by default.

Preview admitting a parcel/workpack:

```powershell
python wom-kit\cli\archive.py admit .\tmp-my-archive `
  .\some-workpack `
  --dry-run
```

Admit/import dry-run reports proposed inbox writes, object manifest merges, duplicate zettel IDs, warnings, blockers, and a receipt preview. Real admit/import is intentionally unavailable.

Preview legacy sharing of a saved view with another archive:

```powershell
python wom-kit\cli\archive.py share wom-kit\examples\fake-life-archive `
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

Preview counterparty-bound zet delegation:

```powershell
python wom-kit\cli\archive.py delegate-zet wom-kit\examples\fake-life-archive `
  --view view.fake.company.derived `
  --target-policy counterparty_bound `
  --target-archive archive:company:fake-blue `
  --counterparty-id archive:company:fake-blue `
  --counterparty-fingerprint SHA256:fake-company-blue `
  --dry-run
```

Preview one-time claimable delegation without choosing the recipient yet:

```powershell
python wom-kit\cli\archive.py delegate-zet wom-kit\examples\fake-life-archive `
  --view view.fake.company.derived `
  --target-policy claimable_once `
  --dry-run
```

`claimable_once` does not write a claim registry yet. It only previews a delegate capability that can later be bound to the attesting archive.

Write a real delegate receipt after review:

```powershell
python wom-kit\cli\archive.py delegate-zet wom-kit\examples\fake-life-archive `
  --view view.fake.company.derived `
  --target-policy counterparty_bound `
  --target-archive archive:company:fake-blue `
  --counterparty-id archive:company:fake-blue `
  --counterparty-fingerprint SHA256:fake-company-blue `
  --approve `
  --reviewed-by person:me
```

Real delegate writes create `receipts/delegate/*.delegate.json` with `dry_run: false`. They do not send data, write attestations, write anchors, or create claim/spent registries.

Preview ownership transfer without changing the archive:

```powershell
python wom-kit\cli\archive.py transfer-ownership .\some-archive `
  --new-owner person:child `
  --operator-after person:child `
  --approved-by person:parent-a `
  --counterparty-id person:child `
  --counterparty-fingerprint SHA256:child-primary `
  --dry-run
```

Apply an archive-internal ownership transfer after the same gates pass:

```powershell
python wom-kit\cli\archive.py transfer-ownership .\some-archive `
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
python wom-kit\cli\archive.py providers .\some-archive --format json
```

`provider-bindings.yml` describes GitHub, R2/B2, Neon, local backup, sync, backup, and keyring references without storing actual secrets. External permission changes remain manual and are listed in `provider_change_plan`. Real share, merge, fork, and external provider mutation are intentionally unavailable.

Plan objet storage metadata without touching any provider:

```powershell
python wom-kit\cli\archive.py object-storage .\tmp-my-archive `
  --dry-run `
  --provider cloudflare-r2 `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --storage-account-ref storage:account:honggildong `
  --format json
```

The default bucket/container proposal is `zettel-kasten-<normalized-profile-slug>-objets`, with `archives/<archive_id>/objets/` as the default prefix. Approved mode writes only `provider-bindings.yml`, a provider setup receipt, and optional ignored local profile hints when `--write-local-profile` is supplied.

Plan a source/objet reference before drafting:

```powershell
python wom-kit\cli\archive.py source-intake .\tmp-my-archive `
  --dry-run `
  --object-id sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --format json
```

`source-intake` accepts exactly one locator mode: `--local-path`, `--source` with `--item-id`, `--source` with `--relative-path`, `--objet-ref`, `--object-id`, provider object refs, or AI artifact refs. It returns metadata-only classification, `objet_status`, object storage context, and safe `source_refs_for_draft` that can be passed to `create-draft --dry-run`.

Compose a draft from the source intake plan without manually copying refs:

```powershell
python wom-kit\cli\archive.py source-intake .\tmp-my-archive `
  --dry-run `
  --object-id sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --format json > source-intake-plan.json

python wom-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft title" `
  --body "Draft body" `
  --dry-run `
  --source-intake-plan source-intake-plan.json `
  --format json
```

`create-draft` validates the plan before using it. The plan must be a successful source-intake dry-run with no blockers and metadata-only content access. WOM-kit does not read the original source file, follow local paths in the plan, or store the local plan file path in draft frontmatter.

Preview a block header from an existing zet:

```powershell
python wom-kit\cli\archive.py block-header wom-kit\examples\fake-life-archive `
  --path inbox\zet_20260519_draft_ai_lunch_note.md `
  --dry-run `
  --format json
```

The preview reads only the target zet file. It derives header metadata from frontmatter, hashes only the zet body text and normalized header preview, and does not hash referenced objet/source files.

## Tests

From `wom-kit/` on any OS:

```powershell
python -m unittest discover -s tests
```

The CLI accepts OS-native archive root paths, but archive-internal paths in JSON output are stable `/` relative paths.

Commands that return structured data support:

```powershell
--format json
```

## Editable Install

From `wom-kit/`:

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

It also validates receipt files at:

```text
receipts/lineage/*.ownership-transfer.json
receipts/delegate/*.delegate.json
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

The runtime validator intentionally supports a small useful JSON Schema subset: `type`, `required`, `properties`, `items`, `enum`, `const`, `allOf`, and simple `if`/`then` conditionals.
