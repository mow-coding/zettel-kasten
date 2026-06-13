# Source Intake Planner

Status: active baseline
Date: 2026-05-25

`source-intake` is the safe dry-run step between runtime context and draft creation.

It answers:

```text
What is this presentation/document/image/provider item/AI artifact,
and what safe reference can a draft zet cite?
```

## Normal Flow

```text
profile-resolve
-> runtime-context
-> source-intake --dry-run
-> create-draft --dry-run with --source-intake-plan
-> human draft approval
-> create inbox draft
-> optional block-header --dry-run
-> mint only with separate approval
```

## CLI

```bash
archive source-intake <archive-root> --dry-run --format json
```

Exactly one locator mode is allowed:

```text
--local-path <path>
--source <source_id> --item-id <source_map_item_id>
--source <source_id> --relative-path <path-inside-source>
--objet-ref <objet:sha256:...>
--object-id <sha256:...>
--provider <provider> --provider-object-id <safe-id> --provider-kind <kind>
--ai-artifact-ref <safe-ref> --runtime <codex|claude_code|other> --artifact-kind <kind>
```

## Output

The JSON result is stable for AI runtimes:

```text
ok
dry_run
lifecycle_action: source_intake_plan
archive_id
profile_id
input_kind
source_kind
objet_status
source_refs_for_draft
objet_ref
provider_object_ref
object_storage_context
content_access
draft_provenance_suggestions
blockers
warnings
next_safe_actions
would_change
```

`content_access` is explicit: file bodies are not read, full hashes are not calculated, and no copy/upload/import/OCR/transcription/provider API action occurs.

## Recording A Plan

For capture evidence, a reviewed dry-run plan can be recorded under
`receipts/sources/`:

```bash
archive source-intake-record <archive-root> \
  --source-intake-plan source-intake-plan.json \
  --dry-run \
  --format json
```

Approved mode writes one redacted source-intake plan record:

```bash
archive source-intake-record <archive-root> \
  --source-intake-plan source-intake-plan.json \
  --approve \
  --reviewed-by person:me \
  --format json
```

The recorder validates the plan with the same metadata-only safety rules used
by draft composition and blocks unredacted local paths, provider URLs, tokens,
and secrets. It does not read file bodies, calculate content hashes, capture
objets, create drafts, mint zets, upload, or clean.

## Draft Composition

From v0.2.23, `create-draft` can consume a saved source intake dry-run result:

```bash
archive create-draft <archive-root> \
  --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

The composer validates the plan before using it:

- `ok` must be true,
- `dry_run` must be true,
- `lifecycle_action` must be `source_intake_plan`,
- `blockers` must be empty,
- `source_refs_for_draft` must contain only safe refs,
- `content_access` must prove metadata-only behavior.

When valid, the safe refs are merged into draft `source_refs`, optional `source_intake` metadata is stored, and the local plan file path is not stored. The composer does not read the original source file or follow local paths inside the plan.

For privacy, `source_intake_candidate` refs from local-file plans are anonymized during draft composition. A candidate ref derived from a filename is rewritten to a plan-hash-based value such as `candidate:source-intake:<hash-prefix>` before it can be stored in draft frontmatter.

`source_intake.plan_sha256` is a commitment to the supplied dry-run JSON plan. It proves which plan object was used for draft composition; it does not independently re-run source intake or prove that the original source file still exists.

## Objet Rules

- `objet` is the WOM product-language term for source/original files outside Git.
- `object_id` remains the technical manifest identifier.
- `objects/manifests/files.jsonl` remains the source of truth for manifested objets.
- Direct `--object-id` and `--objet-ref` lookups block if the manifest record is missing.
- A local file that is not manifested becomes `candidate_unmanifested`.
- A provider-only item becomes `provider_reference`, not a fake `objet_ref`.
- AI artifacts become provenance context and do not pretend to be human-authored sources.

## Object Storage Context

The planner reads `provider-bindings.yml` to report:

```text
object_storage_configured
candidate_storage_providers
manual_setup_required
upload_performed: false
provider_api_called: false
```

If object storage is missing, the planner warns the user to run the object storage / objet setup planner before real objet capture.

## Non-Goals

This release does not:

- read file bodies,
- calculate full SHA-256 hashes,
- copy or upload files,
- import source content,
- OCR or transcribe media,
- parse/extract document bodies,
- call provider APIs,
- create inbox drafts automatically,
- bypass draft approval,
- mint canonical memory,
- sync providers.

MCP exposes only read-only `source_intake_plan`; it exposes no apply/capture/upload/sync/provider API tool.
