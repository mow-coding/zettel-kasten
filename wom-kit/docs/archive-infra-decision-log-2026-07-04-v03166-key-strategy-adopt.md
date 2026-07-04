# Decision Log — v0.3.166 Selectable Key Strategy + Safe Adopt-Existing

Date: 2026-07-04
Batch: v0.3.166 (implements the LOCKED spec: "Object-storage upload: selectable/
recorded key scheme + safe adopt-existing (the 158 GB false-skip fix)").
Anchor tree at spec authoring: HEAD `cf16c11c` (v0.3.165), tree clean.
Release action: working tree only — no git commit/tag/push. Never touches a real
archive or `zettel-kasten-basoon`, and makes no real network call (fake transport
only in tests).

This log records the decisions per §2, §3, §6, §8 and the Critique A/B ledger
(§15), per the AGENTS.md decision-log mandate.

## The one invariant (F0)

A skip is legal only when backed by a live HEAD proving present-at-the-recorded-
key + size-match, in the same run that skips. Implemented as:

- **F0-a** — the executor HEADs the recorded/resolved `remote_key`, not the
  content-addressed `key_hint`. The matcher returns the gating `remote_key`
  (previously a bool) so the executor can HEAD the actual key.
- **F0-b (cardinal)** — under a live transport, an `already_uploaded` verdict is
  NEVER trusted without a re-HEAD of `remote_key`. A 200 + size-match yields
  `skipped_remote_same` (a live-HEAD-backed skip); a 404 falls through and
  UPLOADS. This is the direct data-loss guard.
- **F0-c** — the plan echoes the fully-resolved `remote_key` per row; apply
  re-resolves and refuses the run (fail closed, `plan_apply_key_divergence`) if
  its key diverges.

## §2 Terminology

- **DECISION:** one noun everywhere — `strategy` (flag `--key-strategy`, manifest
  field `key_strategy`, constant `OBJECT_STORAGE_UPLOAD_KEY_STRATEGY`). "Scheme"
  is never used. Rationale: the shipped data already says `key_strategy`; a
  CLI-says-scheme / manifest-says-strategy split is exactly what Critique B forbids.

## §3 Data model (two-field)

- **DECISION (D2):** `key_hint` keeps its exact current meaning (content-addressed
  `sha256/<first2>/<digest>`). A new additive `remote_key` carries the actual
  PUT/HEAD key. HEAD-before, the matcher, and future download consult `remote_key`;
  the digest audits keep validating `key_hint`. New optional fields:
  `remote_key`, `key_strategy` (now may be `prefix`), `remote_key_verified`,
  `remote_key_verification` (`presence_size` | `content_hash` | `none`),
  `remote_size`.
- **Rationale:** the only additive, no-migration path (D6). Repurposing `key_hint`
  would make the three digest audits (V9/V10/V11) and the receipt audit (V12) flag
  every correct non-default location as corrupt at doctor time.
- **§3.1 digest binding:** every strategy's `remote_key` must embed the full 64-hex
  digest (guaranteed by construction for both strategies; asserted defensively).
  New predicate `object_storage_location_remote_key_binds_digest` is checked by the
  audits for any non-default-strategy location — catching a valid-looking key for
  the wrong object (kills hash-collision-across-schemes false-skip).

## §4 Resolver + §5 validator

- **DECISION (D1):** single resolver `object_storage_remote_key(strategy, digest,
  ext, key_prefix, append_extension)`; the content-addressed producer is KEPT (it
  still produces `key_hint` and the default `remote_key`). Prefix normalization
  trims exactly the trailing slash(es) so `.../objets/` and `.../objets` resolve
  identically. Extension is appended only under `--key-append-extension` AND only
  when recoverable byte-exactly from the manifest `logical_key`; otherwise nothing
  is appended (no bare trailing dot). Missing/unsafe prefix REFUSES loudly.
- **§5 validator** `safe_object_storage_remote_key`: allows `A-Za-z0-9/._:-`,
  forbids leading slash, `..`, NUL/whitespace/control, empties, length > 1024, and
  runs the shared leak gate so a bucket/host/URL can never enter a `remote_key`.

## §6 Adopt-existing (the 158 GB path)

- **DECISION (D3):** new `object-storage-adopt-existing` command + service.
- **§6.1 verified adopt (the ONLY gating path):** `--approve` + live transport;
  real HEAD per computed `remote_key`; adopt ONLY on presence + Content-Length
  size-match; writes a matcher-honored `wom_uploaded` location with
  `remote_key_verification="presence_size"`. 404 / size-mismatch is not adopted.
- **§6.2 declared adopt (default OFF, non-gating):** distinct flag
  `--accept-unverified-adopt` (separate from `--approve`); writes
  `declared_uploaded`; the matcher is NOT weakened, so it never gates a PUT; a
  "claimed, not verified — will NOT skip a PUT" caveat is emitted.
- **§6.3 checksum is not cheap on R2:** verified adopt is presence+size only.
  `--content-hash-verify` is an explicit per-object opt-in (GetObject-and-rehash).
- **§6.4 partial-adopt reporting:** the adopt summary reports adopted-count vs
  total ("N of M adopted (presence+size); K will re-upload") — no silent partial.
- **§6.5 migration:** the wom_uploaded de-dup now keys on `remote_key`, so a stale
  `declared_uploaded` location under the old content-addressed key never blocks
  recording the corrected verified `remote_key`.

## §7 Producers + audits migrated

- Plan candidate, executor call, matcher, wom_uploaded writer, evidence writer
  (duplicate literal removed), the three manifest audits (V9/V10/V11), and the
  execution-receipt doctor audit (V12) all migrated. Default path unchanged; a
  non-default location/receipt is validated via `remote_key_binds_digest` instead
  of being flagged for a non-default `key_strategy`. The execution receipt schema
  gains `remote_key` and extends the `key_strategy` enum to include `prefix`.
- **Read-side rule:** the only fetch-key-relevant consumers (matcher, executor)
  prefer `remote_key`. `presigned_url_plan` / `object_storage_operation_request_plan`
  / `resolve_objet_ref` do not derive a fetch key from `key_hint` today, so no
  download tooling needed migration.

## §8 Plan/apply agreement + dry-run honesty

- **DECISION (D4):** per-run explicit strategy, NOT stored-in-binding. Plan echoes
  the resolved `remote_key`; apply re-resolves and refuses on divergence (F0-c).
  Rationale: plan and apply are two independent resolution sites; a binding-stored
  strategy read at a different time is a silent-drift vector, and
  `provider-bindings.yml` is never read by the upload path today.

## §9 Contract doc

- **DECISION (D5):** `key_contract` rewritten truthfully: the default lands at
  exactly `sha256/<first2>/<sha256>` (no prefix — the old `{provider_prefix}/...`
  string was a lie); `prefix` is described as a configured template without echoing
  the value; `object_key_must_not_include_original_filename` replaced by
  `must_not_include_full_original_filename` + `extension_only_under_explicit_opt_in`.
  `docs/object-storage-adapter-execution-contract.md` updated for the strategy model.

## Post-review hardening (confirmed-blocker fixes before release)

An adversarial review surfaced five correctness gaps that the initial diff left;
all are now fixed and each has a mutation-checked regression test.

- **F1 — ledger terminal-success false-skip (BLOCKER).** The resume ledger's
  terminal-success short-circuit is a second recorded-skip authority keyed on
  `object_id` only, with no presence field, that persists across a remote wipe.
  After the F0-b re-HEAD proves an object ABSENT under a live transport, the
  executor now receives `force_upload=True`, which bypasses BOTH the ledger
  terminal-success short-circuit AND the now-redundant HEAD-before, so a
  proven-absent object is re-uploaded, never ledger-skipped. The crash-recovery
  case (T-fake2b: manifest location stripped, verdict `would_upload`, F0-b block
  not entered) is untouched — the ledger stays authoritative there. Test §12.16.
- **F3/F4 — presence+size adopt/skip actually downloaded the whole object
  (BLOCKER).** The sole live `head_object` unconditionally GetObject-rehashed the
  body (R2 has no server-side sha256), so the "presence+size" verified adopt and
  the presence_size skip re-HEAD both downloaded 158 GB. Added a `presence_only`
  parameter to the transport `head_object` (protocol, Null, live S3-compatible,
  and the test fake): when set it returns presence + `Content-Length` and leaves
  `checksum_sha256` None, with NO GetObject. Verified adopt HEADs presence-only
  (unless `--content-hash-verify`); the executor's F0-b skip re-HEAD is
  presence-only when the gating location recorded
  `remote_key_verification="presence_size"` (threaded from the matcher through the
  plan row), keeping the stronger checksum re-check only for genuinely
  content-hashed locations. Tests §12.13, §12.18.
- **F2 — plan/apply verdict divergence (SHOULD).** The matcher gated on any
  `wom_uploaded` location matching `(provider_kind, store_ref)` regardless of key,
  so a prior prefix adopt made a default-strategy plan predict `already_uploaded`
  while apply re-resolved a different key and re-uploaded. The matcher
  (`object_storage_wom_uploaded_location_match`) now takes `expected_remote_key`;
  a gating hit only counts when the recorded key equals the key THIS run resolves.
  Legacy key-agnostic gating is preserved when no run key is passed. Test §12.17.
- **F5 — adopt-existing lacked the tiny-first gate (SHOULD).** Verified adopt is a
  new live surface (a batch = one live HEAD per object). It now enforces the same
  SA-6 requested/proven tiered gate as `object-storage-upload`: a bulk first-live
  adopt REFUSES with `tiered_gate_unmet` until a single `--only` object proves the
  store. The declared (no-network) adopt path is unaffected. Test §12.19.
- **F6 — round-trip tests were self-consistent, not key-anchored (SHOULD).** Added
  §12.20, which seeds the remote at a LITERAL byte-exact basoon key (a string
  constant, not `object_storage_remote_key`) and asserts the adopt/skip HEADed that
  literal key, so a consistent-but-wrong resolver is caught.

## Stage status

Base says Stage 2 live transport landed (v0.3.164). This batch builds the
strategy/adopt machinery so it is correct whenever the live transport is enabled;
it does NOT flip live-execution gating. All prior fail-closed `--approve` behavior
is preserved.
