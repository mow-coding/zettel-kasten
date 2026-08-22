# Decision Log: v0.4.4 R2 Bytes Preservation

Date: 2026-08-22

## Context

The archive has 3,374 non-conflicting local-only Objet whose remote bytes are
not yet evidenced. Formal adoption is blocked by separate metadata conflicts,
but waiting for all metadata decisions leaves the only known bytes exposed to
a larger irreversible-loss risk.

## Decision

- Extend `object-storage-adopt-existing` with an explicit
  `--preserve-local-only` mode; do not add another top-level command.
- Treat emergency preservation as `bytes_preserved`, never as formal adoption.
  Do not add or change `wom_uploaded` manifest locations.
- Derive remote keys only from the full SHA-256 digest under a dedicated
  versioned prefix.
- Scan the central object manifest once and never rewrite it per item.
- Reuse the v0.4.3 `ExactOperationManifest`, authenticated native approval,
  archive-wide writer lock, append-only checkpoints, resume, progress, and
  independent verification.
- Keep the ordinary upload command's 64-call ceiling unchanged. For this exact
  emergency batch only, derive an immutable no-retry call count and bounded
  retry ceiling from every manifest-bound object size and the existing
  per-object retry maximum, so the reviewed 3,374-item operation is executable
  rather than silently stopping after 64 calls.
- Make each exact target an immutable per-object receipt. Persist the private
  exact plan separately for same-approval resume and publish only aggregate,
  content-free results.
- Query existing remote bytes with HEAD plus a complete GET rehash. Refuse every
  present size or checksum mismatch without PUT.
- After a new upload, require writer-side complete verification and a second
  independent HEAD/GET verification before the field checkpoint completes.
- Do not provide unconditional remote deletion as rollback. The safe local
  rollback boundary is the field-bound receipt; removing a verified emergency
  copy without a generation-bound provider condition would increase loss risk.
- Keep 597 strict manifest-scope remote-key-verified objects and 560 official
  de-duplicated WOM-upload evidence objects under distinct names. The latter
  includes two legacy receipt-backed records that have no manifest remote key;
  do not mislabel those two as independently key-verified or re-upload them
  automatically.
- Keep all 1,149 duplicate definitions review-only. Classify their evidence,
  but never infer that equal object ids authorize metadata merging.
- Resolve credential values and construct the live network sender only inside
  the approved writer boundary. Dry-run reads local bytes for exact hashing but
  never reads secrets or calls the provider.

## Consequences

The highest-risk local-only bytes can be copied independently of formal
adoption and conflict resolution. A provider outage or one conflicting key
halts safely without corrupting manifest authority. Crash recovery is O(1) per
checkpoint/receipt append instead of rewriting an O(n) central document after
each object, while a final aggregate projection reports the batch outcome.

A `bytes_preserved` receipt is intentionally insufficient for
`wom_uploaded` skip logic. Later formal adoption must independently reconcile
metadata, query the provider again, and write its own established evidence.
