# Work Log: v0.2.44 Foreign Block Attestation Statement Draft Decision Preview

Date: 2026-05-26

## Goal

Add a read-only decision preview after v0.2.43 statement draft review indexing.

The preview lets a human/operator see one safe next review route for a recorded untrusted statement draft without accepting the draft or creating trust.

## Implemented

- Added CLI `attestation-statement-draft-decision`.
- Added optional decision intent, reviewer, expected review scope, expected statement style, and review-note context.
- Added read-only MCP `foreign_block_attestation_statement_draft_decision_preview`.
- Reused the v0.2.43 statement draft review index for case consistency.
- Added current metadata checks for statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt.
- Added tests for dry-run enforcement, valid routes, invalid routes, unsafe input blocking, mismatch blocking, missing current files, mutation flags, output boundaries, MCP dry-run guards, and doctor strict after preview.

## Boundaries

- The command writes no files.
- It returns `dry_run: true` and `would_change: []`.
- It records no decision.
- It accepts no statement draft.
- Records remain `untrusted_foreign`.
- `attestation_status` and `signature_status` remain `not_created`.
- All mutation flags remain false.
- Original foreign payloads, source documents, objet bodies, provider URL targets, WordPress posts, and external provider state are not read.
- MCP cannot approve, write, apply, accept, attest, sign, trust, import, mint, anchor, publish, sync providers, or run full-auto tools.

## Notes

The default route intent is `needs_more_review`. This keeps the batch conservative until a future explicit statement decision write or acceptance workflow exists.
