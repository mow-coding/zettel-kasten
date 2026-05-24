# Zettel-Kasten Phase 2 Implementation Plan

Date: 2026-05-19

Project/system name: `zettel-kasten`

Current workspace root:

```text
C:\Users\example\dev\zettel-kasten
```

Rename status:

```text
Confirmed on 2026-05-20. The earlier temporary ontology path is now historical context.
```

This document is the handoff plan for Phase 2. It explains what was finished in Phase 1 and what should happen next.

## Phase 1 Completion Snapshot

Phase 1 reached the first useful minimum:

```text
v0.2 zettel-kasten layer design: done
types.yml, actions.yml, policies.yml: done
zettel writing and promotion rules: done
minimal CLI doctor/init: done
minimal MCP server: done
tests and fake archive validation: done
```

Important files created or updated in Phase 1:

```text
wom-kit/specs/zettel-kasten.md
wom-kit/specs/zettel-lifecycle.md
wom-kit/zettel-kasten/types.yml
wom-kit/zettel-kasten/actions.yml
wom-kit/zettel-kasten/policies.yml
wom-kit/zettel-kasten/zettel-rules.yml
wom-kit/src/wom_kit/archive_cli.py
wom-kit/src/wom_kit/mcp_server.py
wom-kit/tests/test_cli.py
wom-kit/tests/test_mcp_server.py
wom-kit/mcp/README.md
wom-kit/cli/README.md
```

Last known verification:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
cd wom-kit
python -m unittest discover -s tests
```

Expected result:

```text
doctor strict: 0 errors, 0 warnings
unittest: 45 tests passed
```

## Phase 2 Goal

Phase 2 should turn the v0.2 draft into a more reliable local toolkit.

The goal is not to make a big app yet. The goal is to make the archive protocol trustworthy enough that a human and AI can use it repeatedly without breaking memory.

Plain-language version:

```text
Phase 1 made the skeleton.
Phase 2 should add stronger bones, better checks, and a safer workflow.
```

## Phase 2 Non-Goals

Do not do these unless the user explicitly changes direction:

```text
Do not build a web UI yet.
Do not migrate the user's real Notion data yet.
Do not connect cloud storage providers yet.
Do not auto-promote AI drafts into canonical zettels.
Do not write private personal data into examples or tests.
Do not rename the physical folder from inside Codex unless the user explicitly asks.
```

## Work Package A: Folder Rename Handoff

Status:

```text
Completed on 2026-05-20.
```

Purpose:

Make sure the project survives the physical folder rename from `ontology` to `zettel-kasten`.

Completed checks:

- The current root was confirmed as `C:\Users\example\dev\zettel-kasten`.
- The old `C:\Users\example\dev\ontology` folder was not present.
- `AGENTS.md` was updated so `Current Working Root` points to the renamed folder.
- Active handoff text was updated so future agents do not treat `ontology` as the current root.
- Historical meeting minutes and decision logs were left intact when they mention the old path.
- `archive doctor --strict` and the unit test suite still pass after the rename.

Useful historical-reference search:

```powershell
rg -n "C:\\Users\\example\\dev\\ontology|dev\\ontology|ontology"
```

Do not erase historical records just because they mention the old path. Update active instructions and current handoff docs only.

Acceptance criteria:

```text
AGENTS.md points to the renamed folder.
Active docs no longer instruct agents to use the old root.
Historical meeting minutes may still mention the old root as past context.
Tests still pass after the rename.
```

## Work Package A.5: Cross-Platform Baseline

Status:

```text
Completed on 2026-05-20.
```

Purpose:

Keep the project Windows-first without splitting the codebase into separate Windows, macOS, and Linux implementations.

Decision:

```text
Use one shared Python core.
Separate only installation notes, command examples, and tests by OS.
Use POSIX-style archive-relative paths in CLI JSON and MCP output.
```

Implemented baseline:

- Added `docs/platform-support.md`.
- Added a shared path helper in the Python package.
- Normalized archive-internal output paths to `/`.
- Allowed Windows-style relative path input such as `inbox\example.md`.
- Rejected archive-relative paths that are absolute or escape through `..`.
- Expanded unsafe zettel reference detection to include common POSIX local absolute paths such as `/Users/...` and `/home/...`.
- Added tests for path normalization, unsafe paths, doctor JSON output paths, and MCP read path handling.

Acceptance criteria:

```text
No OS-specific codebase split.
Windows remains the primary development path.
Archive-internal JSON/MCP paths are stable across OSes.
Tests cover Windows-style and POSIX-style path behavior.
```

## Work Package B: Schema And Validation Layer

Status:

```text
Completed on 2026-05-20.
```

Purpose:

Make `archive doctor` more trustworthy by validating the main files against explicit schemas.

Recommended structure:

```text
wom-kit/schemas/
  archive.schema.json
  zettel-frontmatter.schema.json
  object-manifest-entry.schema.json
  view.schema.json
  workpack.schema.json
  zettel-kasten-types.schema.json
  zettel-kasten-actions.schema.json
  zettel-kasten-policies.schema.json
  zettel-rules.schema.json
```

Completed tasks:

1. Chose JSON Schema files plus a lightweight internal validator.
2. Added validation for `archive.yml`.
3. Added validation for zettel frontmatter.
4. Added validation for `objects/manifests/files.jsonl`.
5. Added validation for `views/*.yml`.
6. Added validation for `workpacks/*/package.yml`.
7. Added validation for `zettel-kasten/*.yml`.
8. Added malformed archive, manifest, view, workpack, and zettel-kasten layer tests.
9. Kept `archive doctor <path> --strict --json` machine-readable output stable.

Acceptance criteria:

```text
Valid fake archive passes.
Invalid fixtures fail with clear error codes.
doctor --json returns stable structured output.
doctor text output remains beginner-readable.
```

Beginner note:

Schemas are like a checklist for files. They help Codex say "this zettel is missing a required field" instead of silently accepting a broken note.

Implemented notes:

```text
The schema files use JSON Schema 2020-12 syntax.
The runtime validator intentionally supports a small subset first: type, required, properties, items, and enum.
This keeps dependencies small while making the protocol contract explicit.
```

## Work Package C: CLI Hardening

Status:

```text
Completed on 2026-05-20 for the safe CLI workbench subset.
```

Purpose:

Turn the CLI from a minimal prototype into the main local workbench.

Candidate commands:

```text
archive doctor <archive>
archive init <target>
archive list-zettels <archive>
archive read-zettel <archive> <zettel-id>
archive create-draft <archive>
archive validate <archive>
archive index <archive>
archive search <archive>
archive promote --dry-run <archive> <draft-id>
```

Completed tasks:

1. Extracted reusable zettel/view service functions into a shared service module.
2. Added `--format text|json` for data-returning CLI commands.
3. Added `list-zettels` using shared service logic.
4. Added `read-zettel`.
5. Added `create-draft`, restricted to `inbox/`.
6. Added `promote --dry-run` before any real promotion command.
7. Added more path-safety checks for zettel reads and promotion.
8. Added tests for the safe CLI commands.

Implemented CLI commands:

```text
archive validate <archive>
archive list-zettels <archive>
archive read-zettel <archive> --zettel-id <id>
archive read-zettel <archive> --path <inbox-or-zettels-path>
archive create-draft <archive>
archive promote <archive> --path <draft-path> --dry-run
archive index <archive>
archive search <archive> "<query>"
```

Notes:

```text
Real promotion remains unavailable; only dry-run promotion exists.
```

Acceptance criteria:

```text
Every CLI command has at least one success test.
Risky commands have failure tests.
Commands return useful text for humans and stable JSON for AI callers.
Canonical zettels are not modified without explicit human intent.
```

## Work Package D: MCP Hardening

Status:

```text
Completed on 2026-05-20 for the safe MCP parity subset.
```

Purpose:

Make MCP a safe AI-facing interface over the same logic used by the CLI.

Completed tasks:

1. Keep MCP stdio-only unless a real need appears.
2. Reuse CLI/service functions, not duplicated logic.
3. Add tool parity for safe CLI commands.
4. Add structured errors that are easy for AI clients to interpret.
5. Considered migrating to the official MCP Python SDK after checking current official docs.
6. Add a small client test harness for JSON-RPC messages.
7. Keep `create_draft_zettel` restricted to `inbox/`.
8. Do not expose real canonical promotion through MCP; keep MCP promotion checks dry-run-only.

Implemented notes:

```text
MCP remains stdio-only.
The official MCP Python SDK is Tier 1 and stable, but this project keeps the dependency-light direct JSON-RPC server for now.
MCP tools now reuse shared archive service logic for list/read/create/list views/promotion check.
MCP tools also expose generated index and search through the shared service layer.
promotion_check is dry-run only and never writes canonical memory.
```

Candidate MCP tools:

```text
archive_doctor
archive_init
list_zettels
read_zettel
create_draft_zettel
list_views
archive_index
archive_search
promotion_check
```

Acceptance criteria:

```text
MCP tests cover initialize, tools/list, tools/call, and errors.
MCP tools match CLI behavior.
MCP stdout contains only protocol JSON messages.
No MCP tool can accidentally overwrite canonical archive memory.
```

## Work Package E: Local Index And Search

Status:

```text
Completed on 2026-05-20 for the generated SQLite index/search subset.
```

Purpose:

Give the archive a practical memory lookup layer.

Recommended first version:

```text
archive index <archive>
archive search <archive> "<query>"
```

Tasks:

1. Decided to use a new generated database file: `db/archive-index.sqlite`.
2. Indexed zettel IDs, titles, kinds, status, frontmatter JSON, and body text.
3. Indexed object manifest entries.
4. Indexed views.
5. Deferred SQLite FTS5; first version uses portable SQLite `LIKE` search.
6. Made indexing repeatable by rebuilding the generated tables on every run.
7. Added CLI and MCP tests using temporary copies of the fake archive.

Implemented commands and tools:

```text
archive index <archive>
archive search <archive> "<query>"
archive_index
archive_search
```

Acceptance criteria:

```text
archive index can be run multiple times without duplicating rows.
archive search can find zettels by title, tag, body text, and object_id.
No raw private paths are copied into public test fixtures.
```

Beginner note:

The index is not the archive itself. It is more like a map. If the map breaks, the original Markdown zettels and object manifests should still be readable.

Implemented note:

```text
The generated index is ignored by wom-kit/.gitignore as **/db/archive-index.sqlite.
```

## Work Package F: Zettel Promotion Workflow

Status:

```text
Completed on 2026-05-20 for dry-run readiness checks and receipt preview.
```

Purpose:

Make the movement from AI draft to canonical zettel safe and reviewable.

Tasks:

1. Implemented `archive promote --dry-run`.
2. Added rule checks from `zettel-kasten/zettel-rules.yml`.
3. Added required checklist status output.
4. Kept unsafe reference detection in promotion checks.
5. Added duplicate hints for same canonical target, same zettel id, same title, and very similar body start.
6. Added proposed canonical file path output.
7. Added proposed receipt path and structured receipt preview output.
8. Kept real promotion unavailable; explicit real promotion remains a later step.

Implemented output:

```text
proposed_canonical_path
proposed_receipt_path
checklist
near_duplicates
receipt_preview
blockers
warnings
would_change
```

Implemented safety behavior:

```text
fleeting_capture cannot be promoted directly because zettel-rules.yml marks it canonical_allowed: false.
Required checklist items must be passed before dry-run reports ok true.
Subjective checklist items can be marked in frontmatter under promotion.checklist.
Dry-run never writes canonical zettels or receipt files.
```

Acceptance criteria:

```text
Dry-run promotion never modifies canonical zettels.
The command explains what would happen.
The command blocks promotion when required provenance or visibility fields are missing.
Promotion receipts are designed before real writes are enabled.
```

## Work Package G: Workpack Export And Import Dry Run

Status:

```text
Completed on 2026-05-20 for view-based pack creation and import dry-run preview.
```

Purpose:

Make archive subsets portable without losing provenance.

Candidate commands:

```text
archive pack <archive> --view <view-id>
archive import --dry-run <archive> <workpack>
```

Tasks:

1. Kept `workpacks/*/package.yml` validated by `archive doctor`.
2. Implemented `archive pack <archive> --view <view-id>`.
3. Included selected zettel files, a view snapshot, and object manifest metadata.
4. Kept real object file copying disabled by default; object references are metadata-only in the first implementation.
5. Implemented `archive import <archive> <workpack> --dry-run`.
6. Added tests around pack creation, unknown views, import dry-run mutation safety, real import being unavailable, and duplicate zettel IDs.

Implemented commands:

```text
archive pack <archive> --view <view-id> --purpose "<purpose>"
archive import <target-archive> <workpack-or-package.yml> --dry-run
```

Implemented safety behavior:

```text
pack writes only under source archive workpacks/.
import without --dry-run is blocked.
import dry-run proposes target inbox/ writes but does not create them.
import dry-run proposes object manifest merges but does not append them.
import dry-run proposes an import receipt but does not write it.
duplicate target zettel IDs block import dry-run.
```

Acceptance criteria:

```text
Pack output is deterministic enough to test.
Import dry-run explains conflicts without mutating the archive.
No private absolute paths leak into portable workpacks.
```

## Work Package H: Keyring And Profile Support

Status:

```text
Completed on 2026-05-20 for local profile/secret safety baseline.
```

Purpose:

Prepare the archive for multiple local identities and mounted archives without committing secrets.

Tasks:

1. Updated `specs/keyring-profile.md`.
2. Decided local-only profile files live under ignored paths such as `profiles/local/`, `keyrings/local/`, and `.archive-local/`.
3. Added `.gitignore` protection for local profiles, env files, private keys, credential exports, and password-manager files.
4. Added `archive doctor` checks for unsafe secret-like files and values.
5. Added a simple future profile resolution design before implementing OS keyring integration.

Implemented local-only paths:

```text
profiles/local/
profiles/*.local.yml
keyrings/local/
keyrings/*.local.yml
.archive-local/
```

Implemented doctor diagnostics:

```text
local_profile_gitignore_missing
local_profile_gitignore_incomplete
secret_file_detected
secret_value_detected
local_profile_env_values
local_profile_secret_value
```

Not implemented yet:

```text
OS keychain/keyring integration.
Runtime profile selection.
Secret retrieval.
Mount enforcement for MCP.
```

Acceptance criteria:

```text
Secrets are never required for the fake archive.
Local profile files are ignored by default.
doctor can warn about common accidental-secret patterns.
```

## Work Package I: Documentation And New User Flow

Status:

```text
Completed on 2026-05-20.
```

Purpose:

Make the kit understandable to a future beginner user and to future AI agents.

Tasks:

1. Added `docs/phase-2-quickstart.md`.
2. Added new archive initialization instructions.
3. Added AI draft creation instructions.
4. Added human promotion dry-run instructions.
5. Added doctor/validate instructions.
6. Added MCP local run instructions.
7. Kept mutation examples on temporary archives or temporary fake archive copies.
8. Added `docs/new-user-flow.md` for the normal operating loop.
9. Linked the beginner docs from README, CLI README, and MCP README.

Implemented docs:

```text
docs/phase-2-quickstart.md
docs/new-user-flow.md
docs/platform-support.md
```

Acceptance criteria:

```text
A new thread can follow the docs without guessing.
Commands are copy-pasteable in PowerShell.
Docs clearly distinguish implemented behavior from planned behavior.
```

## Suggested Phase 2 Order

Recommended order:

```text
0. After folder rename, update AGENTS.md and rerun tests.
1. Complete the cross-platform baseline.
2. Add schema validation and doctor --json.
3. Harden CLI around list/read/create-draft/validate.
4. Refactor shared service logic for CLI and MCP.
5. Harden MCP using shared services.
6. Add local index and search.
7. Add promotion dry-run.
8. Add workpack pack/import dry-run.
9. Add keyring/profile safety checks.
10. Improve quickstart documentation.
```

Why this order:

```text
Validation comes before more features.
CLI comes before MCP because it is easier to test.
Search comes before promotion because promotion needs context.
Dry-run comes before real mutation because archive memory should be hard to damage.
```

## Restart Prompt If Needed

If a future thread needs to inspect or extend Phase 2, start with something like:

```text
Use this project folder as the working root:
C:\Users\example\dev\zettel-kasten

First read:
AGENTS.md
meeting-minutes/2026-05-19-full-project-conversation.md
meeting-minutes/2026-05-20-project-orientation-and-root-confirmation.md
archive-infra-decision-log-2026-05-19.md
archive-infra-decision-log-2026-05-20.md
wom-kit/README.md
wom-kit/plans/phase-2-implementation-plan.md
wom-kit/docs/phase-2-quickstart.md
wom-kit/docs/new-user-flow.md

Confirm the current state, rerun the basic verification commands, then decide whether to start a Phase 3 plan or deepen one of the safe dry-run workflows.
```

## Useful Commands For The Next Thread

From the renamed project root:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
```

From inside `wom-kit/`:

```powershell
python -m unittest discover -s tests
```

Optional package-style execution:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli doctor examples\fake-life-archive --strict
python -m wom_kit.mcp_server
```

Search for old temporary path references:

```powershell
rg -n "C:\\Users\\example\\dev\\ontology|dev\\ontology|ontology"
```

## Risks To Watch

Path confusion:

```text
The physical folder was temporarily named ontology, but the project/system name is zettel-kasten.
After the folder rename, only historical records should keep the old path.
```

Naming confusion:

```text
wom-kit is the toolkit/protocol folder.
zettel-kasten is the project/system name.
```

MCP drift:

```text
The first MCP server is a direct JSON-RPC implementation.
It should eventually be compared with the official MCP Python SDK.
```

Schema overbuild:

```text
Do not make schemas so complex that basic archive use becomes painful.
Prefer small checks with clear messages.
```

Private data risk:

```text
Examples and tests must stay fake.
Real user archive data should not be added to public sample fixtures.
```

## Definition Of Done For Phase 2

Status:

```text
Met on 2026-05-20 for the safe local toolkit subset.
```

Phase 2 can be considered done when:

```text
The renamed root is reflected in active instructions.
doctor has schema-backed validation and JSON output.
CLI has safe list/read/create-draft/validate/index/search basics.
MCP reuses shared logic and has tests for common success and error flows.
Search/index works on the fake archive.
Promotion has a dry-run workflow.
Workpack export/import has at least dry-run behavior.
Docs explain the workflow clearly.
Meeting minutes and decision logs are current.
```

