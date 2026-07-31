# Decision Log - v0.3.294 Checked-Layer Objet Rediscovery

Date: 2026-07-31

## Context

Beta feedback showed that an AI could search the generated SQLite index, see
zero results, and turn that narrow observation into a global statement that an
original file or objet did not exist. The existing `search.complete` field was
also easy to overread: it proves only that the current index result set is not
truncated, not that all possible rediscovery sources are current and checked.

Private original-name search, approved external stores, exact external object
resolution, and source-reference recovery need separate reviewed contracts.
Implementing those writers and scanners in one batch would hide important
privacy and approval decisions.

## Decision

- Add the required-dry-run CLI command
  `archive objet-rediscovery-plan <archive-root> <query> --dry-run
  --count-total --format json`.
- Add the matching read-only MCP tool `objet_rediscovery_plan`.
- Use one shared service result with schema
  `wom-kit/objet-rediscovery-plan/v0.1`.
- Preserve ordinary `archive search.complete` and `truncated` semantics
  unchanged under the nested `index_search` evidence.
- Return ten fixed layer IDs in deterministic order, including on blocked
  execution.
- Treat all five current index channels as snapshot evidence only. Current
  index-health does not prove searched title/body, object-manifest,
  derived-text, view, or source-map freshness.
- Probe all five channels independently with a bounded `limit + 1` read so
  early global result truncation cannot mark an unvisited later channel as
  checked.
- Leave `zettel_objet_edges` unchecked without a reviewed zettel selection.
- Mark private-name, approved-local-store, and unrecovered-reference contracts
  as unknown and not implemented. Mark `external_store_evidence` unknown and
  unchecked, because the existing read-only `backup-evidence` command reports
  storage evidence without consuming the submitted private query.
- Keep successful plans at `status: search_incomplete`,
  `rediscovery_complete: false`, and `negative_claim_supported: false`.
- Normalize invalid archives, unavailable/malformed index data, expected read
  errors, pending WAL or rollback-journal data, unsafe local scan boundaries,
  and mid-read snapshot changes into content-free blocked results.
- Use a plan-private immutable SQLite read, fail closed on a non-empty WAL or
  rollback journal, reject symlink/junction/reparse directory descent, and
  verify the main index snapshot does not change across inspection.
- Never echo query/search/private identifiers or exception details and perform
  no writes, rebuild, provider/network/credential call, external-directory
  scan, Runtime Skill installation, or `AGENTS.md` rewrite.
- Advance action routing to
  `wom-kit/ai-command-path-routing/v0.8` with
  `plan_objet_rediscovery_before_negative_claim`.
- Preserve v0.3.293 runtime-guidance readiness and operator-feedback sequence
  unchanged; do not add a new legacy `AGENTS.md` readiness marker.

## Consequences

AI clients now receive an explicit machine-readable reason not to convert
index absence into global absence. The command is useful immediately because
it names the missing evidence without pretending that future contracts
already exist.

The result is deliberately not a private filename finder. A human or later
approved tool must still select exact follow-up evidence. v0.3.295-v0.3.299
remain separate release batches.

No public release is authorized by this source decision. The implementation
must be rebased onto the exact public v0.3.293 merge commit and pass the full
suite, clean-wheel checks, and public-artifact verification before release.

Implementation record:
`meeting-minutes/2026-07-31-v03294-checked-layer-objet-rediscovery-implementation.md`.
