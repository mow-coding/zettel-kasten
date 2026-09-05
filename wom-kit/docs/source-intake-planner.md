# Source Intake Planner

Status: historical metadata-planner contract, with current writer routing below
Updated: 2026-09-06

## Current writer routing

`source-intake` is still a read-only metadata planner. Do not apply its
metadata-only limits to the separate exact writers: `source-intake-record`
has an exact-human one-file route since v0.4.9, and `source-intake-batch` has
an exact-human batch route since v0.4.10. The latter hashes source bytes,
records reviewed intake evidence and prepares a separate capture request;
it does not itself preserve source files as objets. Use the
[runtime entrypoints](runtime-canonical-entrypoints.md) and
[capability matrix](capability-matrix.md) for the released routes.

The v0.4.0 refusal and older composition descriptions below are historical,
not a claim that currently released exact writers are closed. The unreleased
v0.4.20 scoped route is described separately at the end of this document.

## Historical v0.4.0 boundary

At v0.4.0, source-intake planning remained read-only.
`source-intake-record` and `source-intake-batch` approval fail with
`compound_exact_human_approval_binding_required` before private input read or
mutation and write no item/aggregate receipt. Approval examples below are
historical.

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

Stop after this preview. In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before private input/archive
reads or mutation and writes no source-intake plan record or receipt.

The recorder validates the plan with the same metadata-only safety rules used
by draft composition and blocks unredacted local paths, provider URLs, tokens,
and secrets. It does not read file bodies, calculate content hashes, capture
objets, create drafts, mint zets, upload, or clean.

Relative `--source-intake-plan` paths resolve from the archive root. An exact
existing plan is an idempotent success (`already_recorded`) and returns its
documented receipt path with no new write. Missing files, unsafe relative
paths, and occupied-but-different receipt paths use distinct fixed blocker
codes.

Local-file plans contain `local_file_identity_sha256` so two same-extension,
same-size, same-time files do not collapse to one redacted plan. This is a
path/stat fingerprint, explicitly not a content identity. Source intake still
does not open the file body or calculate its content hash.

## Recording Many Local Plans

Use a private archive-local `wom-kit/source-intake-batch-request/v0.1` JSON
manifest with 1-1,000 unique safe item ids:

```bash
archive source-intake-batch <archive-root> \
  --manifest workbench/source-intake-request.json \
  --dry-run --format json
```

Relative manifest and item paths resolve from the archive root for dry-run.
Approval returns `compound_exact_human_approval_binding_required` before
private item reads or mutation and writes no per-item or aggregate receipt.
The batch preview is not permission to capture, import, upload, draft, or mint.

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

If object storage is missing, the planner warns that object storage is not configured in `provider-bindings.yml` and points at `archive object-storage --dry-run` to plan setup before real objet capture.

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

The released v0.4.19 MCP intake surface exposes read-only `source_intake_plan`;
it does not expose this record writer. The unreleased scoped single-record
extension below must not be confused with source capture or a provider API.

## Unreleased v0.4.20 session-bound batch route

Status: source implementation and synthetic verification; not released and
not proof of a client recovery. This section describes the explicit scoped
CLI route, not MCP parity or replacement of the existing unscoped calls.

An AI with an established, claimed work session supplies its retained app/task/
session references and prepares the private request. The human reviews the
native decision; they do not prepare JSON or copy identifiers.

```text
archive source-intake-batch <archive-root> --client-app-ref <app> --task-route-ref <task> --work-session-ref <session> --manifest <private-request.json> --dry-run --format json
archive source-intake-batch <archive-root> --client-app-ref <app> --task-route-ref <task> --work-session-ref <session> --manifest <private-request.json> --approve --reviewed-by <reviewer> --format json
archive source-intake-batch <archive-root> --client-app-ref <app> --task-route-ref <task> --resume --format json
```

Fresh preview/apply requires the private request; scoped apply does not take a
copied expected-plan hash. Original resume accepts only the saved app/task route
and an optional same-session assertion. It rejects replacement requests,
reviewers, execution/approval identifiers and reconciliation flags. No explicit
original re-review option is available in this first slice: missing original
approval evidence is a blocker, not permission to manufacture another claim.

Resume uses retained original input and authenticated checkpoints. Completed
replay verifies output receipts and the prepared capture request, not absent
source inputs; it can therefore remain read-only after caller JSON/source
removal. `original_completion_verified` is not a claim that the source bytes
were captured, uploaded or backed up. Source intake still reports
`artifact_capture_performed: false`. The development integration now connects
these exact metadata outputs to scoped Git backup; isolated source-CLI tests
verify actual commits/pushes and original continuation. This is not installed
or release acceptance and does not include the referenced source bytes: scoped capture
and its independent preservation proof are still separate unfinished work.
Do not advertise end-to-end source preservation or delete source files based on
intake completion or metadata backup.

## Unreleased v0.4.20 session-bound single record

The existing `source-intake-record` is a separate one-receipt operation. It
records an already redacted metadata plan; it does not hash or copy source
bodies and does not manufacture the batch's prepared capture request.

```text
archive source-intake-record <archive-root> --client-app-ref <app> --task-route-ref <task> --work-session-ref <session> --source-intake-plan <private-plan.json> --dry-run --format json
archive source-intake-record <archive-root> --client-app-ref <app> --task-route-ref <task> --work-session-ref <session> --source-intake-plan <private-plan.json> --approve --reviewed-by <reviewer> --format json
archive source-intake-record <archive-root> --client-app-ref <app> --task-route-ref <task> --resume --format json
```

The AI retains the app/task route and prepares inputs; the person reviews the
native change. Original resume requires no caller JSON, new reviewer, plan
digest or approval ID. A missing or invalid original approval is a blocker,
not an automatic new approval request. Completed replay verifies the original
authenticated receipt/checkpoint and current exact whole output; it does not
turn a copied matching JSON file into an approved record.

MCP `source_intake_record` uses the same service with `mode` set to `preview`,
`apply` or `resume`, explicit `client_app_ref`/`task_route_ref` and optional
same-session assertion on resume. Fresh calls supply `source_intake_plan` and
the claimed `work_session_ref`; only fresh apply supplies `reviewed_by`.
Both archive and input path must satisfy MCP allowed-root policy. There are
no public key-provider, native-dialog, claim or execution override parameters.
Its serial lane retains cancellation while waiting and content-free stage/count
progress. A heartbeat repeating the last observed state is liveness, not proof
that additional items completed.

This is development-source integration, not a release or client result. The
single record is not yet a newly authenticated Git producer; do not assume the
batch producer accepts it. An interrupted unpublished stage remains preserved,
not silently adopted or deleted. Unknown destination bytes, symlinks/reparse
points and unexpected hardlinks block the scoped operation.
