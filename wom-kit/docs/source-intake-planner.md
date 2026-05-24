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
-> create-draft --dry-run with source_refs
-> human draft approval
-> create inbox draft
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
- mint canonical memory,
- sync providers.

MCP exposes only read-only `source_intake_plan`; it exposes no apply/capture/upload/sync/provider API tool.
