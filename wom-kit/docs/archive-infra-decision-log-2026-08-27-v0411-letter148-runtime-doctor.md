# Decision: v0.4.11 keeps Doctor truth and project-runtime truth separate

Date: 2026-08-27

## Context

Feedback 148 confirmed that v0.4.9 completed mint and intake work that had
previously stalled. It also reported a long Doctor run, thousands of paired
mint lifecycle SHA mismatches, and a project whose source, pin, and launcher
agreed while structured version inspection still returned
`project_runtime_mismatch`.

v0.4.10 removed the per-source-file Git subprocess fan-out that exhausted the
version inspection budget, but it did not resolve the runtime-state
contradiction. A valid static runtime receipt was still returned with
`verified: false`, while the caller required that value to be true. Conversely,
promoting a historical receipt to live process proof would be unsafe.

The first v0.4.11 Doctor prototype also made operational byte checking the
default and reused path-only caches. That reduced work but could present a
same-size corrupted objet as an otherwise successful default result and could
reuse stale zet text during secret scanning.

## Decision

- Keep Deep Doctor as the default. Operational mode is explicit and reports
  `byte_integrity_verified: false` and `full_integrity_ok: null`.
- `--strict` requires Deep Doctor.
- Deep Doctor collects unique objet paths while parsing the manifest, then
  performs one descriptor-bound stable SHA-256 read per unique objet at
  completion. It does not read every objet twice.
- Operational Doctor reads no objet bytes. Size and timestamps are never
  treated as byte proof.
- Secret scanning always reads current file text. Other Doctor caches are
  bound to observed filesystem identity instead of path alone.
- Project runtime status has separate evidence axes:
  1. receipt schema and expected release identity,
  2. a recomputed stable live runtime-payload tree hash,
  3. receipt-inventory hashes for the running WOM modules,
  4. canonical launcher bytes,
  5. current executable/module/prefix and `-I/-B` process binding,
  6. project pin and running version equality.
- The project runtime is `aligned` only when all required axes pass. A receipt
  by itself is never relabeled as current-process proof; live payload and
  loaded-module bytes are independently re-observed.
- The common write guard reuses the same process-binding check. A global CLI
  with the same version string does not pass merely because the number matches.
- An already running old global executable cannot be intercepted or repaired
  by newer project source. The canonical project launcher is therefore a
  required client operating boundary, not a claim that v0.4.11 can technically
  block v0.4.2 code that is already running. No silent global PATH mutation is
  introduced.
- Existing public `project_runtime_mismatch` compatibility remains, with a
  content-free `detail_reason_code` for the actual failed boundary.

## Consequences

The release must include a synthetic Letter 148 scale gate and focused tests
for same-size corruption, unstable reads, current secret scanning, one hash per
unique objet, same-version global CLI refusal, and a fully bound project
process. The private client archive is not modified during product development;
the released client runtime performs client-approved verification and writes.

Mint and retired-draft mismatches are handled by a separate evidence decision.
Historical receipts must not be rewritten merely because later, separately
proven zet evolution is valid.

Direct zet–objet receipts may soften a mismatch only when one exact,
chronological, branch-free full-byte chain reaches the current SHA. Historical
local-recovery evidence can additionally prove an exact `frontmatter.assets`
state transition by reconstructing the mint-anchor bytes, but its v0.4.7 final
receipt does not bind completion time. That category remains an ERROR and is
reported explicitly rather than being mislabeled as approved post-mint
evolution.
