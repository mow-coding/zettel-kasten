# Decision Log — v0.3.174 Adopt Tier Decoupled from the Upload 5 GiB Proof

Date: 2026-07-05
Batch: v0.3.174 (implements the LOCKED spec: "Adopt-specific tier ladder: decouple
verified-adopt gating from the 5 GiB upload-multipart proof").
Anchor tree at spec authoring: HEAD `bc330ae9` (v0.3.173), tree clean.
Release action: working tree only — no git commit/tag/push (main session releases
after gates). Never touches a real archive or `zettel-kasten-basoon`, and makes no
real network call (fake transport only in tests).

This log records DEC-1..DEC-8 with one-line rationales, the asymmetry from the
upload ladder, the token rename and F5 supersession, and the standing rule that a
fabricated upload receipt must never unblock an adopt, per the AGENTS.md
decision-log mandate.

## The problem this batch fixes

v0.3.166 (F5) made a batch verified adopt honour the SAME SA-6 tiered gate as
`object-storage-upload`: a batch requested upload tier 3, which needs a store proven
to upload tier >= 2, and upload tier 2 is a genuine 5 GiB multipart / large-object
PUT proof. A verified adopt is HEAD-only — it moves zero bytes and produces no large
PUT — so a store of already-present objects (the basoon 158 GB / 19,054-object
handover, 5th operator letter §2) can never reach upload tier 2 and its batch adopt
could never be unblocked. A HEAD-only operation was gated on a PUT proof it could not
structurally produce.

## Decisions

- **DEC-1 — FORK, do not flag.** Add two NEW pure functions
  (`object_storage_adopt_requested_tier`, `object_storage_adopt_proven_tier`)
  adjacent to the upload tier funcs and point only the adopt gate at them.
  *Rationale:* leaving the upload gate's call sites and the upload tier bodies
  byte-identical is a stronger, cheaper regression guarantee than an `adopt=True`
  flag threaded through the shared functions.
- **DEC-2 — Boolean adopt gate; no tier2/tier3/5 GiB/3-id vocabulary for adopt.**
  Adopt requested tier is 2 for a batch else 1; adopt proven tier is 1 with >= 1
  prior verified adopt else 0; the shared `requested - 1 > proven` arithmetic then
  makes a single adopt always permitted and a batch need exactly one prior verified
  tiny-first adopt. *Rationale:* adopt moves zero bytes and each object runs a
  per-object HEAD-verify self-limit, so a byte/count middle tier for adopt bounds
  nothing real and would re-block basoon.
- **DEC-3 — Positive, adopt-specific, value-checked marker.** A receipt counts as a
  verified-adopt proof only when `adopt_verification in {"presence_size",
  "content_hash"}` AND `result_status == "skipped_remote_same"`. *Rationale:*
  `result_status`/`bytes` do not distinguish adopt from upload (an upload skip is
  also `skipped_remote_same` + `bytes:0`); the `adopt_verification` marker is the
  sole positive, single-site discriminator.
- **DEC-4 — Adopt proof derives from execution receipts, never manifest locations.**
  `object_storage_adopt_proven_tier` reads only `*.object-storage-upload.json`
  receipts. *Rationale:* the declared/unverified path writes a manifest location but
  no receipt, so laundering a declared adopt into a proof is closed by construction.
- **DEC-5 — Rename the adopt blocker token and rewrite the message.** The adopt
  blocker changes `tiered_gate_unmet` → `adopt_tiny_first_unmet`, with a message that
  names the remedy command and states an upload / 5 GiB proof does not help. The
  upload gate keeps `tiered_gate_unmet` byte-identical. *Rationale:* under the
  decoupled gate there is no adopt tier ladder; keeping the old token would mislead
  operators and tests. A distinct honest token lets the two gates be asserted
  independently.
- **DEC-6 — Regression tests mint the proof via a real `--only` verified adopt,
  never `_seed_proven_tier2`.** `_seed_proven_tier2` fabricates an UPLOAD receipt and
  is UPLOAD-only; the adopt tests (T1, §12.13, §8.4) drive a real tiny-first verified
  adopt to mint the exact `bytes:0` + `adopt_verification` receipt the new proven
  tier consumes. *Rationale:* reusing `_seed_proven_tier2` for adopt would silently
  re-couple adopt to the upload proof and defeat the change.
- **DEC-7 — Preserve the declared→PUT boundary with an end-to-end test.** T5 asserts
  `--accept-unverified-adopt` writes no execution receipt, does not lift
  `object_storage_adopt_proven_tier`, never opens a batch, and (with the key absent
  in the transport) never lets a later upload skip its PUT. *Rationale:* the declared
  path is the one boundary a hostile operator would probe as a free unlock; it must
  be asserted end to end.
- **DEC-8 — Reverse leak stays closed; upload path untouched.** Adopt receipts remain
  `bytes_uploaded:0`, so they count only toward upload tier 1 and can never reach
  upload tier 2. *Rationale:* adopt's zero bytes structurally prevent an adopt proof
  from unlocking a PUT batch.

## Asymmetry from the upload ladder (why adopt has no 5 GiB / 3-id tier)

The upload ladder proves a store can absorb a big object (tier 2, a 5 GiB multipart
PUT) and a batch (tier 3, `OBJECT_STORAGE_TIER3_BATCH_MIN` distinct landed objects)
because an upload MOVES bytes and the risk being bounded is real byte transfer. A
verified adopt moves zero bytes and self-limits per object via a live HEAD, so the
only meaningful bound on the first live probe is "prove one live HEAD round-trip
works" — a single verified tiny-first adopt. Any byte- or count-based middle tier for
adopt would bound nothing real and would re-deadlock the very handover adopt exists to
serve. The adopt gate is therefore binary by design, not by omission.

## No new marker field (rejected for this batch)

A future-proof `operation: "adopt_object"` receipt field was considered and rejected
for v0.3.174: `adopt_verification` is already a positive, single-site, value-checked
discriminator, and adding an `operation` variant would change the shared receipt
schema/builder and risk the byte-identical upload guarantee. Noted here as a possible
future consideration only.

## F5 supersession

This batch supersedes the coupling decision in
`docs/archive-infra-decision-log-2026-07-04-v03166-key-strategy-adopt.md` (F5: "verified
adopt honours the SAME tiered tiny-first gate as object-storage-upload"). That log is
historical and is NOT edited. As of v0.3.174 the adopt gate is decoupled from the
upload 5 GiB proof and uses the binary adopt ladder above; the F5 statement should be
read through this supersession.

## Standing rule

`_seed_proven_tier2` (a fabricated UPLOAD receipt: `result_status "uploaded"`, 5 GiB,
NO `adopt_verification`) MUST NEVER be used to unblock a batch adopt. The adopt gate
is decoupled and requires a real verified tiny-first adopt receipt
(`object_storage_adopt_proven_tier`). The helper's docstring is annotated to that
effect and a mirror test (T3) asserts a fabricated upload receipt does not unblock
adopt.

## Files touched (working tree only)

- `wom-kit/src/wom_kit/archive_services.py` — new `object_storage_adopt_requested_tier`
  / `object_storage_adopt_proven_tier` after `object_storage_requested_tier`; the
  adopt gate now calls them and emits `adopt_tiny_first_unmet`.
- `wom-kit/tests/test_cli.py` — T1..T9; updated §12.13 and §12.19 adopt tests and the
  §8.4 key-map test to mint the proof via a real tiny-first verified adopt.
- Version of record: `wom-kit/src/wom_kit/__init__.py`, `wom_kit/__init__.py`,
  `wom-kit/pyproject.toml` → 0.3.174.
- Docs: `CHANGELOG.md`, `wom-kit/docs/releases/v0.3.174.md`, this decision log,
  `wom-kit/docs/capability-matrix.md`, `README.md` / `README.ko.md`, `UPGRADE.md` /
  `UPGRADE.ko.md`, `wom-kit/docs/object-storage-adopt-existing-key-map-runbook.md`.
