# v0.3.317 staged-cleanup evidence decision

Status: v0.3.317 implementation and release scope. This
document does not claim merge, CI, tag, Release, wheel publication, beta-client
execution, or human acceptance.

## Context

Paired capture could durably store BOM-free UTF-8 text while
`staged-cleanup-check` still classified the staged text as not preserved. At the
same time, the legacy path-only deferment list could classify changed unique
bytes as safe for folder cleanup. Long JSON output existed only in the terminal,
and several evidence readers did not provide one strict, race-resistant
authority chain.

## Decision

1. Ordinary preservation requires exact canonical object-store bytes, one
   strict canonical object-manifest row, and one valid linked capture-receipt
   item whose official envelope, action, exact boolean fields, and byte size
   agree. Aborted, unreviewed, malformed, or internally inconsistent envelopes
   do not qualify. A legitimate partial outer result may still prove an item
   whose own durable publication evidence is complete.
2. Derived-text preservation requires an exact raw/stored SHA-256 match, one
   strict canonical derived row, independently rehashed canonical store bytes,
   and one valid direct derived-text terminal receipt. An outer batch receipt
   alone is never sufficient.
3. BOM or UTF-16 transcoding is representation preservation, not raw-byte
   preservation. The staged raw file must be captured as an ordinary objet.
4. Every source, store, manifest, and receipt authority used for a safe verdict
   is rehashed before return. Stat identity alone is not evidence because a
   same-size in-place writer can restore an earlier modification time.
5. Deferred means “keep staged for later.” A deferred entry always makes
   `safe_to_cleanup` false. A future discard/abandon feature would require a
   separate authenticated, digest-bound human approval; this command does not
   implement one.
6. `--output` may create one no-overwrite result under
   `.wom-scratch/diagnostics/` plus its operation journal. Terminal and
   `operation-control` projections contain only state, fixed reason codes,
   bounded counts, and opaque entry references. Paths, names, object ids,
   hashes, receipt names, bodies, and raw messages are excluded.
7. Inspection success and cleanup safety remain distinct. A complete not-safe
   inspection has `ok: true`, `safe_to_cleanup: false`, state
   `not_safe_to_cleanup`, and process exit `1`.

## Consequences

- Exact BOM-free paired text no longer produces a false negative when its full
  direct evidence chain is healthy.
- Missing, malformed, conflicting, stale, transformed, or changing evidence
  fails closed without deleting or moving staged data.
- A deferred item can no longer be mistaken for permission to delete its only
  copy.
- Local focused tests are implementation evidence only; release validation and
  real archive acceptance remain separate gates.
