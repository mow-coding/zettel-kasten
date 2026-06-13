# Changelog

All notable public releases of `zettel-kasten`, `zet`, and `ZET` should be documented here.

This project uses semantic versioning for public compatibility checkpoints.

## Unreleased

- Added optional `archive objet-capture --project-intake-receipt <receipt>` context validation, and matching selection-manifest support via `project_intake_receipt_path`, so reviewed project-intake decisions can gate capture planning before staged bytes are read.

## v0.3.6 - 2026-06-13

- Added optional `archive source-intake --project-intake-receipt <receipt>` context validation so one-item metadata dry-runs can carry a reviewed project-intake session receipt without echoing answer text or granting automatic execution authority.
- Added `archive project-intake-status --receipt <receipt> --dry-run` to review checklist coverage and receipt integrity without echoing recorded answer text or authorizing automatic execution.
- Added `archive project-intake-decisions --dry-run|--approve --reviewed-by <actor>` to validate and record human-reviewed project intake checklist answers as a local receipt without echoing answer text or running capture/draft/mint/cleanup steps.
- Extended `archive project-intake-plan --dry-run` with a human review checklist, classification labels, and a draft decision-record template while preserving the no-names/no-bodies privacy boundary.

## v0.3.5 - 2026-06-13

- Added `archive derive-text capture --from-manifest <jsonl>` for dry-run/approved batch registration of already extracted UTF-8 derived text.
- Batch derived-text manifests accept one JSON object per line with `source_object_id`, `text_file`, `derivation_kind`, `tool_name`, `tool_version`, and `review_status`; relative `text_file` paths resolve from the manifest location.
- Added `archive repair-gitignore <archive-root> --dry-run|--approve --reviewed-by <actor>` to append missing WOM-kit safe `.gitignore` patterns without rewriting existing entries.
- Removed private dogfood archive identifiers from public guardrail code and docs, keeping generic live-archive and `*-objets` protections.

## v0.3.4 - 2026-06-13

- Added `archive derive-text capture` for dry-run/approved registration of externally extracted text as provenance-aware derived text records.
- Added `objects/manifests/derived-text.jsonl`, local derived text body storage under `objects/derived-text/sha256/`, approval receipts under `receipts/derived-text-capture/`, doctor/schema validation, and search index ingestion for derived text.
- Standardized the first implemented derived-text vocabulary to `parser`, `ocr`, `asr`, `llm_vision` and `unreviewed`, `human_corrected`.

## v0.3.3 - 2026-06-13

Compatible fixes from v0.3.2 upgrade field feedback:

- CLI output no longer crashes on console encodings that cannot represent a character (e.g. emoji on a Korean Windows cp949 console); unencodable characters are replaced,
- doctor now warns (`zettel_frontmatter_unquoted_timestamp`) when frontmatter contains an unquoted YAML timestamp, with the field path and a quoting hint; `doctor --strict` and `validate` treat it as failing,
- `validate` accepts `--strict` for parity with doctor (validate already fails on warnings unless `--allow-warnings`),
- `staged-cleanup-check` now exits `0` only when the report is both `ok` and `safe_to_cleanup`; unsafe cleanup reports exit `1` while still returning the JSON report,
- `view-zets` now indexes list-valued facets as repeated scalar facet rows, so saved views and ad-hoc scalar filters can match zettels tagged with lists,
- `view-zets` now blocks list-valued filter inputs instead of silently broadening or guessing,
- objet-capture source-intake plan SHA binding now has regression coverage against a real `source-intake --dry-run` producer plan through dry-run and approve,
- added `wom-kit/docs/validation-surface.md` documenting what doctor, validate, preflight, and staged cleanup checks each guarantee.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- no archive migration is required for v0.3.2 users,
- rebuild the disposable search index with `archive index <archive-root>` to pick up list-valued facet indexing for `view-zets`,
- cleanup remains manual; `staged-cleanup-check` never deletes files.

## v0.3.2 - 2026-06-11

Frontmatter migration, redaction hardening, and the local capture spine.

Added:

- CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json`,
- approve-gated `archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json`,
- lossless handling for clean object-shaped `provenance.source` values by relocating them to `source_refs`,
- manual-review blockers for ambiguous or unsafe source values,
- doctor compatibility output and migration hints for legacy frontmatter failures,
- v0.3 zettel-rules guidance for required `provenance` and `visibility` subfields,
- approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` capturing approved staged files into the local content-addressed objet store (`objects/sha256/<2>/<64>`) with manifest records and always-written capture receipts,
- report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run` verifying every staged file is preserved or explicitly deferred before any manual cleanup; fails closed on unenumerable trees and never deletes,
- read-only CLI `archive related-zets <archive-root> --zettel-id <id>` with bidirectional typed-edge traversal (backlinks), depth 1-3, cycle safety, and edge-type filters,
- read-only CLI `archive view-zets <archive-root> --view-id <id> | --facet key=value ...` executing saved-view facet filters from `views/*.yml`,
- typed edges and zettel facets in the disposable search index,
- report-only artifact hygiene checker and six-class file-lifecycle baseline doc,
- an end-to-end test proving the full loop: stage -> capture -> draft -> mint -> cleanup-safe.

Privacy:

- redacted-zettel content suppression is now enforced across search, the on-disk index, `list-zettels`, `read-zettel`, block-header previews, projection previews, related-zets, and view-zets, with regression tests per surface.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- `--dry-run` writes no files anywhere; approve paths rewrite only reviewed targets,
- archives authored from older v0.2-draft rules should run the migration dry-run before strict v0.3 validation,
- the objet-capture write path refuses archives without an explicit sandbox marker,
- run `archive index` once to pick up edges and facets,
- private/live archives, provider sync, staged-original deletion, MCP write tools, ZET transport, and schema redesign are not part of this release.

## v0.3.1 - 2026-06-04

Shared update route preview.

Added:

- CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- service `shared_update_route_preview`,
- read-only route pointers for `delegate`, `attest`, `anchor`, and `none`,
- explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardening so free-form or hostile proposed-action metadata is not echoed as a route,
- public documentation, release note, and work log for the v0.3.1 route-preview boundary.

Compatibility:

- the route-preview command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- the command is dry-run only and writes no files,
- the command reuses `zet_shared_update_record_review_preview` before returning a route pointer,
- MCP exposes no shared-update route write/apply/approve tool for this boundary,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe free-form route metadata are not echoed,
- the route preview does not create real trust, import, acceptance, attestation, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.3.0 - 2026-06-03

Shared update attestation/review write boundary.

Added:

- CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- service `record_shared_update_attestation_review`,
- deterministic local review record and receipt paths under `shared-updates/attestation-reviews/` and `receipts/shared-updates/`,
- replay/overwrite refusal for the same reviewed shared update record,
- rollback if the receipt write fails after the review record write,
- public documentation, release note, and work log for the v0.3.0 first write boundary.

Compatibility:

- the shared-update attestation/review command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- MCP exposes no write/apply sibling tool for this boundary,
- the write reuses `zet_shared_update_record_review_preview` before recording anything,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed or persisted,
- `attest` records only a local human review decision and does not create real trust, import, acceptance, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.2.60 - 2026-06-02

v0.2.x freeze and v0.3.0 entry boundary.

Added:

- public [v0.2.x freeze and v0.3.0 entry boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md),
- release note and public-safe work log for the v0.2.60 checkpoint batch,
- capability matrix updates for the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- focused documentation tests for the freeze/boundary document.

Compatibility:

- no private archive migration is required,
- no product CLI command was added,
- no MCP tool was added,
- no archive service behavior changed,
- no schema changed,
- v0.3.0 is proposed to start with one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write,
- no real ZET transport, key-sharing registry, radio-frequency access creation, mirroring delivery, feed update, trust/import/acceptance/anchor mutation, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queue, worker, DID registry, wallet/key custody, public proof anchoring, blockchain, token, system token, validator governance, payment, staking, consensus, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.59 - 2026-06-02

ZET transport threat model and would-transport plan.

Added:

- CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- MCP `zet_transport_would_plan`,
- read-only service `zet_transport_would_plan`,
- method-specific planning-only risk/control previews for `key-sharing`, `radio-frequency`, and `mirroring`,
- public documentation, release note, and work log for the v0.2.59 planning batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the planner reuses the v0.2.56 single-record review preview policy before producing any plan,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed,
- no real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queues, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.58 - 2026-06-02

ZET shared update record review index.

Added:

- CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_index`,
- read-only service indexing for direct-child local shared update record JSON files,
- public documentation, release note, and work log for the v0.2.58 index batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the index reuses the v0.2.56 single-record review preview policy,
- unsafe records remain blocked per record and record body text is never echoed,
- no shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.57 - 2026-06-02

Capability matrix and README readability patch.

Added:

- public [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md) for implemented, read-only preview, approval-gated write, documented-only, local hygiene, and not-implemented surfaces,
- release note and public-safe work log for the v0.2.57 readability batch,
- focused documentation tests for the capability matrix and README release-tag sequence.

Changed:

- shortened the top-level README status summary and pointed readers to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- recorded a proposed v0.2.x closing plan and a narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

Compatibility:

- no private archive migration is required,
- no archive product CLI, MCP, service, provider, transport, trust/import, attestation/signature, anchor, payment, blockchain, token, worker, or full-auto behavior changed.

## v0.2.56 - 2026-06-02

ZET shared update record review preview.

Added:

- CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_preview`,
- read-only service validation for local archive-contained shared update record JSON before any receiver-side renewal action,
- release note and public-safe work log for the v0.2.56 preview batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the preview reads only the selected archive-relative JSON record,
- unsafe absolute paths, URL-like record paths, body-included records, token/secret-like values, and true mutation/write/transport/provider/trust flags block,
- no shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.55 - 2026-05-27

ZET shared update record baseline.

Added:

- public documentation for a future receiver-side ZET shared update record,
- sanitized non-executable example JSON for a shared update review preview,
- release note and public-safe work log for the v0.2.55 documentation/example batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the example is body-free and contains placeholder refs only,
- no shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.54 - 2026-05-27

Main branch protection readiness baseline.

Added:

- public documentation for staged future `main` branch protection readiness,
- a recommended path from local release-readiness gate to future GitHub Actions, required status checks, and optional review requirements,
- release note and public-safe work log for the v0.2.54 documentation batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Actions, branch protection, repository settings, or GitHub API behavior changed,
- no files are rewritten automatically,
- no external URLs are fetched,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.53 - 2026-05-27

Release readiness gate patch.

Added:

- local `wom-kit/tools/check_release_readiness.py` gate that runs the existing public release hygiene checkers together,
- unit tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documentation, release note, and public-safe work log for the v0.2.53 gate batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the gate runs local subprocess calls to public hygiene checkers only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no GitHub APIs, GitHub Actions, branch protection, product doctor/test commands, providers, private archives, or GitHub Releases are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.52 - 2026-05-27

Public privacy hygiene checker patch.

Added:

- local `wom-kit/tools/check_public_privacy.py` checker for public release and documentation privacy hygiene,
- unit tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholder allowances, current-repository pass behavior, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.52 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known public text files only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no private archives, provider APIs, GitHub Releases, or full-disk locations are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.51 - 2026-05-27

Korean product-language hygiene checker patch.

Added:

- local `wom-kit/tools/check_korean_product_language.py` checker for public Markdown documentation,
- unit tests for required Korean product-language anchors, risky drift phrases, current-facing spelling variants, messenger thread blockchain claims, WordPress/ZET transport claims, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.51 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known Markdown files only,
- no files are rewritten automatically,
- no code identifiers, CLI commands, JSON fields, schema fields, filenames, or package names are renamed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.50 - 2026-05-27

Korean product-language baseline patch.

Added:

- Korean product-language baseline for WOM, zettel-kasten, zet, ZET, objet, lifecycle verbs, block/header/body wording, foreign block safety terms, sharing forms/methods, surface/action terms, SNS-type ZET actions, and messenger-type ZET threads,
- README and public documentation map pointers to the new Korean concept document,
- release note and public-safe work log for the v0.2.50 batch.

Clarified:

- `WOM` is pronounced `옴`, not `웜`,
- `zet` may be explained as `쪽글` or `토막글`, while the product term remains `zet`,
- `ZET` may be explained as `공유 계층`, while the product term remains `ZET`,
- Korean product terms are for public explanation, not CLI/JSON/schema/file/package renames.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no real ZET transport, real trust/import/acceptance/anchor, attestation/signature write, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.49 - 2026-05-27

Public release link hygiene patch.

Added:

- local public-link checker for repository Markdown and release-note link hygiene,
- tests for case-sensitive local Markdown links, release-note relative link rejection, GitHub `blob` link mapping, and suspicious GitHub `tree` file links,
- documentation explaining repo-local Markdown links, GitHub Release body links, external URLs, and case-sensitive public GitHub paths.

Fixed:

- release note links that were correct inside the repository but unsafe when copied into GitHub Release bodies.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Release was edited by the tool,
- no network URL fetching, provider calls, WordPress publishing, projection writes, receipts, ZET transport, recommendation fetching/ranking, neighbor feed updates, trust/import/acceptance/attestation/signature/minting changes, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.48 - 2026-05-27

ZET radio-frequency recommendation model baseline patch.

Added:

- documentation for the future distinction between followed/neighbor feeds and recommended/broadcast feeds,
- documentation for the radio-frequency metaphor where a node tunes into an accessible ZET channel, frequency, scope, or broadcast lane,
- documentation for prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles rather than only LLM prompts,
- sanitized non-executable selector shape example with central black-box ranking disabled.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- no recommendation fetching, ranking, feed update, provider call, WordPress publishing, projection write, receipt write, ZET transport, trust, import, acceptance, attestation, signature, minting, anchoring, delegation, payment, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.47 - 2026-05-26

ZET closed sharing model baseline patch.

Added:

- documentation for the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documentation for the unit layer distinction between `zet` and `objet`,
- documentation for the future ZET closed sharing/SNS layer above the base system,
- documentation for pluggable user-selected surfaces such as custom SaaS, open-source ZET UI, static site, private archive UI, feed/RSS-like app, team workspace, WordPress, or future dedicated ZET client,
- sanitized non-executable example shape for a future closed sharing update.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- GitHub is clarified as base infrastructure or possible substrate, not the whole ZET sharing architecture,
- WordPress is clarified as one possible projection surface, not the WOM/ZET UI,
- attestation is described as receiver-side verification/review before any future neighbor feed update, mirror, or re-projection,
- this release does not call providers, publish to WordPress, write projection records or receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.46 - 2026-05-26

ZET projection plan dry-run preview patch.

Added:

- `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- read-only MCP `zet_projection_plan_check`,
- metadata-only projection plan output for one local zet and one operator-declared surface kind,
- closed safety flags for provider, WordPress, projection-write, receipt-write, trust, import, acceptance, attestation, signature, mint, ZET transport, and full-auto behavior.

Compatibility:

- no private archive migration is required,
- the preview writes nothing and returns `would_change: []`,
- it does not output the full zet body,
- it uses archive-relative paths only,
- visibility is operator-declared intent, not verified provider state,
- projection format is future intent, not rendered body output,
- this release does not call providers, publish to WordPress, write projection records or receipts, mint, trust, import, accept, attest, sign, anchor, apply, run ZET transport, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.45 - 2026-05-26

ZET publication surface baseline patch.

Added:

- documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- release notes and work log for the ZET publication surface baseline.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- posting is documented as separate from minting,
- a surface locator is documented as separate from canonical zet identity,
- the examples use placeholder identifiers and `https://example.invalid/...` only,
- this release does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## v0.2.44 - 2026-05-26

Foreign block attestation statement draft decision preview patch.

Added:

- `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- non-binding route previews for `keep_under_review`, `revise_statement_draft`, `reject_statement_draft`, `prepare_future_attestation_statement_review`, and `needs_more_review`,
- current statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt consistency checks before any route preview.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the default route intent is `needs_more_review`,
- review notes are preview context only; raw note bodies are not echoed or stored,
- previewed statement drafts remain `untrusted_foreign`, with `decision_status: preview_not_recorded`, `attestation_status: not_created`, and `signature_status: not_created`,
- the decision preview does not create trust, import, acceptance, attestation, signatures, minting, sharing, WordPress publishing, provider calls, ZET transport, receipts, or apply behavior,
- MCP remains read-only and exposes no statement draft decision write/apply/accept, foreign block attest/sign/trust/import, provider sync, WordPress publishing, mint, anchor, or full-auto tool.

## v0.2.43 - 2026-05-26

Foreign block attestation statement draft review index patch.

Added:

- `archive attestation-statement-draft-review <archive-root> --format json`,
- optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- index validation for recorded untrusted attestation statement drafts and matching draft receipts,
- current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed style/scope filters do not hide blockers from other discovered statement draft records,
- `--case-id` scopes the consistency verdict to one case,
- indexed records remain `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- indexing a statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft review apply/write/approve, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.42 - 2026-05-26

Foreign block attestation statement draft write approval patch.

Added:

- `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <safe-actor-id>` to record a local statement draft record and matching receipt,
- read-only MCP `record_attestation_statement_draft_check`,
- stale/tamper checks that treat the v0.2.41 draft preview JSON as untrusted input and revalidate current candidate, receipt, quarantine, and decision state before any write,
- rollback-safe exclusive creation for exactly two files: `attestation-statement-draft.json` and its quarantine receipt.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one statement draft record plus one receipt,
- approved records stay `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- recording the statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft approve/write/apply, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.41 - 2026-05-26

Foreign block attestation statement draft preview patch.

Added:

- `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_preview`,
- non-binding statement draft output for one recorded attestation review candidate,
- validation that re-reads the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before returning a draft.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the statement draft is not an attestation, not trust, not signing, not import, not minting, not a receipt write, and not ZET transport,
- hash commitments remain `not_verified`, `not_trusted`, and not proof of authenticity,
- MCP remains read-only and exposes no statement draft write/apply, foreign block attest/sign/trust/import/accept, receipt-write, full-auto, provider, or ZET transport tool.

## v0.2.40 - 2026-05-26

Foreign block attestation review candidate index patch.

Added:

- `archive attestation-candidate-review <archive-root> --format json`,
- optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_review_candidate_index`,
- index validation for recorded untrusted attestation review candidates and matching candidate receipts,
- current quarantine case, original quarantine receipt, recorded decision, and decision receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed filters do not hide blockers from other discovered candidate records,
- indexed candidates remain `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- indexing a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no candidate review approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.39 - 2026-05-25

Foreign block attestation review candidate write approval patch.

Added:

- `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <actor-id>` to record an untrusted attestation review candidate,
- optional replay guards for expected case id, review scope, and prospective attestor,
- read-only MCP `record_attestation_review_candidate_check`.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one candidate record plus one receipt,
- approved records stay `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- recording a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, or acceptance,
- MCP remains read-only and exposes no candidate approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.38 - 2026-05-25

Foreign block attestation review candidate plan patch.

Added:

- `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- read-only MCP `foreign_block_attestation_review_candidate_plan`,
- a human-review candidate object for cases whose recorded decision is `eligible_for_attestation_review` and whose planned outcome is `prepare_attestation_review_candidate`.

Compatibility:

- no private archive migration is required,
- candidate planning writes nothing and never reads the original foreign artifact, source payloads, objet bodies, or provider URLs,
- all candidates remain `untrusted_foreign`, `planned_not_recorded`, and `not_created`,
- hashes in existing sanitized records are retained only as commitments or claims, not proof of authenticity,
- MCP remains read-only and exposes no candidate apply/write/accept/trust/import/attest/sign/mint/full-auto tool.

## v0.2.37 - 2026-05-25

Foreign block decision outcome plan patch.

Added:

- `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_decision_outcome_plan`,
- conservative outcome routing for recorded quarantine decisions.

Compatibility:

- no private archive migration is required,
- outcome planning writes nothing and never reads the original foreign artifact,
- all outcomes remain `untrusted_foreign` and `planned_not_applied`,
- `eligible_for_attestation_review` only becomes `prepare_attestation_review_candidate`; it does not create trust or an attestation,
- MCP remains read-only and exposes no outcome apply/write/accept/trust/import/attest/mint/full-auto tool.

## v0.2.36 - 2026-05-25

Foreign block quarantine decision review index patch.

Added:

- `archive quarantine-decision-review <archive-root> --format json`,
- optional `--case-id`, `--decision`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_decision_review_index`,
- consistency checks for recorded quarantine decision records and matching decision receipts,
- current quarantine case and original quarantine receipt checks when reviewing recorded decisions.

Compatibility:

- no private archive migration is required,
- the decision review index writes nothing and never reads the original foreign artifact,
- indexed decisions remain `untrusted_foreign` review records only,
- MCP remains read-only and exposes no quarantine decision review apply/write/accept/import/trust/attest/full-auto tool.

## v0.2.35 - 2026-05-25

Foreign block quarantine decision write approval patch.

Added:

- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine decision records under `quarantine/foreign-blocks/<case-id>/quarantine-decision.json`,
- quarantine decision receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`,
- read-only MCP `record_quarantine_decision_check` for dry-run validation only,
- replay validation that re-reads the current quarantine case and receipt before any approved local decision record write.

Compatibility:

- no private archive migration is required,
- decision writes are local review records only; they never trust, import, mint, attest, anchor, delegate, sign, execute, accept, apply, share, or call providers,
- approved writes are limited to the sanitized quarantine decision JSON and quarantine decision receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine decision apply/write/import/trust/attest/accept/full-auto tool.

## v0.2.34 - 2026-05-25

Foreign block quarantine decision preview patch.

Added:

- `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- optional preview context: `--decision-intent`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_quarantine_decision_check`,
- decision-path previews for existing untrusted quarantine cases: `keep_quarantined`, `reject_and_keep_record`, `eligible_for_attestation_review`, and `needs_more_review`.

Compatibility:

- no private archive migration is required,
- quarantine decision preview writes nothing and never reads the original foreign artifact,
- decision preview does not record approval, trust, import, attestation, minting, anchoring, delegation, signing, acceptance, or apply state,
- MCP remains read-only and exposes no quarantine decision apply/write/import/trust/attest tool.

## v0.2.33 - 2026-05-25

Foreign block quarantine review index patch.

Added:

- `archive quarantine-review <archive-root> --format json`,
- optional `--case-id`, `--status`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_review_index`,
- inventory and consistency checks for `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- matching quarantine write receipt checks under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Compatibility:

- no private archive migration is required,
- quarantine review index writes nothing and never reads the original foreign artifact,
- indexing does not mean reviewed, trusted, imported, attested, minted, anchored, delegated, signed, or accepted,
- MCP remains read-only and exposes no quarantine review apply/import/trust/attest/write tool.

## v0.2.32 - 2026-05-25

Foreign block quarantine write approval patch.

Added:

- `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine case writes under `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- quarantine write receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`,
- read-only MCP `quarantine_foreign_block_check` for dry-run validation only,
- validation for v0.2.31 `foreign_block_quarantine_plan` reports before any approved local write.

Compatibility:

- no private archive migration is required,
- quarantine write is an isolation record only; it does not trust, import, mint, attest, anchor, delegate, sign, or execute the foreign block,
- approved writes are limited to the sanitized quarantine case JSON and quarantine write receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine apply/write/import/trust/attest/full-auto tool.

## v0.2.31 - 2026-05-25

Foreign block quarantine plan patch.

Added:

- `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_quarantine_plan`,
- validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write,
- structured quarantine actions: `blocked`, `hold_for_human_review`, and `ready_for_future_quarantine_write`,
- preview-only archive-relative quarantine paths under `quarantine/foreign-blocks/<case-id>/...` that are not created.

Compatibility:

- no private archive migration is required,
- quarantine plan writes nothing and never reads the original foreign artifact,
- `ready_for_future_quarantine_write` is not trust, not import, not approval, and not a quarantine write; it only means a future explicit quarantine-write workflow could be presented to a human/operator,
- no real quarantine write, trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.30 - 2026-05-25

Foreign block attestation packet preview patch.

Added:

- `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_attestation_packet_check`,
- validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review,
- structured packet status values: `blocked`, `manual_review_required`, and `ready_for_human_attestation_review`,
- attestation packet previews that keep `would_attest: false`, `attestation_status: not_created`, `trust_state: untrusted_foreign`, and `would_change: []`.

Compatibility:

- no private archive migration is required,
- attestation packet preview writes nothing and never reads the original foreign artifact,
- `ready_for_human_attestation_review` is not trust, not an attestation, and not approval; it only means the trust report is clean enough to present for a future explicit human review,
- no real trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.29 - 2026-05-25

Foreign block trust / attestation preview patch.

Added:

- `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_trust_check`,
- validation for v0.2.28 `foreign_block_intake` reports before any future trust/attestation workflow,
- structured `proposed_trust_action` values: `reject`, `manual_review_required`, and `eligible_for_future_attestation`,
- hash, reference, and prompt-boundary assessments that keep every foreign block `untrusted_foreign`.

Compatibility:

- no private archive migration is required,
- trust preview writes nothing and always returns `would_change: []`,
- `eligible_for_future_attestation` is not trust; it only means the report is clean enough for a future explicit attestation workflow,
- no real trust/apply/import, attestation write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.28 - 2026-05-25

Foreign block intake preview patch.

Added:

- `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_intake_check`,
- conservative intake for foreign block-header JSON artifacts and Markdown-compatible foreign zets,
- claimed hash summaries that are explicitly `not_verified`,
- prompt-boundary recommendations for foreign text,
- public docs for foreign block intake.

Compatibility:

- no private archive migration is required,
- foreign block intake writes nothing and always returns `would_change: []`,
- foreign text can inform, but cannot command,
- foreign blocks remain `untrusted_foreign` until a future attest/check path exists,
- no real ZET transport, import/apply, draft creation from foreign content, automatic trust, real signing, payment, staking, consensus, blockchain, provider sync, OCR, or LLM classification is implemented.

## v0.2.27 - 2026-05-25

Prompt boundary draft composer patch.

Added:

- `archive create-draft --prompt-boundary-report <json-file>`,
- validation that prompt-boundary reports are dry-run-only, non-mutating, and preserve the untrusted-text boundary before draft composition,
- optional draft frontmatter `prompt_boundary` metadata with report hash, risk level, source kind/path summary, detected pattern ids, and handling note,
- MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--prompt-boundary-report` is omitted,
- low prompt-boundary risk is recorded as heuristic context, not proof of safety,
- medium risk is allowed with warnings,
- high risk blocks draft creation,
- no LLM classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior is implemented.

## v0.2.26 - 2026-05-25

Prompt injection boundary, responsible use, and runtime model guidance baseline.

Added:

- `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- read-only MCP `prompt_boundary_check`,
- conservative prompt-injection and unsafe-agent string heuristics,
- public prompt injection boundary, responsible use, disclaimer, and runtime model guidance docs.

Compatibility:

- no private archive migration is required,
- prompt-boundary is read-only and writes nothing,
- the check does not call LLMs, provider APIs, web browsing, OCR, import apply, or ZET transport,
- this is not a complete prompt-injection classifier or legal advice,
- HITL remains the recommended default and full-auto operation remains advanced/experimental operator responsibility.

## v0.2.25 - 2026-05-25

Profile wallet concept baseline.

Added:

- `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- read-only MCP `wom_profile_wallet_check`,
- optional public-safe `node` and `wallet` metadata fields for WOM profile registry entries,
- documentation for the wallet-ready identity model: WOM profile selects the human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can sign capability/proof actions.

Compatibility:

- no private archive migration is required,
- existing profile registry entries remain valid,
- no private key generation, real cryptographic signing, blockchain API call, provider API call, wallet registration, token storage, seed phrase storage, payment layer, staking layer, consensus, ledger, or P2P transport is implemented,
- WOM profile is not a crypto wallet in v0.2.25; it is a wallet-ready identity model.

## v0.2.24 - 2026-05-25

Block header preview patch.

Added:

- `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- read-only header derivation for `block = zet + header`,
- deterministic `zet_body_sha256`, `header_sha256`, and `block_hash_preview`,
- referenced zet, objet, and receipt summaries from frontmatter metadata,
- read-only MCP `block_header_check`.

Compatibility:

- no private archive migration is required,
- no zets are modified,
- no minting or receipt writing is performed,
- no referenced objet/source file body is read or hashed,
- no provider URL is followed and no provider API is called,
- ZET remains the sharing layer; the product term is `block`, not a ZET-prefixed block term.

## v0.2.23 - 2026-05-25

Source intake draft composer patch.

Added:

- `archive create-draft --source-intake-plan <json-file>` for consuming a v0.2.22 `source-intake --dry-run --format json` result,
- validation that source intake plans are dry-run-only, blocker-free, metadata-only, and safe before refs are merged into draft frontmatter,
- optional `source_intake` draft frontmatter metadata with a plan hash, source/objet status summary, object storage flag, and content access proof,
- MCP `create_draft_zettel` support for a structured `source_intake_plan` object,
- mint receipt previews and receipts preserve `source_refs` and `source_intake` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--source-intake-plan` is omitted,
- the source intake plan file path is not stored in draft frontmatter,
- no source intake apply, objet capture, file copy/upload/import/OCR/transcription/full hashing/provider API call, automatic minting, or MCP real minting is implemented.

## v0.2.22 - 2026-05-25

Source intake planner patch.

Added:

- `archive source-intake <archive-root> --dry-run --format json`, a dry-run-only planner for classifying source/objet references before draft creation,
- locator support for local files, source map items, source-relative paths, `objet:sha256:...`, technical `object_id`, provider object refs, and AI artifact refs,
- stable source intake JSON with draft-ready `source_refs_for_draft`, objet status, object storage context, content access flags, blockers, warnings, and next safe actions,
- object storage context reporting from `provider-bindings.yml`,
- read-only MCP `source_intake_plan`.

Compatibility:

- no private archive migration is required,
- source intake writes nothing,
- no file body is read and no full SHA-256 is calculated,
- no copy, upload, import, OCR, transcription, parser extraction, provider API call, automatic draft creation, mint, or provider sync is implemented,
- MCP exposes no source intake apply/capture/upload/sync/provider API tool.

## v0.2.21 - 2026-05-25

Object storage / objet setup planner patch.

Added:

- `archive object-storage <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped objet storage setup,
- safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- default objet prefix planning as `archives/<archive_id>/objets/`,
- strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a bucket/container,
- optional ignored local object storage account hints with `--write-local-profile`,
- read-only MCP `object_storage_setup_plan`.

Compatibility:

- no bucket/container is created,
- no OAuth, provider API, upload, sync, source copy, file hashing, or source import operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no object storage apply/create/connect/upload/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.20 - 2026-05-25

GitHub profile repository setup planner patch.

Added:

- `archive github-repo <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped GitHub repository setup,
- safe default repository naming as `zettel-kasten-<profile_slug>`,
- strict profile slug and repository name safety gates for ASCII-only, path-free, URL-free, secret-free values,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a GitHub repository,
- optional ignored local account hints with `--write-local-profile`,
- read-only MCP `github_repository_setup_plan`.

Compatibility:

- no GitHub repository is created,
- no OAuth, GitHub API, `gh`, `git remote`, push, or sync operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no GitHub apply/create/connect/push/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.19 - 2026-05-25

WOM-kit naming and path cleanup patch.

Added:

- renamed the implementation folder from the old placeholder path to `wom-kit/`,
- renamed the Python import package to `wom_kit`,
- changed package metadata to `wom-kit`,
- kept compatibility console scripts `archive` and `archive-mcp`,
- added preferred console script aliases `wom` and `wom-mcp`,
- updated current-facing docs, CLI/MCP docs, schema titles, examples, tests, and wrapper scripts to use `WOM-kit`, `wom-kit`, and `wom_kit` by context.

Compatibility:

- repository root remains `zettel-kasten`,
- command behavior is unchanged,
- lifecycle commands remain available,
- the old package/folder names are not current product names,
- this release does not add source-intake, GitHub repo creation, provider sync, UI, or any change to WOM/zet/ZET philosophy.

## v0.2.18 - 2026-05-24

Profile-aware draft zet creation dry-run patch.

Added:

- `archive create-draft --dry-run`, a no-write preview for inbox draft zet creation,
- replay-safe draft fields: `--draft-id`, `--created-at`, `--expected-body-sha256`, and `--draft-approved-by`,
- profile-aware draft context flags for resolved profile id, operator id, authority mode, expected archive id, and expected archive type,
- optional draft provenance fields for creation mode, assisting actors, supervising actors, derived refs, source refs, local AI sessions, and inbox-draft-only approval metadata,
- MCP `create_draft_zettel` dry-run support with the same profile-aware provenance inputs,
- safety gates that block archive id/type mismatch, body hash mismatch, empty body content, malformed deterministic timestamps, unsafe local paths, provider storage locators, and secret-like values,
- line-ending-normalized body hashes so LF/CRLF differences do not break approved draft replay,
- AI-assisted and AI-generated draft gates that require the assisting AI runtime to be identified,
- mint receipt propagation for draft `source_refs`, `provenance.derived_from`, and `local_ai_sessions`.

Compatibility:

- existing `create-draft` usage remains compatible when the new flags are omitted,
- dry-run writes nothing,
- real draft creation still writes only to `inbox/`,
- profile-bound AI draft writes require draft approval and expected body hash replay values,
- minting remains a separate CLI approval step and MCP still exposes no real mint tool.

## v0.2.17 - 2026-05-24

WOM Profile Registry dry-run patch.

Added:

- `archive profile-list --registry <path> --format json`, a read-only CLI command that lists local WOM profile registry entries with local paths redacted by default,
- `archive profile-resolve --registry <path> --target <query> --format json`, a read-only CLI command that resolves a requested profile by exact profile id, label, or alias before runtime context or draft work,
- read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- token-state aware resolution so a missing token can still resolve profile identity while disabling direct write availability,
- delegate fallback previews when a target profile is missing or a matched profile has no usable token,
- an example profile registry template with placeholder paths and fake `token_ref` values only,
- Unicode-normalized matching and blockers for registry version drift, duplicate profile ids, and raw token-like fields.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- profile registry commands never write files, never scan the whole disk, never store tokens, and do not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

## v0.2.16 - 2026-05-24

WOM AI Runtime Context Layer patch.

Added:

- `archive runtime-context <archive-root> --format json`, a read-only CLI command for terminal-capable AI runtimes to confirm archive identity, type/scope, owner/principal summary, AI write policy, safe archive-relative paths, safe next actions, and doctor summary before drafting or asking for mint approval,
- default local path redaction for runtime context JSON, with `--no-redact-local-paths` available only for trusted local debugging,
- `--expected-archive-id`, `--expected-type`, and `--strict` gates so the runtime can block on archive id mismatches and treat archive type mismatches as warning-by-default or blocking in strict mode,
- read-only MCP tool `archive_runtime_context` with the same core behavior and existing MCP allowed-root enforcement,
- stable runtime context summary keys for AI parsing, with unavailable optional values represented as `null`,
- MCP local path disclosure gating through `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1`.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- runtime context never writes files and does not implement create-draft dry-run, provider API sync, UI, real minting through MCP, or any new MCP apply tool.

## v0.2.15 - 2026-05-23

WOM Safe HTML Profile validator dry-run patch.

Added:

- `archive check-safe-html --path <zet> --dry-run` CLI command, a read-only validator that inspects a v0.2 Markdown-compatible zet and reports whether it is compatible with a future WOM Safe HTML Profile migration,
- block detection for `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, and inline event handler attributes (for example `onclick=`),
- structured JSON output with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

Compatibility:

- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- the validator only reads; it never writes files, never converts Markdown to HTML, never changes mint output, and never migrates existing zets,
- the WOM Safe HTML Profile element/attribute allowlist is still not finalized; the validator only flags obviously unsafe patterns at this stage,
- no private archive migration is required.

## v0.2.14 - 2026-05-23

WOM Safe HTML Profile documentation/spec baseline patch.

Added:

- WOM Safe HTML Profile documents in English and Korean,
- public distinction between `WOM`, `zet`, and `ZET`,
- documentation that keeps Markdown as an authoring/import compatibility format while setting WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- stronger explanation that `ZET` is the communication layer that can become messaging, SNS/feed, or collaboration.

Compatibility:

- no private archive migration is required,
- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- no Markdown-to-HTML converter, validator, UI, live sharing, or P2P transport is implemented in this release.

## v0.2.13 - 2026-05-23

WOM naming baseline and compatibility alias patch.

Added:

- public WOM naming documents in English and Korean,
- `mint-zet` as the preferred CLI surface for minting a zet, with `mint-zettel` preserved as a compatibility alias,
- `parcel` as the preferred CLI surface for creating a portable bounded unit, with `pack` preserved as a compatibility alias,
- `admit --dry-run` as the preferred CLI surface for previewing parcel/workpack admission, with `import --dry-run` preserved as a compatibility alias,
- documentation that places `WOM`, `zet`, `node`, and `mint -> delegate -> attest -> anchor` at the center of the product language.

Compatibility:

- `wom-kit`, `zettels/`, `receipts/`, `workpacks/`, and existing schema names remain unchanged for v0.2 compatibility,
- `promote`, `share`, `mint-zettel`, `pack`, and `import` remain available,
- no private archive migration is required.

## v0.2.12 - 2026-05-23

Real delegate receipt write patch.

Added:

- `delegate-zet --approve --reviewed-by <actor>` for writing a schema-backed delegate receipt,
- `receipts/delegate/*.delegate.json` doctor validation,
- real delegate capability nonce issuance with receipt-local claim/spent state,
- duplicate delegate receipt protection through dry-run blockers and exclusive file creation.

Compatibility:

- `delegate-zet --dry-run` remains the preview gate,
- MCP delegate tooling remains read-only and dry-run only,
- no real claim registry, spent registry, revocation registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.11 - 2026-05-23

Delegate capability contract patch.

Added:

- `delegate-zet --target-policy counterparty_bound|claimable_once`,
- `claimable_once` delegate previews that can defer the recipient archive until attestation,
- `delegation_capability` preview fields for capability id, claim/spent preview state, nonce placeholder, binding method, and settlement condition,
- `claim_binding` previews in attestation and anchor metadata,
- MCP parity for `delegate_zet_check` with optional `target_archive`.

Compatibility:

- existing `delegate-zet` and `share --dry-run` flows remain compatible,
- v0.2.10 delegate receipts without capability fields are treated as legacy `counterparty_bound`,
- no real claim registry, spent registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.10 - 2026-05-23

ZET sharing dry-run lifecycle contract.

Added:

- `delegate-zet --dry-run` as the product-facing dry-run surface for scoped zet delegation,
- `attest-zet --dry-run` for verifying a delegated foreign zet receipt without writing files,
- `anchor-zet --dry-run` for previewing local meaning-network anchoring without writing files,
- read-only MCP tools `delegate_zet_check`, `attest_zet_check`, and `anchor_zet_check`,
- schemas for delegate receipts, attestation receipts, and anchor metadata.

Compatibility:

- existing `share --dry-run` and MCP `share_check` remain available,
- no real P2P, SNS/feed, transport, external sending, or foreign zet import is implemented,
- no private archive migration is required.

## v0.2.9 - 2026-05-23

Terminology stabilization patch.

Changed:

- made `mint` the preferred product language for current CLI and user-facing docs,
- changed newly initialized archives to use `ai_write_policy.canonical_requires: human_minting`,
- kept `human_promotion` valid for legacy archives without doctor warnings,
- added optional `minting_rules` to zettel rules while keeping `promotion_rules` for v0.2 compatibility,
- made mint dry-runs prefer `minting_rules` and fall back to legacy `promotion_rules`,
- kept `promote`, `promotion_check`, `promotion` frontmatter, and old promotion receipts as compatibility surfaces.

Migration:

- no private archive migration required,
- existing archives that still use `human_promotion` remain valid,
- new archives should use `human_minting`.

## v0.2.8 - 2026-05-23

Minting lifecycle implementation.

Added:

- `mint-zettel` CLI command for `draft zet -> canonical private zet -> mint receipt -> draft snapshot`,
- mint receipt schema at `schemas/mint-receipt.schema.json`,
- canonical zettel `mint` frontmatter metadata with `authority_mode: basic`,
- `receipts/mint/*.mint.json` and `receipts/mint/drafts/*.draft.md` validation in doctor,
- read-only MCP `mint_zettel_check` dry-run tool.

Changed:

- real minting preserves the original `inbox/` draft,
- real minting snapshots the exact draft text at mint time,
- canonical zettels may now satisfy doctor lifecycle metadata with either new `mint` metadata or legacy `promotion` metadata,
- `promote` remains available as a compatibility command.

Migration:

- no private archive migration required,
- archives that use `mint-zettel` should keep the generated mint receipts and draft snapshots under `receipts/mint/`.

## v0.2.7 - 2026-05-23

Foundational product whitepaper patch.

Added:

- detailed English foundational product whitepaper,
- detailed Korean foundational product whitepaper,
- public-safe product whitepaper depth correction work log.

Clarified:

- `zettel-kasten` is memory infrastructure, not only a note app,
- `zet` is always text and functions as interpreted archive memory,
- minting means private archive issuance, not posting or sharing,
- the same authority model supports HITL workflows and scoped AI-agent harnesses,
- object storage covers source/original documents as well as media,
- Notion, Google Drive, local folders, GitHub, object storage, and external URLs should be handled through provenance-aware provider bindings,
- `zet` sharing can project into messenger, SNS/feed, or collaboration workspace behavior depending on relationship topology,
- the Web3-like property is subject-owned, portable, verifiable memory rather than token hype.

Migration:

- no private archive migration required.

## v0.2.6 - 2026-05-23

README baseline display correction.

Changed:

- updated the English README current public baseline from `v0.2.5` to `v0.2.6`,
- updated the Korean README current public baseline from `v0.2.5` to `v0.2.6`,
- aligned package and citation metadata with the new public patch release.

Why:

- `v0.2.5` correctly published the documentation map and philosophy patch, but the public repository page needed a follow-up patch so the visible README baseline and release chain stayed consistent without moving an already-published tag.

Migration:

- no private archive migration required.

## v0.2.5 - 2026-05-23

Public documentation map and philosophy patch.

Added:

- public documentation map,
- Korean public documentation map,
- product philosophy document,
- Korean product philosophy document.

Clarified:

- public records are separated into product blueprint/design philosophy, implementation reference research, implementation plans, and work logs,
- the project philosophy includes human data primitives, AX rationale, and Web3-like `zet` sharing,
- README files now link directly to those document groups.

Migration:

- no private archive migration required.

## v0.2.4 - 2026-05-23

Documentation polish patch.

Added:

- `README.ko.md` as a full Korean project entrypoint,
- `UPGRADE.ko.md` as a Korean upgrade guide,
- `v0.2.4` release note.

Changed:

- rewrote `README.md` as a cleaner English public entrypoint,
- split bilingual explanations into separate English/Korean documents,
- clarified public status, storage model, text provenance, versioning, and privacy boundaries.

Migration:

- no private archive migration required.

## v0.2.3 - 2026-05-23

Bilingual documentation patch.

Added:

- Korean summary in `README.md`,
- Korean upgrade guidance in `UPGRADE.md`,
- Korean notes in the `v0.2.3` release note.

Migration:

- no private archive migration required.

## v0.2.2 - 2026-05-23

Public history hygiene and text provenance clarification.

Added:

- text provenance hierarchy documentation,
- clearer distinction between original editable text, parser-extracted text, OCR/AI transcription, human-reviewed derived text, and minted zets.

Clarified:

- OCR and AI transcription should be stored, but as model-dependent derived text records,
- born-digital editable text has higher evidence authority than OCR-derived text,
- derived text must keep provenance to the source object and tool/model that produced it.

Repository hygiene:

- public history should be rewritten so older public commits do not remain as normal refs with local/private-looking examples.

Migration:

- no private archive migration required,
- future derived-text schemas may require a migration once implemented.

## v0.2.1 - 2026-05-23

Public documentation and repository hygiene patch.

Added:

- `UPGRADE.md`,
- per-version release notes under `wom-kit/docs/releases/`,
- clearer version compatibility guidance,
- neutralized public examples that looked too close to local/private context.

Clarified:

- document files such as `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, and `.csv` can be source/original objects,
- object storage is the warehouse for original source files, not only media files,
- minted zets remain text and belong in the zettel layer.

Migration:

- no private archive migration required from `v0.2.0`.

## v0.2.0 - 2026-05-23

Initial public showcase baseline.

Includes:

- local-first archive protocol documents,
- zettel and zettel-kasten specs,
- JSON schemas,
- fake sample archive,
- early Python CLI and MCP tooling,
- setup and security docs,
- public product blueprint for `zettel-kasten` and `zet`,
- versioning and compatibility policy,
- source object storage policy for document files and media files.

Notes:

- This is not a production-stable `v1.0.0` release.
- The future `zet` sharing service is not implemented yet.
- Real private archives should not be pushed to the public repository.
