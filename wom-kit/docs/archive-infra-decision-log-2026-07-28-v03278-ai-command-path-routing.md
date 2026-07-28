# Archive Infrastructure Decision Log: v0.3.278 AI Command-Path Routing

Date: 2026-07-28
Status: accepted and implemented

## Context

A beta report showed that an external AI bypassed WOM in four ways:

- raw grep produced a silently truncated false-zero search conclusion;
- an installed local pin was treated as proof that no newer remote release
  existed;
- raw SQLite was treated as the product's authoritative vocabulary/search
  surface;
- Markdown was written directly into `inbox/` instead of using
  `archive create-draft`.

The AI did not run `ai-start-here`, but WOM guidance also had a structural
gap. Generated `AGENTS.md` files described destination folders without naming
the required write command, and the operational/runtime guidance did not
present one general action-to-command map.

## Decision

Add `wom-kit/ai-command-path-routing/v0.1` as a read-only object returned by
runtime-context, ai-start-here, operational-context, and canonical entrypoint
metadata.

- Name official read routes for session entry, search, version truth,
  saved-view inspection, and command discovery.
- Route authoritative bounded WOM search through
  `archive search <archive-root> <query> --count-total --format json`.
- Name preview/approval routes for draft creation, minting, typed edges,
  source capture, and operational-context updates.
- Explicitly mark raw grep and raw SQL as non-authoritative search surfaces.
- Explicitly prohibit direct AI file writes to `inbox/` and canonical zets.
- State that local version truth does not verify remote release freshness.
- State that no persistent saved-view writer exists yet.
- Make all new archive AGENTS templates start with `ai-start-here`.
- Update the packaged runtime skill and focused references with the same
  contract.

## Compatibility Boundary

Do not silently rewrite an existing archive's `AGENTS.md`. This release
changes new-archive templates and live read-only output only. Existing local
instructions remain owner-controlled.

Keep the existing `wom-kit/ai-start-here/v0.3` schema and add the separately
versioned routing object. Existing consumers may ignore the additive field.

## Consequences

An AI entering through WOM now receives an explicit answer to both questions:

1. where the relevant archive state lives;
2. which command is authorized to operate on it.

This reduces model-quality dependence without granting new write authority.
All writes remain preview-first, separately approved, and receipt-bound where
the underlying command already provides a receipt.

The release does not detect historical direct-written drafts and does not add
a saved-view writer. A later read-only pipeline-bypass audit must classify
possible legacy files conservatively and perform no automatic repair.
