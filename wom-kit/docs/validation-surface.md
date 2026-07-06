# Validation Surface: What doctor, validate, repair, and preflight Each Guarantee

Status: reference
Date: 2026-06-11

Field feedback from the v0.3.2 upgrade asked a fair question: "which command
guarantees what?" This document is the answer. It describes the current
behavior of the shipped code, not an aspiration.

## The commands

| Command | What it runs | Failing condition | Notes |
| --- | --- | --- | --- |
| `archive doctor <root>` | The full Doctor walk (below) | any ERROR | warnings are reported but do not fail |
| `archive doctor <root> --strict` | same | any ERROR **or any WARN** | the strict gate for real use |
| `archive validate <root>` | the same Doctor walk | any ERROR **or any WARN** (strict by default) | `--allow-warnings` relaxes; `--strict` is accepted for doctor parity and changes nothing |
| `archive repair-gitignore <root> --dry-run` | missing WOM-kit safe `.gitignore` pattern planner | never writes | previews missing local-only/generated-store ignore patterns |
| `archive repair-gitignore <root> --approve --reviewed-by <actor>` | approved `.gitignore` pattern append | missing approval or archive errors | appends missing safe defaults only; does not rewrite or delete existing entries |
| `archive preflight <root>` | Doctor + readiness gates | per its own readiness report | adds Docker/runtime, source-map, and restore-drill readiness signals on top of diagnostics |

The Doctor walk checks: archive structure and symlink boundaries, zettel
frontmatter against `zettel-frontmatter.schema.json` (for `zettels/` and
`inbox/`), the `zettel-kasten/` rules layer against its schemas, object
manifests, derived text manifests, mint/promotion receipts, lifecycle
consistency, secret-like values, and provider-URL/absolute-path leaks.

## The YAML timestamp policy (the WOM-COMPAT-1 root, made explicit)

YAML 1.1 parses an **unquoted** ISO timestamp (`created_at:
2026-06-11T10:00:00+09:00`) into a datetime object, not a string.

- **Internally**, WOM-kit deliberately tolerates this: the schema validator
  accepts YAML datetimes where the schema says `string`
  (`schema_validator.matches_type`), and every writing pipeline (mint, migrate,
  index) normalizes datetimes back to ISO strings on serialization.
- **Externally**, a standard JSON Schema validator run against the raw parsed
  YAML will reject the same file. The on-disk file is therefore silently
  non-portable.

Since v0.3.2+, doctor surfaces this as a warning per field:

```text
WARN zettel_frontmatter_unquoted_timestamp: $.created_at is an unquoted YAML timestamp; quote it ...
```

`doctor --strict` and `validate` (default) treat it as failing. The fix is to
quote timestamp strings in hand-authored frontmatter:

```yaml
created_at: "2026-06-11T10:00:00+09:00"
```

`archive create-draft` and `archive migrate` already emit quoted strings; only
hand-written frontmatter is exposed.

## Output encoding

CLI output replaces characters the console encoding cannot represent instead of
crashing (`UnicodeEncodeError`). On a Korean Windows cp949 console, Korean text
renders natively; characters outside the codepage (emoji, box drawing) appear
as replacement characters rather than killing the command.

## Staged cleanup verifier exit status

`archive staged-cleanup-check <root> --staged <folder> --dry-run` is report-only
and never deletes. Its process exit status is also a safety signal:

- exit `0`: the check ran and `safe_to_cleanup` is `true`;
- exit `1`: the check failed, or the report says cleanup is not safe.

Automation should still read the JSON report for the detailed file statuses, and
must treat cleanup as approved only when `safe_to_cleanup` is `true`.

Use `--progress` when a large staged folder or large source/store file could make
the command appear silent. Progress goes to stderr and contains only stage names,
counts, and large-file byte totals; it does not add staged file names, object ids,
local absolute paths, provider URLs, tokens, or secret values.

## What none of these commands do

Doctor/validate/preflight are read-only. `repair-gitignore --approve` appends
missing `.gitignore` safety patterns only; it does not delete, clean, inspect
source bodies, upload, or sync. Frontmatter rewriting is exclusively `archive
migrate --approve` after its dry-run.

`repair-gitignore` includes local collaboration/runtime guardrails such as
`/collab/` and `/.mow-harness/` because those folders can contain prompts,
mailbox state, coordination logs, or local-only secrets when an archive is
operated from a larger AI workspace. The patterns are harmless when the folders
do not exist.
