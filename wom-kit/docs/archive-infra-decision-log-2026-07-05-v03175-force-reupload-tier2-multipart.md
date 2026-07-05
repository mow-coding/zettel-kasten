# Decision Log — v0.3.175 Force-Reupload for Live Multipart, and Multipart-Proven Upload Tier2

Date: 2026-07-05
Batch: v0.3.175 (implements the LOCKED spec: "force-reupload + multipart-proven tier2").
Anchor tree at spec authoring: HEAD `a15705f6` (v0.3.174), tree clean.
Release action: working tree only — no git commit/tag/push (main session releases after
gates). Never touches a real archive or `zettel-kasten-basoon`, and makes no real network
call (fake transport only in tests).

This log records DEC-1..DEC-20 with one-line rationales, both critiques' required changes, and
the Q1-Q6 safety resolutions, per the AGENTS.md decision-log mandate.

## The problem this batch fixes

The basoon 5th operator letter (§3) surfaced two independent gaps that make a **live** R2
multipart demonstration impossible today.

- **GAP A** — an already-present object is auto-skipped by `object_storage_upload_run`'s F0-b
  present+match short-circuit (`skipped_remote_same` + `continue`), so the only object > 5 MiB
  the client has (already uploaded) can never be re-PUT to exercise a live provider multipart.
- **GAP B** — `object_storage_proven_tier` proved upload tier2 ONLY by `bytes_uploaded >= 5 GiB`.
  A forced small multipart (`part_count > 1`, possible since v0.3.172) has bytes < 5 GiB, so it
  was not recognized as the multipart proof it actually is.

## Decisions — FIX A (force-reupload)

- **DEC-1 — the flag.** Add `--force-reupload` (`store_true`, `dest=force_reupload`) to the
  `object-storage-upload` subparser after `--allow-tiny-parts`. *Rationale:* mirrors
  `--allow-tiny-parts` and threads through `getattr(args, "force_reupload", False)` like the
  existing overrides.
- **DEC-2 — CLI gating + refusal messages.** In `command_object_storage_upload`, after the
  approve/reviewed-by gate: refuse under `--dry-run`, without `--approve`, and without a
  non-empty `--reviewed-by`. *Rationale:* grounds force-reupload in the same gates already in
  place; the dry-run refusal makes the flag provably inert in preview.
- **DEC-3 — thread flag into the run call** as `force_reupload=force_reupload`. *Rationale:*
  single new keyword, no positional churn.
- **DEC-4 — new run parameter** `force_reupload: bool = False` next to `skip_uploaded`.
  *Rationale:* default `False` guarantees byte-identical default path; the service re-declares
  the param so a direct service/MCP call re-enforces the gates.
- **DEC-5 — service-layer gate re-enforcement** alongside the reviewer gate: `not approve`,
  `not normalized_reviewer`, `dry_run` all append blockers under `if force_reupload`.
  *Rationale:* the CLI gate is not the only entry; the service must fail closed identically.
- **DEC-6 — non-sha key-strategy REFUSAL (the load-bearing PIN).** `force_reupload` with
  `normalized_strategy not in {sha256_content_addressed, prefix}` appends
  `force_reupload_requires_sha_derived_key`. *Rationale:* the conflict-guard bypass
  (HEAD-before suppressed, so `remote_conflict_different_bytes` never fires) is safe ONLY
  because both current strategies embed the full 64-hex digest (hard-enforced by the
  `clean not in key` raise in `object_storage_remote_key`). A future non-sha strategy would
  make force-reupload a real clobber vector. This is the allowlist form; the digest-substring
  assertion is the durable defense-in-depth that already exists.
- **DEC-7 — bypass the F0-b present+match skip.** Change `if skip_ok:` to
  `if skip_ok and not force_reupload:`, then add `if force_reupload: force_upload_after_absent = True`
  so a forced re-PUT of a present object marks `force_upload`. *Rationale:* the only two things
  force-reupload changes are (a) do not take the present+match skip, and (b) set the executor's
  `force_upload=True`. Control MUST fall through to the pre-PUT local re-verify; it does not
  touch `skip_ok` computation, the `local_available` guard, `size = stat`, or `content_sha256`.
- **DEC-8 — bypass the ledger terminal-success short-circuit.** No new code: DEC-7 sets
  `force_upload_after_absent=True`, passed as `force_upload` into the executor, whose
  `if not force_upload and object_id in ledger.terminal_success_object_ids()` is thereby
  bypassed. *Rationale:* the EXISTING F1 mechanism reused verbatim; the novelty is reaching it
  for a *present* object rather than only a *proven-absent* one.
- **DEC-9 — exactly which short-circuits are bypassed, and what is preserved.** Bypassed:
  (1) the F0-b present+match skip; (2) the ledger terminal-success short-circuit. Preserved
  unchanged: the pre-PUT local-byte re-verify (a corrupt local file returns `failed_upload`,
  never PUT); the HEAD-after GET-rehash verification (not `force_upload`-gated); the orphan
  `delete_object` on HEAD-after mismatch; the PUT ceiling; `--max-objects`. *Rationale:*
  force-reupload is a *sequencing* change, never an *integrity* change.
- **DEC-10 — receipt field `forced_reupload`.** A top-level scalar boolean next to
  `part_count`, fed by a new `forced_reupload` keyword; MUST NOT be nested in `retry_summary`.
  *Rationale:* the schema has no `additionalProperties:false`, so an unknown field is accepted;
  the C7 validator checks only named fields plus a scalar-only `retry_summary`, so a top-level
  boolean trips nothing; the §6 leak gate sees only `true`/`false`. Nesting it in
  `retry_summary` would risk the non-scalar guard.

- **DEC-21 — C7 manifest-linkage EXEMPTION for a forced receipt (adversarial-review closer).**
  The C7 execution-receipt validator (`_check_object_storage_execution_receipts`) requires that
  every `uploaded`/`skipped_remote_same` receipt be linked by a `wom_uploaded` manifest location
  whose `execution_receipt_ref` is exactly that receipt. A `--force-reupload` re-PUT lands a
  SECOND `uploaded` receipt at the SAME content-addressed `remote_key` of an already-linked
  object; `_object_storage_apply_wom_uploaded_location` is idempotent-per-`remote_key`, so it
  appends NO new location and the lone existing location keeps linking the ORIGINAL receipt.
  Without an exemption the forced receipt would emit a spurious
  `object_storage_upload_wom_location_missing` ERROR under Doctor/validate. Decision: a receipt
  with `forced_reupload=true` is EXEMPT from the manifest-linkage requirement only (every other
  invariant — schema, `operation`, `dry_run`, `reviewed_by`, `key_hint`/`remote_key` digest
  bind, `retry_summary` scalar-only — still applies). *Rationale:* a forced re-PUT is by design a
  live-verification action, not a new manifest transition; requiring it to carry its own
  location would force either a duplicate location per key or an in-place re-link that merely
  relocates the ERROR onto the original receipt. Exemption is the minimal, data-safe resolution
  — it never suppresses a real anomaly (the ORIGINAL, non-forced receipt is still fully linkage-
  checked) and requires zero manifest mutation. Recorded here because the earlier
  implementation flagged this as "deviation #2" and left it undocumented; the closer both fixes
  the production behavior (the exemption in `archive_cli.py`) and documents it (release note +
  this log). Covered by the tightened test 14, which now asserts NO object-storage-upload ERROR
  — including `object_storage_upload_wom_location_missing` — on a forced receipt whose original
  receipt/location persist on disk under distinct case_ids.

## Decisions — FIX B (tier)

- **DEC-11 — the exact tier2 edit.** Add a second disjunct to the tier2 compare:
  `... >= 5 GiB or (status == "uploaded" and int(part_count) > 1)`. The 5 GiB path is kept
  verbatim as the first disjunct. *Rationale:* recognizes a forced small multipart as the
  tier2 proof it is; the `status == "uploaded"` guard prevents a fabricated skip receipt with
  `part_count > 1` from minting tier2. This is the ONLY functional edit to the function.
- **DEC-12 — tier3 semantic drift made intentional + documented.** The new disjunct sets the
  SAME `saw_multipart_proof` flag, so a forced small multipart + >= 3 distinct ids reaches
  tier3 without any 5 GiB object. The docstring is updated to say so. *Rationale:* no consumer
  treats `proven == 3` as stronger than `proven == 2`, so no gate is loosened — but the change
  must be intentional and tested.
- **DEC-13 — `object_storage_requested_tier` NOT changed.** Its body is outside the edited
  span; `git diff` shows zero hunks there.
- **DEC-14 — R1 adopt tier funcs NOT changed.** `object_storage_adopt_requested_tier` and
  `object_storage_adopt_proven_tier` begin after the edited span; the adopt proof is keyed on
  `adopt_verification`, structurally independent of `part_count`/`bytes_uploaded`, so a FIX-B
  forced-multipart UPLOAD receipt can never lift adopt tier above 0.

## Default-path byte-identicality

- **DEC-19 — DEFAULT (flag absent) run is behavior-identical to v0.3.174.** All new
  `if force_reupload …` gates are no-ops; the F0-b `if skip_ok and not force_reupload:` reduces
  to the original `if skip_ok:`; the receipt gains only the always-present `forced_reupload: false`
  boolean, which trips no validator or leak gate and changes no control flow.
- **DEC-20 — FIX B DEFAULT tier path unchanged.** The 5 GiB disjunct is kept verbatim as the
  first operand; a receipt with `bytes_uploaded >= 5 GiB` still reaches tier2, and a
  `part_count <= 1`, sub-5 GiB receipt still yields tier1.

## Critiques' required changes (addressed)

- Critique 1 req #1 → DEC-6 (non-sha refusal, the load-bearing pin).
- Critique 1 req #2 → DEC-7/DEC-9 (control falls through to the pre-PUT local re-verify; a
  corrupt local file is refused before any PUT; test 9).
- Critique 1 req #3 → DEC-9 (HEAD-after + orphan cleanup preserved; test 10).
- Critique 1 req #4 → DEC-2/DEC-5 (dry-run refusal; service re-enforces).
- Critique 1 req #5 → DEC-10 (top-level boolean, not nested in `retry_summary`; test 14).
- Critique 1 req #6 → DEC-11 (`status == "uploaded"` guard; test 3).
- Critique 2 req #1 → DEC-11 (forged skip `part_count` not tier2; test 3).
- Critique 2 req #2 → the PUT ceiling, not `--max-objects`, is the cost bound (Q3; test 15).
- Critique 2 req #3 → DEC-12 (intentional tier3 drift documented + tested; test 2).
- Critique 2 req #4 → the 5 GiB path stays recognized (DEC-20; test 4).
- Critique 2 req #5 → DEC-14 (adopt tiers byte-identical, independent of `part_count`; test 5).
- Adversarial-review finding #1 (release-closer) → DEC-21 (C7 manifest-linkage exemption for a
  forced receipt; production behavior fixed in `archive_cli.py` + documented; test 14 tightened
  to assert the forced receipt is now ERROR-clean under Doctor).

## Safety resolutions (Q1-Q6)

- **Q1 (clobber wrong bytes?) — BLOCKED.** The unconditional local re-verify
  `sha256(local) == digest` gates every PUT; force-reupload is refused for any non-sha key.
- **Q2 (lose the `remote_conflict_different_bytes` fail-closed?) — SAFE.** `force_upload`
  suppresses HEAD-before, but the key is content-addressed and force-reupload is refused for a
  non-sha key, so any pre-existing "different bytes" at that exact key are a hash anomaly, not
  legitimate data. DEC-6 closes the only real-clobber path.
- **Q3 (FIX B weakens the cost gate?) — BLOCKED.** Batch cost is bound by the HARD cumulative
  `OBJECT_STORAGE_TOTAL_PUT_CEILING = 64`, not by the tier gate and not by `--max-objects`.
- **Q4 (forge `part_count > 1`?) — BLOCKED in-process.** `part_count` counts real `put_part`
  calls over real `handle.read()` chunks and lands in a receipt only on an `uploaded` status
  after HEAD-after passes; DEC-11's guard blocks a fabricated skip receipt.
- **Q5 (force_upload still verifies?) — YES.** HEAD-after, orphan cleanup, and PUT-ceiling
  accounting are all preserved; a re-PUT is verified exactly like a first PUT.
- **Q6 (refuse non-sha key?) — YES, DEC-6**, belt-and-suspenders with the durable
  `clean not in key` raise.
