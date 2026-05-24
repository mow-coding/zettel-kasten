# Work Log: v0.2.23 Source Intake Draft Composer

Date: 2026-05-25

## Goal

Implement a safe bridge from `source-intake --dry-run` to `create-draft`, so AI runtimes can use the planner result without manually copying source refs.

## Implemented

- Added `--source-intake-plan <json-file>` to `archive create-draft`.
- Added shared validation for source intake plan objects.
- Merged validated `source_refs_for_draft` into draft `source_refs`.
- Preserved explicit `--source-ref` values alongside plan refs.
- Added optional `source_intake` frontmatter metadata without storing the local plan file path.
- Added MCP structured `source_intake_plan` input for `create_draft_zettel`.
- Preserved `source_intake` metadata in mint receipt previews and real mint receipts.
- Updated the frontmatter schema with optional `source_intake`.
- Added focused CLI and MCP tests.
- Anonymized `source_intake_candidate` refs during draft composition.

## Safety Decisions

- The composer reads only the JSON plan file supplied to `create-draft`.
- It does not read the original source file.
- It does not follow local paths inside the plan.
- It blocks plans that are not successful metadata-only dry-runs.
- It blocks refs containing local absolute paths, provider URLs, token-like values, or secret-like values.
- MCP accepts only a structured plan object, not a local plan file path.
- A no-redact local-file source intake plan cannot persist a private filename stem through `source_intake_candidate`; the composer rewrites those refs and matching `derived_from` entries to `candidate:source-intake:<plan-hash-prefix>`.
- `source_intake.plan_sha256` commits to the supplied dry-run JSON plan object; it is not independent proof that the original source still exists.

## Not Implemented

- Source intake apply.
- Objet capture or manifest writes.
- File copy/upload/import/OCR/transcription/parser extraction.
- Full source hashing.
- Provider API calls.
- Automatic minting.
- MCP real mint/apply tools.

## Verification Plan

- Run focused CLI and MCP tests for source intake draft composition.
- Run the full WOM-kit unit test suite.
- Run strict doctor on the fake archive.
- Run `git diff --check`.
- Run naming and privacy scans.

## Review Follow-Up

Claude review found no Critical or Medium issues. One privacy note remained: a source intake plan created with `--no-redact-local-paths` could contain a `source_intake_candidate` ref derived from the real filename stem.

The composer now rewrites those candidate refs, and matching `derived_from` entries, to `candidate:source-intake:<plan-hash-prefix>` before storing draft metadata. The release note and source intake docs also clarify the meaning of `plan_sha256`.
